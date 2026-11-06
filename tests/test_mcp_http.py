"""원격 MCP 엔드포인트(POST /mcp) 테스트. 가짜 Supabase + 로컬 server.py에 실제 HTTP로 JSON-RPC를 보낸다."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_server  # noqa: E402  (클래스를 직접 import하면 그 테스트가 여기서 또 돈다)


class RemoteMcpTest(unittest.TestCase):
    seed = test_server.SurveyServerTest.seed
    setUp = test_server.SurveyServerTest.setUp
    request = test_server.SurveyServerTest.request

    @classmethod
    def setUpClass(cls):
        test_server.SurveyServerTest.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        test_server.SurveyServerTest.tearDownClass.__func__(cls)

    def rpc(self, method, params=None, id_=1, path="/mcp"):
        msg = {"jsonrpc": "2.0", "method": method}
        if id_ is not None:
            msg["id"] = id_
        if params is not None:
            msg["params"] = params
        status, headers, body = self.request("POST", path, json.dumps(msg).encode("utf-8"),
                                             {"Content-Type": "application/json",
                                              "Accept": "application/json, text/event-stream"})
        return status, headers, json.loads(body) if body else None

    def call(self, name, args=None):
        status, _, data = self.rpc("tools/call", {"name": name, "arguments": args or {}})
        self.assertEqual(status, 200)
        return data["result"]

    def test_initialize_and_list(self):
        status, headers, data = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                         "clientInfo": {"name": "t", "version": "0"}})
        self.assertEqual(status, 200)
        self.assertTrue(headers["content-type"].startswith("application/json"))
        self.assertEqual(data["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(data["result"]["serverInfo"]["name"], "samsung-lunch-survey")
        status, _, data = self.rpc("notifications/initialized", id_=None)
        self.assertEqual((status, data), (202, None))
        _, _, data = self.rpc("tools/list", path="/api/mcp")
        self.assertEqual([t["name"] for t in data["result"]["tools"]],
                         ["list_restaurants", "submit_vote", "get_results", "get_votes", "render_html"])

    def test_tools(self):
        self.seed()
        self.assertEqual(len(json.loads(self.call("list_restaurants")["content"][0]["text"])), 7)
        res = self.call("get_results")
        self.assertEqual(res["structuredContent"]["voters"], 4)
        votes = self.call("get_votes", {"restaurant": "송"})["structuredContent"]
        self.assertEqual(votes["total"], 3)
        self.assertTrue(all("송" in v["picks"] for v in votes["votes"]))

    def test_submit_vote(self):
        res = self.call("submit_vote", {"picks": ["song", "nope"], "nickname": " mcp "})
        self.assertEqual(res["structuredContent"], {"id": 1})
        self.assertEqual(self.fake.rows[0]["picks"], ["song"])
        self.assertEqual(self.fake.rows[0]["nickname"], "mcp")
        res = self.call("submit_vote", {"picks": []})
        self.assertTrue(res["isError"])
        self.fake.fail = True
        self.assertTrue(self.call("submit_vote", {"picks": ["song"]})["isError"])

    def test_render_html(self):
        self.fake.rows = [{"id": 1, "picks": ["song"], "nickname": "<b>x</b>", "comment": "<script>alert(1)</script>",
                           "created_at": "2026-11-05T00:00:00+00:00"}]
        page = self.call("render_html", {"title": "보고서", "sections": ["ranking", "comments"], "theme": "dark",
                                         "top_n": 2})["content"][0]["text"]
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertNotIn("<script>alert", page)
        self.assertEqual(page.count('<li><span class="name">'), 2)
        self.assertTrue(self.call("render_html", {"sections": ["chart"]})["isError"])

    def test_errors(self):
        _, _, data = self.rpc("nope")
        self.assertEqual(data["error"]["code"], -32601)
        _, _, data = self.rpc("tools/call", {"name": "nope"})
        self.assertEqual(data["error"]["code"], -32602)
        status, _, body = self.request("POST", "/mcp", b"{bad", {"Content-Type": "application/json"})
        self.assertEqual((status, json.loads(body)["error"]["code"]), (400, -32700))
        status, headers, _ = self.request("GET", "/mcp")
        self.assertEqual((status, headers["allow"]), (405, "POST"))
        self.fake.fail = True
        self.assertTrue(self.call("get_results")["isError"])


if __name__ == "__main__":
    unittest.main()
