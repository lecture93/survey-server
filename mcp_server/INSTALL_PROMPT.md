아래 내용을 Claude Code에 그대로 붙여 넣으면 삼성역 맛집 투표 MCP 서버를 설치해요.

---

삼성역 맛집 투표 MCP 서버(`samsung-lunch-survey`)를 설치하고 이 프로젝트에 등록해 줘.

1) 준비
   - Python 3.10 이상인지 확인해. Windows는 `python`(또는 `py`), macOS·Linux는 `python3`를 써.
   - `python -m pip install "mcp>=2"`를 실행해. 다른 외부 패키지는 필요 없어.

2) 서버 파일 받기
   - 공개 저장소 https://github.com/lecture93/survey-server 의 `main` 브랜치에서 `mcp_server/server.py`만 받아 작업 폴더의 `survey-mcp/server.py`로 저장해.
     원본 주소: https://raw.githubusercontent.com/lecture93/survey-server/main/mcp_server/server.py
   - 저장한 뒤 파일을 열어 내용을 확인해. `urllib`로 설문 사이트 API만 부르고, 파일은 `survey-mcp/out/` 안에만 쓰는지 봐.
   - 폴더 이름을 `mcp`로 하지 마. `import mcp`가 그 폴더를 잡아서 서버가 안 떠.

3) 등록 (프로젝트 범위)
   - 작업 폴더에서 이렇게 등록해:
     `claude mcp add samsung-lunch-survey --scope project -- python survey-mcp/server.py`
     (macOS·Linux는 `python3`)
   - 그러면 `.mcp.json`에 다음이 생겨:
     ```json
     { "mcpServers": { "samsung-lunch-survey": { "command": "python", "args": ["survey-mcp/server.py"] } } }
     ```
   - 기본 대상은 배포본 `https://survey-server-drab.vercel.app`이야. 로컬 서버(`python -X utf8 server.py`, 포트 8000)로 시험하려면 등록할 때 `--env SURVEY_API=http://127.0.0.1:8000`을 붙여.

4) 확인
   - 세션을 다시 열고 `/mcp`에서 `samsung-lunch-survey`가 connected인지 봐. 처음엔 프로젝트 MCP 승인을 물어봐.
   - 도구 5개가 보여야 해: `list_restaurants`, `submit_vote`, `get_results`, `get_votes`, `render_html`.
   - 읽기만 하는 `get_results`를 한 번 불러 투표자 수가 나오는지 확인해.
   - `submit_vote`는 실제 DB에 저장되니 확인용으로 부르지 마.

5) 써 보기 (예시 요청)
   - "지금 투표 결과 1~3위만 알려 줘" → `get_results`
   - "한줄평에 '국물'이 들어간 표만 보여 줘" → `get_votes(keyword="국물")`
   - "다크 테마, 파란색 막대, 상위 3곳과 한줄평만 넣은 보고서 HTML 만들어 줘" →
     `render_html(sections=["summary","ranking","comments"], theme="dark", accent="#3a7bd5", top_n=3)`
     결과 파일은 `survey-mcp/out/`에 생기고, 경로를 알려 주면 브라우저로 열어 볼 수 있어.

`render_html` 옵션: `title`, `subtitle`, `sections`(summary·ranking·comments·votes 중 고르고 순서대로), `theme`(light|dark), `accent`(#hex), `top_n`(0=전부), `restaurants`(가게 이름 또는 id 목록), `comment_limit`, `filename`.
