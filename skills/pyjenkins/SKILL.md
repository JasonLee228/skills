---
name: pyjenkins
description: python-jenkins 기반 CLI 로 Jenkins 서버에 접근한다. 파이프라인(잡) 실행·완료 대기·실패 자동 진단, 콘솔 로그 조회(tail/grep/에러 추출/실시간 follow), 스테이지·스텝 단위 실패 지점 분석, 잡·노드·큐 상태 점검, 파이프라인 정의(config) 확인, Declarative Jenkinsfile lint, 테스트 리포트·변경 커밋·아티팩트 조회. Use when the user asks to run or trigger a Jenkins job/pipeline, find out why a build failed, read or watch a console log, check build status, list failed or running jobs, inspect a pipeline definition or agent nodes, or mentions Jenkins, 젠킨스, 파이프라인 실행, 빌드 실패 원인, 콘솔 로그, 빌드 상태, 잡 목록, 에이전트/노드 상태. Credentials come from ~/.config/pyjenkins.json.
version: 1.0.0
---

# pyjenkins — Jenkins 파이프라인 실행·점검

동봉 스크립트 `scripts/jenkins_cli.py` 가 인증(crumb/토큰)·잡 이름 해석·큐→빌드번호 추적·
wfapi 스테이지/스텝 분석·로그 처리를 전부 담당한다. **직접 curl 이나 python 을 새로 짜지 말고
스크립트를 쓴다.** 스크립트에 없는 조회는 `api <path>` 로, 그래도 부족하면
[references/python-jenkins-api.md](references/python-jenkins-api.md) 를 읽고 즉석 스크립트를 작성한다.

## 사전 조건

- 자격증명: `~/.config/pyjenkins.json` (`--config PATH` 또는 `$PYJENKINS_CONFIG` 로 변경) — `{"JENKINS_URL","JENKINS_USERNAME","JENKINS_API_TOKEN"}`.
  값을 대화에 출력하지 말 것. 없으면 스크립트가 기대 형식을 안내하며 종료한다.
- 실행은 `uv run` 으로 한다. 스크립트에 PEP 723 메타데이터가 있어 python-jenkins 를 uv 가 첫 실행 때 자동 설치한다.
  uv 가 없는 환경이면 `pip install --user python-jenkins` 후 `python3` 로 실행해도 된다.

## 사용법

```bash
J=<skill-dir>/scripts/jenkins_cli.py   # 예: ~/.claude/skills/pyjenkins/scripts/jenkins_cli.py
uv run $J -h                # 전체 명령, uv run $J <cmd> -h 로 옵션
uv run $J --json <cmd> ...  # 구조화 출력이 필요할 때
```

빌드 지정자: 번호 | `last`(기본) | `-2`(직전) | `lastFailed` | `lastSuccessful` | `lastCompleted`.
잡 인자에는 이름 대신 **Jenkins URL 을 그대로** 넣어도 된다 — view 경로(`/view/Team%20A/job/x/`), 폴더(`/job/a/job/b/`),
빌드 URL(`/job/x/252/console` → 빌드 252 자동 적용, `/lastFailedBuild/` 도 인식), Blue Ocean URL 모두 지원.
**view URL** (`https://jenkins.example.com/view/Team%20A/`) 은 잡이 아니라 잡 묶음이므로 `jobs <URL>` 로 그 view 의 잡들을 나열한다
(view 이름으로도 가능: `jobs "Team A"`, `views` 로 전체 view 목록).
이름은 대소문자 무시·유일한 부분 문자열 허용 (`cloud-common` ≒ `CLOUD-COMMON`), 모호하면 후보를 나열하고 실패한다.

| 목적 | 명령 |
|---|---|
| 접속 확인 | `whoami` |
| 잡 목록/상태 | `jobs [VIEW\|VIEW_URL] [-f REGEX] [-s failed\|running\|bad\|...] [--sort time] [-n N]`, `views` |
| 잡 상세(파라미터·최근 빌드·health) | `job JOB`, `params JOB`, `builds JOB -n 15` |
| **실행 + 완료 대기 + 실패 진단** | `build JOB [-p K=V ...] [--timeout 1800] [--follow] [--no-wait]` |
| 같은 파라미터로 재실행 | `rebuild JOB [N] [-p K=V]` |
| 실행 중 빌드 대기 | `wait JOB N`, 중단은 `stop JOB N` |
| 빌드 요약 / 스테이지 | `status JOB [N]`, `stages JOB [N] [--steps [all] --log 40]` |
| **실패 원인 진단** | `diagnose JOB [N]` |
| 콘솔 로그 | `log JOB [N] [--tail 200\|--head N\|--full] [--grep RX -C 3] [--errors] [--save PATH] [--follow]` |
| 테스트·변경·아티팩트 | `test-report JOB [N]`, `changes JOB [N]`, `artifacts JOB [N] [--download DIR]` |
| 파이프라인 정의 | `config JOB [--jenkinsfile\|--xml\|--save PATH]`, `lint <Jenkinsfile 경로\|JOB>` |
| 인프라 | `nodes`, `node <이름\|master>`, `queue`, `running`, `cancel-queue ID` |
| 잡 활성/비활성 | `enable JOB`, `disable JOB` |
| 그 외 REST | `api "job/X/api/json?tree=..."` (`-d k=v` 로 POST) |

종료 코드: `0` SUCCESS · `2` UNSTABLE · `3` FAILURE/ABORTED · `4` timeout(아직 실행 중) · `1` 오류.

## 워크플로우

### 1. 파이프라인 실행하고 결과 확인

1. `job JOB` 으로 파라미터·최근 상태를 본다. 파라미터 잡이면 필요한 값을 `-p` 로 준비한다.
2. `build JOB -p K=V` 를 실행한다. 큐 대기 사유 → 빌드 번호 → 스테이지 진행이 stderr 로 출력되고,
   끝나면 결과 한 줄 + (실패 시) `diagnose` 결과가 자동으로 붙는다.
3. 20~30분 넘게 걸리는 잡은 `--no-wait` 로 번호만 받고 `wait JOB N` 으로 이어서 기다린다.
   `exit 4` 는 timeout 이지 실패가 아니다 — 같은 `wait` 를 다시 실행한다.
4. 실패했으면 [references/failure-triage.md](references/failure-triage.md) 의 절차로 원인을 분류하고 보고한다.

### 2. 콘솔 로그 확인

- 기본 `log JOB` 은 마지막 200줄만 낸다. 큰 로그(수천 줄, 1MB+)는 **`--full` 로 컨텍스트에 붓지 말고**
  `--save PATH` 로 저장한 뒤 `grep -n`/`sed -n` 으로 필요한 부분만 읽는다. 라인 번호는 `wc -l` 과 일치한다.
- `--errors` 는 오류로 보이는 줄만, `--grep RX -C N` 은 키워드 앞뒤 문맥을 낸다.
- 실행 중인 빌드는 `log JOB N --follow` 로 끝날 때까지 스트리밍한다.

### 3. 파이프라인 점검

- 전체 현황: `jobs --status bad --sort time -n 20` (최근 실패 순), `jobs -s running`, `queue`, `nodes`.
- 제품/팀 단위 현황: `views` 로 view 목록을 보고 `jobs "Team A" -s bad` 처럼 view 로 좁힌다. 사용자가 view URL 을 주면 그대로 `jobs <URL>`.
- 개별 잡: `job JOB` → `config JOB` (inline 스크립트인지 SCM 의 `jenkins-pipelines.groovy` 인지, 트리거, credentialsId)
  → `stages JOB lastSuccessful --steps all` 로 정상 실행 흐름 파악 → `builds JOB` 로 소요시간 추세.
- Jenkinsfile 수정 검증: Declarative 면 `lint 경로`. 잡이 **scripted pipeline** 이면 서버 lint 가 불가하니
  `config JOB --jenkinsfile` 로 현재 정의와 비교해 검토한다.

## 답변 요령

- 결과는 `잡 #번호 상태 소요시간 URL` 한 줄 → 실패 스테이지/스텝 → 원인 로그 3~10줄 인용 → 분류(소스/파이프라인/인프라/외부) → 다음 조치 순으로 정리한다.
- `diagnose` 의 힌트는 후보일 뿐이다. 실패 스텝의 로그 마지막 부분에서 실제 오류를 확인한 뒤 결론을 낸다.
- 이 Jenkins 는 **Kubernetes 파드 에이전트**를 쓴다. 빌드마다 `<잡>-<번호>-xxxx` 노드가 생겼다 사라지고, 콘솔 초반의
  `Still waiting to schedule task` 는 정상적인 파드 기동 대기다. `nodes` 에 보이는 노드 수 = 지금 돌고 있는 빌드 수.

## 제약·주의

- 상태를 바꾸는 명령은 `build`, `rebuild`, `stop`, `cancel-queue`, `enable`, `disable` 뿐이며, **사용자가 지목한 잡에만**
  실행한다. 배포 파이프라인일 수 있으므로 "확인차" 임의 실행하지 않는다. 유사 이름 매칭으로 잡이 바뀌었으면(stderr 의 `note: job 'x' -> 'y'`)
  실행 전에 사용자에게 확인한다.
- 잡·빌드 삭제, config 변경, 스크립트 콘솔(`run_script`) 은 의도적으로 제공하지 않는다. 요청받으면 Jenkins UI 를 안내한다.
- 즉석 python 을 짤 때 `get_version()` 을 첫 호출로 쓰면 403 이 난다 — `get_whoami()` 를 먼저 호출한다
  (자세한 함정 목록은 references/python-jenkins-api.md §2).
