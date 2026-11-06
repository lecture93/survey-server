# supabase

- 스키마는 `migrations/`. RLS만 켜고 정책이 없어 브라우저에서 직접 못 읽고 서버의 secret key로만 읽고 쓴다.
- 서버는 `.env.local`(`vercel env pull`)에서 `SUPABASE_URL`, `SUPABASE_SECRET_KEY`(없으면 `SUPABASE_SERVICE_ROLE_KEY`)를 읽고 없으면 시작 시 안내 문구를 내고 종료한다(종료 코드 1).
- 루트의 `survey.db`는 SQLite 시절 잔재로 쓰지 않는다.
