#!/usr/bin/env python3
"""Regenerate the brief list in index.html from the files in briefs/."""
import re, os, glob, html, sys

REPO = "/Users/jerry/Develop/JerryStudio/GithubPageHome/daily-brief"
BRIEFS = os.path.join(REPO, "briefs")

SKIP = re.compile(r'^\d+\s|背景故事|底层逻辑|交叉引用|结论与判断|发散话题|信源|参考资料|深度周报|本期|因果链|导航')

def text(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s)).strip()

def meta(path):
    h = open(path, encoding="utf-8").read()
    body = re.sub(r'<script.*?</script>|<style.*?</style>', '', h, flags=re.S)
    name = os.path.basename(path)
    d = re.search(r'(\d{4})(\d{2})(\d{2})', name).groups()
    date = "-".join(d)
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
    files = glob.glob(os.path.join(BRIEFS, "*.html"))
    if not files:
        sys.exit("no briefs found")
    rows = [meta(f) for f in files]
    # newest first; weekly before daily on the same date
    rows.sort(key=lambda r: (r["date"], r["kind"] == "周报"), reverse=True)

    li = []
    for r in rows:
        li.append(
            '        <li>\n'
            f'          <h3 class="brief-title"><a href="briefs/{r["file"]}">{html.escape(r["title"])}</a></h3>\n'
            f'          <time class="brief-date" datetime="{r["date"]}">{r["date"]}<span class="kind">{r["kind"]}</span></time>\n'
            f'          <p class="brief-summary">{html.escape(r["summary"])}</p>\n'
            '        </li>'
        )
    block = '      <ul class="briefs">\n' + "\n".join(li) + '\n      </ul>'

    idx = os.path.join(REPO, "index.html")
    src = open(idx, encoding="utf-8").read()
    new = re.sub(r'      <ul class="briefs">.*?</ul>', block, src, flags=re.S)
    if new == src:
        sys.exit("marker <ul class=\"briefs\"> not found in index.html")
    open(idx, "w", encoding="utf-8").write(new)
    print(f"index.html updated with {len(rows)} briefs:")
    for r in rows:
        print(f"  {r['date']}  {r['kind']}  {r['title']}")

main()
