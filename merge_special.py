#!/usr/bin/env python3
"""
把特刊内容合并进"今天已经发布过、但特刊还是筹备中占位"的数据文件里，重新渲染。

使用场景：特刊任务比简报任务晚完成（比如深度分析研究耗时较长），
简报任务已经先发布了一版"特刊筹备中"的页面，特刊任务做完后用这个脚本补一次更新。

不会消耗新的期号（issue_no 沿用当天已经写好的那个）。
跑完这个脚本后，仍然需要你自己运行 publish.py --in-repo 来提交+推送更新。

用法：
    python3 merge_special.py --date 20260907 \
        --special-title "本周财经周展望" \
        --special-html-file special_body.html

special_body.html 是一个只包含特刊正文片段的 HTML 文件（不要整页 <html>，
就是 <h4>...</h4><p>...</p> 这种片段，会被原样注入模板里的特刊卡片正文区域）。
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
BRIEFS_DIR = REPO_ROOT / "briefs"
TEMPLATE_PATH = REPO_ROOT / "template.html"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--special-title", required=True)
    parser.add_argument("--special-html-file", required=True, help="特刊正文HTML片段文件路径")
    args = parser.parse_args()

    data_path = DATA_DIR / f"{args.date}.json"
    if not data_path.exists():
        print(f"找不到当天数据文件: {data_path}\n"
              f"说明简报任务今天还没跑过，没法合并——正常情况下简报任务应该先跑。", file=sys.stderr)
        sys.exit(1)

    special_html_path = Path(args.special_html_file)
    if not special_html_path.exists():
        print(f"找不到特刊正文文件: {special_html_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(data_path.read_text(encoding="utf-8"))
    data["special"] = {
        "title": args.special_title,
        "html": special_html_path.read_text(encoding="utf-8"),
        "status": "ready",
    }
    # issue_no 沿用已有的，不重新分配
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    template_html = TEMPLATE_PATH.read_text(encoding="utf-8")
    injected = template_html.replace(
        "__BRIEF_DATA_JSON__",
        json.dumps(data, ensure_ascii=False, indent=2),
    )
    out_path = BRIEFS_DIR / f"daily_brief_{args.date}.html"
    out_path.write_text(injected, encoding="utf-8")

    print(f"已合并特刊并重新渲染: {out_path}")
    print("接下来运行 publish.py --in-repo 提交这次更新。")


if __name__ == "__main__":
    main()
