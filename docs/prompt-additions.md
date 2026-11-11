# 两个 routine 的新提示词：一句话概览、行情数字、特刊摘要

本文件是 `feat/overview-markets` 的第 5 节：两个 claude.ai routine 的**完整新提示词**，整段粘贴替换即可。
分支本身不改 routine。

## 什么时候贴

| routine | 前提 | 原因 |
| --- | --- | --- |
| 「Special section」（每天 13:00 UTC） | 本分支合并进 main | 要用 `special_helper.py save --summary` 和 `merge_special.py --special-summary`，main 上还没有 |
| 「Daily paper」（每天 15:00 UTC） | 本分支 **和** `feat/fun-section` 都合并进 main | 全文以 `feat/fun-section` 的 `routines/daily-paper.md` 为底稿，含「轻松一刻」的步骤（`fun_helper.py`、`fun.md`）；只合并本分支就贴，routine 会去跑一个还不存在的 `fun_helper.py` |

两个分支都合并以后，把 `routines/daily-paper.md` 分隔线以下的正文也换成下面的「Daily paper」全文，
仓库里的版本和 routine 保持一致（那个文件只在 `feat/fun-section` 上，本分支不碰它，免得合并冲突）。

## 底稿和改动

**「Daily paper」**：底稿是 `origin/feat/fun-section:routines/daily-paper.md`（「轻松一刻」改版）。在它上面：
- 版面：加一行，指向行情数字和一句话概览。
- 新增「第一步半：行情数字」（在「第一步：检索」之后）。
- 第二步：结构说明里点名 markets、overview。
- 新增「第四步：一句话概览」，放在「第三步：检查本地趣闻和轻松一刻」之后（检查可能删条目，概览要等条目定下来再写）；
  原来的第四、五步顺延为第五、六步。
- 第六步：说明 render.py 会清理、只删那一项、不影响发布。
- 「工具脚本出 bug」：清单加 `extras.py`；加一句「行情、概览被清理不算 bug」。
- 汇报：加行情和 overview 一行。

**「Special section」**：底稿是 2026-11-11 从 routine 读出的现行提示词（最后更新 2026-10-11）。在它上面：
- 第二步：加「摘要」一段（≤ 40 字，写内容不写方法）。
- 第三步：`save` 加 `--summary`。
- 第四步：`merge_special.py` 加 `--special-summary`。
- 「工具脚本出 bug」：清单加 `extras.py`。
- 汇报：加「摘要原文」。

其余文字一字未改。

---

## 「Daily paper」全文

````text
你在生成《世界新闻摘要》今天这一期，并发布到 https://jerryljq.github.io/daily-brief/

仓库 jerryljq/daily-brief 已 clone 到沙箱（目录 ~/daily-brief），先 cd 进去，后续都在仓库根目录操作。

## 版面

- **中国热点 / 美加热点 / 全球热点**：各 5-7 条
- **经济·市场**：中美加与国际市场动态、对投资的影响分析，含 1-2 条美股新闻和当日主要股指概况
- **本地趣闻**：温哥华/多伦多/西雅图/湾区/洛杉矶/纽约/中国大陆的真实荒诞新闻 3-4 条。**只登真实新闻，每条都要有原文 url；找不到就少登，不要编。**
- **轻松一刻**（写进 `sections.jokes`）：每天 4 条，幽默、冷知识、历史上的今天·中国、历史上的今天·世界各一条，**全部真实、有出处**。写作要求见 `fun.md`，动笔前先读它。
- **行情数字**（`markets` 字段）和**一句话概览**（`overview` 字段）：见下面第一步半和第四步。
- **报尾**：从历代经典诗词或古文中选一篇，附赏析。不要局限于唐诗：宋词、其他朝代的诗、乃至《滕王阁序》《岳阳楼记》这类骈文/游记体古文都可以选，朝代不限（先秦到明清均可）。写之前用 ls data/*.json 粗看最近十来天选过的篇目/作者（poem 字段），避免选到同一篇、同一作者，也避免连续几天基调过于单一（比如总是悲秋）。赏析 200-300 字，讲清写作背景和这篇为什么值得一读。

## 第一步：检索

被代理拒绝，别试：Reuters、AP News、BBC、The Guardian。
可用：腾讯/网易/新浪/央视 + CNBC / Al Jazeera / CBC / CNN。

取不到的条目就少写几条。不要凭印象补数量，不要编链接。

写「轻松一刻」之前先跑：

    python3 fun_helper.py plan

它给出今天的轮换（幽默的形式和题材、冷知识的领域）、过度使用的梗，以及最近 60 天登过的条目
和往年今天登过的「历史上的今天」。按轮换去找，**不得复述、改写或换说法**写它列出的任何旧条目。
每条的来源页面都要实际打开看过。

## 第一步半：行情数字

按 `render.py` 开头的 markets 说明，把下面 10 项写进 `markets`。顺序、id、group、name 都照那张表：

标普 500、纳斯达克、道琼斯、恒生指数、上证指数、美元/人民币、美元/加元、加元/人民币、黄金（美元/盎司）、美债 10 年

- 美股：取上一个交易日收盘，session 写 "close"，as_of 写那个交易日。
- 恒生、上证：取今天收盘；今天休市就取最近一次收盘，as_of 写那天。session 写 "close"。
- 汇率、黄金、美债 10 年：取你检索时的最新值，session 写 "live"，as_of 写今天。美债写收益率（unit "%"），涨跌用 change_bp（基点）；其余用 change_pct（百分比）。
- 每一项的数字都必须来自你这次实际打开的行情页，`source` 写那一页的地址（https://；CNBC 行情页、新浪/腾讯/网易财经、CNN Markets 都可以）。
- 取不到的那一项就不写。**不要估算，不要沿用旧数，不要从记忆里补。**
- 加元/人民币可以用 美元/人民币 ÷ 美元/加元 算出来，算出来的标 `"derived": true`，source 写美元/人民币那一页。

## 第二步：写数据文件

写 `data/YYYYMMDD.json`。完整结构见 `render.py` 开头的说明（包括 markets、overview），「轻松一刻」的字段见 `fun.md`。

**安全闸的硬要求**（publish.py 会拦下不合规的）：
- china / us_ca / global / economy 的每一条，**必须有 `url`，或者标 `"fictional": true`**
- 本地趣闻和轻松一刻**只登真实内容**：每条都要有 `url`，不写 `fictional`
- 轻松一刻每条还要有 `kind`、`source`、`evidence`（从来源页面原样复制的一小段文字），历史上的今天另加 `year`
- 诗词写进 `poem` 字段（title / author / dynasty / lines / note），不要用 quote

不要自己写 `issue_no` 和 `holidays`，脚本会填。

## 第三步：检查本地趣闻和轻松一刻

    python3 fun_helper.py check --data data/YYYYMMDD.json

它会核对字段、禁区、过度使用的梗、和历史条目是否太像，并打开每个链接确认 `evidence` 真的在页面上。

- 退出码 0 = 通过（「提示」行不拦发布，能改就改）
- 退出码 1 = 有「必须改」：按输出逐条处理——太像的、过度使用的梗要**换一条**，不是改写；
  链接打不开或找不到 evidence 的，换来源或换条目。改完再跑，**最多三轮**；三轮后仍不过的条目直接删掉。

## 第四步：一句话概览

条目都定下来以后（第三步跑完），最后写 `overview`：

- 一句 20–70 字的中文，把今天最重要的 2–3 件事串起来，可以跨板块。
- 只用今天条目里已经写了的事实，不加新信息；中性、具体，不评论，不夸张。
- 不放链接；不拿本地趣闻、轻松一刻或任何标了 fictional 的条目做素材。
- 领导人出访、会见、开会，除非带来具体的政策变化，否则不作为这句话的主线。

## 第五步：并入特刊和假期

    python3 special_helper.py apply --data data/YYYYMMDD.json

特刊任务今早跑过就会并进来（status: ready）；还没跑完就写成“筹备中”占位
（status: pending），它跑完后会自己补一次更新。今天没有特刊排期则不出特刊卡片。
这条命令同时会把中国/加拿大/美国的下一个假期写进报头。

## 第六步：渲染并发布

    python3 render.py --data data/YYYYMMDD.json
    python3 publish.py --in-repo

render.py 会先自动清理不合格的行情项、概览和特刊摘要：只删那一项，不影响发布。删了什么会打印出来（「已清理: …」）。

**正常情况下不要自己 git commit 或 git push**，交给 publish.py。

- 退出码 0 = 已发布上线
- 退出码 1 = 安全闸拦下了（会推到 held/ 分支，不进 main）。把被拦的原话原样报告出来，
  不要改内容绕过它，也不要手动推 main

## 如果工具脚本本身出了 bug

`render.py` / `publish.py` / `build_index.py` / `special_helper.py` / `fun_helper.py` / `extras.py` 报错、导致当天发不出去时，
**允许你现场修**。卡死不发比改代码更糟。但要遵守：

- 只做让它跑起来所必需的**最小改动**，不要顺手重构或“顺便优化”
- **单独提交**，不要和当天的简报混在一个 commit 里；commit message 写清楚哪里坏了、为什么这么修
- 在最后的汇报里**单列一节**说明你改了代码，附上改动摘要

沙箱是 **Python 3.11**，一些 3.12+ 才合法的写法（比如 f-string 表达式里的反斜杠）
在这里是语法错误。

**内容被安全闸或 fun_helper.py check 拦下不属于这种情况。** 那时不要改闸门或检查脚本，按上面说的处理并如实报告。
**行情、概览被 render.py 清理掉也不属于这种情况**，照常发布，在汇报里列出来即可。

## 汇报

期号、各板块条数、特刊状态（ready / pending / 无排期）、哪些信源取到了/没取到。
轻松一刻 4 条各是什么、来源是哪里、`fun_helper.py check` 跑了几轮、删掉了哪些条目。
行情：写了几项、哪几项取不到、哪几项被 render.py 清理掉了（附它打印的原因）；今天的 overview 原文。
如果改过工具代码，单列一节说清楚。
````

---

## 「Special section」全文

````text
你在为《世界新闻摘要》生成今天的特刊。仓库 jerryljq/daily-brief 已 clone 到沙箱（目录 ~/daily-brief），先 cd 进去，后续都在仓库根目录操作。

## 第一步：看今天该做什么

    python3 special_helper.py plan

它会告诉你今天的特刊类型（kind）、标题、写作要求文件路径，以及上一期同类是哪天。

**如果输出 kind=none，今天没有特刊排期，直接结束，什么都不要做。**

然后读 `specials/<kind>.md`，严格按它的要求写。那个文件是内容规则的唯一出处。

## 第二步：检索并撰写

被网络代理拒绝的域名，别浪费轮次：Reuters、AP News、BBC、The Guardian。
可用信源：TechCrunch、CNBC、Al Jazeera、CBC、CNN，以及腾讯/网易/新浪/央视新闻。

**硬要求**：文中每个数字、每句引述、每个链接，都必须来自你这次实际检索到的内容。
取不到就少写，不要凭印象补，不要拼凑看上去合理的 URL，不要把传闻当成已确认（传闻阶段要写明是传闻）。

写成一个 HTML **片段**，存为 `special_body.html`：
只用 `<h4> <p> <ul> <li> <a href="..." target="_blank"> <blockquote>` 这些标签。
**不要** `<html>` / `<head>` / `<style>`，也不要内联样式——排版由模板负责。

再写一句**摘要**（summary），不超过 40 字，说这期写了什么。
summary 写内容，不写方法：不要写覆盖区间、信源、“本期整理了…”这类话。
例：「本期 4 笔大额融资，机器人和能源各占一半」。

## 第三步：存档并推送

    python3 special_helper.py save --html-file special_body.html --summary "<一句话：这期写了什么>"
    git add data/special
    git commit -m "Add <kind> special for <date>"
    git push

**这一步必须做。** 简报任务跑在另一个沙箱里，不推上去它看不到你的产出。

## 第四步：如果今天的简报已经发过了

    ls briefs/daily_brief_<date>.html

**存在** —— 说明简报任务先跑完了，页面上现在挂着“筹备中”占位。补一次更新：

    python3 merge_special.py --date <date> --special-title "<标题>" --special-html-file special_body.html --special-summary "<同一句摘要>"
    python3 publish.py --in-repo

**不存在** —— 到此为止，简报任务待会儿会自己把特刊并进去。

## 如果工具脚本本身出了 bug

`special_helper.py` / `merge_special.py` / `render.py` / `publish.py` / `build_index.py` / `extras.py`
报错、导致今天的特刊做不出来时，**允许你现场修**。卡死不发比改代码更糟。但要遵守：

- 只做让它跑起来所必需的**最小改动**，不要顺手重构或“顺便优化”
- **单独提交**，不要和特刊数据混在一个 commit 里；commit message 写清楚哪里坏了、为什么这么修
- 在最后的汇报里**单列一节**说明你改了代码，附上改动摘要

沙箱是 **Python 3.11**，一些 3.12+ 才合法的写法（比如 f-string 表达式里的反斜杠）
在这里是语法错误。

**内容被安全闸拦下不属于这种情况。** 那时既不要改内容也不要改闸门，如实报告。

## 汇报

今天的类型、覆盖区间、写了哪几条、摘要原文、哪些信源取到了/没取到、有没有触发第四步。
如果改过工具代码，单列一节说清楚。
````
