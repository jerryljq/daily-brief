#!/usr/bin/env python3
"""Prepare the brief pages in briefs/ and regenerate the index list.

Run this after dropping a new brief HTML into briefs/. It is idempotent:

1. mobile patch  — appends a @media (max-width:600px) block so the page reads
                   on a phone without touching the desktop layout
2. fiction label — badges every 趣闻 / 本地简报 / 笑话 heading as 虚构, because
                   the brief specs generate those sections as fabricated
3. index         — rewrites the <ul class="briefs"> list in index.html

audit() is exported for publish.py, which refuses to push when it returns
anything blocking.
"""
import re, os, glob, html, json, sys

REPO   = os.path.dirname(os.path.abspath(__file__))
BRIEFS = os.path.join(REPO, "briefs")

# ── 1. 移动端适配 ────────────────────────────────────────────────
MOBILE = """
/* MOBILE-PATCH ── 仅 ≤600px 生效，桌面端不受影响 */
@media (max-width:600px){
  .mh-top,.mh-meta,.masthead-top,.masthead-meta,.meta-row,.sec-hdr,.byline{
    flex-direction:column!important;align-items:center!important;
    gap:6px!important;text-align:center!important;
  }
  .mh-top>span,.mh-meta>span,.masthead-top>span,.masthead-meta>span{
    white-space:normal!important;width:auto!important;
  }
  [class*="grid"],[class*="col"]{grid-template-columns:1fr!important;}
  img,iframe,video{max-width:100%!important;height:auto;}
  table,pre{display:block;max-width:100%;overflow-x:auto;}
  body{-webkit-text-size-adjust:100%;}
  blockquote{margin-left:0!important;margin-right:0!important;}
}
.fic-tag{display:inline-block;margin-left:.5em;padding:.1em .5em;
  border:1px solid currentColor;border-radius:4px;font-size:.68em;font-weight:600;
  opacity:.8;vertical-align:middle;letter-spacing:.02em;white-space:nowrap;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;}
"""

# ── 2. 虚构标注 ─────────────────────────────────────────────────
SECTION = re.compile(r'(>[^<>]{0,30}(?:趣闻|本地简报)[^<>]{0,30})(<)')
BADGE   = re.compile(r'(<span class="badge b-lo">[^<]*</span>)')
JOKE    = re.compile(r'(<(?!a[\s>])(?!/)[a-zA-Z0-9]+[^>]*>)'
                     r'([^<>]{0,32}(?:笑话|JOKE|再来一个)[^<>]{0,20})(<)')

def tag(label="虚构 · 非真实新闻"):
    return f'<span class="fic-tag">{label}</span>'

def prepare(path):
    h = open(path, encoding="utf-8").read()
    changed = False

    # 新格式的简报自己按 fictional 字段逐条打标签，而且本身就是响应式的。
    # 旧的正则标注器只会认字面，把索引按钮「趣闻」「笑话」和栏目标题「本地趣闻」
    # 也当成虚构内容标上——那等于把一整栏真新闻标成编的。这里直接放行。
    if brief_data(h) is not None:
        return False, 0

    styles = []
    h = re.sub(r'<style.*?</style>',
               lambda m: styles.append(m.group(0)) or f"@@S{len(styles)-1}@@", h, flags=re.S)

    added = [0]

    def insert(m, before, after, label):
        """Put the badge between `before` and `after`; skip if one is already there."""
        if 'fic-tag' in m.group(0) or 'fic-tag' in h[m.end():m.end() + 24]:
            return m.group(0)
        added[0] += 1
        return before + tag(label) + after

    h = SECTION.sub(lambda m: insert(m, m.group(1), m.group(2), "虚构 · 非真实新闻"), h)
    h = BADGE.sub(  lambda m: insert(m, m.group(1), "",          "虚构 · 非真实新闻"), h)
    h = JOKE.sub(   lambda m: m.group(0) if '话题' in m.group(2)
                    else insert(m, m.group(1) + m.group(2), m.group(3), "虚构"), h)

    for i, s in enumerate(styles):
        h = h.replace(f"@@S{i}@@", s)

    if 'MOBILE-PATCH' not in h:
        if '</style>' in h:
            i = h.rfind('</style>'); h = h[:i] + MOBILE + h[i:]
        else:
            h = h.replace('</head>', f'<style>{MOBILE}</style>\n</head>', 1)
        changed = True

    open(path, "w", encoding="utf-8").write(h)
    return changed, added[0]

# ── 3. 索引 ────────────────────────────────────────────────────
SKIP = re.compile(r'^\d+\s|背景故事|底层逻辑|交叉引用|结论与判断|发散话题|信源|参考资料|深度周报|本期|因果链|导航')

def text(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s)).strip()

def meta(path):
    h = open(path, encoding="utf-8").read()
    body = re.sub(r'<script.*?</script>|<style.*?</style>', '', h, flags=re.S)
    name = os.path.basename(path)
    date = "-".join(re.search(r'(\d{4})(\d{2})(\d{2})', name).groups())
    title = text(re.search(r'<title>(.*?)</title>', h, re.S).group(1))

    data = brief_data(h)
    if data is not None:
        sec = data.get('sections') or {}
        # 三条轨道各取头条一条。原来是把各板块首尾相连再截前三条，
        # 中国板块条目最多，结果预览里全是中国新闻。
        heads = []
        for key in ('china', 'us_ca', 'global'):
            for it in sec.get(key) or []:
                t = (it.get('title') or '').strip()
                if t:
                    heads.append(t)
                    break
        no = data.get('issue_no')
        # 目录页每行都跟着报名是冗余的，那页本身就是这份报纸的
        return dict(file=name, date=date,
                    title=(f"第 {no} 期" if no else title),
                    kind="日报",
                    summary=("；".join(heads[:3]) + "。") if heads else "本期内容见全文。")

    if name.startswith("daily"):
        kind = "日报"
        anchors = [(m.start(), text(m.group(2))) for m in
                   re.finditer(r'<a\s[^>]*href="(http[^"]*)"[^>]*>(.*?)</a>', body, re.S)]
        anchors = [(pos, t) for pos, t in anchors if 8 < len(t) < 80]
        # 同样三条轨道各取一条：找到栏目标记的位置，取它之后的第一个链接
        items = []
        for marker in ('中国热点', '美加热点', '全球热点'):
            at = body.find(marker)
            if at < 0:
                continue
            nxt = next((t for pos, t in anchors if pos > at), None)
            if nxt and nxt not in items:
                items.append(nxt)
        if not items:
            items = [t for _, t in anchors][:3]
    else:
        kind = "周报"
        items = [text(t) for t in re.findall(r'<h[123][^>]*>(.*?)</h[123]>', body, re.S)]
        items = [i for i in items if 8 < len(i) < 90 and not SKIP.search(i)][:3]
    summary = "；".join(items) + "。" if items else "本期内容见全文。"
    return dict(file=name, date=date, title=title, kind=kind, summary=summary)


# ── 4. 安全闸：找出“像编的、又没标注、又没出处”的段落 ──────────────
from html.parser import HTMLParser

# 一级：虚构内容的典型说法，未覆盖就拦截发布
TELL_BLOCK = re.compile(
    r'网友|论坛|据说|传闻|爆料|目击|小道消息|笑称|戏称|吐槽|据本地|非正式统计|本地居民')
# 二级：正经报道里也常见，只记录不拦截
TELL_WARN = re.compile(
    r'分析师|发言人|受访|接受采访|经纪人表示|老板表示|经济学界|市民')

_VOID = {'br','img','meta','link','hr','input','source'}

class _Node:
    __slots__ = ('tag','attrs','parent','kids','text')
    def __init__(s, tag, attrs, parent):
        s.tag, s.attrs, s.parent, s.kids, s.text = tag, dict(attrs), parent, [], []
    def has(s, pred):
        return pred(s) or any(k.has(pred) for k in s.kids)

class _P(HTMLParser):
    def __init__(s):
        super().__init__(convert_charrefs=True)
        s.root = _Node('root', [], None); s.cur = s.root
    def handle_starttag(s, tag, attrs):
        n = _Node(tag, attrs, s.cur); s.cur.kids.append(n)
        if tag not in _VOID: s.cur = n
    def handle_endtag(s, tag):
        n = s.cur
        while n is not None and n.tag != tag: n = n.parent
        if n is not None and n.parent is not None: s.cur = n.parent
    def handle_data(s, d): s.cur.text.append(d)

_BLOCK_TAGS = ('div','section','article','li','aside','p','td','blockquote')
_has_fic  = lambda n: 'fic-tag' in n.attrs.get('class','')
_has_link = lambda n: n.tag == 'a' and n.attrs.get('href','').startswith('http')

def _classed_ancestors(node, limit):
    """自身往上最近的若干个“带 class 的块级容器”。"""
    out, b, steps = [], node, 0
    while b is not None and steps < 12 and len(out) < limit:
        if b.tag in _BLOCK_TAGS and b.attrs.get('class'): out.append(b)
        b = b.parent; steps += 1
    return out

def _covered(node):
    """已标虚构，或所在卡片自带原文链接。

    两者判定范围不同，因为它们在结构里的位置不同：
    - 虚构标签打在栏目标题上，和正文是兄弟关系 → 向上找 3 层卡片
    - 源链接和摘要同属一个条目卡片 → 只认最近一层，放宽会摸到页面级
      容器（.wrap 之类），把编造段落误判成有出处
    """
    anc = _classed_ancestors(node, 3)
    if any(a.has(_has_fic) for a in anc): return True
    return bool(anc) and anc[0].has(_has_link)


# ── 新格式：内容在 <script id="brief-data"> 的 JSON 里，不在 HTML 正文 ──
BRIEF_DATA = re.compile(r'<script id="brief-data"[^>]*>(.*?)</script>', re.S)

def brief_data(html_text):
    """新版简报返回 dict，旧版（内容直接写在 HTML 里）返回 None。"""
    m = BRIEF_DATA.search(html_text)
    if not m:
        return None
    try:
        return json.loads(m.group(1).strip())
    except ValueError:
        return None

# 必须“有出处或已标虚构”的板块。笑话不要求链接，诗词赏析不是报道。
SOURCED_KEYS = ('china', 'us_ca', 'global', 'economy', 'local_fun')

def audit_json(data):
    blocking, warnings = [], []
    sec = data.get('sections') or {}

    for key in SOURCED_KEYS:
        for it in sec.get(key) or []:
            txt = (it.get('title') or '') + ' ' + (it.get('summary') or '')
            sourced, flagged = bool(it.get('url')), bool(it.get('fictional'))
            if not sourced and not flagged:
                blocking.append(f"[{key}] {txt.strip()[:120]} —— 既无原文链接，也没标 fictional")
            elif sourced and TELL_BLOCK.search(txt) and not flagged:
                warnings.append(f"[{key}] {txt.strip()[:120]}")

    # 笑话一律要标 fictional：笑话本来就不是报道，而“给真实主体编台词”
    # （记者问美联储主席…、审计师问 CFO…）靠关键词根本认不出来，
    # 与其猜，不如要求全部标注。
    for it in sec.get('jokes') or []:
        if not it.get('fictional'):
            txt = (it.get('title') or '') + ' ' + (it.get('summary') or '')
            blocking.append(f"[jokes] {txt.strip()[:120]} —— 笑话必须标 fictional")

    # 特刊是 HTML 片段，按有无出处链接判断
    sp = data.get('special') or {}
    if sp.get('html'):
        frag = sp['html']
        text = html.unescape(re.sub(r'<[^>]+>', ' ', frag))
        if TELL_BLOCK.search(text) and 'href="http' not in frag:
            blocking.append(f"[special] {re.sub(r'\s+', ' ', text).strip()[:120]} —— 无出处链接")

    return blocking, warnings

def audit(path):
    """→ (blocking, warnings)，各是一串文字片段。"""
    raw = open(path, encoding="utf-8").read()
    data = brief_data(raw)
    if data is not None:
        return audit_json(data)
    # 旧版简报：内容就在 HTML 正文里
    src = re.sub(r'<style.*?</style>|<script.*?</script>', '', raw, flags=re.S)
    p = _P(); p.feed(src)
    blocking, warnings = [], []
    def walk(n):
        t = "".join(n.text).strip()
        if t and (TELL_BLOCK.search(t) or TELL_WARN.search(t)) and not _covered(n):
            (blocking if TELL_BLOCK.search(t) else warnings).append(re.sub(r'\s+', ' ', t)[:160])
        for k in n.kids: walk(k)
    walk(p.root)
    return blocking, warnings


def main():
    files = sorted(glob.glob(os.path.join(BRIEFS, "*.html")))
    if not files:
        sys.exit("briefs/ 是空的")

    for f in files:
        patched, n = prepare(f)
        if patched or n:
            print(f"  {os.path.basename(f):36s} mobile={'+' if patched else '-'} 新增标注={n}")

    rows = sorted((meta(f) for f in files),
                  key=lambda r: (r["date"], r["kind"] == "周报"), reverse=True)

    # 按月分组，最新的月份排最前且默认展开
    groups = []
    for r in rows:
        ym = r["date"][:7]
        if not groups or groups[-1][0] != ym:
            groups.append((ym, []))
        groups[-1][1].append(r)

    def entry(r):
        return ('            <li>\n'
                f'              <h3 class="brief-title"><a href="briefs/{r["file"]}">{html.escape(r["title"])}</a></h3>\n'
                f'              <time class="brief-date" datetime="{r["date"]}">{r["date"]}'
                f'<span class="kind">{r["kind"]}</span></time>\n'
                f'              <p class="brief-summary">{html.escape(r["summary"])}</p>\n'
                '            </li>')

    blocks = []
    for i, (ym, items) in enumerate(groups):
        y, m = ym.split("-")
        label = f"{y} 年 {int(m)} 月"
        blocks.append(
            f'        <details class="month"{" open" if i == 0 else ""}>\n'
            f'          <summary><span class="m-label">{label}</span>'
            f'<span class="m-count">{len(items)} 期</span><i class="chev"></i></summary>\n'
            '          <ul class="briefs">\n'
            + "\n".join(entry(r) for r in items) + '\n'
            '          </ul>\n'
            '        </details>')
    block = ('      <!-- BRIEFS:START -->\n' + "\n".join(blocks) +
             '\n      <!-- BRIEFS:END -->')

    idx = os.path.join(REPO, "index.html")
    src = open(idx, encoding="utf-8").read()
    pat = re.compile(r'      <!-- BRIEFS:START -->.*?<!-- BRIEFS:END -->', re.S)
    if not pat.search(src):
        sys.exit('index.html 里找不到 <!-- BRIEFS:START/END --> 标记')
    new = pat.sub(lambda _: block, src)
    open(idx, "w", encoding="utf-8").write(new)
    print(f"index.html 已更新，共 {len(rows)} 期")
    return rows

if __name__ == "__main__":
    main()
