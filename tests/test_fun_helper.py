"""python3 -m unittest discover -s tests   （在仓库根目录运行，只用标准库）"""
import ast, json, sys, tempfile, unittest
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import build_index  # noqa: E402
import fun_helper as fh  # noqa: E402

DAY = date(2026, 11, 1)


def good_items():
    return [
        {"kind": "humor", "title": "马克·吐温：我的死讯被夸大了",
         "summary": "1897 年有报纸误传马克·吐温病危，记者上门求证，他回了一句流传至今的话：关于我死讯的报道言过其实。",
         "url": "https://example.org/twain", "source": "示例来源", "evidence": "greatly exaggerated"},
        {"kind": "trivia", "title": "章鱼有三颗心脏",
         "summary": "两颗心把血泵过鳃，一颗把血送往全身；游泳时主心脏会停跳，所以章鱼更爱爬行而不是游泳。",
         "url": "https://example.org/octopus", "source": "示例来源", "evidence": "three hearts"},
        {"kind": "today_cn", "title": "1957 年武汉长江大桥建成",
         "summary": "1957 年秋天，武汉长江大桥建成，这是长江上第一座公路铁路两用桥，从此“一桥飞架南北”。",
         "url": "https://example.org/bridge", "source": "示例来源", "evidence": "武汉长江大桥建成", "year": 1957},
        {"kind": "today_world", "title": "1512 年西斯廷礼拜堂天顶画首次公开",
         "summary": "1512 年 11 月 1 日，米开朗琪罗花了四年画成的西斯廷礼拜堂天顶画第一次向公众展出。",
         "url": "https://example.org/sistine", "source": "示例来源", "evidence": "Sistine Chapel ceiling", "year": 1512},
    ]


def issue(jokes=None, local_fun=None):
    return {"date": DAY.isoformat(), "sections": {"jokes": jokes if jokes is not None else good_items(),
                                                   "local_fun": local_fun or []}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, day, jokes=(), local_fun=()):
        (self.dir / f"{day:%Y%m%d}.json").write_text(json.dumps(
            {"date": day.isoformat(), "sections": {"jokes": list(jokes), "local_fun": list(local_fun)}},
            ensure_ascii=False), encoding="utf-8")

    def check(self, data, fetcher=None):
        return fh.check_issue(data, DAY, data_dir=self.dir, fetcher=fetcher)


class Rotation(unittest.TestCase):
    def test_neighbouring_days_differ_and_a_cycle_does_not_repeat(self):
        for key, pool in (("humor_form", fh.HUMOR_FORMS), ("humor_topic", fh.HUMOR_TOPICS),
                          ("trivia_domain", fh.TRIVIA_DOMAINS)):
            seen = [fh.rotation(DAY + timedelta(days=i))[key] for i in range(len(pool))]
            self.assertEqual(sorted(seen), sorted(pool), key)
            self.assertNotEqual(fh.rotation(DAY)[key], fh.rotation(DAY + timedelta(days=1))[key])
        self.assertFalse(set(fh.HUMOR_TOPICS) & set(fh.TRIVIA_DOMAINS), "humor and trivia never share a topic")


class Similarity(unittest.TestCase):
    def test_rewordings_of_the_october_reruns_score_high(self):
        a = "问：为什么程序员总分不清万圣节和圣诞节？答：因为 Oct 31 == Dec 25。"
        b = "为什么程序员总分不清万圣节和圣诞节？因为在他们眼里，Oct 31 = Dec 25。"
        self.assertGreaterEqual(fh.jaccard(a, b), fh.SIMILAR_SUMMARY)
        self.assertLess(fh.jaccard(a, "章鱼有三颗心脏，游泳时主心脏会停跳。"), 0.1)


class Check(Base):
    def test_a_good_issue_passes_offline(self):
        errors, warnings = self.check(issue())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_the_old_shape_and_the_overused_memes_are_refused(self):
        errors, _ = self.check(issue([{"title": "今日一则", "summary": "问：为什么程序员总分不清万圣节和圣诞节？答：因为 Oct 31 = Dec 25。", "fictional": True}]))
        text = "\n".join(errors)
        for needle in ("kind 必须是", "不许标 fictional", "缺 url", "缺 source", "evidence", "没有信息量", "过度使用的梗"):
            self.assertIn(needle, text)

    def test_forbidden_topics_and_kind_rules(self):
        items = good_items()
        items[3] = dict(items[3], summary="1512 年 11 月 1 日，一场地震之后……这里故意写进禁区的词，凑够字数凑够字数凑够字数。")
        items[2] = dict(items[2], year=None)
        items.append(dict(good_items()[1], title="另一条冷知识标题", summary="完全不同的内容，讲的是水母没有大脑却能游泳，凑够三十个字以上的长度。"))
        errors, _ = self.check(issue(items))
        text = "\n".join(errors)
        self.assertIn("禁区：灾难、疾病与死亡", text)
        self.assertIn("要写 year", text)
        self.assertIn("同一种 kind", text)

    def test_more_than_two_wikipedia_links_a_day_is_a_warning(self):
        items = [dict(it, url=f"https://zh.wikipedia.org/wiki/{i}") for i, it in enumerate(good_items())]
        errors, warnings = self.check(issue(items[:2] + good_items()[2:]))
        self.assertEqual((errors, warnings), ([], []))
        errors, warnings = self.check(issue(items[:3] + good_items()[3:]))
        self.assertEqual(errors, [])
        self.assertIn("3 条来自维基百科", warnings[0])

    def test_missing_kinds_are_a_warning_not_an_error(self):
        errors, warnings = self.check(issue(good_items()[:2]))
        self.assertEqual(errors, [])
        self.assertIn("历史上的今天 · 中国", warnings[0])

    def test_near_duplicates_of_the_last_60_days_and_reused_urls_are_refused(self):
        self.write(DAY - timedelta(days=10), [{"title": "今日一则", "summary": "章鱼有三颗心脏：两颗心把血泵过鳃，一颗把血送往全身，游泳时主心脏会停跳。", "fictional": True}])
        self.write(DAY - timedelta(days=200), [dict(good_items()[0], title="很久以前的一条", summary="毫不相干的另一段正文，长度足够长足够长足够长足够长。")])
        errors, _ = self.check(issue())
        text = "\n".join(errors)
        self.assertIn("太像", text)
        self.assertIn("url 以前用过", text)

    def test_older_than_60_days_is_not_compared_but_the_same_day_of_an_earlier_year_is(self):
        self.write(DAY - timedelta(days=90), [{"title": "今日一则", "summary": good_items()[1]["summary"], "fictional": True}])
        self.write(date(2025, 11, 1), [dict(good_items()[3], url="https://example.org/other")])
        errors, _ = self.check(issue())
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("20251101", errors[0])
        self.assertIn("today_world", errors[0])

    def test_links_must_open_and_carry_the_evidence_and_year(self):
        pages = {"https://example.org/twain": (200, "the report of my death was greatly exaggerated"),
                 "https://example.org/octopus": (404, ""),
                 "https://example.org/bridge": (200, "1957 年 武汉 大桥 建成"),
                 "https://example.org/sistine": (200, "The Sistine Chapel ceiling was first shown.")}

        def fetcher(url):
            return pages[url]
        errors, _ = self.check(issue(), fetcher)
        text = "\n".join(errors)
        self.assertNotIn("humor", text)
        self.assertIn("HTTP 404", text)
        self.assertIn("找不到 evidence", text)
        self.assertIn("找不到年份 1512", text)

    def test_local_fun_must_be_real_and_new(self):
        old = {"title": "西雅图网红浣熊Jimothy现身Ballard", "summary": "", "url": "https://example.org/jimothy"}
        self.write(DAY - timedelta(days=3), local_fun=[old])
        errors, _ = self.check(issue(local_fun=[
            {"title": "【虚构】温哥华一只浣熊连续三晚潜入咖啡馆", "summary": "", "fictional": True},
            {"title": "西雅图网红浣熊Jimothy再次现身Ballard", "summary": "", "url": "https://example.org/x"},
        ]))
        text = "\n".join(errors)
        self.assertIn("只登真实新闻", text)
        self.assertIn("缺原文 url", text)
        self.assertIn("已经报过", text)


class Pages(unittest.TestCase):
    def test_page_text_strips_markup_and_decodes_gbk(self):
        raw = '<html><head><meta charset="gbk"><script>var x="秘密"</script></head><body><p>长江&nbsp;大桥</p></body></html>'.encode("gbk")
        text = fh.page_text(raw)
        self.assertIn("长江", text)
        self.assertNotIn("秘密", text)
        self.assertIn(fh.norm("长江大桥"), fh.norm(text))


class Plan(Base):
    def test_plan_lists_rotation_memes_history_and_same_day(self):
        self.write(DAY - timedelta(days=1), [{"title": "今日一则", "summary": "旧笑话正文", "fictional": True}],
                   [{"title": "多伦多浣熊头卡排水篦子", "url": "https://example.org/r"}])
        self.write(date(2025, 11, 1), [dict(good_items()[2])])
        text = fh.plan_text(DAY, data_dir=self.dir)
        for needle in ("月日=11月1日", fh.rotation(DAY)["trivia_domain"], "Oct 31 = Dec 25", "旧笑话正文",
                       "1957 1957 年武汉长江大桥建成", "多伦多浣熊头卡排水篦子"):
            self.assertIn(needle, text)


class Gate(unittest.TestCase):
    def test_typed_items_need_a_link_and_legacy_jokes_stay_fictional(self):
        ok = {"sections": {"jokes": good_items() + [{"title": "旧笑话", "summary": "…", "fictional": True}]}}
        self.assertEqual(build_index.audit_json(ok)[0], [])
        bad = {"sections": {"jokes": [dict(good_items()[0], url=""), dict(good_items()[1], fictional=True),
                                      {"title": "旧笑话", "summary": "没标虚构"}]}}
        blocking = build_index.audit_json(bad)[0]
        self.assertEqual(len(blocking), 3)
        self.assertEqual(sum("轻松一刻" in b for b in blocking), 2)


class Python311(unittest.TestCase):
    def test_sources_parse_as_python_3_11(self):
        for name in ("fun_helper.py", "build_index.py"):
            ast.parse((REPO / name).read_text(encoding="utf-8"), feature_version=(3, 11))


if __name__ == "__main__":
    unittest.main()
