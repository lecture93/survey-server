"""리팩터링 안전망: server.py의 현재 동작을 HTTP 바깥에서 그대로 기록한 테스트.

- 실제 Supabase 대신 tests/fake_supabase.py를 띄우고, server.py는 별도 프로세스로 실행한다.
- 내부 구현(함수·변수 이름)에 기대지 않으므로 리팩터링 뒤에도 그대로 돌릴 수 있다.
- 다른 구현을 검사하려면 SURVEY_SERVER 환경변수에 server.py 경로를 넣는다.

실행 (survey-server 폴더에서):
    python -X utf8 -m unittest discover -s tests -v
"""
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from fake_supabase import FakeSupabase

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.abspath(os.environ.get("SURVEY_SERVER", os.path.join(HERE, "..", "server.py")))
PUBLIC = os.path.join(os.path.dirname(SERVER), "public")
KEY = "test-secret-key"

RESTAURANTS = [
    {"id": "hummus", "name": "허머스키친", "category": "중동 요리"},
    {"id": "chogye", "name": "미사리밀빛초계국수", "category": "냉면·초계국수"},
    {"id": "haejang", "name": "중앙해장", "category": "해장국"},
    {"id": "song", "name": "송", "category": "칼국수·수제비"},
    {"id": "steak", "name": "공대아르미", "category": "스테이크"},
    {"id": "baekse", "name": "백세주마을", "category": "한식 주점"},
    {"id": "kervan", "name": "케르반", "category": "터키 요리"},
]

# 결과·CSV 테스트에 쓰는 고정 데이터 (created_at은 Supabase처럼 UTC)
SEED = [
    {"id": 1, "picks": ["hummus", "song"], "nickname": "철수", "comment": "맛있어요",
     "created_at": "2026-11-05T05:30:00.123456+00:00"},
    {"id": 2, "picks": ["song"], "nickname": None, "comment": "",
     "created_at": "2026-11-05T15:10:00+00:00"},
    {"id": 3, "picks": ["song", "kervan", "unknown_x"], "nickname": "", "comment": "최고",
     "created_at": "2026-11-04T23:59:59+00:00"},
    {"id": 4, "picks": ["chogye"], "nickname": "영희", "comment": None,
     "created_at": "2026-11-05T00:00:00+00:00"},
]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class SurveyServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeSupabase()
        cls.fake.start()
        cls.port = free_port()
        cls.log = tempfile.TemporaryFile()
        env = dict(os.environ, SUPABASE_URL=cls.fake.url + "/", SUPABASE_SECRET_KEY=KEY,
                   PYTHONUTF8="1")
        cls.proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", os.path.join(HERE, "run_server.py"), SERVER, str(cls.port)],
            env=env, stdout=cls.log, stderr=cls.log)
        deadline = time.time() + 10
        while True:
            try:
                socket.create_connection(("127.0.0.1", cls.port), timeout=0.5).close()
                break
            except OSError:
                if cls.proc.poll() is not None or time.time() > deadline:
                    cls.log.seek(0)
                    output = cls.log.read().decode("utf-8", "replace")
                    cls.tearDownClass()
                    raise RuntimeError("서버가 뜨지 않았어요:\n" + output)
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.fake.stop()
        cls.log.close()

    def setUp(self):
        self.fake.reset()

    # ---------- 도우미 ----------
    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            res = conn.getresponse()
            return res.status, {k.lower(): v for k, v in res.getheaders()}, res.read()
        finally:
            conn.close()

    def get_json(self, path):
        status, headers, body = self.request("GET", path)
        return status, headers, json.loads(body.decode("utf-8"))

    def post_vote(self, payload):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        status, headers, body = self.request("POST", "/api/votes", raw,
                                             {"Content-Type": "application/json"})
        return status, headers, json.loads(body.decode("utf-8"))

    def seed(self, rows=SEED):
        self.fake.rows = [dict(r) for r in rows]

    def public(self, name):
        with open(os.path.join(PUBLIC, name), "rb") as f:
            return f.read()

    # ---------- 정적 파일 ----------
    def test_root_serves_index_html(self):
        for path in ("/", "/?from=qr"):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertTrue(headers["content-type"].startswith("text/html"))
            self.assertEqual(body, self.public("index.html"))

    def test_result_paths_serve_result_html(self):
        for path in ("/result", "/result/", "/result.html"):
            status, _, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertEqual(body, self.public("result.html"), path)

    def test_missing_file_is_404(self):
        for path in ("/nope.html", "/api/unknown"):
            status, _, _ = self.request("GET", path)
            self.assertEqual(status, 404, path)

    def raw(self, request_bytes):
        """http.client가 고쳐 보내지 않도록 원시 요청을 그대로 보내고 응답 전체를 받는다"""
        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as s:
            s.sendall(request_bytes)
            data = b""
            while chunk := s.recv(4096):
                data += chunk
        self.assertTrue(data.startswith(b"HTTP/1."), data[:50])
        return data

    def test_path_traversal_is_blocked(self):
        data = self.raw(b"GET /../server.py HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
        self.assertIn(b" 404 ", data.split(b"\r\n")[0])
        self.assertNotIn(b"SUPABASE", data)

    def test_sibling_folder_with_public_prefix_is_blocked(self):
        # public_xxx/처럼 이름이 public으로 시작하는 형제 폴더도 열리면 안 된다
        sibling = tempfile.mkdtemp(prefix="public_", dir=os.path.dirname(PUBLIC))
        try:
            with open(os.path.join(sibling, "secret.html"), "wb") as f:
                f.write(b"SECRET")
            name = os.path.basename(sibling).encode()
            data = self.raw(b"GET /../" + name + b"/secret.html HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
            self.assertIn(b" 404 ", data.split(b"\r\n")[0])
            self.assertNotIn(b"SECRET", data)
        finally:
            for f in os.listdir(sibling):
                os.remove(os.path.join(sibling, f))
            os.rmdir(sibling)

    # ---------- /api/restaurants ----------
    def test_restaurants_list(self):
        status, headers, data = self.get_json("/api/restaurants")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertEqual(data, RESTAURANTS)
        self.assertEqual(self.fake.requests, [], "가게 목록은 DB를 부르지 않아요")

    # ---------- POST /api/votes ----------
    def test_vote_is_saved_and_cleaned(self):
        status, headers, data = self.post_vote({
            "picks": ["song", "hummus", "song", "nope"],
            "nickname": "  " + "가" * 25 + " ",
            "comment": " " + "x" * 250,
        })
        self.assertEqual(status, 201)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(data, {"id": 1})

        self.assertEqual(len(self.fake.requests), 1)
        req = self.fake.requests[0]
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["path"], "/rest/v1/votes")
        self.assertEqual(req["headers"]["apikey"], KEY)
        self.assertEqual(req["headers"]["authorization"], "Bearer " + KEY)
        self.assertEqual(req["headers"]["prefer"], "return=representation")
        self.assertTrue(req["headers"]["content-type"].startswith("application/json"))
        self.assertEqual(req["body"], {"picks": ["song", "hummus"], "nickname": "가" * 20,
                                       "comment": "x" * 200})

    def test_vote_returns_new_id(self):
        self.seed()
        status, _, data = self.post_vote({"picks": ["kervan"]})
        self.assertEqual((status, data), (201, {"id": 5}))

    def test_vote_nickname_and_comment_default_to_empty(self):
        for payload in ({"picks": ["song"]}, {"picks": ["song"], "nickname": None, "comment": None}):
            self.fake.reset()
            status, _, _ = self.post_vote(payload)
            self.assertEqual(status, 201)
            self.assertEqual(self.fake.requests[0]["body"],
                             {"picks": ["song"], "nickname": "", "comment": ""})

    def test_vote_without_valid_picks_is_400(self):
        for payload in ({}, {"picks": []}, {"picks": ["nope", "HUMMUS"]}, b""):
            status, _, data = self.post_vote(payload)
            self.assertEqual(status, 400, payload)
            self.assertEqual(data, {"error": "가게를 한 곳 이상 골라 주세요"})
        self.assertEqual(self.fake.requests, [])

    def test_vote_bad_request_is_400(self):
        for payload in (b"{bad json", {"picks": 5}, {"picks": ["song"], "nickname": 5},
                        {"picks": ["song"], "comment": ["x"]},
                        # picks는 배열만: dict면 키가, 문자열이면 글자가 순회돼 엉뚱하게 저장되던 문제
                        {"picks": {"song": 1}}, {"picks": "song"}, b'["song"]', b'"song"'):
            status, _, data = self.post_vote(payload)
            self.assertEqual(status, 400, payload)
            self.assertEqual(data, {"error": "잘못된 요청이에요"})
        self.assertEqual(self.fake.requests, [])

    def test_vote_bad_content_length(self):
        # 숫자가 아니거나 음수면 400 (음수는 예전엔 연결이 닫힐 때까지 읽으며 멈췄다), 너무 크면 413
        for value, status in ((b"abc", b" 400 "), (b"-1", b" 400 "), (b"99999999", b" 413 ")):
            data = self.raw(b"POST /api/votes HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                            b"Content-Length: " + value + b"\r\n\r\n")
            head, _, body = data.partition(b"\r\n\r\n")
            self.assertIn(status, head.split(b"\r\n")[0], value)
            self.assertIn("error", json.loads(body.decode("utf-8")), value)
        self.assertEqual(self.fake.requests, [])

    def test_vote_db_failure_is_502(self):
        self.fake.fail = True
        status, _, data = self.post_vote({"picks": ["song"]})
        self.assertEqual(status, 502)
        self.assertEqual(data, {"error": "저장에 실패했어요. 잠시 후 다시 시도해 주세요"})

    def test_post_to_other_path_is_404(self):
        status, _, body = self.request("POST", "/api/other", b"{}")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body), {"error": "not found"})

    # ---------- GET /api/results ----------
    def test_results_empty(self):
        status, _, data = self.get_json("/api/results")
        self.assertEqual(status, 200)
        self.assertEqual(data, {
            "voters": 0, "totalVotes": 0, "comments": [],
            "ranking": [dict(r, votes=0, pct=0) for r in RESTAURANTS],
        })

    def test_results_with_votes(self):
        self.seed()
        status, headers, data = self.get_json("/api/results")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(headers["cache-control"], "no-store")

        req = self.fake.requests[0]
        self.assertEqual((req["method"], req["path"]), ("GET", "/rest/v1/votes?select=*&order=id.desc"))
        self.assertEqual(req["headers"]["apikey"], KEY)
        self.assertEqual(req["headers"]["authorization"], "Bearer " + KEY)

        self.assertEqual(data["voters"], 4)
        self.assertEqual(data["totalVotes"], 6, "목록에 없는 가게 id는 세지 않아요")
        # 득표순, 동점이면 원래 가게 순서 유지. 비율 분모는 투표자 수
        by = {r["id"]: r for r in RESTAURANTS}
        expected = [("song", 3, 75), ("hummus", 1, 25), ("chogye", 1, 25), ("kervan", 1, 25),
                    ("haejang", 0, 0), ("steak", 0, 0), ("baekse", 0, 0)]
        self.assertEqual(data["ranking"], [dict(by[i], votes=v, pct=p) for i, v, p in expected])
        # 한줄평: 최신 id 먼저, 빈 값·None 제외, 닉네임 없으면 익명, 시각은 KST
        self.assertEqual(data["comments"], [
            {"nickname": "익명", "text": "최고", "picks": ["송", "케르반", "unknown_x"],
             "at": "2026-11-05 08:59:59"},
            {"nickname": "철수", "text": "맛있어요", "picks": ["허머스키친", "송"],
             "at": "2026-11-05 14:30:00"},
        ])

    def test_results_pct_rounding(self):
        # 1/8 = 12.5% → 12 (파이썬 round, 짝수 쪽으로), 3/8 = 37.5% → 38
        rows = [{"id": i, "picks": ["song"] if i <= 3 else (["hummus"] if i == 4 else []),
                 "nickname": None, "comment": None, "created_at": "2026-11-05T00:00:00+00:00"}
                for i in range(1, 9)]
        self.seed(rows)
        _, _, data = self.get_json("/api/results")
        pct = {r["id"]: r["pct"] for r in data["ranking"]}
        self.assertEqual((pct["song"], pct["hummus"]), (38, 12))

    def test_results_keeps_latest_20_comments(self):
        rows = [{"id": i, "picks": ["song"], "nickname": f"n{i}", "comment": f"c{i}",
                 "created_at": "2026-11-05T00:00:00+00:00"} for i in range(1, 26)]
        self.seed(rows)
        _, _, data = self.get_json("/api/results")
        self.assertEqual([c["text"] for c in data["comments"]], [f"c{i}" for i in range(25, 5, -1)])

    def test_results_db_failure_is_500(self):
        # DB 조회 실패 시 JSON 본문이 있는 500 (프론트가 JSON 파싱에 실패하지 않게)
        self.fake.fail = True
        status, headers, body = self.request("GET", "/api/results")
        self.assertEqual(status, 500)
        self.assertTrue(headers["content-type"].startswith("application/json"))
        self.assertEqual(json.loads(body), {"error": "서버 오류가 발생했어요"})

    # ---------- GET /api/export.csv ----------
    def test_export_csv(self):
        self.seed()
        status, headers, body = self.request("GET", "/api/export.csv")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "text/csv; charset=utf-8")
        self.assertEqual(headers["content-disposition"], 'attachment; filename="samsung-votes.csv"')
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertTrue(body.startswith(b"\xef\xbb\xbf"), "엑셀용 BOM")
        self.assertEqual(body.decode("utf-8"), (
            "﻿번호,시각,닉네임,선택한 가게,한줄평\r\n"
            "1,2026-11-05 14:30:00,철수,\"허머스키친, 송\",맛있어요\r\n"
            "2,2026-11-06 00:10:00,익명,송,\r\n"
            "3,2026-11-05 08:59:59,익명,\"송, 케르반, unknown_x\",최고\r\n"
            "4,2026-11-05 09:00:00,영희,미사리밀빛초계국수,\r\n"
        ))

    def test_export_csv_escapes_formulas(self):
        # 엑셀이 수식으로 실행하지 않도록 =,+,-,@,탭,CR로 시작하는 셀 앞에 ' 를 붙인다
        self.seed([
            {"id": 1, "picks": ["song"], "nickname": "=1+1", "comment": '=HYPERLINK("http://x","클릭")',
             "created_at": "2026-11-05T00:00:00+00:00"},
            {"id": 2, "picks": ["@evil"], "nickname": "+a", "comment": "-b",
             "created_at": "2026-11-05T00:00:00+00:00"},
            {"id": 3, "picks": ["song"], "nickname": "a=b", "comment": "\tx",
             "created_at": "2026-11-05T00:00:00+00:00"},
        ])
        _, _, body = self.request("GET", "/api/export.csv")
        self.assertEqual(body.decode("utf-8"), (
            "﻿번호,시각,닉네임,선택한 가게,한줄평\r\n"
            "1,2026-11-05 09:00:00,'=1+1,송,\"'=HYPERLINK(\"\"http://x\"\",\"\"클릭\"\")\"\r\n"
            "2,2026-11-05 09:00:00,'+a,'@evil,'-b\r\n"
            "3,2026-11-05 09:00:00,a=b,송,'\tx\r\n"
        ))

    def test_export_csv_empty(self):
        _, _, body = self.request("GET", "/api/export.csv")
        self.assertEqual(body.decode("utf-8"), "﻿번호,시각,닉네임,선택한 가게,한줄평\r\n")

    def test_export_csv_with_query_string(self):
        status, _, _ = self.request("GET", "/api/export.csv?t=1")
        self.assertEqual(status, 200)

    # ---------- 흐름 ----------
    def test_vote_then_results(self):
        self.post_vote({"picks": ["steak", "baekse"], "nickname": "민수", "comment": "굿"})
        self.post_vote({"picks": ["steak"]})
        _, _, data = self.get_json("/api/results")
        self.assertEqual(data["voters"], 2)
        self.assertEqual(data["totalVotes"], 3)
        self.assertEqual([(r["id"], r["votes"], r["pct"]) for r in data["ranking"][:2]],
                         [("steak", 2, 100), ("baekse", 1, 50)])
        self.assertEqual([(c["nickname"], c["text"], c["picks"]) for c in data["comments"]],
                         [("민수", "굿", ["공대아르미", "백세주마을"])])


if __name__ == "__main__":
    unittest.main()
