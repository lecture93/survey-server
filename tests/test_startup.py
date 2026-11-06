"""서버 시작 시 설정이 없을 때의 안내 (이슈 #12 덧붙임)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.environ.get("SURVEY_SERVER") or os.path.join(HERE, "..", "server.py")


class MissingEnvTest(unittest.TestCase):
    def test_missing_supabase_settings_gives_clear_message(self):
        with tempfile.TemporaryDirectory() as d:  # 실제 설정 파일이 없는 빈 폴더에 복사해 실행
            shutil.copy(SERVER, os.path.join(d, "server.py"))
            env = {k: v for k, v in os.environ.items() if not k.startswith("SUPABASE_")}
            p = subprocess.run([sys.executable, "-X", "utf8", os.path.join(d, "server.py")],
                               env=env, capture_output=True, timeout=10)
        err = p.stderr.decode("utf-8", "replace")
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("Traceback", err)
        self.assertIn("SUPABASE_URL", err)
        self.assertIn("vercel env pull", err)


if __name__ == "__main__":
    unittest.main()
