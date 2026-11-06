# CLAUDE.md

```bash
python -X utf8 server.py                                   # http://localhost:8000/ (투표), /result (결과)
python -X utf8 -m unittest discover -s tests -v            # 전체 테스트
python -X utf8 -m unittest discover -s tests -k test_export_csv   # 하나만
```

AI 입력창 키: `vercel env add OPENROUTER_API_KEY production` 후 재배포, 로컬은 `.env.local`에 `OPENROUTER_API_KEY=...`

원격 MCP: https://survey-server-drab.vercel.app/mcp (`mcp_http.py`) · 로컬 MCP: `python mcp_server/server.py`

자세한 내용은 `tests/`, `api/`, `public/`, `supabase/`, `mcp_server/`의 CLAUDE.md에 있다.
