#!/usr/bin/env python3
"""Prepare the brief pages in briefs/ and regenerate the index list.

Run this after dropping a new brief HTML into briefs/. It is idempotent:

1. mobile patch  — appends a @media (max-width:600px) block so the page reads
                   on a phone without touching the desktop layout
2. fiction label — badges every 趣闻 / 本地简报 / 笑话 heading as 虚构, because
                   the brief specs generate those sections as fabricated
3. index         — rewrites the <ul class="briefs"> list in index.html
"""
import re, os, glob, html, sys

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
    if name.startswith("daily"):
        kind = "日报"
        items = [text(t) for _, t in
                 re.findall(r'<a\s[^>]*href="(http[^"]*)"[^>]*>(.*?)</a>', body, re.S)]
        items = [i for i in items if 8 < len(i) < 80][:3]
    else:
        kind = "周报"
        items = [text(t) for t in re.findall(r'<h[123][^>]*>(.*?)</h[123]>', body, re.S)]
        items = [i for i in items if 8 < len(i) < 90 and not SKIP.search(i)][:3]
    summary = "；".join(items) + "。" if items else "本期内容见全文。"
    return dict(file=name, date=date, title=title, kind=kind, summary=summary)

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

    li = ['        <li>\n'
          f'          <h3 class="brief-title"><a href="briefs/{r["file"]}">{html.escape(r["title"])}</a></h3>\n'
          f'          <time class="brief-date" datetime="{r["date"]}">{r["date"]}<span class="kind">{r["kind"]}</span></time>\n'
          f'          <p class="brief-summary">{html.escape(r["summary"])}</p>\n'
          '        </li>' for r in rows]
    block = '      <ul class="briefs">\n' + "\n".join(li) + '\n      </ul>'

    idx = os.path.join(REPO, "index.html")
    src = open(idx, encoding="utf-8").read()
    pat = re.compile(r'      <ul class="briefs">.*?</ul>', re.S)
    if not pat.search(src):
        sys.exit('index.html 里找不到 <ul class="briefs"> 标记')
    new = pat.sub(lambda _: block, src)
    open(idx, "w", encoding="utf-8").write(new)
    print(f"index.html 已更新，共 {len(rows)} 期")

main()
