삼성역 맛집 투표 MCP는 Vercel에 원격 MCP로 올라가 있어요. 코드를 받을 필요 없이 주소만 등록하면 돼요.

MCP 주소: https://survey-server-drab.vercel.app/mcp  (Streamable HTTP, 인증 없음)

아래 내용을 Claude Code에 그대로 붙여 넣으면 등록해요.

---

원격 MCP 서버 `samsung-lunch-survey`를 이 프로젝트에 등록해 줘. 코드는 받지 말고 주소만 등록해.

1) 등록
   - `claude mcp add --transport http samsung-lunch-survey https://survey-server-drab.vercel.app/mcp --scope project`
   - 그러면 `.mcp.json`에 다음이 생겨:
     ```json
     { "mcpServers": { "samsung-lunch-survey": { "type": "http", "url": "https://survey-server-drab.vercel.app/mcp" } } }
     ```
   - 나만 쓰려면 `--scope user`로 등록해.

2) 확인
   - 세션을 다시 열고 `/mcp`에서 `samsung-lunch-survey`가 connected인지 봐. 처음엔 프로젝트 MCP 승인을 물어봐.
   - 도구 5개가 보여야 해: `list_restaurants`, `submit_vote`, `get_results`, `get_votes`, `render_html`.
   - 읽기만 하는 `get_results`를 한 번 불러 투표자 수가 나오는지 확인해.
   - `submit_vote`는 실제 DB에 저장되니 확인용으로 부르지 마.

3) 써 보기 (예시 요청)
   - "지금 투표 결과 1~3위만 알려 줘" → `get_results`
   - "한줄평에 '국물'이 들어간 표만 보여 줘" → `get_votes(keyword="국물")`
   - "다크 테마, 파란색 막대, 상위 3곳과 한줄평만 넣은 보고서 HTML 만들어서 report.html로 저장해 줘" →
     `render_html(sections=["summary","ranking","comments"], theme="dark", accent="#3a7bd5", top_n=3)`
     원격 서버는 파일을 못 쓰니 HTML 문자열을 돌려줘. 받은 내용을 `report.html`로 저장하고 브라우저로 열어.

`render_html` 옵션: `title`, `subtitle`, `sections`(summary·ranking·comments·votes 중 고르고 순서대로), `theme`(light|dark), `accent`(#hex), `top_n`(0=전부), `restaurants`(가게 이름 또는 id 목록), `comment_limit`.

claude.ai(웹·데스크톱)에서는 설정 → 커넥터 → 사용자 지정 커넥터 추가에 같은 주소를 넣으면 돼요.

참고: 로컬에서 파일로 바로 저장까지 하는 버전이 필요하면 저장소의 `mcp_server/server.py`(stdio)를 `python mcp_server/server.py`로 등록해 쓸 수 있어요.
