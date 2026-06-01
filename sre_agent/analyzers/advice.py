ISSUE_ADVICE = {
    "DB connection pool timeout": {
        "severity": "high",
        "meaning": "DB connection pool에서 사용 가능한 connection을 제때 얻지 못한 상태입니다.",
        "possible_causes": [
            "DB connection pool size 부족",
            "connection leak 가능성",
            "DB 응답 지연 또는 lock 경합",
            "외부 요청 지연으로 worker/thread가 connection을 오래 점유했을 가능성",
        ],
        "checks": [
            "DB active/max connection 수 확인",
            "HikariCP maximumPoolSize, connectionTimeout 설정 확인",
            "connection leak detection 로그 확인",
            "최근 배포에서 DB connection close 누락 여부 확인",
            "DB slow query, lock wait, CPU 사용률 확인",
        ],
    },
    "External payment gateway delay": {
        "severity": "medium",
        "meaning": "외부 결제 게이트웨이 응답 지연이 관측되었습니다.",
        "possible_causes": [
            "외부 결제사 응답 지연",
            "네트워크 지연 또는 timeout 설정 문제",
            "재시도 증가로 인한 요청 적체 가능성",
        ],
        "checks": [
            "gateway별 latency, timeout, error rate 확인",
            "payment-api의 retry/backoff 설정 확인",
            "외부 결제사 상태 페이지 또는 공지 확인",
            "동일 시간대 다른 외부 API 호출 지연 여부 확인",
        ],
    },
    "Redis connection failure": {
        "severity": "high",
        "meaning": "Redis endpoint로 연결하지 못한 로그가 발생했습니다.",
        "possible_causes": [
            "Redis 서버 장애 또는 재시작",
            "DNS/service endpoint 문제",
            "network policy 또는 security group 차단",
            "connection pool 고갈 가능성",
        ],
        "checks": [
            "Redis pod/service 상태 확인",
            "Redis endpoint DNS resolve 확인",
            "payment-api pod에서 Redis port 연결 가능 여부 확인",
            "Redis connection count, rejected connection 확인",
            "network policy/security group 변경 여부 확인",
        ],
    },
    "Java OutOfMemoryError": {
        "severity": "high",
        "meaning": "JVM heap memory 부족 신호가 관측되었습니다.",
        "possible_causes": [
            "memory leak 가능성",
            "JVM -Xmx 설정이 컨테이너 memory limit과 맞지 않음",
            "트래픽 증가 또는 대용량 객체 처리",
            "GC pressure 증가",
        ],
        "checks": [
            "pod memory usage 추이 확인",
            "container memory request/limit 확인",
            "JVM -Xmx, MaxRAMPercentage 설정 확인",
            "최근 배포 이후 heap 사용량 변화 확인",
            "heap dump 또는 GC log 확인 가능 여부 검토",
        ],
    },
    "Kubernetes OOMKilled": {
        "severity": "high",
        "meaning": "컨테이너가 memory limit을 초과해 Kubernetes에 의해 종료된 신호입니다.",
        "possible_causes": [
            "컨테이너 memory limit 부족",
            "애플리케이션 메모리 누수",
            "JVM heap/native memory 설정 불일치",
        ],
        "checks": [
            "kubectl describe pod에서 last state reason 확인",
            "restart count 확인",
            "container memory limit/request 확인",
            "OOMKilled 직전 application log 확인",
            "동일 deployment의 다른 pod에서도 발생하는지 확인",
        ],
    },
    "Kubernetes BackOff restarting container": {
        "severity": "medium",
        "meaning": "컨테이너가 실패 후 반복 재시작되어 Kubernetes가 재시작 간격을 늘리는 상태입니다.",
        "possible_causes": [
            "애플리케이션 프로세스 비정상 종료",
            "OOMKilled 이후 재시작 반복",
            "startup probe/liveness probe 실패",
        ],
        "checks": [
            "kubectl logs --previous로 이전 컨테이너 로그 확인",
            "kubectl describe pod의 Events 확인",
            "exit code와 termination reason 확인",
            "liveness/readiness/startup probe 설정 확인",
        ],
    },
    "Kubernetes CrashLoopBackOff": {
        "severity": "high",
        "meaning": "컨테이너가 반복적으로 실패하여 재시작 루프에 들어간 상태입니다.",
        "possible_causes": [
            "애플리케이션 시작 실패",
            "설정값/secret/configmap 오류",
            "OOMKilled 또는 dependency 연결 실패",
        ],
        "checks": [
            "kubectl logs --previous 확인",
            "kubectl describe pod Events 확인",
            "최근 configmap/secret/deployment 변경 확인",
            "이미지 버전과 최근 rollout history 확인",
        ],
    },
    "Downstream failure from payment-api": {
        "severity": "medium",
        "meaning": "다른 서비스가 payment-api의 실패 응답으로 영향을 받은 것으로 보입니다.",
        "possible_causes": [
            "payment-api 500 응답 전파",
            "주문 생성 플로우에서 결제 확인 실패",
            "upstream 장애로 인한 downstream 오류",
        ],
        "checks": [
            "order-api 오류 시각과 payment-api 오류 시각 비교",
            "trace_id 기반 호출 경로 확인",
            "order-api retry/fallback 동작 확인",
            "payment-api 5xx rate와 order-api 5xx rate 상관관계 확인",
        ],
    },
    "Order queued due to payment delay": {
        "severity": "medium",
        "meaning": "payment-api 응답 지연으로 order-api가 주문을 즉시 완료하지 않고 큐잉한 상태입니다.",
        "possible_causes": [
            "payment-api 응답 지연",
            "외부 결제 게이트웨이 지연",
            "order-api fallback/async queue 동작",
        ],
        "checks": [
            "order-api queue backlog 확인",
            "payment-api latency와 order-api queue 증가 시점 비교",
            "주문 처리 지연 건수 확인",
            "fallback 또는 retry 정책 확인",
        ],
    },
}