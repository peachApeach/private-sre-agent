import subprocess
from dataclasses import dataclass


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def run_command(
    command: list[str],
    timeout: int = 60,
    max_stdout_chars: int = 300_000,
    max_stderr_chars: int = 30_000,
) -> CommandResult:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout[:max_stdout_chars],
            stderr=result.stderr[:max_stderr_chars],
        )
    except subprocess.TimeoutExpired:
        cmd_str = " ".join(command)
        return CommandResult(
            returncode=1,
            stdout="",
            stderr=f"[timeout] 명령이 {timeout}초 내에 완료되지 않았습니다: {cmd_str}",
        )
    except FileNotFoundError:
        return CommandResult(
            returncode=1,
            stdout="",
            stderr=f"[not found] 명령을 찾을 수 없습니다: {command[0]}",
        )
