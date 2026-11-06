"""삼성역 맛집 투표 MCP 서버.

설문 서버(server.py, 기본은 Vercel 배포본)의 공개 API를 그대로 감싼다. DB 키가 필요 없다.
- 설문: list_restaurants, submit_vote
- 데이터: get_results, get_votes
- 재구성: render_html — 받은 데이터를 옵션대로 골라 정적 HTML 파일로 만든다(대시보드가 아니라 한 장짜리 보고서)

API 주소는 환경변수 SURVEY_API로 바꿀 수 있다 (예: 로컬 http://127.0.0.1:8000).
"""
import csv
import html
import io
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime

from mcp.server.mcpserver import MCPServer

API = os.environ.get("SURVEY_API", "https://survey-server-drab.vercel.app").rstrip("/")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SECTIONS = ("summary", "ranking", "comments", "votes")

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


# ---------- HTML 재구성 ----------
def _e(v):
    return html.escape(str(v), quote=True)


def _color(value, default):
    return value if re.fullmatch(r"#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}", value or "") else default


def _build(title, subtitle, sections, theme, accent, top_n, restaurants, comment_limit, results, votes):
    ranking = results["ranking"]
    if restaurants:
        ranking = [r for r in ranking if r["name"] in restaurants or r["id"] in restaurants]
        names = {r["name"] for r in ranking}
        votes = [v for v in votes if names & set(v["picks"])]
    if top_n > 0:
        ranking = ranking[:top_n]
    dark = theme == "dark"
    bg, card, ink, muted, line = (("#14161a", "#1d2026", "#eef0f3", "#9aa1ab", "#2c3038") if dark
                                  else ("#f6f7f9", "#ffffff", "#1b1e23", "#69707a", "#e4e7eb"))
    parts = []
    if "summary" in sections:
        leader = results["ranking"][0]["name"] if results["voters"] and results["ranking"][0]["votes"] else "-"
        parts.append(
            '<section class="kpis">'
            f'<div class="kpi"><span>참여 인원</span><b>{results["voters"]}명</b></div>'
            f'<div class="kpi"><span>현재 1위</span><b>{_e(leader)}</b></div>'
            f'<div class="kpi"><span>총 표 수</span><b>{results["totalVotes"]}표</b></div></section>')
    if "ranking" in sections:
        top = max([r["votes"] for r in ranking] + [1])
        rows = "".join(
            f'<li><span class="name">{_e(r["name"])} <small>{_e(r["category"])}</small></span>'
            f'<span class="bar"><i style="width:{r["votes"] / top * 100:.1f}%"></i></span>'
            f'<span class="num">{r["votes"]}표 · {r["pct"]}%</span></li>' for r in ranking)
        parts.append(f'<section class="card"><h2>득표 순위</h2><ol class="rank">{rows}</ol></section>')
    if "comments" in sections:
        cms = [v for v in reversed(votes) if v["comment"]][:comment_limit]
        items = "".join(
            f'<li>{_e(v["comment"])}<small>{_e(v["nickname"])} · {_e(", ".join(v["picks"]))} · {_e(v["at"])}</small></li>'
            for v in cms) or '<li class="empty">한줄평이 없어요.</li>'
        parts.append(f'<section class="card"><h2>한줄평</h2><ul class="cm">{items}</ul></section>')
    if "votes" in sections:
        trs = "".join(
            f'<tr><td>{v["id"]}</td><td>{_e(v["at"])}</td><td>{_e(v["nickname"])}</td>'
            f'<td>{_e(", ".join(v["picks"]))}</td><td>{_e(v["comment"])}</td></tr>' for v in votes)
        parts.append('<section class="card"><h2>전체 투표</h2><div class="scroll"><table>'
                     '<tr><th>번호</th><th>시각</th><th>닉네임</th><th>선택한 가게</th><th>한줄평</th></tr>'
                     f'{trs}</table></div></section>')
    made = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title>
<style>
:root {{ --bg:{bg}; --card:{card}; --ink:{ink}; --muted:{muted}; --line:{line}; --accent:{accent}; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.6 system-ui,-apple-system,"Malgun Gothic",sans-serif; }}
.wrap {{ max-width:880px; margin:0 auto; padding:32px 16px 48px; }}
h1 {{ margin:0; font-size:26px; }} .sub {{ color:var(--muted); margin:4px 0 24px; }}
h2 {{ font-size:16px; margin:0 0 12px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:16px; }}
.kpi, .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; }}
.card {{ margin-bottom:16px; }}
.kpi span {{ display:block; color:var(--muted); font-size:13px; }} .kpi b {{ font-size:22px; }}
.rank {{ list-style:none; margin:0; padding:0; }}
.rank li {{ display:grid; grid-template-columns:minmax(120px,1.2fr) 2fr auto; gap:12px; align-items:center; padding:6px 0; }}
.rank small, .cm small {{ color:var(--muted); }}
.bar {{ height:10px; background:var(--line); border-radius:6px; overflow:hidden; }}
.bar i {{ display:block; height:100%; background:var(--accent); }}
.num {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
.cm {{ list-style:none; margin:0; padding:0; }} .cm li {{ padding:10px 0; border-top:1px solid var(--line); }}
.cm li:first-child {{ border-top:0; }} .cm small {{ display:block; font-size:12px; }} .empty {{ color:var(--muted); }}
.scroll {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th, td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ color:var(--muted); font-weight:600; }}
footer {{ color:var(--muted); font-size:12px; text-align:center; }}
@media (max-width:560px) {{ .rank li {{ grid-template-columns:1fr auto; }} .bar {{ grid-column:1 / -1; order:3; }} }}
</style></head>
<body><div class="wrap">
<h1>{_e(title)}</h1><p class="sub">{_e(subtitle)}</p>
{"".join(parts)}
<footer>데이터: {_e(API)} · 생성 {made}</footer>
</div></body></html>
"""


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
    bad = [s for s in sections if s not in SECTIONS]
    if bad or not sections:
        raise ValueError(f"sections는 {', '.join(SECTIONS)} 중에서 고르세요 (잘못된 값: {bad})")
    results = _json("GET", "/api/results")
    votes = _votes()
    page = _build(title, subtitle or f"투표 {results['voters']}명 기준",
                  [s for s in sections], "dark" if theme == "dark" else "light",
                  _color(accent, "#ff6b35"), top_n, restaurants, max(comment_limit, 0), results, votes)
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
