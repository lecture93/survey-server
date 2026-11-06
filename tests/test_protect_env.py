"""protect_env 훅 단위 테스트 (이슈 #8). 훅은 실수 방지용이라 모든 우회를 막지는 못한다."""
import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks", "protect_env.py")


def run(tool, **tool_input):
    p = subprocess.run([sys.executable, HOOK], input=json.dumps({"tool_name": tool, "tool_input": tool_input}).encode(),
                       capture_output=True)
    out = p.stdout.decode("utf-8")
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"


class ProtectEnvTest(unittest.TestCase):
    def test_file_tools(self):
        self.assertEqual(run("Edit", file_path="/x/.env.local"), "deny")
        self.assertEqual(run("Write", file_path="C:\\x\\.env"), "deny")
        self.assertEqual(run("Write", file_path="/x/.env.example"), "allow")
        self.assertEqual(run("Edit", file_path="/x/server.py"), "allow")

    def test_shell_blocked(self):
        for cmd in [
            "echo >> .env",
            "rm .env.local",
            "Set-Content .env.local x",
            "python -c \"open('.env.local','w').write('')\"",
            "node -e \"require('fs').writeFileSync('.env.local','')\"",
            "git checkout -- .env.local",
            "git restore .env.local",
            "vercel env pull --yes",
            "vercel env pull .env.local",
        ]:
            self.assertEqual(run("Bash", command=cmd), "deny", cmd)

    def test_shell_allowed(self):
        for cmd in ["git status", "python -X utf8 server.py", "cat README.md", "cp .env.example sample.txt"]:
            self.assertEqual(run("Bash", command=cmd), "allow", cmd)


if __name__ == "__main__":
    unittest.main()
