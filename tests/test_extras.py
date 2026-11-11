"""python3 -m unittest discover tests   （在仓库根目录运行，只用标准库，Python 3.11）"""
import copy, json, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import extras  # noqa: E402
import special_helper  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def full():
    return load("issue_full.json")


def entry(mid):
    return copy.deepcopy(next(e for e in full()["markets"] if e["id"] == mid))


def ids(data):
    return [e["id"] for e in data.get("markets", [])]


class Untouched(unittest.TestCase):
    def test_issue_without_new_fields_is_unchanged(self):
        # 现有的每一期都没有新字段：清理后必须一字不差，也没有提示
        for path in sorted((REPO / "data").glob("2026*.json"))[-5:]:
            raw = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(issue=path.name):
                out, warnings = extras.clean(raw)
                self.assertEqual(out, raw)
                self.assertEqual(warnings, [])

    def test_full_fixture_keeps_everything(self):
        raw = full()
        out, warnings = extras.clean(raw)
        self.assertEqual(warnings, [])
        self.assertEqual(out, raw)
        self.assertEqual(ids(out), extras.ORDER)

    def test_input_is_not_mutated(self):
        raw = load("issue_bad.json")
        before = copy.deepcopy(raw)
        extras.clean(raw)
        self.assertEqual(raw, before)

    def test_bad_fixture_keeps_the_rest_with_four_warnings(self):
        out, warnings = extras.clean(load("issue_bad.json"))
        self.assertEqual(len(warnings), 4, warnings)
        self.assertNotIn("overview", out)
        self.assertEqual(ids(out), [m for m in extras.ORDER if m not in ("spx", "hsi", "xau")])
        for mid in ("spx", "hsi", "xau"):
            self.assertTrue(any(f"行情 {mid} 已删" in w for w in warnings), mid)


class MarketDrops(unittest.TestCase):
    """每条删除规则：改坏一项，只删那一项，提示里点名。"""

    def assert_dropped(self, mid, mutate, *, expect_in_warning=None):
        data = full()
        e = next(x for x in data["markets"] if x["id"] == mid)
        mutate(e)
        out, warnings = extras.clean(data)
        self.assertNotIn(mid, ids(out))
        self.assertEqual(len(ids(out)), 9)
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn(f"行情 {mid} 已删", warnings[0])
        if expect_in_warning:
            self.assertIn(expect_in_warning, warnings[0])

    def test_unknown_id(self):
        data = full()
        data["markets"].append({**entry("spx"), "id": "ftse"})
        out, warnings = extras.clean(data)
        self.assertEqual(ids(out), extras.ORDER)
        self.assertEqual(len(warnings), 1)
        self.assertIn("未知的 id", warnings[0])

    def test_unhashable_or_missing_id(self):
        data = full()
        data["markets"] += [{**entry("spx"), "id": ["spx"]}, {"value": 1}, "spx"]
        out, warnings = extras.clean(data)
        self.assertEqual(ids(out), extras.ORDER)
        self.assertEqual(len(warnings), 3, warnings)

    def test_duplicate_id_keeps_the_first(self):
        data = full()
        dup = {**entry("spx"), "value": 7000.0}
        data["markets"].append(dup)
        out, warnings = extras.clean(data)
        self.assertEqual(ids(out), extras.ORDER)
        self.assertEqual(out["markets"][0]["value"], 7412.63)
        self.assertEqual(len(warnings), 1)
        self.assertIn("id 重复", warnings[0])

    def test_wrong_group(self):
        self.assert_dropped("hsi", lambda e: e.update(group="us"), expect_in_warning="group")

    def test_wrong_unit(self):
        self.assert_dropped("spx", lambda e: e.update(unit="%"), expect_in_warning="unit")
        self.assert_dropped("us10y", lambda e: e.update(unit=""), expect_in_warning="unit")

    def test_value_not_a_positive_number(self):
        for bad in (0, -5, "7412.6", True, None, float("nan"), float("inf")):
            with self.subTest(value=bad):
                self.assert_dropped("spx", lambda e: e.update(value=bad), expect_in_warning="value")
        self.assert_dropped("spx", lambda e: e.pop("value"), expect_in_warning="value")

    def test_value_outside_sanity_range(self):
        cases = {"spx": 741.26, "ixic": 250_000, "dji": 4821, "hsi": 2793, "sse": 40_217,
                 "usdcny": 71.2, "usdcad": 0.72, "cadcny": 0.19, "xau": 41, "us10y": 43.1}
        self.assertEqual(set(cases), set(extras.ORDER))
        for mid, bad in cases.items():
            with self.subTest(id=mid):
                self.assert_dropped(mid, lambda e: e.update(value=bad), expect_in_warning="合理区间")

    def test_range_bounds_are_inclusive(self):
        data = full()
        lo, hi = extras.RANGES["usdcad"]
        for v in (lo, hi):
            next(x for x in data["markets"] if x["id"] == "usdcad")["value"] = v
            out, warnings = extras.clean(data)
            self.assertIn("usdcad", ids(out))
            # 0.9 和 2 两端都合格；加元/人民币的交叉核对会提示，但不删
            self.assertTrue(all("usdcad 已删" not in w for w in warnings))

    def test_change_beyond_limits(self):
        self.assert_dropped("spx", lambda e: e.update(change_pct=15.01), expect_in_warning="±15")
        self.assert_dropped("spx", lambda e: e.update(change_pct=-20), expect_in_warning="±15")
        self.assert_dropped("us10y", lambda e: e.update(change_bp=101), expect_in_warning="±100")
        self.assert_dropped("us10y", lambda e: e.update(change_bp=-150), expect_in_warning="±100")
        data = full()
        data["markets"][0]["change_pct"] = -15
        self.assertEqual(extras.clean(data)[1], [])

    def test_change_not_a_number(self):
        self.assert_dropped("spx", lambda e: e.update(change_pct="-0.84%"), expect_in_warning="不是数字")

    def test_bad_session(self):
        for bad in ("open", "", None, "Close"):
            with self.subTest(session=bad):
                self.assert_dropped("dji", lambda e: e.update(session=bad), expect_in_warning="session")

    def test_as_of_not_a_date(self):
        for bad in ("2026-8-14", "20260814", "2026-02-30", "昨天", 20260814, None):
            with self.subTest(as_of=bad):
                self.assert_dropped("sse", lambda e: e.update(as_of=bad), expect_in_warning="as_of")

    def test_as_of_outside_the_week_before_the_issue(self):
        # 简报日期 2026-08-15：08-08 到 08-15（含）都行
        self.assert_dropped("sse", lambda e: e.update(as_of="2026-08-07"), expect_in_warning="7 天")
        self.assert_dropped("sse", lambda e: e.update(as_of="2026-08-16"), expect_in_warning="7 天")
        data = full()
        data["markets"][4]["as_of"] = "2026-08-08"
        self.assertEqual(extras.clean(data)[1], [])

    def test_issue_without_a_date_drops_everything(self):
        data = full()
        del data["date"]
        out, warnings = extras.clean(data)
        self.assertNotIn("markets", out)
        self.assertEqual(len(warnings), 11)      # 10 项各一条 + “一项都没留下”

    def test_source_missing_or_not_https(self):
        for bad in (None, "", "http://www.cnbc.com/quotes/.SPX", "www.cnbc.com", "https://", "https://a b"):
            with self.subTest(source=bad):
                self.assert_dropped("ixic", lambda e: e.update(source=bad), expect_in_warning="source")
        self.assert_dropped("ixic", lambda e: e.pop("source"), expect_in_warning="source")


class MarketShape(unittest.TestCase):
    def test_survivors_are_put_in_table_order(self):
        data = full()
        data["markets"].reverse()
        out, warnings = extras.clean(data)
        self.assertEqual(warnings, [])
        self.assertEqual(ids(out), extras.ORDER)

    def test_partial_list_keeps_order_without_gaps(self):
        data = full()
        data["markets"] = [entry("us10y"), entry("hsi"), entry("spx")]
        out, _ = extras.clean(data)
        self.assertEqual(ids(out), ["spx", "hsi", "us10y"])

    def test_nothing_survives_drops_the_field(self):
        data = full()
        for e in data["markets"]:
            e["source"] = "http://example.com"
        out, warnings = extras.clean(data)
        self.assertNotIn("markets", out)
        self.assertEqual(len(warnings), 11)
        self.assertIn("整个删掉", warnings[-1])

    def test_empty_or_non_list_markets(self):
        data = full()
        data["markets"] = []
        out, warnings = extras.clean(data)
        self.assertNotIn("markets", out)
        self.assertEqual(warnings, [])
        data["markets"] = {"spx": 1}
        out, warnings = extras.clean(data)
        self.assertNotIn("markets", out)
        self.assertEqual(len(warnings), 1)

    def test_missing_fields_that_follow_from_the_id_are_filled(self):
        data = full()
        data["markets"] = [entry("us10y"), entry("spx")]
        for e in data["markets"]:
            del e["group"], e["name"]
        data["markets"][0].pop("unit")
        data["markets"][1]["change_pct"] = None     # null 等于没写
        out, warnings = extras.clean(data)
        self.assertEqual(warnings, [])
        spx, us10y = out["markets"]
        self.assertEqual((spx["group"], spx["name"]), ("us", "标普 500"))
        self.assertNotIn("change_pct", spx)
        self.assertNotIn("unit", spx)
        self.assertEqual((us10y["group"], us10y["unit"], us10y["name"]),
                         ("commodities_rates_fx", "%", "美债 10 年"))

    def test_wrong_change_field_is_removed_but_the_entry_stays(self):
        data = full()
        data["markets"][0]["change_bp"] = 12         # spx 用 change_pct
        data["markets"][9]["change_pct"] = 0.9       # us10y 用 change_bp
        out, warnings = extras.clean(data)
        self.assertEqual(ids(out), extras.ORDER)
        self.assertNotIn("change_bp", out["markets"][0])
        self.assertNotIn("change_pct", out["markets"][9])
        self.assertEqual(out["markets"][9]["change_bp"], 4)
        self.assertEqual(len(warnings), 2, warnings)

    def test_cadcny_disagreement_warns_but_keeps(self):
        data = full()
        cad = next(e for e in data["markets"] if e["id"] == "cadcny")
        del cad["derived"]
        cad["value"] = 5.25                      # 7.1235 / 1.3862 = 5.1389，差 2.2%
        out, warnings = extras.clean(data)
        self.assertIn("cadcny", ids(out))
        self.assertEqual(len(warnings), 1)
        self.assertIn("相差", warnings[0])
        cad["value"] = 5.17                      # 差 0.6%，不提示
        self.assertEqual(extras.clean(data)[1], [])

    def test_cadcny_check_needs_both_usd_rates(self):
        data = full()
        data["markets"] = [e for e in data["markets"] if e["id"] != "usdcad"]
        next(e for e in data["markets"] if e["id"] == "cadcny")["value"] = 6.5
        self.assertEqual(extras.clean(data)[1], [])


class Overview(unittest.TestCase):
    def check(self, value):
        data = full()
        data["overview"] = value
        return extras.clean(data)

    def test_valid_is_stripped_and_kept(self):
        out, warnings = self.check("  " + full()["overview"] + "\n")
        self.assertEqual(out["overview"], full()["overview"])
        self.assertEqual(warnings, [])

    def test_length_bounds(self):
        for n in (15, 80):
            out, warnings = self.check("字" * n)
            self.assertEqual(warnings, [], n)
            self.assertEqual(len(out["overview"]), n)
        for n in (0, 14, 81):
            out, warnings = self.check("字" * n)
            self.assertNotIn("overview", out, n)
            self.assertEqual(len(warnings), 1)

    def test_drop_rules(self):
        base = "霍尔木兹海峡油轮触雷推高油价，华尔街因 AI 回报存疑继续抛售"
        for bad in (base + "\n美国期中选举进入最后四天。", base + "，见 https://x.cn",
                    base + "，见 HTTP://x.cn", "【虚构】" + base, 42, ["x"]):
            with self.subTest(overview=bad):
                out, warnings = self.check(bad)
                self.assertNotIn("overview", out)
                self.assertEqual(len(warnings), 1)
                self.assertIn("overview 已删", warnings[0])

    def test_null_is_removed_quietly(self):
        out, warnings = self.check(None)
        self.assertNotIn("overview", out)
        self.assertEqual(warnings, [])


class SpecialSummary(unittest.TestCase):
    def check(self, value):
        data = full()
        data["special"]["summary"] = value
        return extras.clean(data)

    def test_valid_is_stripped_and_kept(self):
        out, warnings = self.check(" 本期 4 笔大额融资 ")
        self.assertEqual(out["special"]["summary"], "本期 4 笔大额融资")
        self.assertEqual(warnings, [])
        out, warnings = self.check("字" * 60)
        self.assertEqual(warnings, [])

    def test_drop_rules(self):
        for bad in ("字" * 61, "详见 https://techcrunch.com", 3):
            with self.subTest(summary=bad):
                out, warnings = self.check(bad)
                self.assertNotIn("summary", out["special"])
                self.assertEqual(out["special"]["title"], "创投观察")
                self.assertEqual(len(warnings), 1)

    def test_empty_is_removed_quietly(self):
        for empty in ("", "   ", None):
            out, warnings = self.check(empty)
            self.assertNotIn("summary", out["special"])
            self.assertEqual(warnings, [])

    def test_special_without_summary_or_no_special(self):
        data = full()
        del data["special"]["summary"]
        self.assertEqual(extras.clean(data), (data, []))
        del data["special"]
        self.assertEqual(extras.clean(data), (data, []))


class WarningLog(unittest.TestCase):
    def test_save_load_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(extras, "LOG_DIR", Path(tmp) / "logs"):
            self.assertEqual(extras.load_warnings("20260815"), [])
            extras.save_warnings("20260815", ["a", "b"])
            self.assertEqual(extras.load_warnings("20260815"), ["a", "b"])
            extras.save_warnings("20260815", [])
            self.assertFalse(extras.log_path("20260815").exists())


class SpecialHelperSummary(unittest.TestCase):
    """special_helper.py save --summary 存进 data/special/，apply 再带进简报。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        day = special_helper.datetime(2026, 8, 15)
        patches = [mock.patch.object(special_helper, "OUT_DIR", self.dir / "special"),
                   mock.patch.object(special_helper, "kind_today", lambda: (day, "venture"))]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.frag = self.dir / "frag.html"
        self.frag.write_text("<p>正文</p>", encoding="utf-8")
        self.brief = self.dir / "brief.json"
        self.brief.write_text(json.dumps({"date": "2026-08-15", "sections": {}}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, summary):
        args = SimpleNamespace(html_file=str(self.frag), title=None, summary=summary)
        with mock.patch("sys.stdout"):
            special_helper.cmd_save(args)
        return json.loads((self.dir / "special" / "20260815.json").read_text(encoding="utf-8"))

    def apply(self):
        with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            special_helper.cmd_apply(SimpleNamespace(data=str(self.brief)))
        return json.loads(self.brief.read_text(encoding="utf-8"))["special"]

    def test_summary_round_trip(self):
        saved = self.save("  本期 4 笔大额融资，机器人和能源各占一半 ")
        self.assertEqual(saved["summary"], "本期 4 笔大额融资，机器人和能源各占一半")
        sp = self.apply()
        self.assertEqual(sp["status"], "ready")
        self.assertEqual(sp["summary"], "本期 4 笔大额融资，机器人和能源各占一半")

    def test_without_summary_behaves_as_before(self):
        saved = self.save(None)
        self.assertNotIn("summary", saved)
        sp = self.apply()
        self.assertEqual(set(sp), {"title", "html", "status"})


if __name__ == "__main__":
    unittest.main()
