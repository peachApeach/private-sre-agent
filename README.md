# Private SRE Agent

Kubernetes 운영 환경에서 로그, Pod 상태, Events, Deployment 상태를 읽기 전용으로 수집하고 장애를 진단하는 Private SRE CLI 도구입니다.

## 주요 기능

- 로그 파일 / stdin 분석
- `kubectl logs` 기반 Pod 로그 분석
- Pod 상태, Events, current/previous logs 종합 점검
- Deployment 기준 관련 Pod 전체 점검
- Rule 기반 known/unknown 장애 신호 분류
- **LLM 직접 분석** — 원본 로그를 LLM이 직접 보고 rule이 놓친 패턴까지 분석
- **에이전트 모드** (`--agent`) — LLM이 kubectl tool을 직접 호출해 스스로 조사 후 리포트
- **대화 모드** — 분석 후 자동 진입, 후속 질문 가능 (`quit`으로 종료)
- 민감정보 마스킹 (redaction)
- 한글 compact 리포트 출력
- JSON 출력 지원

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

확인:

```bash
sre-agent --help
```

## 지원 명령

```bash
sre-agent analyze          # 로그 파일 / stdin 분석
sre-agent klogs            # kubectl logs → 분석
sre-agent inspect          # Pod 종합 점검
sre-agent inspect-deploy   # Deployment 종합 점검
sre-agent providers        # LLM provider 목록 확인
sre-agent config           # 기본값 설정 (show / set / unset)
```

## 사용 예시

### 1. 로그 파일 분석

```bash
sre-agent analyze app.log
cat app.log | sre-agent analyze
```

LLM 없이 rule 분석만:

```bash
sre-agent analyze app.log --no-llm
```

### 2. Pod 로그 분석

```bash
sre-agent klogs <pod-name> -n <namespace> --since 30m
```

### 3. Pod 종합 점검

Pod 상태, Events, current/previous logs를 함께 수집해 진단합니다.

```bash
sre-agent inspect <pod-name> -n <namespace> --since 30m
```

상세 출력 (`--verbose`):

```bash
sre-agent inspect <pod-name> -n <namespace> --verbose
```

JSON 출력:

```bash
sre-agent inspect <pod-name> -n <namespace> --json | jq .
```

### 4. Deployment 종합 점검

Deployment에 속한 Pod 전체를 한 번에 점검합니다.

```bash
sre-agent inspect-deploy <deployment-name> -n <namespace> --since 30m
```

### 5. 에이전트 모드 (`--agent`)

LLM이 `kubectl` tool을 직접 호출해 스스로 조사하고 최종 리포트를 작성합니다.
기존 파이프라인(수집 → 분석 → LLM 요약)과 달리, LLM이 필요한 정보를 스스로 판단해 추가 조회합니다.

```bash
sre-agent inspect <pod-name> --agent
sre-agent inspect-deploy <deployment-name> --agent
sre-agent klogs <pod-name> --agent
```

흐름 예시:

```
sre-agent inspect my-pod --agent --provider anthropic
  → LLM: get_pod_status(my-pod) 호출
  → LLM: get_pod_logs(my-pod) 호출
  → LLM: get_events(default) 호출
  → LLM: "OOM 패턴 발견, DB pod도 확인" → get_pod_logs(db-pod) 호출
  → LLM: 최종 리포트 작성
  → 대화 모드 자동 진입
```

사용 가능한 kubectl tool:

| tool | 설명 |
|------|------|
| `get_pod_logs` | `kubectl logs` (current / previous 선택 가능) |
| `get_pod_status` | `kubectl get pod -o json` (phase, restartCount 등) |
| `get_events` | `kubectl get events` (BackOff, OOMKilled 등) |
| `get_deployment` | `kubectl get deploy -o json` (replicas, conditions 등) |

> **주의:** 에이전트 모드는 tool use를 지원하는 `openai` / `anthropic` / `openai-compat` provider에서만 동작합니다. `ollama`는 지원하지 않습니다.

## LLM 설정

### 동작 방식 (일반 모드)

```
로그 수집
  → rule engine 분석 (테이블 출력)
  → LLM 직접 분석 (redacted 원본 로그를 봄)
  → 대화 모드 자동 진입
     You: 이 에러 09시에 갑자기 늘었는데 배포 영향일까요?
     AI:  ...
     You: quit
```

LLM 없이 rule 분석만 원할 때는 `--no-llm`을 붙입니다.

### 지원 Provider

| Provider | 값 | 필요한 환경변수 | 에이전트 모드 |
|----------|----|----------------|:---:|
| Ollama (기본) | `ollama` | 없음 (로컬 실행) | ✗ |
| OpenAI | `openai` | `OPENAI_API_KEY` | ✓ |
| Anthropic (Claude) | `anthropic` | `ANTHROPIC_API_KEY` | ✓ |
| OpenAI 호환 (vLLM, LM Studio 등) | `openai-compat` | `SRE_AGENT_BASE_URL` | ✓ |

### 설정 방법

**우선순위: CLI 플래그 > 환경변수 > `~/.sre-agent.yaml` > 기본값**

#### config 명령으로 기본값 저장 (권장)

```bash
sre-agent config set provider anthropic
sre-agent config set model claude-haiku-4-5-20251001

# 설정 확인
sre-agent config show

# 키 삭제 (기본값으로 복귀)
sre-agent config unset model
```

저장 후에는 `--provider`/`--model` 없이 실행해도 설정값이 사용됩니다.

#### CLI 플래그 (일회성 override)

```bash
sre-agent inspect <pod> --provider anthropic --model claude-sonnet-4-6
sre-agent inspect <pod> --provider openai --model gpt-4o-mini
sre-agent inspect <pod> --provider ollama --model qwen2.5:7b
```

#### 환경변수

```bash
export SRE_AGENT_PROVIDER=anthropic
export SRE_AGENT_MODEL=claude-haiku-4-5-20251001
export ANTHROPIC_API_KEY=your-api-key

sre-agent inspect <pod>
```

#### 설정 파일 (`~/.sre-agent.yaml`) 직접 편집

```yaml
provider: anthropic
model: claude-haiku-4-5-20251001
# base_url: http://localhost:8000/v1  # openai-compat 사용 시
```

### Provider별 사용 예시

#### Ollama (로컬, 프라이빗)

```bash
ollama pull qwen2.5:7b
sre-agent inspect <pod> --provider ollama --model qwen2.5:7b
```

#### Anthropic (Claude)

```bash
export ANTHROPIC_API_KEY=your-api-key
sre-agent inspect <pod> --provider anthropic --model claude-haiku-4-5-20251001

# 에이전트 모드
sre-agent inspect <pod> --agent --provider anthropic
```

#### OpenAI

```bash
export OPENAI_API_KEY=your-api-key
sre-agent inspect <pod> --provider openai --model gpt-4o-mini

# 에이전트 모드
sre-agent inspect <pod> --agent --provider openai
```

#### vLLM / LM Studio (OpenAI 호환)

```bash
export SRE_AGENT_BASE_URL=http://localhost:8000/v1
sre-agent inspect <pod> --provider openai-compat --model your-model-name
```

## 보안 원칙

- read-only kubectl 명령만 사용 (`get`, `logs`, `events`) — 에이전트 모드에서도 동일
- `shell=True` 미사용, 모든 kubectl 명령은 `list[str]` 형식
- kubectl timeout / 명령 미존재 오류는 traceback 없이 안전하게 처리
- 로그는 LLM 전달 전에 반드시 redaction 수행

| 마스킹 대상 | 예시 | 치환값 |
|-------------|------|--------|
| 이메일 | `user@example.com` | `<email>` |
| Bearer token | `Bearer eyJ...` | `Bearer <token>` |
| JWT (단독) | `eyJhbGci...` | `<jwt>` |
| AWS access key | `AKIAIOSFODNN7EXAMPLE` | `<aws-key>` |
| AWS secret key | `aws_secret_access_key=...` | `<redacted>` |
| GCP API key | `AIza...` | `<gcp-key>` |
| 시크릿 파라미터 | `password=`, `secret=`, `api_key=`, `token=`, `auth=` | `<redacted>` |
| IPv4 주소 | `10.0.0.5` | `<ip>` |
| 전화번호 | `010-1234-5678` | `<phone>` |

- 장애 원인은 단정하지 않고 가능성으로 표현
- API key는 환경변수 또는 `~/.sre-agent.yaml`로 관리, 코드에 하드코딩 금지

## Known / Unknown 이슈 분류

Rule 기반으로 분류되는 known issue:

- DB connection pool timeout
- Redis connection failure
- Java OutOfMemoryError
- Kubernetes OOMKilled
- Kubernetes BackOff restarting container
- Kubernetes CrashLoopBackOff
- External payment gateway delay
- Downstream failure from payment-api
- Order queued due to payment delay

Rule에 없는 패턴은 `Unknown`으로 분류되며 샘플과 함께 표시됩니다. 새 rule은 `sre_agent/analyzers/advice.py`와 `sre_agent/analyzers/log_patterns.py`에 추가합니다.

## 테스트용 Kubernetes 리소스

`samples/` 디렉토리의 YAML을 사용합니다.

```bash
kubectl apply -f samples/error-pod.yaml
kubectl apply -f samples/deploy.yaml
```

점검:

```bash
sre-agent inspect error-log-pod -n default --no-llm
sre-agent inspect-deploy crash-loop-demo -n default --no-llm

# 에이전트 모드
sre-agent inspect error-log-pod --agent --provider anthropic
```

정리:

```bash
kubectl delete -f samples/error-pod.yaml
kubectl delete -f samples/deploy.yaml
```

## 프로젝트 구조

```
sre_agent/
├── cli.py                  # 진입점 (명령 선언만)
├── config.py               # AgentConfig, ~/.sre-agent.yaml 로더
├── commands/               # 명령별 로직
│   ├── analyze.py
│   ├── klogs.py
│   ├── inspect.py
│   ├── deploy.py
│   └── config_cmd.py
├── agent/                  # 에이전트 모드
│   ├── tools.py            # kubectl tool schema + 실행 함수
│   └── loop.py             # OpenAI / Anthropic tool-use 루프
├── render/
│   ├── rich_renderer.py    # Rich 렌더링 (테이블, 진단 요약)
│   └── llm_runner.py       # LLM 분석 실행 + 대화 루프
├── llm/
│   ├── prompts.py
│   └── providers/
│       ├── base.py         # LLMProvider 추상 클래스
│       ├── ollama.py
│       ├── openai_provider.py
│       ├── openai_compat.py
│       └── anthropic_provider.py
├── analyzers/
│   ├── advice.py           # Known issue rule 정의
│   ├── log_patterns.py     # 로그 패턴 분석
│   ├── pod_state.py
│   ├── events.py
│   └── deployment.py
├── collectors/
│   └── kubernetes.py       # kubectl 명령 실행
├── harness/
│   ├── command_runner.py
│   └── redactor.py
└── report/
    └── diagnosis.py
```

## 향후 작업

- Unknown pattern 기반 rule suggestion 추가
- 테스트 코드 추가
- Deployment rollout history 분석 추가
- Prometheus / Loki / OpenSearch 연동
- `inspect --json` 결과를 Slack bot / 웹 UI와 연동
- ~~deploy.py pod 로그 수집 병렬화~~ (완료)
