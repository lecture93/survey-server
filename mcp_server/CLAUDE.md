# mcp_server

- 설문 서비스용 MCP 서버(`mcp>=2`, 표준 라이브러리 HTTP). 실행 `python mcp_server/server.py`, 기본 대상은 Vercel 배포본이고 `SURVEY_API=http://127.0.0.1:8000`으로 로컬 서버를 쓴다. DB 키를 쓰지 않고 공개 API만 부른다.
- 도구: `list_restaurants`, `submit_vote`(운영 DB에 실제 저장), `get_results`, `get_votes`(`/api/export.csv`를 파싱), `render_html`(sections·theme·accent·top_n·restaurants로 고른 정적 HTML을 `out/`에 저장).
- 폴더 이름을 `mcp`로 하면 `import mcp`가 이 폴더를 잡으니 바꾸지 않는다. `out/`은 git에서 뺀다.
- 테스트: `python -X utf8 -m unittest tests.test_mcp_server` (가짜 Supabase + 로컬 서버, `mcp` 패키지 없으면 건너뜀).
