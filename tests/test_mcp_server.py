"""MCP 서버(mcp_server/server.py) 도구 테스트. 가짜 Supabase + 로컬 server.py를 띄워 실제 HTTP로 호출한다.

mcp 패키지(>=2)가 없으면 건너뛴다.
"""
import importlib.util
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_server  # noqa: E402  (클래스를 직접 import하면 그 테스트가 여기서 또 돈다)
SEED = test_server.SEED

HAS_MCP = importlib.util.find_spec("mcp") is not None


@unittest.skipUnless(HAS_MCP, "mcp 패키지 없음")
class McpToolsTest(unittest.TestCase):
    # 서버 띄우기·정리는 SurveyServerTest의 것을 그대로 빌려 쓴다(그 클래스의 테스트는 다시 돌리지 않음)
    seed = test_server.SurveyServerTest.seed
    setUp = test_server.SurveyServerTest.setUp

    @classmethod
    def setUpClass(cls):
        test_server.SurveyServerTest.setUpClass.__func__(cls)
        os.environ["SURVEY_API"] = f"http://127.0.0.1:{cls.port}"
        spec = importlib.util.spec_from_file_location(
            "survey_mcp", os.path.join(HERE, "..", "mcp_server", "server.py"))
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.m.OUT_DIR = cls.tmp.name

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SURVEY_API", None)
        test_server.SurveyServerTest.tearDownClass.__func__(cls)

    def test_list_and_vote(self):
        self.assertEqual(len(self.m.list_restaurants()), 7)
        self.assertEqual(self.m.submit_vote(["song", "nope"], "  mcp ", "좋아요"), {"id": 1})
        self.assertEqual(self.fake.rows[0]["picks"], ["song"])
        with self.assertRaisesRegex(RuntimeError, "400"):
            self.m.submit_vote([])

    def test_results_and_votes(self):
        self.seed()
        self.assertEqual(self.m.get_results()["voters"], 4)
        data = self.m.get_votes()
        self.assertEqual(data["total"], 4)
        self.assertEqual([v["id"] for v in data["votes"]], sorted(r["id"] for r in SEED))
        self.assertTrue(all(isinstance(v["picks"], list) for v in data["votes"]))
        self.assertEqual(self.m.get_votes(restaurant="송")["total"], 3)

    def test_render_html(self):
        self.fake.rows = [{"id": 1, "picks": ["song"], "nickname": "<b>x</b>", "comment": "<script>alert(1)</script>",
                           "created_at": "2026-11-05T00:00:00+00:00"}]
        out = self.m.render_html(title="점심 보고서", sections=["ranking", "comments", "votes"],
                                 theme="dark", accent="red;}", top_n=2, filename="../evil")
        self.assertEqual(os.path.dirname(out["path"]), self.tmp.name)
        page = open(out["path"], encoding="utf-8").read()
        self.assertIn("<title>점심 보고서</title>", page)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("--accent:#ff6b35", page)  # 잘못된 색은 기본값
        self.assertEqual(page.count("<li><span class=\"name\">"), 2)
        self.assertNotIn("참여 인원", page)  # summary 빠짐
        with self.assertRaises(ValueError):
            self.m.render_html(sections=["chart"])


if __name__ == "__main__":
    unittest.main()
