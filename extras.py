#!/usr/bin/env python3
"""清理简报数据里三个可选字段：overview、markets、special.summary。

    import extras
    data, warnings = extras.clean(data)

只清理、不拦截：不合格的那一项删掉，其余照常发布，删了什么写进 warnings。

- render.py 渲染前调用它，并把清理后的 JSON 写回 data/YYYYMMDD.json。JerryStudio 的
  sync-briefs 原样复制那个文件，所以网站永远看不到不合格的条目。
- merge_special.py 补特刊时也调用一次（检查新加的 special.summary）。
- warnings 另存一份到 logs/extras-YYYYMMDD.txt（不进 git），publish.py 读它，
  打印在日志和通知里。**行情和概览永远不会让一期简报发不出去。**

字段的写法见 render.py 开头的说明。只用标准库，兼容 Python 3.11。
"""
import copy, math, re
from datetime import date, timedelta
from pathlib import Path

# ── 10 项行情：顺序即页面顺序 ───────────────────────────────────
# name 是印出来的名字；group、unit、change（用哪个涨跌字段）由 id 决定。
MARKETS = (
    ("spx",    "标普 500",          "us",                   "",  "change_pct"),
    ("ixic",   "纳斯达克",          "us",                   "",  "change_pct"),
    ("dji",    "道琼斯",            "us",                   "",  "change_pct"),
    ("hsi",    "恒生指数",          "cn_hk",                "",  "change_pct"),
    ("sse",    "上证指数",          "cn_hk",                "",  "change_pct"),
    ("usdcny", "美元/人民币",       "commodities_rates_fx", "",  "change_pct"),
    ("usdcad", "美元/加元",         "commodities_rates_fx", "",  "change_pct"),
    ("cadcny", "加元/人民币",       "commodities_rates_fx", "",  "change_pct"),
    ("xau",    "黄金（美元/盎司）", "commodities_rates_fx", "",  "change_pct"),
    ("us10y",  "美债 10 年",        "commodities_rates_fx", "%", "change_bp"),
)
SPEC = {m[0]: {"name": m[1], "group": m[2], "unit": m[3], "change": m[4]} for m in MARKETS}
ORDER = [m[0] for m in MARKETS]

# 合理区间：只为挡住明显的笔误（少写一位、多写一位、填串了项），故意放得很宽。
# 2026-11-11 设定。行情长期走出区间时放宽这里，不要收紧成“接近今天的值”。
RANGES = {
    "spx":    (1_000, 30_000),
    "ixic":   (3_000, 80_000),
    "dji":    (10_000, 150_000),
    "hsi":    (5_000, 80_000),
    "sse":    (1_000, 12_000),
    "usdcny": (5, 10),
    "usdcad": (0.9, 2),
    "cadcny": (3, 8),
    "xau":    (500, 15_000),
    "us10y":  (0, 15),        # 收益率，单位 %
}
MAX_CHANGE = {"change_pct": 15, "change_bp": 100}   # 2026-11-11 设定：单日涨跌超过这个就当写错
AS_OF_DAYS = 7              # as_of 必须在简报日期之前 7 天以内（含当天）
CADCNY_TOLERANCE = 0.01     # 加元/人民币和 美元/人民币 ÷ 美元/加元 相差超过 1% 就提示
SESSIONS = ("close", "live")

OVERVIEW_LEN = (15, 80)     # 写作要求是 20–70 字，清理时留一点余量
SUMMARY_MAX = 60            # 写作要求是 ≤ 40 字

HTTPS = re.compile(r"^https://\S+$")        # 和 JerryStudio 的 schema 一致
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LOG_DIR = Path(__file__).resolve().parent / "logs"


def _number(v):
    """有限的实数。bool 在 Python 里也是 int，要排除；NaN 写进 JSON 网站读不了。"""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _day(s):
    if not isinstance(s, str) or not ISO_DATE.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _short(v, n=24):
    s = v if isinstance(v, str) else repr(v)
    return s if len(s) <= n else s[:n] + "…"


# ── markets ────────────────────────────────────────────────────
def _entry_problem(e, issue_day):
    """一条行情不合格的原因，合格返回 None。e 已经过 _normalize。"""
    spec = SPEC[e["id"]]
    if e["group"] != spec["group"]:
        return f"group 应为 {spec['group']}，写的是 {_short(e['group'])}"
    if e.get("unit", "") != spec["unit"]:
        return f"unit 应为 {spec['unit'] or '空'}，写的是 {_short(e['unit'])}"
    v = e.get("value")
    if not _number(v) or v <= 0:
        return f"value 不是正数：{_short(v)}"
    lo, hi = RANGES[e["id"]]
    if not lo <= v <= hi:
        return f"value {v} 超出合理区间 {lo}–{hi}"
    for field, limit in MAX_CHANGE.items():
        if field in e:
            c = e[field]
            if not _number(c):
                return f"{field} 不是数字：{_short(c)}"
            if abs(c) > limit:
                return f"{field} {c} 超过 ±{limit}"
    if e.get("session") not in SESSIONS:
        return f"session 应为 close 或 live，写的是 {_short(e.get('session'))}"
    d = _day(e.get("as_of"))
    if d is None:
        return f"as_of 不是 YYYY-MM-DD 日期：{_short(e.get('as_of'))}"
    if issue_day is None:
        return "简报没有有效的 date，没法核对 as_of"
    if not issue_day - timedelta(days=AS_OF_DAYS) <= d <= issue_day:
        return f"as_of {d} 不在简报日期 {issue_day} 之前 {AS_OF_DAYS} 天以内"
    src = e.get("source")
    if not isinstance(src, str) or not HTTPS.match(src):
        return f"source 缺失或不是 https:// 地址：{_short(src, 40)}"
    return None


def _normalize(e):
    """补上由 id 决定的字段、去掉 null 和用错的涨跌字段。不删条目。→ (e, 提示)"""
    e = {k: v for k, v in e.items() if v is not None}   # null 等于没写（网站不收 null）
    spec = SPEC[e["id"]]
    e.setdefault("group", spec["group"])
    if spec["unit"]:
        e.setdefault("unit", spec["unit"])
    if not isinstance(e.get("name"), str) or not e["name"].strip():
        e["name"] = spec["name"]
    notes = []
    wrong = "change_pct" if spec["change"] == "change_bp" else "change_bp"
    if wrong in e:
        notes.append(f"行情 {e['id']}：去掉 {wrong}（这一项的涨跌用 {spec['change']}），数值保留")
        del e[wrong]
    return e, notes


def _clean_markets(data, issue_day, warnings):
    if "markets" not in data:
        return
    raw = data["markets"]
    if not isinstance(raw, list):
        warnings.append(f"markets 不是列表，整个删掉：{_short(raw)}")
        del data["markets"]
        return

    kept, seen = {}, set()
    for i, e in enumerate(raw):
        mid = e.get("id") if isinstance(e, dict) else None
        label = f"行情 {mid}" if isinstance(mid, str) else f"行情第 {i + 1} 项"
        if not isinstance(e, dict):
            warnings.append(f"{label} 已删：不是对象")
            continue
        if not isinstance(mid, str) or mid not in SPEC:
            warnings.append(f"{label} 已删：未知的 id {_short(mid)}")
            continue
        if mid in seen:
            warnings.append(f"{label} 已删：id 重复，保留第一条")
            continue
        seen.add(mid)
        e, notes = _normalize(e)
        problem = _entry_problem(e, issue_day)
        if problem:
            warnings.append(f"{label} 已删：{problem}")
            continue
        warnings += notes
        kept[mid] = e

    if not kept:
        if raw:
            warnings.append("markets 一项都没留下，整个删掉")
        del data["markets"]
        return
    data["markets"] = [kept[m] for m in ORDER if m in kept]

    usdcny, usdcad, cadcny = (kept.get(k) for k in ("usdcny", "usdcad", "cadcny"))
    if usdcny and usdcad and cadcny:
        implied = usdcny["value"] / usdcad["value"]
        gap = abs(cadcny["value"] - implied) / implied
        if gap > CADCNY_TOLERANCE:
            how = "（标了 derived，算错了？）" if cadcny.get("derived") else ""
            warnings.append(
                f"行情 cadcny：{cadcny['value']} 和 美元/人民币 ÷ 美元/加元 = {implied:.4f} "
                f"相差 {gap:.1%}，超过 {CADCNY_TOLERANCE:.0%}，请核对{how}（未删）")


# ── overview / special.summary ─────────────────────────────────
def _clean_overview(data, warnings):
    if "overview" not in data:
        return
    v = data["overview"]
    if v is None:
        del data["overview"]
        return
    if not isinstance(v, str):
        reason = f"不是字符串：{_short(v)}"
    else:
        v = v.strip()
        lo, hi = OVERVIEW_LEN
        if "\n" in v or "\r" in v:
            reason = "含换行"
        elif "http" in v.lower():
            reason = "含链接"
        elif "【虚构】" in v:
            reason = "含【虚构】"
        elif not lo <= len(v) <= hi:
            reason = f"{len(v)} 字，应为 {lo}–{hi} 字"
        else:
            data["overview"] = v
            return
    warnings.append(f"overview 已删（{reason}）：{_short(v, 30)}")
    del data["overview"]


def summary_problem(v):
    """special.summary 的问题，合格（或为空）返回 None。special_helper.py save 也用它提示。"""
    if not isinstance(v, str):
        return f"不是字符串：{_short(v)}"
    v = v.strip()
    if len(v) > SUMMARY_MAX:
        return f"{len(v)} 字，超过 {SUMMARY_MAX} 字"
    if "http" in v.lower():
        return "含链接"
    return None


def _clean_summary(data, warnings):
    sp = data.get("special")
    if not isinstance(sp, dict) or "summary" not in sp:
        return
    v = sp["summary"]
    if v is None or (isinstance(v, str) and not v.strip()):
        del sp["summary"]
        return
    problem = summary_problem(v)
    if problem:
        warnings.append(f"special.summary 已删（{problem}）：{_short(v, 30)}")
        del sp["summary"]
    else:
        sp["summary"] = v.strip()


# ── 入口 ───────────────────────────────────────────────────────
def clean(data):
    """→ (清理后的 data, warnings)。不改传进来的对象；没有新字段的数据原样返回。"""
    data = copy.deepcopy(data)
    warnings = []
    if not isinstance(data, dict):
        return data, warnings
    _clean_overview(data, warnings)
    _clean_markets(data, _day(data.get("date")), warnings)
    _clean_summary(data, warnings)
    return data, warnings


def log_path(stamp):
    """stamp 是 YYYYMMDD。"""
    return LOG_DIR / f"extras-{stamp}.txt"


def save_warnings(stamp, warnings):
    """给 publish.py 留一份：有提示就写，没有就删掉旧的。"""
    p = log_path(stamp)
    if warnings:
        LOG_DIR.mkdir(exist_ok=True)
        p.write_text("\n".join(warnings) + "\n", encoding="utf-8")
    elif p.exists():
        p.unlink()


def load_warnings(stamp):
    p = log_path(stamp)
    if not p.exists():
        return []
    return [line for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
