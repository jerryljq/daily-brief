# feat/overview-markets: report

Brief: `kickoff-daily-brief/daily-brief-overview-markets.md`. Branch cut from `origin/main` at
`d0c9211`. `feat/fun-section` was not merged, so this branch is not based on it. Not merged; waiting
for the owner's review.

## What changed

| File | Change |
| --- | --- |
| `extras.py` (new) | `clean(data) -> (data, warnings)` for `overview`, `markets` and `special.summary`. Drops only the bad item and never blocks. Sanity ranges and limits are constants at the top, dated 2026-11-11. It also writes the warnings to `logs/extras-YYYYMMDD.txt` (gitignored) so `publish.py` can show them. |
| `render.py` | Calls `extras.clean` before rendering, prints `已清理: …` for each warning, and writes the cleaned JSON back to `data/YYYYMMDD.json` (not with `--dry-run`). The docstring documents the three fields: schema lines plus a section with the 10-row markets table and the rules. |
| `special_helper.py` | `save --summary "…"` stores `summary` in `data/special/<date>.json` and warns, without blocking, if it would be dropped. `apply` copies it into `special.summary`. |
| `merge_special.py` | `--special-summary "…"`. Runs `extras.clean` too, so a bad summary is dropped there as well. |
| `publish.py` | Cleaned items appear in the log, in the commit body and in the notification, never as blocking items. `--dry-run` now runs the audit read-only and says 「会发布」 or 「会被拦下」. Before, it stopped before the audit, and `--in-repo --dry-run` found no briefs because `git status` was skipped. `notify()` no longer crashes where `osascript` is missing. |
| `template.html` | Overview as one line under the masthead (「今日 …」). Markets in 经济·市场 as two compact tables (indices; FX, gold and the 10-year). Each row shows name (linked to `source`), value, change, and 「收盘 MM.DD」 or 「写稿时」. Up uses the section accent, down uses grey; no red or green. 「换算」 marks a derived CAD/CNY. 「仅为信息整理，不构成投资建议」 sits below the tables. Pages without the new fields are unchanged. |
| `tests/test_extras.py`, `tests/fixtures/` | 38 stdlib `unittest` tests. Fixtures: a complete issue, and the same issue with 3 bad market entries and a bad overview. |
| `docs/prompt-additions.md` | The complete new text for both routines, with when to paste each. |

### Decisions (minor, beyond the letter of the brief)

- **Fields that follow from the id are filled, not dropped.** A missing `group`, `name` or (for
  us10y) `unit` is filled in, and `null` values are removed. JerryStudio's schema requires `group`
  and `name`, and a missing value is an omission, not a mix-up. A *wrong* group or unit still drops
  the entry, as the brief says.
- **Wrong change field.** `change_bp` on an index, or `change_pct` on the 10-year, is removed
  with a warning. The entry is kept. A non-numeric change drops the entry, because the site would
  otherwise fail its build.
- **CAD/CNY cross-check** also runs on `derived` entries, to catch arithmetic mistakes. It only
  warns.
- **No valid issue `date`.** `as_of` cannot be checked, so the markets are dropped with a warning.
- **Duplicate id.** The first entry is kept, even if it later turns out invalid.
- The `as_of` window is the 7 days up to and including the issue date. After a holiday longer than
  7 days (for example Spring Festival in Shanghai), the stale index entry is dropped, which is the
  intended outcome.

## Acceptance (brief §6)

| Item | Result |
| --- | --- |
| `python3 -m unittest discover tests` passes on Python 3.11 | **Pass.** 38 tests on 3.11.18. Homebrew cannot install 3.11 on this macOS version, so I used a standalone CPython 3.11 from `uv` in a temporary folder; nothing was installed system-wide. All `.py` files also compile on 3.11. |
| Rendering an existing issue (`--dry-run`) produces the same page as before | **Pass.** Five issues (0915, 1030, 1108, 1110, 1111) rendered with `main` and with this branch: the embedded JSON is byte-identical, and full-page screenshots are pixel-identical at 1440 and 390 px, light and dark (20 out of 20). No console errors. |
| Fixture with all fields renders; cleaned JSON keeps all 10 entries | **Pass.** A real (non-dry) render keeps 10 entries in the data file and in the page, plus the overview and `special.summary`. There are no warnings and the data file is not rewritten. |
| Fixture with 3 bad entries and a bad overview keeps the rest and prints 4 warnings | **Pass.** 7 entries remain (spx, hsi and xau dropped), the overview is dropped, and exactly 4 `已清理:` lines are printed. The output is below. |
| `publish.py --dry-run` on that fixture would publish, not hold | **Pass**, in both modes (outputs glob and `--in-repo`): 「安全闸通过，会发布（清理提示 4 条，不影响发布）」. As a control, the same fixture with a joke lacking `fictional` reports 「会被安全闸拦下（1 处）」. |
| `docs/prompt-additions.md` contains the final prompt text for both tasks | **Pass.** |
| Branch pushed (not merged); short report | This file. |

Also checked: `merge_special.py --special-summary` with a good summary (stored, trimmed), a
61-character one (dropped, warned) and none (behaves as before). Every temporary file was removed
afterwards.

### Output

```
$ python3.11 -m unittest discover tests
......................................
----------------------------------------------------------------------
Ran 38 tests in 0.018s

OK

$ python3.11 render.py --data <copy of tests/fixtures/issue_bad.json> --out …/daily_brief_20260815.html
已清理: overview 已删（含链接）：华尔街继续抛售，详见 https://example.com…
已清理: 行情 spx 已删：value 741.26 超出合理区间 1000–30000
已清理: 行情 hsi 已删：as_of 2026-08-01 不在简报日期 2026-08-15 之前 7 天以内
已清理: 行情 xau 已删：source 缺失或不是 https:// 地址：http://www.cnbc.com/quotes/@GC.1
已渲染: …/daily_brief_20260815.html

$ DAILY_BRIEF_SOURCE_GLOB=…/bad/*brief*.html python3.11 publish.py --dry-run
发现 1 份新简报: daily_brief_20260815.html
  已清理 daily_brief_20260815.html: overview 已删（含链接）：…
  已清理 daily_brief_20260815.html: 行情 spx 已删：value 741.26 超出合理区间 1000–30000
  已清理 daily_brief_20260815.html: 行情 hsi 已删：as_of 2026-08-01 不在简报日期 2026-08-15 之前 7 天以内
  已清理 daily_brief_20260815.html: 行情 xau 已删：source 缺失或不是 https:// 地址：…
[dry-run] 安全闸通过，会发布（清理提示 4 条，不影响发布）
```

## Merge with feat/fun-section

**No conflicts, in either direction.** I did a trial merge in a throwaway worktree, both
this-branch-then-fun and fun-then-this-branch: git auto-merges `render.py` and `template.html`, and
`build_index.py` is untouched here. On the merged tree:

- all 53 tests pass on 3.11 (38 here plus 15 from `test_fun_helper.py`);
- the fixture page renders the 10-row table, the overview line and the 轻松一刻 header, with no
  script errors.

## For the owner

1. **Paste order.** Paste the Special section prompt after this branch is merged. Paste the Daily
   paper prompt only after this branch **and** `feat/fun-section` are both merged: it is built on
   `routines/daily-paper.md` from fun-section and runs `fun_helper.py`.
2. After both merges, the body of `routines/daily-paper.md` should be replaced with the new Daily
   paper text, so the versioned copy matches the routine. That file exists only on fun-section, so
   this branch leaves it alone to avoid a conflict.
