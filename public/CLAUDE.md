# public

- `index.html`(투표), `result.html`(결과·CSV): 정적 페이지이고 `fetch`(async)로 `/api/*`를 호출한다. HTML 출력은 각 파일의 `esc()`로 이스케이프한다. `eval`·인라인 문자열 코드는 쓰지 않는다.
- 화면 쪽은 테스트가 없다.
