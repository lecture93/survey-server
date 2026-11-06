"""원격 MCP 엔드포인트 (POST /mcp, Streamable HTTP · 상태 없음 · JSON 응답).

Vercel 서버리스에서 돌아야 해서 mcp 패키지 없이 표준 라이브러리로 JSON-RPC만 처리한다.
세션·SSE 스트림은 쓰지 않는다(요청마다 독립). 도구는 server.py의 함수를 직접 부른다.
"""
import json

import report

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "samsung-lunch-survey", "version": "1.0.0"}

TOOLS = [
    {
        "name": "list_restaurants",
        "description": "투표할 수 있는 가게 목록 (id, name, category). submit_vote의 picks에는 id를 넣는다.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "submit_vote",
        "description": "투표를 실제 DB에 저장한다. 되돌릴 수 없으니 사용자가 요청했을 때만 호출한다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "picks": {"type": "array", "items": {"type": "string"}, "description": "가게 id 목록(여러 개 가능)"},
                "nickname": {"type": "string", "description": "20자까지, 비우면 익명"},
                "comment": {"type": "string", "description": "한줄평 200자까지"},
            },
            "required": ["picks"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "get_results",
        "description": "집계 결과: voters(투표자 수), totalVotes, ranking(득표순, pct는 투표자 대비 %), comments(최근 20개).",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_votes",
        "description": "원본 투표 목록(오래된 순). 각 표: id, at(KST), nickname, picks(가게 이름), comment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "restaurant": {"type": "string", "description": "가게 이름(일부)으로 거르기"},
                "keyword": {"type": "string", "description": "닉네임·한줄평에서 찾기"},
                "limit": {"type": "integer", "description": "최대 개수(최신 기준), 기본 200"},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "render_html",
        "description": "최신 설문 데이터를 원하는 모양의 한 장짜리 정적 HTML 보고서로 재구성해 HTML 문자열로 돌려준다. "
                       "받은 HTML을 .html 파일로 저장하면 브라우저로 열 수 있다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "sections": {"type": "array", "items": {"type": "string", "enum": list(report.SECTIONS)},
                             "description": "넣을 블록과 순서. 기본 summary, ranking, comments"},
                "theme": {"type": "string", "enum": ["light", "dark"]},
                "accent": {"type": "string", "description": "막대 색 #hex"},
                "top_n": {"type": "integer", "description": "상위 N개 가게만(0=전부)"},
                "restaurants": {"type": "array", "items": {"type": "string"}, "description": "이 가게들만(이름 또는 id)"},
                "comment_limit": {"type": "integer"},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
]


class ToolError(Exception):
    pass


def _votes(server):
    """server.all_votes()(최신순, picks는 id) → MCP용 목록(오래된 순, picks는 이름)."""
    return [{"id": r["id"], "at": r["created_at"], "nickname": server.display_name(r["nickname"]),
             "picks": server.pick_names(r["picks"]), "comment": r["comment"] or ""}
            for r in reversed(server.all_votes())]


def _call(server, name, args):
    if name == "list_restaurants":
        return server.RESTAURANTS
    if name == "get_results":
        return server.results()
    if name == "get_votes":
        rows = _votes(server)
        if args.get("restaurant"):
            rows = [r for r in rows if any(args["restaurant"] in p for p in r["picks"])]
        if args.get("keyword"):
            rows = [r for r in rows if args["keyword"] in r["nickname"] or args["keyword"] in r["comment"]]
        limit = int(args.get("limit", 200))
        return {"total": len(rows), "votes": rows[-limit:] if limit > 0 else rows}
    if name == "submit_vote":
        body = json.dumps({k: args[k] for k in ("picks", "nickname", "comment") if k in args}).encode("utf-8")
        try:
            picks, nickname, comment = server.parse_vote(body)
        except server.BadRequest:
            raise ToolError("잘못된 요청이에요")
        if not picks:
            raise ToolError("가게를 한 곳 이상 골라 주세요 (list_restaurants의 id)")
        try:
            return {"id": server.save_vote(picks, nickname, comment)}
        except Exception:
            raise ToolError("저장에 실패했어요. 잠시 후 다시 시도해 주세요")
    if name == "render_html":
        opts = {k: args[k] for k in ("title", "subtitle", "sections", "theme", "accent", "top_n",
                                     "restaurants", "comment_limit") if k in args}
        try:
            return report.render(server.results(), _votes(server), source="원격 MCP", **opts)
        except (ValueError, TypeError) as e:
            raise ToolError(str(e))
    raise KeyError(name)


def _result(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _handle_one(server, msg):
    """메시지 하나 처리. 알림(id 없음)이면 None."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    id_, method, params = msg.get("id"), msg["method"], msg.get("params") or {}
    if "id" not in msg:
        return None  # notifications/initialized 등
    if method == "initialize":
        asked = params.get("protocolVersion")
        return _result(id_, {
            "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": "삼성역 맛집 투표 설문. 결과 조회·원본 투표·HTML 보고서 재구성, 투표(submit_vote는 실제 저장).",
        })
    if method == "ping":
        return _result(id_, {})
    if method == "tools/list":
        return _result(id_, {"tools": TOOLS})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        try:
            data = _call(server, name, args)
        except KeyError:
            return _error(id_, -32602, f"알 수 없는 도구: {name}")
        except ToolError as e:
            return _result(id_, {"content": [{"type": "text", "text": str(e)}], "isError": True})
        except Exception:
            return _result(id_, {"content": [{"type": "text", "text": "서버 오류가 났어요"}], "isError": True})
        if name == "render_html":
            return _result(id_, {"content": [{"type": "text", "text": data}]})
        result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
        if isinstance(data, dict):
            result["structuredContent"] = data
        return _result(id_, result)
    return _error(id_, -32601, f"Method not found: {method}")


def handle(server, body):
    """POST /mcp 본문 → (status, 응답 bytes). 알림만 있으면 202 빈 본문."""
    try:
        msg = json.loads(body or b"")
    except ValueError:
        return 400, json.dumps(_error(None, -32700, "Parse error")).encode("utf-8")
    if isinstance(msg, list):
        out = [r for r in (_handle_one(server, m) for m in msg) if r is not None]
    else:
        out = _handle_one(server, msg)
    if not out:
        return 202, b""
    return 200, json.dumps(out, ensure_ascii=False).encode("utf-8")
