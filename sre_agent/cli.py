import typer

from sre_agent.commands.analyze import cmd_analyze
from sre_agent.commands.config_cmd import cmd_config_set, cmd_config_show, cmd_config_unset
from sre_agent.commands.deploy import cmd_inspect_deploy
from sre_agent.commands.inspect import cmd_inspect
from sre_agent.commands.klogs import cmd_klogs


def _print_help() -> None:
    from rich.console import Console
    from rich.table import Table

    c = Console()
    c.print("\n[bold]Private SRE Agent[/bold] — Kubernetes 로그 진단 CLI\n")
    c.print("Usage: sre-agent [bold cyan]COMMAND[/bold cyan] [OPTIONS] [ARGS]\n")

    t = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    t.add_column(style="bold cyan", min_width=14)
    t.add_column(style="dim", min_width=12)
    t.add_column()
    t.add_row("analyze",        "[FILE]",       "로그 파일 또는 stdin 분석")
    t.add_row("klogs",          "POD",          "kubectl logs 수집 후 분석")
    t.add_row("inspect",        "POD",          "Pod 상태·이벤트·로그 종합 점검")
    t.add_row("inspect-deploy", "DEPLOYMENT",   "Deployment 전체 Pod 종합 점검")
    t.add_row("providers",      "",             "LLM provider 목록 및 설정 방법")
    t.add_row("config",         "SUBCOMMAND",   "기본값 설정 (show / set / unset)")
    c.print(t)

    c.print("\n[bold]analyze[/bold] [FILE]")
    c.print("  [cyan]FILE[/cyan]                  로그 파일 경로. 생략 시 stdin")
    c.print("  [cyan]--provider TEXT[/cyan]       LLM: ollama(기본) | openai | anthropic | openai-compat")
    c.print("  [cyan]--model TEXT[/cyan]          모델 이름. 생략 시 provider 기본 모델")
    c.print("  [cyan]--no-llm[/cyan]              LLM 없이 rule 기반 패턴 분석만 실행")
    c.print("  [cyan]--json[/cyan]                결과를 JSON으로 출력")
    c.print("  [cyan]--debug-patterns[/cyan]      raw 패턴 그룹 출력 (rule 추가 참고용)")
    c.print("  [dim]예: sre-agent analyze app.log --provider anthropic --model claude-sonnet-4-6[/dim]")

    c.print("\n[bold]klogs[/bold] POD")
    c.print("  [cyan]POD[/cyan]                   분석할 Pod 이름 [required]")
    c.print("  [cyan]-n, --namespace TEXT[/cyan]  namespace (기본: default)")
    c.print("  [cyan]--since TEXT[/cyan]          로그 기간. 예: 30m, 1h (기본: 30m)")
    c.print("  [cyan]-c, --container TEXT[/cyan]  특정 컨테이너 지정")
    c.print("  [cyan]--previous[/cyan]            재시작 전 종료 컨테이너 로그 조회")
    c.print("  [cyan]--provider TEXT[/cyan]       LLM: ollama(기본) | openai | anthropic | openai-compat")
    c.print("  [cyan]--model TEXT[/cyan]          모델 이름. 생략 시 provider 기본 모델")
    c.print("  [cyan]--no-llm[/cyan]              LLM 없이 rule 기반 패턴 분석만 실행")
    c.print("  [cyan]--agent[/cyan]               에이전트 모드. LLM이 kubectl을 직접 호출해 자율 조사")
    c.print("  [dim]예: sre-agent klogs my-pod -n prod --since 1h --provider openai --model gpt-4o[/dim]")
    c.print("  [dim]예: sre-agent klogs my-pod --agent --provider anthropic[/dim]")

    c.print("\n[bold]inspect[/bold] POD")
    c.print("  [cyan]POD[/cyan]                   점검할 Pod 이름 [required]")
    c.print("  [cyan]-n, --namespace TEXT[/cyan]  namespace (기본: default)")
    c.print("  [cyan]--since TEXT[/cyan]          로그 기간. 예: 30m, 1h (기본: 30m)")
    c.print("  [cyan]-c, --container TEXT[/cyan]  특정 컨테이너 지정")
    c.print("  [cyan]-v, --verbose[/cyan]         Pod 상태 테이블·이벤트·전체 로그 상세 출력")
    c.print("  [cyan]--provider TEXT[/cyan]       LLM: ollama(기본) | openai | anthropic | openai-compat")
    c.print("  [cyan]--model TEXT[/cyan]          모델 이름. 생략 시 provider 기본 모델")
    c.print("  [cyan]--no-llm[/cyan]              LLM 없이 rule 기반 패턴 분석만 실행")
    c.print("  [cyan]--agent[/cyan]               에이전트 모드. LLM이 kubectl을 직접 호출해 자율 조사")
    c.print("  [cyan]--json[/cyan]                결과를 JSON으로 출력")
    c.print("  [dim]예: sre-agent inspect my-pod -n prod --provider anthropic --model claude-sonnet-4-6[/dim]")
    c.print("  [dim]예: sre-agent inspect my-pod --agent --provider anthropic[/dim]")

    c.print("\n[bold]inspect-deploy[/bold] DEPLOYMENT")
    c.print("  [cyan]DEPLOYMENT[/cyan]            점검할 Deployment 이름 [required]")
    c.print("  [cyan]-n, --namespace TEXT[/cyan]  namespace (기본: default)")
    c.print("  [cyan]--since TEXT[/cyan]          로그 기간. 예: 30m, 1h (기본: 30m)")
    c.print("  [cyan]-v, --verbose[/cyan]         전체 로그 패턴 분석 추가 출력")
    c.print("  [cyan]--provider TEXT[/cyan]       LLM: ollama(기본) | openai | anthropic | openai-compat")
    c.print("  [cyan]--model TEXT[/cyan]          모델 이름. 생략 시 provider 기본 모델")
    c.print("  [cyan]--no-llm[/cyan]              LLM 없이 rule 기반 패턴 분석만 실행")
    c.print("  [cyan]--agent[/cyan]               에이전트 모드. LLM이 kubectl을 직접 호출해 자율 조사")
    c.print("  [cyan]--json[/cyan]                결과를 JSON으로 출력")
    c.print("  [dim]예: sre-agent inspect-deploy my-service -n prod --provider ollama --model qwen2.5:7b[/dim]")
    c.print("  [dim]예: sre-agent inspect-deploy my-service --agent --provider anthropic[/dim]")

    c.print("\n[bold]config[/bold] SUBCOMMAND")
    c.print("  [cyan]show[/cyan]                  현재 설정 파일(~/.sre-agent.yaml) 내용 출력")
    c.print("  [cyan]set KEY VALUE[/cyan]         기본값 저장. KEY: provider | model | base_url")
    c.print("  [cyan]unset KEY[/cyan]             기본값 삭제")
    c.print("  [dim]예: sre-agent config set provider anthropic[/dim]")
    c.print("  [dim]예: sre-agent config set model claude-haiku-4-5-20251001[/dim]")
    c.print("  [dim]예: sre-agent config show[/dim]")

    c.print("\n[dim]provider별 환경변수 및 기본 모델 확인: sre-agent providers[/dim]\n")


app = typer.Typer(
    help="Private SRE CLI agent — Kubernetes 로그 진단 도구",
    rich_markup_mode="rich",
    add_help_option=False,
)


@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    help: bool = typer.Option(False, "--help", "-h", is_eager=True, expose_value=False,
                              callback=lambda v: (_print_help(), raise_exit()) if v else None),
) -> None:
    if ctx.invoked_subcommand is None:
        _print_help()
        raise typer.Exit()


def raise_exit():
    raise typer.Exit()


_PROVIDER_HELP = "LLM provider. ollama(기본) | openai | openai-compat | anthropic. 전체 목록: sre-agent providers"
_MODEL_HELP = "사용할 모델 이름. 생략 시 provider 기본 모델 사용. 기본 모델 목록: sre-agent providers"
_AGENT_HELP = "에이전트 모드. LLM이 kubectl tool을 직접 호출해 자율 조사. openai/anthropic/openai-compat만 지원."


@app.command()
def providers() -> None:
    """지원 LLM provider 목록과 설정 방법을 표시합니다."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    table = Table(title="지원 LLM Provider", show_lines=True)
    table.add_column("--provider", style="bold cyan")
    table.add_column("기본 모델")
    table.add_column("필요한 환경변수")
    table.add_column("비고")
    table.add_row("ollama",        "qwen2.5:3b",               "(없음)",             "로컬 실행. http://localhost:11434")
    table.add_row("openai",        "gpt-4o-mini",              "OPENAI_API_KEY",     "")
    table.add_row("anthropic",     "claude-haiku-4-5-20251001","ANTHROPIC_API_KEY",  "")
    table.add_row("openai-compat", "(서버 의존)",               "SRE_AGENT_BASE_URL", "vLLM, LM Studio 등 OpenAI 호환 서버")
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


config_app = typer.Typer(help="기본값 설정 (~/.sre-agent.yaml)")
app.add_typer(config_app, name="config")


@config_app.callback(invoke_without_command=True)
def _config_default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        cmd_config_show()


@config_app.command("show")
def config_show() -> None:
    """현재 설정을 출력합니다."""
    cmd_config_show()


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="설정 키. provider | model | base_url"),
    value: str = typer.Argument(..., help="설정 값"),
) -> None:
    """기본값을 ~/.sre-agent.yaml에 저장합니다.

    예: sre-agent config set provider anthropic
    예: sre-agent config set model claude-haiku-4-5-20251001
    """
    cmd_config_set(key, value)


@config_app.command("unset")
def config_unset(
    key: str = typer.Argument(..., help="삭제할 키. provider | model | base_url"),
) -> None:
    """~/.sre-agent.yaml에서 키를 삭제합니다."""
    cmd_config_unset(key)


@app.command()
def analyze(
    file: str | None = typer.Argument(None, help="분析할 로그 파일 경로. 생략하면 stdin으로 읽음."),
    no_llm: bool = typer.Option(False, "--no-llm", help="LLM 없이 rule 기반 패턴 분석만 실행."),
    json_output: bool = typer.Option(False, "--json", help="결과를 JSON으로 출력."),
    provider: str | None = typer.Option(None, "--provider", help=_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help=_MODEL_HELP),
    debug_patterns: bool = typer.Option(False, "--debug-patterns", help="정규화된 raw 로그 패턴 그룹 출력. rule 추가 시 참고용."),
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
    pod: str = typer.Argument(..., help="분析할 Pod 이름."),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace."),
    since: str = typer.Option("30m", "--since", help="조회할 로그 기간. 예: 30m, 1h."),
    container: str | None = typer.Option(None, "--container", "-c", help="특정 컨테이너 이름. 생략 시 첫 번째 컨테이너."),
    previous: bool = typer.Option(False, "--previous", help="재시작 전 종료 컨테이너 로그 조회."),
    no_llm: bool = typer.Option(False, "--no-llm", help="LLM 없이 rule 기반 패턴 분석만 실행."),
    provider: str | None = typer.Option(None, "--provider", help=_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help=_MODEL_HELP),
    debug_patterns: bool = typer.Option(False, "--debug-patterns", help="정규화된 raw 로그 패턴 그룹 출력."),
    agent: bool = typer.Option(False, "--agent", help=_AGENT_HELP),
) -> None:
    """kubectl logs로 Pod 로그를 수집하고 분석합니다."""
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
        agent_mode=agent,
    )


@app.command()
def inspect(
    pod: str = typer.Argument(..., help="점검할 Pod 이름."),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace."),
    since: str = typer.Option("30m", "--since", help="조회할 로그 기간. 예: 30m, 1h."),
    container: str | None = typer.Option(None, "--container", "-c", help="특정 컨테이너 이름. 생략 시 첫 번째 컨테이너."),
    no_llm: bool = typer.Option(False, "--no-llm", help="LLM 없이 rule 기반 패턴 분석만 실행."),
    provider: str | None = typer.Option(None, "--provider", help=_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help=_MODEL_HELP),
    debug_patterns: bool = typer.Option(False, "--debug-patterns", help="정규화된 raw 로그 패턴 그룹 출력."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Pod 상태 테이블, 이벤트, 전체 로그 분석 상세 출력."),
    json_output: bool = typer.Option(False, "--json", help="결과를 JSON으로 출력."),
    agent: bool = typer.Option(False, "--agent", help=_AGENT_HELP),
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
        agent_mode=agent,
    )


@app.command("inspect-deploy")
def inspect_deploy(
    deployment: str = typer.Argument(..., help="점검할 Deployment 이름."),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace."),
    since: str = typer.Option("30m", "--since", help="조회할 로그 기간. 예: 30m, 1h."),
    no_llm: bool = typer.Option(False, "--no-llm", help="LLM 없이 rule 기반 패턴 분석만 실행."),
    provider: str | None = typer.Option(None, "--provider", help=_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help=_MODEL_HELP),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="전체 로그 패턴 분석 추가 출력."),
    json_output: bool = typer.Option(False, "--json", help="결과를 JSON으로 출력."),
    agent: bool = typer.Option(False, "--agent", help=_AGENT_HELP),
) -> None:
    """Deployment에 속한 Pod 전체를 종합 점검합니다."""
    cmd_inspect_deploy(
        deployment=deployment,
        namespace=namespace,
        since=since,
        no_llm=no_llm,
        provider=provider,
        model=model,
        verbose=verbose,
        json_output=json_output,
        agent_mode=agent,
    )


if __name__ == "__main__":
    app()
