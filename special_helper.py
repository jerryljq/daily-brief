#!/usr/bin/env python3
"""特刊排期助手。两个 routine 都用它，避免把同一套判断写进两份 prompt。

    python3 special_helper.py plan
        打印今天该出哪种特刊、写作要求在哪个文件、上一期同类是哪天。

    python3 special_helper.py save --html-file frag.html [--title "..."]
        把特刊片段存成 data/special/YYYYMMDD.json（特刊任务用）。

    python3 special_helper.py apply --data data/YYYYMMDD.json
        把今天的特刊并进简报数据：文件在就是 ready，不在就是 pending，
        今天排期本来就没有特刊则不放 special 字段（简报任务用）。

日期一律按温哥华时区算，不用 UTC——云端跑在 UTC，跨零点会算错天。
"""
import argparse, glob, json, os, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
SCHEDULE = REPO / "special_schedule.json"
SPEC_DIR = REPO / "specials"
OUT_DIR = REPO / "data" / "special"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
ZH = {"mon": "周一", "tue": "周二", "wed": "周三", "thu": "周四",
      "fri": "周五", "sat": "周六", "sun": "周日"}


def today():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Vancouver"))
    except Exception:
        # 没有 tzdata 时退到固定偏移，够用：只是为了取对“今天是几号星期几”
        return datetime.now(timezone(timedelta(hours=-7)))


def schedule():
    return {k: v for k, v in json.loads(SCHEDULE.read_text(encoding="utf-8")).items()
            if not k.startswith("_")}


def spec_title(kind):
    p = SPEC_DIR / f"{kind}.md"
    if not p.exists():
        return kind
    m = re.search(r'^title:\s*(.+)$', p.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else kind


def kind_today():
    d = today()
    return d, schedule().get(WEEKDAYS[d.weekday()])


def last_same_kind(kind, before):
    """上一期同类特刊的日期字符串，没有则 None。"""
    dates = []
    for f in glob.glob(str(OUT_DIR / "*.json")):
        try:
            j = json.loads(Path(f).read_text(encoding="utf-8"))
        except ValueError:
            continue
        stem = Path(f).stem
        if j.get("kind") == kind and stem < before:
            dates.append(stem)
    return max(dates) if dates else None


def cmd_plan():
    d, kind = kind_today()
    stamp = d.strftime("%Y%m%d")
    print(f"date={stamp}")
    print(f"weekday={WEEKDAYS[d.weekday()]} ({ZH[WEEKDAYS[d.weekday()]]})")
    if not kind:
        print("kind=none")
        print("今天排期里没有特刊。")
        return
    print(f"kind={kind}")
    print(f"title={spec_title(kind)}")
    print(f"spec={SPEC_DIR.relative_to(REPO)}/{kind}.md")
    prev = last_same_kind(kind, stamp)
    print(f"last_same_kind={prev or 'none'}")
    if prev:
        print(f"覆盖区间：{prev} 之后到今天。")


def cmd_save(args):
    d, kind = kind_today()
    if not kind:
        sys.exit("今天排期里没有特刊，不该调用 save。")
    frag = Path(args.html_file)
    if not frag.exists():
        sys.exit(f"找不到片段文件: {frag}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = d.strftime("%Y%m%d")
    out = OUT_DIR / f"{stamp}.json"
    out.write_text(json.dumps({
        "date": stamp,
        "kind": kind,
        "title": args.title or spec_title(kind),
        "html": frag.read_text(encoding="utf-8"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存: {out.relative_to(REPO)}")


def cmd_apply(args):
    d, kind = kind_today()
    data_path = Path(args.data)
    if not data_path.exists():
        sys.exit(f"找不到简报数据文件: {data_path}")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    stamp = d.strftime("%Y%m%d")
    sp_path = OUT_DIR / f"{stamp}.json"

    if not kind:
        data.pop("special", None)
        state = "今天没有特刊排期，已移除 special 字段"
    elif sp_path.exists():
        sp = json.loads(sp_path.read_text(encoding="utf-8"))
        data["special"] = {"title": sp.get("title") or spec_title(kind),
                           "html": sp.get("html", ""), "status": "ready"}
        state = f"特刊已就位（{sp.get('kind')}），status=ready"
    else:
        data["special"] = {"title": spec_title(kind), "status": "pending"}
        state = f"特刊（{kind}）还没到，status=pending"

    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(state)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    s = sub.add_parser("save"); s.add_argument("--html-file", required=True); s.add_argument("--title")
    a = sub.add_parser("apply"); a.add_argument("--data", required=True)
    args = ap.parse_args()
    if args.cmd == "plan":  cmd_plan()
    elif args.cmd == "save": cmd_save(args)
    elif args.cmd == "apply": cmd_apply(args)


if __name__ == "__main__":
    main()
