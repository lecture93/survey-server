"""PreToolUse 훅: .env 파일(.env, .env.local 등)을 고치지 못하게 막는다.

- Write/Edit/MultiEdit/NotebookEdit: 대상 파일 이름이 .env 계열이면 거부
- Bash/PowerShell: 명령에 .env 계열 파일과 쓰기·삭제 동작이 같이 있으면 거부
- .env.example, .env.sample, .env.template 은 예시 파일이라 허용

실수 방지용이다. 셸 명령은 패턴으로만 보므로 모든 우회를 막지는 못한다.
그래서 settings.json의 permissions.deny(Edit/Write .env*)도 함께 둔다.
"""
import json
import os
import re
import sys

ALLOWED_SUFFIXES = (".example", ".sample", ".template")


def is_env_file(path: str) -> bool:
    name = os.path.basename(path.replace("\\", "/")).lower()
    if name != ".env" and not name.startswith(".env."):
        return False
    return not name.endswith(ALLOWED_SUFFIXES)


PATH_TOKEN = re.compile(r"[^\s'\"<>|;&()]*\.env[\w.-]*", re.I)
WRITE_IN_CMD = re.compile(
    r">|\btee\b|\bsed\s+-i|\b(rm|mv|cp|truncate|del|ren|move|copy)\b"
    r"|Set-Content|Add-Content|Out-File|Clear-Content|Remove-Item|Move-Item|Copy-Item|Rename-Item"
    r"|WriteAllText|AppendAllText"
    r"|\bopen\s*\(|writeFile|appendFile|write_text|write_bytes"  # python -c / node -e 한 줄 스크립트
    r"|\bgit\s+(checkout|restore|reset|stash)\b",  # 추적 파일 되돌리기로 덮어쓰기
    re.I,
)
# 파일 이름 없이도 .env.local을 덮어쓰는 명령
OVERWRITES_ENV = re.compile(r"\bvercel\s+env\s+pull\b", re.I)


def deny(reason: str) -> None:
    out = json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False)
    sys.stdout.buffer.write(out.encode("utf-8"))  # Windows 콘솔 코드페이지와 무관하게 UTF-8로
    sys.exit(0)


def main() -> None:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if is_env_file(path):
            deny(f".env 파일은 수정할 수 없어요: {path} (protect_env 훅)")
    elif tool in ("Bash", "PowerShell"):
        cmd = tool_input.get("command", "")
        touches_env = any(is_env_file(t) for t in PATH_TOKEN.findall(cmd))
        if (touches_env and WRITE_IN_CMD.search(cmd)) or OVERWRITES_ENV.search(cmd):
            deny(".env 파일을 쓰거나 지우는 명령은 실행할 수 없어요 (protect_env 훅)")


if __name__ == "__main__":
    main()
