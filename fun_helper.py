#!/usr/bin/env python3
"""「轻松一刻」和「本地趣闻」助手。写作要求在 fun.md，简报任务每天用它。

    python3 fun_helper.py plan [--date YYYYMMDD]
        打印今天的轮换（幽默的形式和题材、冷知识的领域）、过度使用的梗、
        最近 60 天登过的条目、往年同月同日登过的「历史上的今天」。

    python3 fun_helper.py check --data data/YYYYMMDD.json [--offline]
        检查当天的 sections.jokes 和 sections.local_fun：字段、禁区、过度使用的梗、
        和历史条目是否太像；联网时再打开每个链接，核对 evidence 确实在页面上。
        有必须改的问题时退出码为 1。

只用标准库：云端沙箱是 Python 3.11，不要用 3.12+ 的写法。
"""
import argparse, html, json, re, sys, unicodedata, urllib.request
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent
DATA = REPO / "data"

KINDS = {
    "humor": "幽默",
    "trivia": "冷知识",
    "today_cn": "历史上的今天 · 中国",
    "today_world": "历史上的今天 · 世界",
}
TODAY_KINDS = ("today_cn", "today_world")

# 轮换：按日期序号取模，相邻两天一定不同，一个周期内不重复。
# 幽默的题材和冷知识的领域互不重叠，同一天两条不会撞题。
HUMOR_FORMS = ["有出处的妙语", "历史人物的机智回答", "真实发生的乌龙趣事",
               "真实的双关或谐音", "文字游戏", "当事人的自嘲"]
HUMOR_TOPICS = ["科学家", "文学艺术", "体育", "交通出行", "日常生活", "音乐",
                "发明创造", "学校与考试", "旅行", "节日"]
TRIVIA_DOMAINS = ["动物", "天文", "人体", "植物", "地理", "物理", "语言文字",
                  "饮食", "发明", "海洋", "数学", "气象", "古代生活", "化学"]

# 2026-09 到 10 月反复出现、已经被读者看腻的梗。换说法也算。
OVERUSED = [
    ("程序员分不清万圣节和圣诞节（Oct 31 = Dec 25）",
     r"oct\s*31|dec\s*25|万圣节.{0,20}圣诞|圣诞.{0,20}万圣节"),
    ("程序员买包子和西瓜", r"包子.{0,40}西瓜|西瓜.{0,40}包子"),
    ("股民的投资组合“稳定地往下走”", r"(股民|投资组合|账户).{0,40}(稳定|往下走|跌)"),
    ("越炒越少 / 割韭菜", r"越炒越少|割韭菜|当韭菜|韭菜们"),
    ("老板、员工和加薪", r"(老板|上司|领导).{0,40}加薪|加薪.{0,40}(老板|上司|领导)"),
    ("程序员掉头发", r"程序员.{0,30}(头发|秃|发际线)|(头发|秃|发际线).{0,30}程序员"),
    ("产品经理改需求", r"产品经理.{0,30}需求|需求.{0,30}产品经理"),
]

# 禁区（fun.md）。命中必须改；RELIGION 只提示，因为引文里常有“上帝”之类的说法。
FORBIDDEN = [
    ("灾难、疾病与死亡",
     r"逝世|去世|身亡|遇难|丧生|罹难|阵亡|自杀|空难|地震|海啸|屠杀|恐怖袭击|爆炸事故|瘟疫|癌症|绝症"),
    ("政治", r"习近平|特朗普|拜登|普京|泽连斯基|内塔尼亚胡|共产党|国民党|民进党|台独|藏独|疆独|六四|法轮"),
    ("性暗示与低俗", r"色情|性爱|嫖|裸体|黄段子"),
]
RELIGION = r"上帝|真主|耶稣|佛祖|穆罕默德|基督教|伊斯兰教|佛教"

GENERIC_TITLE = re.compile(
    r"^(今日一[则笑个]|再来一[个则]|冷笑话[一二三四1-4]?|笑话[一二三四1-4]?|轻松一刻|冷知识"
    r"|幽默|历史上的今天)$")

SIMILAR_SUMMARY = 0.35   # 字符二元组 Jaccard；2026-10 的复读笑话两两之间都在 0.45 以上
SIMILAR_TITLE = 0.5
SIMILAR_NEWS_TITLE = 0.6
HISTORY_DAYS = 60
WIKI_MAX = 2             # 每天超过这么多条维基来源就提示（大陆打不开）
UA = "Mozilla/5.0 (compatible; daily-brief-fun-check/1.0)"


def norm(s):
    """比对用：NFKC、小写，去掉空白、标点和符号。"""
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return "".join(ch for ch in s if unicodedata.category(ch)[0] not in "PSZC")


def bigrams(s):
    t = norm(s)
    return {t[i:i + 2] for i in range(len(t) - 1)} or ({t} if t else set())


def jaccard(a, b):
    a, b = bigrams(a), bigrams(b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def rotation(day):
    n = day.toordinal()
    return {
        "humor_form": HUMOR_FORMS[n % len(HUMOR_FORMS)],
        "humor_topic": HUMOR_TOPICS[n % len(HUMOR_TOPICS)],
        "trivia_domain": TRIVIA_DOMAINS[n % len(TRIVIA_DOMAINS)],
    }


def parse_stamp(stamp):
    return date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))


def load_issues(data_dir, before):
    """data_dir 里日期早于 before 的每一期：[(date, data)]，按日期排序。"""
    out = []
    for p in sorted(Path(data_dir).glob("[0-9]" * 8 + ".json")):
        try:
            d = parse_stamp(p.stem)
        except ValueError:
            continue
        if d >= before:
            continue
        try:
            out.append((d, json.loads(p.read_text(encoding="utf-8"))))
        except ValueError:
            continue
    return out


def entries(issues, section):
    out = []
    for d, data in issues:
        for it in (data.get("sections") or {}).get(section) or []:
            out.append(dict(it, _date=d))
    return out


def label(it):
    return KINDS.get(it.get("kind"), "旧笑话")


def short(s, n=60):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n] + "…"


# ── plan ──────────────────────────────────────────────────────────

def plan_text(day, data_dir=DATA):
    issues = load_issues(data_dir, day)
    recent = [x for x in issues if x[0] >= day - timedelta(days=HISTORY_DAYS)]
    rot = rotation(day)
    lines = [
        f"date={day.strftime('%Y%m%d')}",
        f"月日={day.month}月{day.day}日",
        "",
        "## 今天的轮换",
        f"- humor（幽默）：形式「{rot['humor_form']}」，题材「{rot['humor_topic']}」",
        f"- trivia（冷知识）：领域「{rot['trivia_domain']}」",
        f"- today_cn / today_world：{day.month}月{day.day}日，中国一条、世界一条",
        "",
        "## 过度使用的梗（不要写，换说法也不行）",
    ]
    lines += [f"- {name}" for name, _ in OVERUSED]
    lines += ["", f"## 最近 {HISTORY_DAYS} 天登过的「轻松一刻」和旧笑话（不得复述、改写或换说法）"]
    jokes = entries(recent, "jokes")
    lines += [f"- {it['_date']:%Y%m%d} [{label(it)}] {short(it.get('title'), 30)}：{short(it.get('summary'), 80)}"
              for it in jokes] or ["- （无）"]
    same_day = [it for it in entries(issues, "jokes")
                if it.get("kind") in TODAY_KINDS
                and (it["_date"].month, it["_date"].day) == (day.month, day.day)]
    lines += ["", f"## 往年 {day.month}月{day.day}日 登过的「历史上的今天」（换一件事）"]
    lines += [f"- {it['_date']:%Y} [{label(it)}] {it.get('year', '')} {short(it.get('title'), 40)}"
              for it in same_day] or ["- （无）"]
    news = [it for it in entries(recent, "local_fun") if it["_date"] >= day - timedelta(days=30)]
    lines += ["", "## 最近 30 天登过的本地趣闻（同一件事不要再报）"]
    lines += [f"- {it['_date']:%Y%m%d} {short(it.get('title'), 50)}" for it in news] or ["- （无）"]
    lines += ["", "写作要求：fun.md。写完运行 python3 fun_helper.py check --data data/YYYYMMDD.json"]
    return "\n".join(lines)


# ── check ─────────────────────────────────────────────────────────

def page_text(raw, charset=None):
    """HTML 字节 → 纯文本。"""
    text = None
    head = raw[:4096].decode("ascii", "ignore")
    m = re.search(r"charset=[\"']?([A-Za-z0-9_-]+)", head)
    for enc in [charset, m.group(1) if m else None, "utf-8", "gb18030"]:
        if not enc:
            continue
        try:
            text = raw.decode(enc)
            break
        except (LookupError, UnicodeDecodeError):
            continue
    if text is None:
        text = raw.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text))


def fetch(url, timeout=20):
    """→ (HTTP 状态码, 页面纯文本)。打不开时抛异常。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(4_000_000)
        return r.status, page_text(raw, r.headers.get_content_charset())


def hits(pattern, text):
    return re.search(pattern, unicodedata.normalize("NFKC", text), re.I) is not None


def check_issue(data, day, data_dir=DATA, fetcher=fetch):
    """→ (errors, warnings)，各是一串中文说明。fetcher=None 时不联网。"""
    errors, warnings = [], []
    sec = data.get("sections") or {}
    issues = load_issues(data_dir, day)
    recent = [x for x in issues if x[0] >= day - timedelta(days=HISTORY_DAYS)]
    old_jokes = entries(recent, "jokes")
    old_urls = {it.get("url") for it in entries(issues, "jokes") if it.get("url")}
    same_day = [it for it in entries(issues, "jokes")
                if it.get("kind") in TODAY_KINDS
                and (it["_date"].month, it["_date"].day) == (day.month, day.day)]

    jokes = sec.get("jokes") or []
    seen = {}
    for i, it in enumerate(jokes):
        where = f"jokes[{i}] {it.get('kind') or '?'}「{short(it.get('title'), 24)}」"
        err = lambda msg: errors.append(f"{where}：{msg}")
        kind = it.get("kind")
        title, summary = str(it.get("title") or ""), str(it.get("summary") or "")
        text = title + " " + summary
        if kind not in KINDS:
            err(f"kind 必须是 {' / '.join(KINDS)} 之一")
        elif kind in seen:
            err(f"和 jokes[{seen[kind]}] 是同一种 kind，每种只登一条")
        else:
            seen[kind] = i
        if it.get("fictional"):
            err("不许标 fictional：这一栏只登真实、有出处的内容（fun.md）")
        url = str(it.get("url") or "")
        if not re.match(r"^https?://", url):
            err("缺 url（必须是这次实际打开过的来源页面）")
        elif url in old_urls:
            err("这个 url 以前用过，换一条")
        if not str(it.get("source") or "").strip():
            err("缺 source（来源网站或机构的名字）")
        evidence = str(it.get("evidence") or "")
        if not 6 <= len(norm(evidence)) <= 80:
            err("evidence 要从来源页面原样复制 8–40 字")
        if not 4 <= len(title) <= 30:
            err("title 要 4–30 字，写出这一条具体是什么")
        if GENERIC_TITLE.match(norm(title)):
            err("title 没有信息量（如「今日一则」），写出这一条具体是什么")
        if not 30 <= len(summary) <= 260:
            err("summary 要 2–4 句，约 40–220 字")
        year = it.get("year")
        if kind in TODAY_KINDS:
            if not isinstance(year, int) or not 0 < year < day.year:
                err("历史上的今天要写 year（事件年份，整数）")
            elif str(year) not in text:
                err(f"正文里要写出年份 {year}")
        for name, pattern in OVERUSED:
            if hits(pattern, text):
                err(f"过度使用的梗：{name}")
        for name, pattern in FORBIDDEN:
            if hits(pattern, text):
                err(f"禁区：{name}")
        if hits(RELIGION, text):
            warnings.append(f"{where}：涉及宗教词语，确认不是拿宗教开玩笑")
        pool = old_jokes + [dict(x, _date=day) for x in jokes[:i]]
        if kind in TODAY_KINDS:
            pool += same_day
        for old in pool:
            s = jaccard(summary, old.get("summary"))
            t = jaccard(title, old.get("title"))
            if s >= SIMILAR_SUMMARY or (t >= SIMILAR_TITLE and not GENERIC_TITLE.match(norm(old.get("title")))):
                err(f"和 {old['_date']:%Y%m%d} 的「{short(old.get('title'), 20)}：{short(old.get('summary'), 30)}」"
                    f"太像（正文 {s:.2f} / 标题 {t:.2f}），换一条，改写也不行")
                break
        if fetcher and re.match(r"^https?://", url):
            try:
                status, page = fetcher(url)
            except Exception as e:  # noqa: BLE001 — 打不开的原因五花八门，都算打不开
                err(f"链接打不开（{short(e, 80)}），换一个来源")
            else:
                if status >= 400:
                    err(f"链接返回 HTTP {status}，换一个来源")
                elif evidence and norm(evidence) not in norm(page):
                    err("来源页面上找不到 evidence 这段文字：确认这一页确实说了这件事，并原样复制")
                elif kind in TODAY_KINDS and isinstance(year, int) and str(year) not in page:
                    err(f"来源页面上找不到年份 {year}")
    wiki = sum(1 for it in jokes if re.match(r"^https?://[^/]*\.(wikipedia|wikiquote)\.org/", str(it.get("url") or "")))
    if wiki > WIKI_MAX:
        warnings.append(f"jokes：{wiki} 条来自维基百科/维基语录，中国大陆读者打不开，尽量换成大陆能打开的来源（fun.md）")
    missing = [k for k in KINDS if k not in seen]
    if missing:
        warnings.append(f"jokes：今天缺 {'、'.join(KINDS[k] for k in missing)}（找不到合格的可以不登）")

    old_news = [it for it in entries(recent, "local_fun")]
    for i, it in enumerate(sec.get("local_fun") or []):
        where = f"local_fun[{i}]「{short(it.get('title'), 24)}」"
        url = str(it.get("url") or "")
        if it.get("fictional"):
            errors.append(f"{where}：本地趣闻只登真实新闻，删掉虚构的这条（不要拿虚构的凑数）")
        if not re.match(r"^https?://", url):
            errors.append(f"{where}：缺原文 url")
        for old in old_news:
            if (url and url == old.get("url")) or jaccard(it.get("title"), old.get("title")) >= SIMILAR_NEWS_TITLE:
                errors.append(f"{where}：{old['_date']:%Y%m%d} 已经报过「{short(old.get('title'), 30)}」，换一条")
                break
        text = f"{it.get('title') or ''} {it.get('summary') or ''}"
        for name, pattern in FORBIDDEN:
            if hits(pattern, text):
                warnings.append(f"{where}：可能涉及禁区「{name}」，确认是否合适")
        if fetcher and re.match(r"^https?://", url):
            try:
                status, _ = fetcher(url)
                if status >= 400:
                    warnings.append(f"{where}：原文链接返回 HTTP {status}")
            except Exception as e:  # noqa: BLE001
                warnings.append(f"{where}：原文链接打不开（{short(e, 60)}）")
    return errors, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--date", help="YYYYMMDD，默认温哥华时间的今天")
    c = sub.add_parser("check")
    c.add_argument("--data", required=True)
    c.add_argument("--offline", action="store_true", help="不联网：不打开链接核对")
    args = ap.parse_args(argv)

    if args.cmd == "plan":
        if args.date:
            day = parse_stamp(args.date)
        else:
            from special_helper import today
            day = today().date()
        print(plan_text(day))
        return 0

    path = Path(args.data)
    data = json.loads(path.read_text(encoding="utf-8"))
    day = parse_stamp(path.stem) if re.fullmatch(r"\d{8}", path.stem) else date.fromisoformat(data["date"])
    errors, warnings = check_issue(data, day, data_dir=path.parent, fetcher=None if args.offline else fetch)
    for w in warnings:
        print(f"提示  {w}")
    for e in errors:
        print(f"必须改  {e}")
    print(f"结果：{len(errors)} 处必须改，{len(warnings)} 条提示" + ("" if errors else "，通过"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
