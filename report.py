"""설문 데이터를 골라 한 장짜리 정적 HTML 보고서로 만든다 (표준 라이브러리만).

로컬 MCP(mcp_server/server.py)와 원격 MCP(mcp_http.py)가 함께 쓴다.
"""
import html
import re
from datetime import datetime

SECTIONS = ("summary", "ranking", "comments", "votes")
DEFAULT_ACCENT = "#ff6b35"


def _e(v):
    return html.escape(str(v), quote=True)


def _color(value, default):
    return value if re.fullmatch(r"#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}", value or "") else default


def build(title, subtitle, sections, theme, accent, top_n, restaurants, comment_limit, results, votes, source=""):
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
<footer>데이터: {_e(source)} · 생성 {made}</footer>
</div></body></html>
"""




def render(results, votes, title="삼성역 맛집 투표 결과", subtitle="", sections=("summary", "ranking", "comments"),
           theme="light", accent=DEFAULT_ACCENT, top_n=0, restaurants=(), comment_limit=20, source=""):
    """옵션을 검사하고 HTML 문자열을 돌려준다. sections가 틀리면 ValueError."""
    sections = list(sections)
    bad = [s for s in sections if s not in SECTIONS]
    if bad or not sections:
        raise ValueError(f"sections는 {', '.join(SECTIONS)} 중에서 고르세요 (잘못된 값: {bad})")
    return build(title, subtitle or f"투표 {results['voters']}명 기준", sections,
                 "dark" if theme == "dark" else "light", _color(accent, DEFAULT_ACCENT),
                 int(top_n or 0), list(restaurants or []), max(int(comment_limit), 0), results, votes, source)
