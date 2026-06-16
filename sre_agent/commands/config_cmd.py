from pathlib import Path

import typer
from rich.console import Console

_CONFIG_PATH = Path.home() / ".sre-agent.yaml"
_VALID_KEYS = {"provider", "model", "base_url"}
_VALID_PROVIDERS = {"ollama", "openai", "anthropic", "openai-compat"}

console = Console()


def cmd_config_show() -> None:
    if not _CONFIG_PATH.exists():
        console.print(f"[dim]설정 파일 없음: {_CONFIG_PATH}[/dim]")
        console.print("[dim]기본값(ollama / qwen2.5:3b)이 사용됩니다.[/dim]")
        return

    import yaml
    with _CONFIG_PATH.open() as f:
        cfg = yaml.safe_load(f) or {}

    console.print(f"[bold]{_CONFIG_PATH}[/bold]\n")
    if not cfg:
        console.print("[dim](비어 있음)[/dim]")
        return
    for k, v in cfg.items():
        console.print(f"  [cyan]{k}[/cyan] = {v}")


def cmd_config_set(key: str, value: str) -> None:
    if key not in _VALID_KEYS:
        console.print(f"[red]알 수 없는 키: {key}[/red]")
        console.print(f"사용 가능한 키: {', '.join(sorted(_VALID_KEYS))}")
        raise typer.Exit(code=1)

    try:
        import yaml
    except ImportError:
        console.print("[red]PyYAML이 설치되지 않았습니다. pip install pyyaml[/red]")
        raise typer.Exit(code=1)

    cfg: dict = {}
    if _CONFIG_PATH.exists():
        with _CONFIG_PATH.open() as f:
            cfg = yaml.safe_load(f) or {}

    cfg[key] = value
    with _CONFIG_PATH.open("w") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

    console.print(f"[green]저장됨[/green] {_CONFIG_PATH}")
    console.print(f"  [cyan]{key}[/cyan] = {value}")


def cmd_config_unset(key: str) -> None:
    if not _CONFIG_PATH.exists():
        console.print("[dim]설정 파일이 없습니다.[/dim]")
        return

    try:
        import yaml
    except ImportError:
        console.print("[red]PyYAML이 설치되지 않았습니다. pip install pyyaml[/red]")
        raise typer.Exit(code=1)

    with _CONFIG_PATH.open() as f:
        cfg = yaml.safe_load(f) or {}

    if key not in cfg:
        console.print(f"[dim]{key}는 설정되어 있지 않습니다.[/dim]")
        return

    del cfg[key]
    with _CONFIG_PATH.open("w") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

    console.print(f"[green]삭제됨[/green] {key}")
