import typer

from sre_agent.commands.analyze import cmd_analyze
from sre_agent.commands.deploy import cmd_inspect_deploy
from sre_agent.commands.inspect import cmd_inspect
from sre_agent.commands.klogs import cmd_klogs

app = typer.Typer(help="Private SRE CLI agent")

_PROVIDER_HELP = (
    "LLM provider. ollama(기본) | openai | openai-compat | anthropic. "
    "전체 목록: sre-agent providers"
)
_MODEL_HELP = (
    "사용할 모델 이름. 생략 시 provider 기본 모델 사용. "
    "기본 모델 목록: sre-agent providers"
)


@app.command()
def providers() -> None:
    """사용 가능한 LLM provider 목록과 설정 방법을 표시합니다."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    table = Table(title="지원 LLM Provider", show_lines=True)
    table.add_column("--provider", style="bold cyan")
    table.add_column("기본 모델")
    table.add_column("필요한 환경변수")
    table.add_column("비고")

    table.add_row(
        "ollama",
        "qwen2.5:3b",
        "(없음)",
        "로컬 실행. http://localhost:11434",
    )
    table.add_row(
        "openai",
        "gpt-4o-mini",
        "OPENAI_API_KEY",
        "",
    )
    table.add_row(
        "anthropic",
        "claude-haiku-4-5-20251001",
        "ANTHROPIC_API_KEY",
        "",
    )
    table.add_row(
        "openai-compat",
        "(서버 의존)",
        "SRE_AGENT_BASE_URL",
        "vLLM, LM Studio 등 OpenAI 호환 서버",
    )

    console.print(table)
    console.print()
    console.print("[bold]설정 우선순위[/bold]")
    console.print("  CLI 플래그 > 환경변수 > ~/.sre-agent.yaml > 기본값\n")
    console.print("[bold]CLI 플래그 예시[/bold]")
    console.print("  sre-agent analyze app.log [cyan]--provider anthropic --model claude-sonnet-4-6[/cyan]")
    console.print("  sre-agent analyze app.log [cyan]--provider openai --model gpt-4o[/cyan]")
    console.print("  sre-agent analyze app.log [cyan]--provider ollama --model qwen2.5:7b[/cyan]\n")
    console.print("[bold]환경변수 예시[/bold]")
    console.print("  export [cyan]SRE_AGENT_PROVIDER[/cyan]=anthropic")
    console.print("  export [cyan]SRE_AGENT_MODEL[/cyan]=claude-sonnet-4-6")
    console.print("  export [cyan]ANTHROPIC_API_KEY[/cyan]=sk-ant-...\n")
    console.print("[bold]~/.sre-agent.yaml 예시[/bold]")
    console.print("  [cyan]provider: anthropic[/cyan]")
    console.print("  [cyan]model: claude-haiku-4-5-20251001[/cyan]")


@app.command()
def analyze(
    file: str | None = typer.Argument(None, help="분석할 로그 파일 경로. 생략하면 stdin에서 읽음."),
    no_llm: bool = typer.Option(False, "--no-llm", help="LLM 요약 없이 로컬 패턴 분석만 실행."),
    json_output: bool = typer.Option(False, "--json", help="결과를 JSON으로 출력."),
    provider: str | None = typer.Option(None, "--provider", help=_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help=_MODEL_HELP),
    debug_patterns: bool = typer.Option(False, "--debug-patterns", help="Raw log patterns 출력."),
) -> None:
    """로그 파일 또는 stdin을 분석합니다."""
    cmd_analyze(
        no_llm=no_llm,
        json_output=json_output,
        provider=provider,
        model=model,
        debug_patterns=debug_patterns,
        file=file,
    )


@app.command()
def klogs(
    pod: str = typer.Argument(..., help="Pod 이름."),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace."),
    since: str = typer.Option("30m", "--since", help="30m, 1h 형식의 로그 기간."),
    container: str | None = typer.Option(None, "--container", "-c", help="컨테이너 이름."),
    previous: bool = typer.Option(False, "--previous", help="이전 컨테이너 로그 조회."),
    no_llm: bool = typer.Option(False, "--no-llm", help="LLM 요약 없이 로컬 패턴 분석만 실행."),
    provider: str | None = typer.Option(None, "--provider", help=_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help=_MODEL_HELP),
    debug_patterns: bool = typer.Option(False, "--debug-patterns", help="Raw log patterns 출력."),
) -> None:
    """kubectl logs를 통해 Pod 로그를 수집하고 분석합니다."""
    cmd_klogs(
        pod=pod,
        namespace=namespace,
        since=since,
        container=container,
        previous=previous,
        no_llm=no_llm,
        provider=provider,
        model=model,
        debug_patterns=debug_patterns,
    )


@app.command()
def inspect(
    pod: str = typer.Argument(..., help="Pod 이름."),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace."),
    since: str = typer.Option("30m", "--since", help="30m, 1h 형식의 로그 기간."),
    container: str | None = typer.Option(None, "--container", "-c", help="컨테이너 이름."),
    no_llm: bool = typer.Option(False, "--no-llm", help="LLM 요약 없이 로컬 분석만 실행."),
    provider: str | None = typer.Option(None, "--provider", help=_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help=_MODEL_HELP),
    debug_patterns: bool = typer.Option(False, "--debug-patterns", help="Raw log patterns 출력."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="상세 Pod 상태, 이벤트, 로그 분석 출력."),
    json_output: bool = typer.Option(False, "--json", help="결과를 JSON으로 출력."),
) -> None:
    """Pod 상태, 이벤트, 현재/이전 로그를 종합 점검합니다."""
    cmd_inspect(
        pod=pod,
        namespace=namespace,
        since=since,
        container=container,
        no_llm=no_llm,
        provider=provider,
        model=model,
        debug_patterns=debug_patterns,
        verbose=verbose,
        json_output=json_output,
    )


@app.command("inspect-deploy")
def inspect_deploy(
    deployment: str = typer.Argument(..., help="Deployment 이름."),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace."),
    since: str = typer.Option("30m", "--since", help="30m, 1h 형식의 로그 기간."),
    no_llm: bool = typer.Option(False, "--no-llm", help="LLM 요약 없이 로컬 분석만 실행."),
    provider: str | None = typer.Option(None, "--provider", help=_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help=_MODEL_HELP),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="상세 분석 출력."),
    json_output: bool = typer.Option(False, "--json", help="결과를 JSON으로 출력."),
) -> None:
    """Deployment 단위로 관련 Pod 전체를 종합 점검합니다."""
    cmd_inspect_deploy(
        deployment=deployment,
        namespace=namespace,
        since=since,
        no_llm=no_llm,
        provider=provider,
        model=model,
        verbose=verbose,
        json_output=json_output,
    )


if __name__ == "__main__":
    app()
