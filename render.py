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
  "overview": "一句话概览……",           // 可选，最后写，见下方「三个可选字段」
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
    "summary": "本周 5 家大厂发财报，重点看 AI 资本开支",   // 可选，见下方「三个可选字段」
    "html": "<h4>本周财报日历</h4><p>...</p>",   // status 为 pending 时可省略
    "status": "pending" | "ready"       // pending 只出占位卡片，不计入版数
  },
  "holidays": [                         // 报头假期带，由 special_helper.py apply 自动写入
    {"region":"cn","label":"中国","name":"中秋节","date":"2026-09-25","days":23}
  ],
  "markets": [                          // 可选，10 项行情，见下方「三个可选字段」
    {"id": "spx", "group": "us", "name": "标普 500", "value": 7412.6,
     "change_pct": -0.84, "session": "close", "as_of": "2026-10-29",
     "source": "https://www.cnbc.com/quotes/.SPX"}, ...
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

三个可选字段（JerryStudio 首页用）。渲染前 extras.py 会清理：不合格的只删那一项并打印
原因，清理后的 JSON 写回数据文件。**它们永远不会让一期简报发不出去。**

overview —— 一句 20–70 字的中文，其他板块都写完以后最后写：
  把今天最重要的 2–3 件事串起来（可以跨板块）；只用今天条目里已有的事实，中性、具体；
  不放链接，不提虚构栏目。领导人出访、会见、开会，除非带来具体政策变化，否则不作主线。
  清理：不是字符串、不到 15 字或超过 80 字、含换行、含 http、含【虚构】的，删掉。

markets —— 10 项行情。id、name、group、unit 和顺序都照下表（顺序不对会被重排）：

    id      name                group                  unit  涨跌字段
    spx     标普 500            us                           change_pct
    ixic    纳斯达克            us                           change_pct
    dji     道琼斯              us                           change_pct
    hsi     恒生指数            cn_hk                        change_pct
    sse     上证指数            cn_hk                        change_pct
    usdcny  美元/人民币         commodities_rates_fx         change_pct
    usdcad  美元/加元           commodities_rates_fx         change_pct
    cadcny  加元/人民币         commodities_rates_fx         change_pct
    xau     黄金（美元/盎司）   commodities_rates_fx         change_pct
    us10y   美债 10 年          commodities_rates_fx   "%"   change_bp（基点）

  每项写 id / group / name / value / 涨跌字段 / session / as_of / source（us10y 另加 unit）。
  - 简报约温哥华 08:00 写，所以：美股取上一个交易日收盘（session "close"，as_of 那个交易日）；
    恒生、上证取今天收盘，没开市就取最近一次收盘（"close"，as_of 那天）；汇率、黄金、
    美债取写稿时的最新值（"live"，as_of 今天）。
  - source 是读到这个数的那一页，https://。沙箱打不开 Reuters / AP / BBC / Guardian，
    用 CNBC 行情页、新浪 / 腾讯 / 网易财经、CNN Markets。
  - 加元/人民币可以用同一时刻的 美元/人民币 ÷ 美元/加元 算出，算出来的加 "derived": true，
    source 写美元/人民币那一页。
  - 取不到的项就不写：不估算，不沿用旧数。
  清理（删掉那一项）：id 未知或重复；group / unit 和 id 不符；value 不是正数或超出
  extras.RANGES 的合理区间；change_pct 超过 ±15、change_bp 超过 ±100；session 不是
  close / live；as_of 不在简报日期前 7 天以内；source 缺失或不是 https://。
  一项都没留下就删掉整个 markets。加元/人民币和两个美元汇率对不上（差 > 1%）只提示。

special.summary —— 一句话（≤ 40 字）说这期特刊写了什么：写内容，不写方法。
  例：「本期 4 笔大额融资，机器人和能源各占一半」；不要写「覆盖区间…信源…」。
  由 special_helper.py save --summary 或 merge_special.py --special-summary 写入。
  清理：超过 60 字或含 http 的，删掉。
"""
import argparse
import json
import sys
from pathlib import Path

import extras

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

    raw = json.loads(data_path.read_text(encoding="utf-8"))
    # 行情 / 概览 / 特刊摘要：不合格的只删那一项，照常渲染发布（见 extras.py）
    data, warnings = extras.clean(raw)
    for w in warnings:
        print(f"已清理: {w}")

    if "issue_no" not in data:
        data["issue_no"] = 0 if args.dry_run else next_issue_no()
    if not args.dry_run and data != raw:
        # 写回数据文件：merge_special.py 之后要靠它沿用同一个期号，
        # 只留在内存里的话合并后会渲染成“总第 -- 期”；
        # 清理掉的项也要从文件里删掉——JerryStudio 原样复制这个文件
        data_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if not TEMPLATE_PATH.exists():
        print(f"找不到模板文件: {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)

    date_str = data.get("date", "").replace("-", "")
    if date_str:
        extras.save_warnings(date_str, warnings)   # publish.py 读它，写进日志和通知

    template_html = TEMPLATE_PATH.read_text(encoding="utf-8")
    injected = template_html.replace(
        "__BRIEF_DATA_JSON__",
        json.dumps(data, ensure_ascii=False, indent=2),
    ).replace(
        # 访客统计像素要知道自己是哪一页；--out 只用于预览，统计路径始终按正式位置写
        "__PAGE_PATH__", f"/briefs/daily_brief_{date_str}.html",
    )
    if "__PAGE_PATH__" in injected:
        print("警告: 模板里的 __PAGE_PATH__ 没有被替换", file=sys.stderr)

    out_path = Path(args.out) if args.out else BRIEFS_DIR / f"daily_brief_{date_str}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(injected, encoding="utf-8")

    print(f"已渲染: {out_path}")
    print(f"期号: 总第 {data['issue_no']} 期")


if __name__ == "__main__":
    main()
