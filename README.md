# Private SRE Agent

Kubernetes 운영 환경에서 로그, Pod 상태, Events, Deployment 상태를 읽기 전용으로 수집하고 장애 신호를 요약하는 Private SRE CLI 도구입니다.

이 도구는 `kubectl logs`, `kubectl get pod`, `kubectl get deploy`, `kubectl get events` 같은 read-only 명령을 안전하게 감싸고, 수집된 로그를 기반으로 known issue / unknown issue를 분류합니다.

## 주요 기능

* stdin 로그 분석
* `kubectl logs` 기반 Pod 로그 분석
* Pod 상태, Events, current logs, previous logs 종합 점검
* Deployment 기준 관련 Pod 전체 점검
* Known issue rule 기반 장애 신호 분류
* Unknown issue pattern 표시
* 민감정보 마스킹
* 한글 compact 리포트 출력
* JSON 출력 지원
* 선택적 LLM provider 기반 요약 지원(Ollama, OpenAI API 등 확장 가능)

## 지원 명령

```bash
sre-agent analyze
sre-agent klogs
sre-agent inspect
sre-agent inspect-deploy
```

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install --upgrade pip
pip install -e .
```

설치 확인:

```bash
sre-agent --help
```

## 1. 로그 파일 또는 stdin 분석

```bash
cat samples/sample_payment_api_error.log | sre-agent analyze --no-llm
```

정상 로그만 있는 경우:

```bash
cat samples/normal.log | sre-agent analyze --no-llm
```

예상 출력:

```text
장애 신호가 발견되지 않았습니다.
현재 입력 로그에서는 ERROR/WARN/Exception/OOMKilled/CrashLoopBackOff 같은 분석 대상 신호가 발견되지 않았습니다.
```

## 2. Pod 로그 분석

`kubectl logs`를 직접 실행하지 않고 `sre-agent`가 read-only 방식으로 로그를 가져와 분석합니다.

```bash
sre-agent klogs <pod-name> -n <namespace> --since 30m --no-llm
```

예시:

```bash
sre-agent klogs error-log-pod -n default --since 30m --no-llm
```

## 3. Pod 종합 점검

Pod 상태, Events, current logs, previous logs를 함께 수집해 진단합니다.

```bash
sre-agent inspect <pod-name> -n <namespace> --since 30m --no-llm
```

예시:

```bash
sre-agent inspect crash-loop-pod -n default --since 30m --no-llm
```

예상 출력:

```text
Private SRE Agent

대상: pod/crash-loop-pod 네임스페이스=default
상태: Running | Ready=False | 재시작=7회 | 이전 로그=있음

진단 요약
- Pod가 7회 재시작되었습니다.
- Pod가 Ready 상태가 아닙니다.
- Kubernetes BackOff 이벤트가 감지되었습니다.
- 이전 컨테이너 로그를 함께 분석했습니다.
- Java OutOfMemoryError가 감지되었습니다.
- DB connection pool timeout이 감지되었습니다.

주요 신호
- [높음] Java OutOfMemoryError: 2건
- [높음] DB connection pool timeout: 2건
- [중간] Kubernetes BackOff event: 1건

다음 확인 액션
- 이전 컨테이너 로그와 종료 사유를 확인하세요.
- memory request/limit 및 JVM -Xmx/MaxRAMPercentage 설정을 확인하세요.
- HikariCP maximumPoolSize, connectionTimeout, leakDetectionThreshold 설정을 확인하세요.
- liveness/readiness/startup probe와 최근 rollout/config/secret 변경 여부를 확인하세요.
```

상세 출력:

```bash
sre-agent inspect crash-loop-pod -n default --since 30m --no-llm --verbose
```

JSON 출력:

```bash
sre-agent inspect crash-loop-pod -n default --since 30m --json | jq .
```

## 4. Deployment 종합 점검

Deployment selector를 기반으로 관련 Pod를 찾고, Pod 상태와 로그, Events를 종합해 Deployment 단위로 진단합니다.

```bash
sre-agent inspect-deploy <deployment-name> -n <namespace> --since 30m --no-llm
```

예시:

```bash
sre-agent inspect-deploy crash-loop-demo -n default --since 30m --no-llm
```

예상 출력:

```text
Deployment 점검 중: deploy=crash-loop-demo, namespace=default, since=30m
Private SRE Agent

대상: deploy/crash-loop-demo 네임스페이스=default
상태: replicas=2 | ready=0 | available=0 | updated=2

진단 요약
- desired replicas(2) 대비 ready pod(0)가 부족합니다.
- available replicas(0)가 desired replicas(2)보다 적습니다.
- Ready가 아닌 pod가 2개 있습니다.
- 관련 pod들의 총 재시작 횟수는 48회입니다.
- Java OutOfMemoryError가 감지되었습니다.
- DB connection pool timeout이 감지되었습니다.

Pod 요약
- crash-loop-demo-xxxxx | Ready=False | Restarts=24 | Reason=CrashLoopBackOff | 이전로그=있음
- crash-loop-demo-yyyyy | Ready=False | Restarts=24 | Reason=CrashLoopBackOff | 이전로그=있음

Kubernetes 이벤트
- [중간] Kubernetes BackOff event: 2건

주요 신호
- [높음] Java OutOfMemoryError: 4건
- [높음] DB connection pool timeout: 4건

다음 확인 액션
- 문제 pod를 대상으로 sre-agent inspect <pod>를 실행하세요.
- memory request/limit 및 JVM -Xmx/MaxRAMPercentage 설정을 확인하세요.
- HikariCP maximumPoolSize, connectionTimeout, leakDetectionThreshold 설정을 확인하세요.
- 최근 rollout/config/secret 변경 여부를 확인하세요.
```

JSON 출력:

```bash
sre-agent inspect-deploy crash-loop-demo -n default --since 30m --json | jq .
```

## Known issue / Unknown issue

Private SRE Agent는 known issue rule을 기반으로 자주 발생하는 장애 신호를 분류합니다.

현재 예시 rule:

* DB connection pool timeout
* Redis connection failure
* Java OutOfMemoryError
* Kubernetes OOMKilled
* Kubernetes BackOff restarting container
* Kubernetes CrashLoopBackOff
* External payment gateway delay
* Downstream failure from payment-api

룰에 등록되지 않은 패턴은 `Unknown`으로 분류합니다.

예시:

```text
Unknown auth-related error
sample: ERROR service=auth-api exception=JwtExpiredException message="JWT token expired"
```

Unknown 패턴은 추후 검토 후 `advice.py`에 rule로 추가할 수 있습니다.

## JSON 출력

`--json` 옵션은 다른 도구와 연동하기 위한 머신 리더블 출력입니다.

지원 명령:

```bash
sre-agent inspect <pod-name> --json
sre-agent inspect-deploy <deployment-name> --json
```

JSON 출력은 OpenLens extension, 웹 UI, Slack bot, Grafana 연동 등에 사용할 수 있습니다.

JSON 모드에서는 일반 안내 문구를 stdout에 출력하지 않고 순수 JSON만 출력해야 합니다.

## LLM 요약

Private SRE Agent는 기본적으로 rule 기반 deterministic 분석을 먼저 수행합니다.

LLM은 원본 로그를 직접 판단하는 역할이 아니라, 이미 마스킹되고 정리된 진단 결과를 사람이 읽기 쉬운 형태로 요약하는 보조 역할로 사용합니다.

기본적으로 LLM 없이 실행할 수 있습니다.

```bash
sre-agent inspect crash-loop-pod -n default --since 30m --no-llm
sre-agent inspect-deploy crash-loop-demo -n default --since 30m --no-llm
```

### 지원 가능한 LLM Provider

현재 기본 provider는 `ollama`입니다.

향후 아래와 같은 provider를 선택적으로 추가할 수 있습니다.

```text
ollama
openai
vllm
lm-studio
custom-http
```

권장 구조는 provider 인터페이스를 두고, CLI 옵션으로 사용할 모델 백엔드를 선택하는 방식입니다.

```bash
sre-agent inspect crash-loop-pod \
  -n default \
  --since 30m \
  --model-provider ollama \
  --model qwen2.5:3b
```

OpenAI API provider를 추가한 경우:

```bash
sre-agent inspect crash-loop-pod \
  -n default \
  --since 30m \
  --model-provider openai \
  --model gpt-4.1-mini
```

### Ollama 사용

로컬 환경에서 private하게 실행하려면 Ollama를 사용할 수 있습니다.

```bash
ollama pull qwen2.5:3b
```

실행:

```bash
sre-agent inspect crash-loop-pod \
  -n default \
  --since 30m \
  --model-provider ollama \
  --model qwen2.5:3b
```

### OpenAI API 사용

OpenAI API provider를 사용할 경우 API key를 환경변수로 설정합니다.

```bash
export OPENAI_API_KEY="your-api-key"
```

실행:

```bash
sre-agent inspect crash-loop-pod \
  -n default \
  --since 30m \
  --model-provider openai \
  --model gpt-4.1-mini
```

### 보안 원칙

운영 로그를 LLM에 직접 보내지 않는 것을 원칙으로 합니다.

Private SRE Agent의 권장 흐름은 다음과 같습니다.

```text
raw log
  -> redact
  -> known / unknown issue classification
  -> deterministic diagnosis
  -> LLM summary
```

즉, LLM에는 가능한 한 원본 로그 전체가 아니라 아래와 같은 정리된 데이터만 전달합니다.

```text
- 장애 신호 카테고리
- 건수
- severity
- known / unknown 여부
- 마스킹된 샘플
- 추천 확인 액션
```

외부 API provider를 사용할 경우 다음을 지켜야 합니다.

```text
- API key를 코드에 하드코딩하지 않는다.
- 환경변수 또는 secret manager를 사용한다.
- 원본 로그 대신 redacted diagnosis JSON을 전송한다.
- 민감정보 마스킹을 우회하지 않는다.
- LLM 응답은 참고 정보로만 사용하고 원인을 단정하지 않는다.
```

### 권장 사용 방식

운영 환경에서는 먼저 LLM 없이 deterministic 분석을 확인합니다.

```bash
sre-agent inspect-deploy my-service -n prod --since 30m --no-llm
```

필요할 때만 LLM 요약을 추가합니다.

```bash
sre-agent inspect-deploy my-service \
  -n prod \
  --since 30m \
  --model-provider ollama \
  --model qwen2.5:7b
```

JSON 연동이 필요한 경우 LLM보다 JSON 출력을 우선 사용합니다.

```bash
sre-agent inspect-deploy my-service -n prod --since 30m --json | jq .
```


## 안전 원칙

이 도구는 Kubernetes read-only 진단 도구입니다.

허용하는 명령:

```text
kubectl get
kubectl describe
kubectl logs
kubectl get events
```

금지해야 하는 명령:

```text
kubectl delete
kubectl apply
kubectl edit
kubectl exec
kubectl cp
kubectl port-forward
kubectl scale
kubectl patch
```

구현 원칙:

* `shell=True`를 사용하지 않습니다.
* 모든 kubectl 명령은 `list[str]` 형태로 실행합니다.
* 로그는 LLM에 전달하기 전에 반드시 redaction을 수행합니다.
* 기본 출력은 compact하게 유지합니다.
* 상세 정보는 `--verbose` 또는 `--json`으로 분리합니다.
* 장애 원인은 단정하지 않고 가능성으로 표현합니다.

## 테스트용 Kubernetes 리소스

### Error log Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: error-log-pod
  namespace: default
spec:
  restartPolicy: Never
  containers:
    - name: app
      image: busybox:1.36
      command:
        - sh
        - -c
        - |
          echo 'ERROR service=payment-api exception=SQLTransientConnectionException message="HikariPool-1 - Connection is not available, request timed out after 30000ms"'
          echo 'ERROR service=payment-api exception=RedisConnectionFailureException message="Unable to connect to Redis at redis-master.prod.svc.cluster.local:6379"'
          echo 'ERROR service=payment-api exception=java.lang.OutOfMemoryError message="Java heap space"'
          echo 'WARN service=kubernetes reason=BackOff message="Back-off restarting failed container payment-api"'
          echo 'ERROR service=auth-api exception=JwtExpiredException message="JWT token expired"'
          sleep 3600
```

### CrashLoopBackOff Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crash-loop-demo
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: crash-loop-demo
  template:
    metadata:
      labels:
        app: crash-loop-demo
    spec:
      containers:
        - name: app
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              echo 'ERROR service=payment-api exception=java.lang.OutOfMemoryError message="Java heap space"'
              echo 'ERROR service=payment-api exception=SQLTransientConnectionException message="HikariPool-1 - Connection is not available, request timed out after 30000ms"'
              exit 1
```

적용:

```bash
kubectl apply -f k8s-crash-loop-deploy.yaml
```

확인:

```bash
kubectl get pods -l app=crash-loop-demo
sre-agent inspect-deploy crash-loop-demo -n default --since 30m --no-llm
```

정리:

```bash
kubectl delete deploy crash-loop-demo -n default
kubectl delete pod error-log-pod -n default --ignore-not-found
```

## 개발 체크

문법 검사:

```bash
python3 -m py_compile sre_agent/cli.py
python3 -m py_compile sre_agent/collectors/kubernetes.py
python3 -m py_compile sre_agent/analyzers/log_patterns.py
python3 -m py_compile sre_agent/analyzers/pod_state.py
python3 -m py_compile sre_agent/analyzers/events.py
python3 -m py_compile sre_agent/analyzers/deployment.py
```

권장 커밋:

```bash
git add .
git commit -m "Add Kubernetes SRE inspection CLI"
```

## 향후 작업

* `inspect-deploy --json` 결과를 OpenLens extension과 연동
* `inspect --json` 결과를 웹 UI 또는 Slack bot과 연동
* Unknown pattern 기반 rule suggestion 추가
* 테스트 코드 추가
* `cli.py`를 commands/renderers/analyzers로 리팩터링
* Deployment rollout history 분석 추가
* Prometheus/Loki/OpenSearch 연동
