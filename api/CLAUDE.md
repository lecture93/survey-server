# api (Vercel)

- `vercel.json`이 `/api/*`를 `index.py`로 보내고, `index.py`는 `from server import Handler`로 로컬과 같은 핸들러를 쓴다. 그래서 `server.py`는 import 시 서버를 띄우면 안 된다(`if __name__ == "__main__"` 안에서만).
- API(모두 `server.py`): `GET /api/restaurants`, `POST /api/votes`(`{picks, nickname≤20자, comment≤200자}`, 목록에 없는 id는 버리고 남는 게 없으면 400, DB 실패 502), `GET /api/results`(투표자 수 기준 비율, 최근 한줄평 20개), `GET /api/export.csv`(BOM). 시각은 KST `YYYY-MM-DD HH:MM:SS`.
- `server.py` 흐름: `load_env` → `supabase`/`all_votes` → `results`/`export_csv`/`parse_vote`/`save_vote` → `Handler.route_get`/`route_post`/`static_file`. 라우트 예외는 `_respond`가 본문 없는 500으로 보낸다.
- 가게 목록은 `RESTAURANTS` 하나만 고친다. DB `picks`에 id가 저장되므로 id를 바꾸면 기존 표가 빠진다.
- `.backup-clean/`은 git·배포에서 빠진 예전 정리본 사본이다.
- AI 입력창(`ai.py`, OpenRouter, 표준 라이브러리): `POST /api/ai/vote {text}` → 모델이 자연어를 `{picks,nickname,comment}`로 바꾸고 `parse_vote` 규칙으로 정리해 바로 저장(201, 고를 가게가 없으면 400). `POST /api/ai/ask {question}` → `results()`와 최근 300표를 근거로 답변. 키 `OPENROUTER_API_KEY`가 없으면 503, OpenRouter 실패는 502. 모델은 `OPENROUTER_MODEL`(기본 `anthropic/claude-sonnet-5.5`). 테스트는 `tests/test_ai.py`(가짜 OpenRouter, `OPENROUTER_BASE_URL`).
- 왼쪽 챗봇(`public/chat.js`, 두 페이지 공통): `POST /api/ai/chat {messages:[{role,content}]}`(최근 12개, user 메시지 500자 이하, 마지막은 user) → 모델이 `action`을 고른다. `vote`면 `parse_vote` 규칙으로 정리해 저장하고 201 `{reply, vote:{id,picks,nickname,comment}}`, 고를 가게가 없거나 `answer`면 200 `{reply, vote:null}`. 데이터 근거는 `ask`와 같은 `_results_context`.
