#!/usr/bin/env python3
"""
渲染当天的《嘻嘻哈哈报》。

用法：
    python3 render.py --data data/20260901.json

约定的仓库结构：
    template.html          固定模板骨架（不需要每天重新生成，长期不变）
    issue_no.txt            期号计数器（自动维护，从1开始递增）
    data/YYYYMMDD.json       Claude 每天只需要生成这一个文件（结构见下方 SCHEMA 说明）
    briefs/daily_brief_YYYYMMDD.html   渲染输出，这个才是真正发布到 Pages 的页面

data JSON 结构（Claude 每天只需要产出这个，不需要重写HTML/CSS）：
{
  "date": "2026-09-01",
  "weekday": "星期二",
  "lunar": "农历七月二十",              // 可选，没查到就留空字符串
  "sections": {
    "china":     [{"title": "...", "summary": "...", "url": "..."}, ...],
    "us_ca":     [...],
    "global":    [...],
    "economy":   [{"title": "...", "summary": "...", "url": "..."}, ...],
    "local_fun": [{"title": "...", "summary": "...", "url": "...", "fictional": false}, ...],
    "jokes":     [{"title": "今日一则", "summary": "笑话正文"}, ...]
  },
  "special": {                          // 可选，按 special_schedule.json 排期
    "title": "本周财经展望",
    "html": "<h4>本周财报日历</h4><p>...</p>",   // status 为 pending 时可省略
    "status": "pending" | "ready"       // pending 只出占位卡片，不计入版数
  },
  "holidays": [                         // 报头假期带，由 special_helper.py apply 自动写入
    {"region":"cn","label":"中国","name":"中秋节","date":"2026-09-25","days":23}
  ],
  "poem": {                             // 报尾的诗词赏析，取代旧的 quote
    "title": "鹿柴", "author": "王维", "dynasty": "唐",
    "lines": ["空山不见人，但闻人语响。", "返景入深林，复照青苔上。"],
    "note": "赏析文字……"
  }
}

安全闸（publish.py 会跑）要求：china / us_ca / global / economy / local_fun
里的每一条，必须有 url，或者标 "fictional": true。两者都没有就拒绝发布。

版数（"今日X版"）会由模板自动根据有内容的板块数量计算，不需要在数据里指定。
期号（"总第X期"）由本脚本自动维护，不需要在数据里指定。
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = REPO_ROOT / "template.html"
ISSUE_COUNTER_PATH = REPO_ROOT / "issue_no.txt"
BRIEFS_DIR = REPO_ROOT / "briefs"


def next_issue_no() -> int:
    if ISSUE_COUNTER_PATH.exists():
        try:
            current = int(ISSUE_COUNTER_PATH.read_text().strip())
        except ValueError:
            current = 0
    else:
        current = 0
    nxt = current + 1
    ISSUE_COUNTER_PATH.write_text(str(nxt))
    return nxt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="当天内容的JSON文件路径")
    parser.add_argument("--out", default=None, help="输出HTML路径（默认 briefs/daily_brief_YYYYMMDD.html）")
    parser.add_argument("--dry-run", action="store_true", help="只渲染，不消耗期号计数器（用于测试预览）")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"找不到数据文件: {data_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(data_path.read_text(encoding="utf-8"))

    if "issue_no" not in data:
        data["issue_no"] = 0 if args.dry_run else next_issue_no()
        if not args.dry_run:
            # 写回数据文件：merge_special.py 之后要靠它沿用同一个期号，
            # 只留在内存里的话合并后会渲染成“总第 -- 期”
            data_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if not TEMPLATE_PATH.exists():
        print(f"找不到模板文件: {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)

    template_html = TEMPLATE_PATH.read_text(encoding="utf-8")
    injected = template_html.replace(
        "__BRIEF_DATA_JSON__",
        json.dumps(data, ensure_ascii=False, indent=2),
    )

    date_str = data.get("date", "").replace("-", "")
    out_path = Path(args.out) if args.out else BRIEFS_DIR / f"daily_brief_{date_str}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(injected, encoding="utf-8")

    print(f"已渲染: {out_path}")
    print(f"期号: 总第 {data['issue_no']} 期")


if __name__ == "__main__":
    main()
