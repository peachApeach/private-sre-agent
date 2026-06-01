import subprocess
from dataclasses import dataclass


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(
    command: list[str],
    timeout: int = 60,
    max_stdout_chars: int = 300_000,
    max_stderr_chars: int = 30_000,
) -> CommandResult:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return CommandResult(
        command=command,
        returncode=result.returncode,
        stdout=result.stdout[:max_stdout_chars],
        stderr=result.stderr[:max_stderr_chars],
    )