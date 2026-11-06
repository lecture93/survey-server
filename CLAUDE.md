# CLAUDE.md

```bash
python -X utf8 server.py                                   # http://localhost:8000/ (투표), /result (결과)
python -X utf8 -m unittest discover -s tests -v            # 전체 테스트
python -X utf8 -m unittest discover -s tests -k test_export_csv   # 하나만
```

MCP 서버: `python mcp_server/server.py`

자세한 내용은 `tests/`, `api/`, `public/`, `supabase/`, `mcp_server/`의 CLAUDE.md에 있다.
