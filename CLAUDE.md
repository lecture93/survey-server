# CLAUDE.md

Python 3.11 이상 권장(최소 3.9). Windows는 `python`/`py`, macOS·Linux는 `python3`로 바꿔 실행한다.

```bash
python -X utf8 server.py                                   # http://localhost:8000/ (투표), /result (결과)
python -X utf8 -m unittest discover -s tests -v            # 전체 테스트
python -X utf8 -m unittest discover -s tests -k test_export_csv   # 하나만
```

자세한 내용은 `tests/`, `api/`, `public/`, `supabase/`의 CLAUDE.md에 있다.
