"""삼성역 맛집 투표 서버 (Python 표준 라이브러리 + Supabase REST API)

실행:  python -X utf8 server.py
투표:  http://localhost:8000/
결과:  http://localhost:8000/result

DB 접속 정보는 .env.local의 SUPABASE_URL, SUPABASE_SECRET_KEY(없으면 SUPABASE_SERVICE_ROLE_KEY)를
읽는다(`vercel env pull`로 받은 파일). 테이블 정의: supabase/migrations/
Vercel에서는 api/index.py가 이 파일의 Handler를 그대로 쓴다.
"""
import csv
import io
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8000  # 이 노트북에서만 접속
BASE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(BASE, "public")
KST = timezone(timedelta(hours=9))

# 투표 후보. DB의 picks에는 id가 저장되므로 id를 바꾸면 기존 표가 집계에서 빠진다.
RESTAURANTS = [
    {"id": "hummus",  "name": "허머스키친",         "category": "중동 요리"},
    {"id": "chogye",  "name": "미사리밀빛초계국수", "category": "냉면·초계국수"},
    {"id": "haejang", "name": "중앙해장",           "category": "해장국"},
    {"id": "song",    "name": "송",                 "category": "칼국수·수제비"},
    {"id": "steak",   "name": "공대아르미",         "category": "스테이크"},
    {"id": "baekse",  "name": "백세주마을",         "category": "한식 주점"},
    {"id": "kervan",  "name": "케르반",             "category": "터키 요리"},
]
NAMES = {r["id"]: r["name"] for r in RESTAURANTS}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "text/javascript",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}
JSON_TYPE = "application/json; charset=utf-8"


# ---------- 설정 ----------
def _unquote(value):
    """앞뒤 따옴표를 한 겹씩 벗긴다: "값" 또는 '값'"""
    for q in ('"', "'"):
        if value.startswith(q):
            value = value[1:]
        if value.endswith(q):
            value = value[:-1]
    return value


def load_env(path=os.path.join(BASE, ".env.local")):
    """KEY=value 형식의 env 파일을 읽어 os.environ에 채운다 (이미 있는 값은 유지)"""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), _unquote(value.strip()))


load_env()
SUPABASE_URL = os.environ["SUPABASE_URL"].removesuffix("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY") or os.environ["SUPABASE_SERVICE_ROLE_KEY"]


# ---------- Supabase ----------
def supabase(method, path, payload=None, prefer=None):
    """Supabase PostgREST 호출 (/rest/v1/...)"""
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", method=method)
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type", "application/json")
    if prefer:
        req.add_header("Prefer", prefer)
    if payload is not None:
        req.data = json.dumps(payload).encode("utf-8")
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())


_FRACTION = re.compile(r"\.(\d+)")


def kst(ts):
    """'2026-11-05T05:31:29.12+00:00' → '2026-11-05 14:31:29'

    Postgres는 소수점 끝의 0을 잘라 1~6자리로 준다. Python 3.10 이하 fromisoformat은
    3·6자리와 'Z'를 못 읽어서, 6자리로 맞추고 'Z'를 +00:00으로 바꾼 뒤 파싱한다.
    """
    ts = _FRACTION.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), ts, count=1)
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")


def all_votes():
    """최신 표부터. created_at은 KST 문자열로 바꿔 돌려준다."""
    rows = supabase("GET", "votes?select=*&order=id.desc")
    for row in rows:
        row["created_at"] = kst(row["created_at"])
    return rows


def pick_names(picks):
    return [NAMES.get(p, p) for p in picks]


def display_name(nickname):
    return nickname or "익명"


# ---------- 기능 ----------
def results():
    rows = all_votes()
    counts = {r["id"]: 0 for r in RESTAURANTS}
    comments = []
    for row in rows:
        for p in row["picks"]:
            if p in counts:
                counts[p] += 1
        if row["comment"]:
            comments.append({
                "nickname": display_name(row["nickname"]),
                "text": row["comment"],
                "picks": pick_names(row["picks"]),
                "at": row["created_at"],
            })

    voters = len(rows)
    ranking = [
        {**r, "votes": counts[r["id"]],
         "pct": round(counts[r["id"]] / voters * 100) if voters else 0}
        for r in RESTAURANTS
    ]
    ranking.sort(key=lambda x: -x["votes"])  # 안정 정렬: 동점이면 원래 가게 순서
    return {
        "voters": voters,
        "totalVotes": sum(counts.values()),
        "ranking": ranking,
        "comments": comments[:20],
    }


def export_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["번호", "시각", "닉네임", "선택한 가게", "한줄평"])
    for row in reversed(all_votes()):  # 오래된 표부터
        w.writerow([row["id"], row["created_at"], display_name(row["nickname"]),
                    ", ".join(pick_names(row["picks"])), row["comment"] or ""])
    return "﻿" + buf.getvalue()  # BOM: 엑셀에서 한글 안 깨지게


class BadRequest(Exception):
    pass


def parse_vote(body):
    """요청 본문 → (picks, nickname, comment). 형식이 틀리면 BadRequest."""
    try:
        data = json.loads(body or b"{}")
        picks = []
        if "picks" in data:
            for p in data["picks"]:
                if p in NAMES and p not in picks:
                    picks.append(p)
        nickname = _text(data, "nickname", 20)
        comment = _text(data, "comment", 200)
    except Exception as e:
        raise BadRequest from e
    return picks, nickname, comment


def _text(data, key, limit):
    if key in data and data[key] is not None:
        return data[key].strip()[:limit]
    return ""


def save_vote(picks, nickname, comment):
    rows = supabase("POST", "votes", {"picks": picks, "nickname": nickname, "comment": comment},
                    prefer="return=representation")
    return rows[0]["id"]


# ---------- HTTP ----------
def json_body(payload):
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def static_file(path):
    """public/ 아래 파일 → (status, content_type, body). 폴더 밖은 404."""
    if path in ("/result", "/result/"):
        path = "/result.html"
    if path in ("/", ""):
        path = "/index.html"
    fp = os.path.normpath(PUBLIC + path)
    if not (fp.startswith(os.path.normpath(PUBLIC)) and os.path.isfile(fp)):
        return 404, "text/plain; charset=utf-8", b"404 Not Found"
    with open(fp, "rb") as f:
        body = f.read()
    ctype = CONTENT_TYPES.get(os.path.splitext(fp)[1], "application/octet-stream")
    return 200, ctype, body


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass  # 요청마다 로그를 찍지 않음

    def do_GET(self):
        self._respond(self.route_get)

    def do_POST(self):
        self._respond(self.route_post)

    def _respond(self, route):
        try:
            status, ctype, body, extra = route(self.path.split("?")[0])
        except Exception:
            status, ctype, body, extra = 500, None, b"", {}
        self.send_response(status)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if ctype:
            self.send_header("Cache-Control", "no-store")
        for k, v in extra.items():
            self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def route_get(self, path):
        if path == "/api/restaurants":
            return 200, JSON_TYPE, json_body(RESTAURANTS), {}
        if path == "/api/results":
            return 200, JSON_TYPE, json_body(results()), {}
        if path == "/api/export.csv":
            return 200, "text/csv; charset=utf-8", export_csv().encode("utf-8"), {
                "Content-Disposition": 'attachment; filename="samsung-votes.csv"'}
        return (*static_file(path), {})

    def route_post(self, path):
        if path != "/api/votes":
            return 404, JSON_TYPE, json_body({"error": "not found"}), {}
        length = int(self.headers.get("Content-Length") or 0)
        try:
            picks, nickname, comment = parse_vote(self.rfile.read(length))
        except BadRequest:
            return 400, JSON_TYPE, json_body({"error": "잘못된 요청이에요"}), {}
        if not picks:
            return 400, JSON_TYPE, json_body({"error": "가게를 한 곳 이상 골라 주세요"}), {}
        try:
            vote_id = save_vote(picks, nickname, comment)
        except Exception:
            return 502, JSON_TYPE, json_body({"error": "저장에 실패했어요. 잠시 후 다시 시도해 주세요"}), {}
        return 201, JSON_TYPE, json_body({"id": vote_id}), {}


if __name__ == "__main__":
    print(f"투표:  http://localhost:{PORT}/")
    print(f"결과:  http://localhost:{PORT}/result")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
