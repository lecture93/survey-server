"""테스트용 가짜 Supabase(PostgREST) 서버.

실제 DB 대신 메모리의 rows 목록을 쓰고, 받은 요청을 requests에 기록한다.
fail=True로 두면 모든 요청에 500을 돌려준다.
GET은 실제 PostgREST처럼 limit/offset을 받고, 한 번에 max_rows(기본 1000)행까지만 준다.
"""
import json
import threading
from urllib.parse import parse_qs, urlsplit
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeSupabase:
    def __init__(self):
        self.rows = []
        self.requests = []
        self.fail = False
        self.max_rows = 1000
        self._lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _record(self, body):
                fake.requests.append({
                    "method": self.command,
                    "path": self.path,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": body,
                })

            def _send(self, status, payload):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._record(None)
                if fake.fail:
                    return self._send(500, {"message": "fake failure"})
                if self.path.split("?")[0] != "/rest/v1/votes":
                    return self._send(404, {"message": "no such table"})
                q = parse_qs(urlsplit(self.path).query)
                offset = int(q.get("offset", ["0"])[0])
                limit = min(int(q.get("limit", [fake.max_rows])[0]), fake.max_rows)
                with fake._lock:
                    rows = sorted(fake.rows, key=lambda r: -r["id"])
                self._send(200, rows[offset:offset + limit])

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"null")
                self._record(body)
                if fake.fail:
                    return self._send(500, {"message": "fake failure"})
                with fake._lock:
                    row = {
                        "id": max((r["id"] for r in fake.rows), default=0) + 1,
                        "picks": body["picks"],
                        "nickname": body.get("nickname"),
                        "comment": body.get("comment"),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    fake.rows.append(row)
                self._send(201, [row])

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def reset(self):
        with self._lock:
            self.rows = []
        self.requests = []
        self.fail = False
        self.max_rows = 1000
