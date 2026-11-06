"""삼성역 맛집 투표 MCP 서버.

설문 서버(server.py, 기본은 Vercel 배포본)의 공개 API를 그대로 감싼다. DB 키가 필요 없다.
- 설문: list_restaurants, submit_vote
- 데이터: get_results, get_votes
- 재구성: render_html — 받은 데이터를 옵션대로 골라 정적 HTML 파일로 만든다(대시보드가 아니라 한 장짜리 보고서)

API 주소는 환경변수 SURVEY_API로 바꿀 수 있다 (예: 로컬 http://127.0.0.1:8000).
"""
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import report  # noqa: E402  (HTML 만드는 부분은 원격 MCP와 같이 씀)

API = os.environ.get("SURVEY_API", "https://survey-server-drab.vercel.app").rstrip("/")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

mcp = MCPServer("samsung-lunch-survey")


# ---------- HTTP ----------
def _request(method, path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _json(method, path, payload=None):
    status, body = _request(method, path, payload)
    try:
        data = json.loads(body.decode("utf-8")) if body else {}
    except ValueError:
        data = {}
    if status >= 400:
        raise RuntimeError(f"설문 서버 오류 {status}: {data.get('error') if isinstance(data, dict) else ''}".strip())
    return data


def _votes():
    status, body = _request("GET", "/api/export.csv")
    if status != 200:
        raise RuntimeError(f"설문 서버 오류 {status}")
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
    return [{"id": int(r[0]), "at": r[1], "nickname": r[2],
             "picks": [p for p in r[3].split(", ") if p], "comment": r[4]} for r in rows[1:] if r]


# ---------- 설문 ----------
@mcp.tool()
def list_restaurants() -> list[dict]:
    """투표할 수 있는 가게 목록 (id, name, category). submit_vote의 picks에는 id를 넣는다."""
    return _json("GET", "/api/restaurants")


@mcp.tool()
def submit_vote(picks: list[str], nickname: str = "", comment: str = "") -> dict:
    """투표를 실제 DB에 저장한다. 되돌릴 수 없으니 사용자가 요청했을 때만 호출한다.

    picks: 가게 id 목록(여러 개 가능, list_restaurants 참고). nickname ≤20자(비우면 익명), comment ≤200자.
    """
    return _json("POST", "/api/votes", {"picks": picks, "nickname": nickname, "comment": comment})


# ---------- 데이터 ----------
@mcp.tool()
def get_results() -> dict:
    """집계 결과: voters(투표자 수), totalVotes, ranking(득표순, pct는 투표자 대비 %), comments(최근 20개)."""
    return _json("GET", "/api/results")


@mcp.tool()
def get_votes(restaurant: str = "", keyword: str = "", limit: int = 200) -> dict:
    """원본 투표 목록(오래된 순). 각 표: id, at(KST), nickname, picks(가게 이름), comment.

    restaurant: 가게 이름(일부)으로 거르기. keyword: 닉네임·한줄평에서 찾기. limit: 최대 개수(최신 기준).
    """
    rows = _votes()
    if restaurant:
        rows = [r for r in rows if any(restaurant in p for p in r["picks"])]
    if keyword:
        rows = [r for r in rows if keyword in r["nickname"] or keyword in r["comment"]]
    total = len(rows)
    return {"total": total, "votes": rows[-limit:] if limit > 0 else rows}


@mcp.tool()
def render_html(
    title: str = "삼성역 맛집 투표 결과",
    subtitle: str = "",
    sections: list[str] = ["summary", "ranking", "comments"],
    theme: str = "light",
    accent: str = "#ff6b35",
    top_n: int = 0,
    restaurants: list[str] = [],
    comment_limit: int = 20,
    filename: str = "",
) -> dict:
    """최신 설문 데이터를 받아 원하는 모양의 정적 HTML 보고서 파일로 재구성한다.

    sections: 넣을 블록과 순서. summary(참여 인원·1위·총 표), ranking(득표 막대), comments(한줄평), votes(전체 투표 표).
    theme: light|dark. accent: 막대 색 #hex. top_n: 상위 N개 가게만(0=전부).
    restaurants: 이 가게들만(이름 또는 id). comment_limit: 한줄평 최대 개수.
    filename: 저장할 파일 이름(.html, 비우면 시각으로 자동). mcp/out/ 폴더에 저장하고 경로를 돌려준다.
    """
    results = _json("GET", "/api/results")
    page = report.render(results, _votes(), title, subtitle, sections, theme, accent, top_n,
                         restaurants, comment_limit, source=API)
    name = re.sub(r"[^\w.-]", "_", os.path.basename(filename)) if filename else datetime.now().strftime("report-%Y%m%d-%H%M%S")
    if not name.endswith(".html"):
        name += ".html"
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return {"path": path, "bytes": len(page.encode("utf-8")), "voters": results["voters"], "sections": sections}


if __name__ == "__main__":
    mcp.run()
