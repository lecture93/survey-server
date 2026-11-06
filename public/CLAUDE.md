# public

- `index.html`(투표), `result.html`(결과·CSV): 정적 페이지이고 동기 XHR로 `/api/*`를 호출한다.
- `chat.js`: 두 페이지가 같이 쓰는 왼쪽 AI 챗봇(폭 1000px 이상은 고정 사이드바, 그보다 좁으면 왼쪽 아래 버튼으로 여는 서랍). 대화는 sessionStorage에만 남는다.
- 화면 쪽은 테스트가 없다.
