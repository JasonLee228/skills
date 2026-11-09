# 빌드 실패 진단(triage) 가이드

`jenkins_cli.py diagnose` 출력을 읽고 원인을 분류·보고하는 절차. 원칙: **로그를 통째로 읽지 말고 실패 스텝 → 스텝 로그 → 필요한 곳만 grep** 순서로 좁힌다.

## 목차
1. 진단 절차
2. 원인 분류 기준 (소스 / 파이프라인 / 인프라 / 외부)
3. 패턴별 확인 명령
4. 재실행 판단
5. 보고 템플릿

## 1. 진단 절차

```
diagnose JOB [N]              # 1) 요약·스테이지·실패 스텝·스텝 로그 tail·에러 라인·힌트
stages JOB N --steps --log 60 # 2) 실패 스텝 로그를 더 길게
log JOB N --grep '<키워드>' -C 5   # 3) 특정 문자열 앞뒤 문맥
log JOB N --save /tmp/x.log   # 4) 1MB 넘는 로그는 저장 후 grep/sed 로 탐색
builds JOB -n 10 / changes JOB N   # 5) 언제부터 깨졌나, 무엇이 바뀌었나
test-report JOB N             # 6) UNSTABLE 이거나 테스트 단계 실패일 때
nodes / queue / running       # 7) 에이전트·큐 문제 의심 시
config JOB / lint             # 8) 파이프라인 정의 자체가 의심될 때
```

읽는 순서: **실패 스텝의 error 메시지 → 스텝 로그의 마지막 30줄에서 첫 번째 진짜 오류 → 그 직전 몇 줄**. `[ERROR]` 가 수백 줄이면 대부분 같은 원인의 반복이므로 첫 발생 지점(`log --grep ... --limit 0 | head`) 을 본다.

## 2. 원인 분류 기준

| 분류 | 신호 | 담당/조치 |
|---|---|---|
| **소스 코드** | 컴파일 오류, 테스트 실패, lint 실패, `exit code 1` 이 빌드 도구(mvn/npm/go) 출력 뒤에 옴 | 개발자. `changes` 로 해당 커밋·작성자 확인 |
| **파이프라인 정의** | `No such DSL method`, `MissingPropertyException`, `WorkflowScript: N`, `Scripts not permitted`, 스테이지 진입 전 실패(stages 비어 있음), 파라미터 누락 | Jenkinsfile 수정. `config JOB --jenkinsfile`, `lint` |
| **인프라(에이전트/K8s)** | 파드 스케줄 대기 중 abort, `ImagePullBackOff`, `Cannot contact`, `ChannelClosedException`, `No space left`, OOM(137), 첫 스테이지도 못 감 | 에이전트/클러스터. `nodes`, `node built-in` 디스크, 동일 시각 다른 잡도 실패했는지 `jobs --status bad --sort time` |
| **외부 의존** | 레지스트리/Nexus/Git/Azure DevOps 인증·연결 오류, 배포 대상 `kubectl`/`helm` 오류, 타사 API 타임아웃 | 자격증명/네트워크. 동일 오류가 여러 잡에서 같은 시각에 나면 외부 장애 |
| **의도된 중단** | `Aborted by <user>`, timeout 스텝, 새 빌드가 이전 빌드 취소(milestone), input 거절 | 원인 아님. 누가/왜 중단했는지 status 의 aborted 항목 |

## 3. 패턴별 확인 명령

- **`script returned exit code N`** — 스텝 로그가 답이다. `stages JOB N --steps --log 80`. 로그가 잘렸으면(`server-truncated`) `log JOB N --grep '<마지막 명령 키워드>' -C 20`.
- **Maven `cannot find symbol` / `COMPILATION ERROR`** — 첫 오류 파일:라인 → `changes JOB N` 의 커밋과 대조. 보통 다른 모듈(공통 라이브러리) 버전 불일치.
- **테스트 실패 / UNSTABLE** — `test-report JOB N --trace 800`. 직전 성공 빌드와 같은 테스트가 반복 실패하면 회귀, 매번 다른 테스트면 flaky.
- **K8s 파드 기동 실패** — 콘솔 초반의 `Still waiting to schedule task` 가 몇 분 이상 반복되다 abort 되면 스케줄링 문제. `nodes` 에 파드 노드가 생겼는지, `queue` 의 why 문구 확인. 이 서버의 정상 빌드도 파드 기동에 30초~2분 걸린다.
- **이미지 pull 실패** — Jenkinsfile 의 `containerTemplate(image: ...)` 태그 확인. Harbor 이미지면 `scr-harbor-images` 스킬로 태그 존재 여부 확인.
- **Git/Azure DevOps 인증** — `config JOB` 의 credentialsId, 콘솔의 `Obtained ... from git` 줄 이후 오류. 토큰 만료가 흔하다.
- **Pipeline 정의 오류(스테이지 0개)** — `diagnose` 에 stages 가 비고 콘솔 상단 수십 줄 안에 `WorkflowScript` 오류. `config JOB --jenkinsfile` 로 해당 라인 확인, Declarative 면 `lint`.
- **오래 걸리다 timeout** — `stages` 의 TOOK 로 어느 스테이지가 평소보다 긴지 `builds` 의 이전 소요시간과 비교.
- **여러 잡이 동시에 실패** — `jobs --status bad --sort time --limit 20`. 같은 시각·같은 오류면 인프라/외부 장애로 판단하고 개별 잡 분석은 보류.

## 4. 재실행 판단

재실행(`rebuild JOB N` 또는 `build JOB`) 은 다음일 때만 의미가 있다: 인프라 일시 오류(파드 스케줄 실패, 네트워크 타임아웃, 이미지 pull 일시 실패), flaky 테스트, 사용자 abort. 컴파일 오류·정의 오류는 재실행해도 같은 결과이므로 하지 않는다. 사용자가 요청하지 않은 재실행은 하지 않는다 (배포 파이프라인일 수 있음).

## 5. 보고 템플릿

```
**cloud-common #478 FAILURE** (1m20s, 2026-07-14 09:49, Started by user ci-bot)
- 실패 지점: stage `cloud-common deploy` › step Shell Script (mvn package) — `script returned exit code 1`
- 원인: 컴파일 오류 — QueryItems.java:489,501 `cannot find symbol setSearchDepth/setPaginateType` (소스 코드 문제)
- 근거 로그:
    [ERROR] .../QueryItems.java:[501,17] cannot find symbol
    [ERROR]   symbol:   method setPaginateType(...)
- 관련 변경: e2d3648 dev.user "fix: CryptoLibrary.getCRC32 ..." 외 1건
- 분류: 소스 코드 / 재실행 무의미
- 다음 조치: 해당 메서드를 제공하는 공통 모듈 버전 확인 후 커밋 수정
- URL: https://jenkins.example.com/job/cloud-common/478/
```

로그 인용은 원인을 보여주는 3~10줄만. 전체 로그나 수백 줄의 `[ERROR]` 반복은 붙이지 않는다.
