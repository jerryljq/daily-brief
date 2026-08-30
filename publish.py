#!/usr/bin/env python3
"""Collect new briefs from the Claude Desktop scheduled tasks and publish them.

Run by a LaunchAgent每天上午。流程：

  发现新简报 → 复制进 briefs/ → 移动端补丁 + 虚构标注
             → 安全闸 → 重建索引 → commit → push

安全闸拦下的东西不会上线：脚本仍然本地 commit（方便你 diff），但不 push，
并弹一条通知。原因见 build_index.audit —— 虚构栏目的标题每天写法都不一样，
标注规则可能漏掉新写法，那种情况下宁可停下。

两种模式：

    --in-repo   简报已经被写进 briefs/（云端 routine 用这个）。闸门拦下时
                推到 held/ 分支而不是丢在本地 —— 云端沙箱跑完就销毁，
                不推走就没了。
    （默认）    去本机 Claude 桌面版的 session outputs/ 里捞（本地定时任务用）

用法:
    python3 publish.py            # 从本机 session outputs 收
    python3 publish.py --in-repo  # 简报已在 briefs/ 里
    python3 publish.py --dry-run  # 只看会发生什么，不碰 git
"""
import glob, os, re, shutil, subprocess, sys, time

REPO   = os.path.dirname(os.path.abspath(__file__))
BRIEFS = os.path.join(REPO, "briefs")
# 定时任务把简报写进每次运行自己的 session 目录，目录名带随机 uuid，
# 所以只能靠通配去捞。DAILY_BRIEF_SOURCE_GLOB 仅供测试时改指向。
SOURCE = os.environ.get("DAILY_BRIEF_SOURCE_GLOB") or os.path.expanduser(
    "~/Library/Application Support/Claude/local-agent-mode-sessions"
    "/*/*/local_*/outputs/*brief*.html")

sys.path.insert(0, REPO)
import build_index

DRY     = "--dry-run" in sys.argv
IN_REPO = "--in-repo" in sys.argv


def log(msg=""):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{stamp}  {msg}" if msg else "", flush=True)


def notify(title, body):
    if DRY:
        return
    body = body.replace('"', "'")[:240]
    subprocess.run(["osascript", "-e",
                    f'display notification "{body}" with title "{title}"'],
                   capture_output=True)


def git(*args, check=True):
    if DRY:
        log(f"  [dry-run] git {' '.join(args)}")
        return ""
    r = subprocess.run(["git", "-C", REPO, *args],
                       capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)} 失败:\n{r.stderr.strip()}")
    return r.stdout.strip()


def collect_in_repo():
    """简报已经在 briefs/ 里，认 git 眼中的未跟踪文件。"""
    out = []
    for line in git("status", "--porcelain", "--", "briefs").splitlines():
        status, _, path = line.partition(" ")
        name = os.path.basename(path.strip())
        if line.startswith("??") and name.endswith(".html") and re.search(r"\d{8}", name):
            out.append(name)
    return sorted(out)


def collect():
    """把 outputs/ 里还没收录的简报复制进 briefs/，返回新增的文件名。"""
    have = {os.path.basename(p) for p in glob.glob(os.path.join(BRIEFS, "*.html"))}
    fresh = []
    for src in sorted(glob.glob(SOURCE)):
        name = os.path.basename(src)
        if name in have or not re.search(r"\d{8}", name):
            continue
        if not DRY:
            shutil.copy2(src, os.path.join(BRIEFS, name))
        have.add(name)
        fresh.append(name)
    return fresh


def main():
    log("=" * 58)
    fresh = collect_in_repo() if IN_REPO else collect()
    if not fresh:
        log("没有新简报，跳过")
        return 0
    log(f"发现 {len(fresh)} 份新简报: {', '.join(fresh)}")

    if DRY:
        log("[dry-run] 后续步骤需要文件已复制，到此为止")
        return 0

    # 补丁 + 标注 + 索引（对全部文件幂等，只有新文件会有改动）
    build_index.main()

    # 安全闸：只查新文件，老文件早已人工过过
    blocking, warnings = [], []
    for name in fresh:
        b, w = build_index.audit(os.path.join(BRIEFS, name))
        blocking += [(name, x) for x in b]
        warnings += [(name, x) for x in w]

    for name, x in warnings:
        log(f"  提示 {name}: {x[:110]}")

    git("add", "briefs", "index.html")
    if not git("status", "--porcelain", "--", "briefs", "index.html"):
        log("文件无变化，跳过提交")
        return 0

    subject = f"Add {', '.join(n.replace('.html', '') for n in fresh)}"
    if len(subject) > 68:
        subject = f"Add {len(fresh)} briefs ({fresh[0][:22]}…)"
    body = "\n".join(f"- {n}" for n in fresh)
    if blocking:
        body += ("\n\nNOT PUSHED — the fiction audit found passages that read as "
                 "reporting but carry neither a 虚构 label nor a source link:\n"
                 + "\n".join(f"- {n}: {x[:100]}" for n, x in blocking))
    git("commit", "-m", subject, "-m", body,
        "-m", "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>")

    if blocking:
        log(f"✗ 安全闸拦截 {len(blocking)} 处，未进 main：")
        for name, x in blocking:
            log(f"    {name}: {x[:110]}")
        if IN_REPO:
            # 云端沙箱跑完即销毁，本地提交等于丢失 —— 必须推到分支保住
            branch = "held/" + time.strftime("%Y%m%d-%H%M")
            git("branch", branch)
            git("push", "origin", f"{branch}:{branch}")
            log(f"  已推到分支 {branch}（未合入 main）")
            notify("每日简报 · 已暂停发布",
                   f"{len(blocking)} 处疑似虚构但无标注，见分支 {branch}")
        else:
            notify("每日简报 · 已暂停发布",
                   f"{len(blocking)} 处疑似虚构但无标注，已本地提交未推送")
        return 1

    log(f"✓ 安全闸通过（{len(warnings)} 条提示）")
    git("push", "origin", "main")
    log("✓ 已推送 https://jerryljq.github.io/daily-brief/")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"✗ 出错: {e}")
        notify("每日简报 · 发布失败", str(e))
        sys.exit(2)
