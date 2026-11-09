# python-jenkins 즉석 스크립트 치트시트

`jenkins_cli.py` 에 없는 조회가 필요할 때만 사용한다. 대부분은 `jenkins_cli.py api <path>` 로 충분하다.

## 목차
1. 접속 보일러플레이트
2. 반드시 알아야 할 함정(gotchas)
3. 자주 쓰는 메서드와 반환 형태
4. REST 경로 모음 (tree 파라미터, wfapi, progressiveText, computer, Blue Ocean)
5. color → 상태 매핑 / 예외

## 1. 접속 보일러플레이트

`uv run` 으로 실행할 즉석 스크립트에도 `jenkins_cli.py` 상단과 같은 PEP 723 헤더(`# /// script` … `dependencies = ["python-jenkins", "requests"]`)를 붙이면 별도 설치가 필요 없다.

```python
import json, os, jenkins, requests
cfg = json.load(open(os.path.expanduser("~/.config/pyjenkins.json")))
s = jenkins.Jenkins(cfg["JENKINS_URL"], username=cfg["JENKINS_USERNAME"],
                    password=cfg["JENKINS_API_TOKEN"], timeout=60)
s.get_whoami()                       # 반드시 먼저 호출 (아래 함정 1)

# 임의 REST GET (crumb/auth 자동 처리, 404 -> NotFoundException)
def get(path, params=None):
    return s.jenkins_request(requests.Request("GET", s.server + path.lstrip("/"), params=params)).json()
```

## 2. 함정(gotchas)

1. **첫 호출이 `get_version()`/`get_info()` 이면 403.** 이 두 메서드는 지연 인증 설정(`_maybe_add_auth`)을 건너뛰고 `_request` 를 직접 쓴다. `get_whoami()` 등 `jenkins_request` 기반 메서드를 먼저 호출해 세션에 auth 를 심어야 한다.
2. **폴더 잡 이름은 `folder/sub/job`** 로 쓴다. 라이브러리가 `job/folder/job/sub/job/job` 으로 바꿔 준다. 현재 서버는 폴더 없이 226개 flat.
3. **파라미터 잡을 `build_job(name)` 으로 파라미터 없이 호출하면** `/build` 엔드포인트를 쳐서 실패(400)할 수 있다. `parameters={"delay": "0sec"}` 처럼 아무 값이나 넘기면 `/buildWithParameters` 로 가고 기본값이 적용된다. (`jenkins_cli.py build` 가 이렇게 처리)
4. **`build_job()` 반환값은 큐 ID** 이지 빌드 번호가 아니다. `get_queue_item(qid)["executable"]["number"]` 가 생길 때까지 폴링. 큐 항목은 빌드 시작 후 약 5분 뒤 사라진다(`JenkinsException`).
5. **`get_build_stages()` 는 wfapi(pipeline-stage-view)** 를 쓴다. 스테이지 ID → `execution/node/<id>/wfapi/describe` 로 스텝(`stageFlowNodes`) → 각 스텝 `_links.log.href` 로 스텝 로그. 스텝 로그 텍스트는 **HTML 이스케이프(`&gt;`, `<a href>`)** 되어 있으니 태그 제거 후 `html.unescape`. `hasMore: true` 면 서버가 잘라낸 것.
6. **`get_build_console_output()` 은 전체 로그를 한 번에** 받는다. 1MB 넘는 로그는 컨텍스트에 붓지 말고 파일로 저장 후 grep. 실시간은 `logText/progressiveText?start=N` (+ 응답 헤더 `X-Text-Size`, `X-More-Data`).
7. **`get_running_builds()` 는 built-in 노드의 oneOffExecutors(flyweight) 를 못 본다.** 파이프라인 빌드는 built-in 의 flyweight + 에이전트 executor 둘 다 차지한다. `computer/api/json?depth=1&tree=computer[executors[...],oneOffExecutors[...]]` 로 직접 보는 편이 정확.
8. **404 는 `jenkins.NotFoundException`**, 401/403/500 은 `jenkins.JenkinsException("Possibly authentication failed [403] ...")`, 그 외 HTTP 오류는 `requests.HTTPError` 그대로 올라온다. 타임아웃은 `jenkins.TimeoutException`.
9. `cancel_queue()` 는 항상 404 를 삼키므로 성공 여부는 `get_queue_info()` 로 재확인.
10. `check_jenkinsfile_syntax()` 는 **Declarative 전용** (`pipeline-model-converter/validateJenkinsfile`). scripted 파이프라인은 항상 오류.

## 3. 자주 쓰는 메서드

| 메서드 | 반환 |
|---|---|
| `get_whoami()` | `{id, fullName, ...}` |
| `get_all_jobs()` | `[{name, fullname, url, color, _class}]` 폴더 재귀 |
| `get_job_info(name, depth=0)` | `builds[]`, `lastBuild`, `lastFailedBuild`, `lastSuccessfulBuild`, `property[].parameterDefinitions[]`, `healthReport[]`, `inQueue`, `disabled`, `nextBuildNumber` |
| `get_job_config(name)` | config.xml 문자열. `<definition class="...CpsFlowDefinition"><script>` (inline) 또는 `CpsScmFlowDefinition` + `<scm>`/`<scriptPath>` |
| `build_job(name, parameters=None)` | 큐 ID(int) |
| `get_queue_item(qid)` | `{why, executable:{number,url}, cancelled, ...}` |
| `get_build_info(name, n, depth=0)` | `building, result, duration, timestamp, url, actions[causes/parameters/BuildData/TestResultAction], changeSets[], artifacts[], culprits[]` |
| `get_build_stages(name, n)` | wfapi describe: `{status, durationMillis, stages:[{id,name,status,durationMillis,_links}]}` (파이프라인 아니면 None) |
| `get_build_console_output(name, n)` | 전체 콘솔 텍스트 |
| `get_build_test_report(name, n)` | junit `{failCount, passCount, skipCount, suites[cases[]]}` 또는 None |
| `get_build_env_vars(name, n)` | injectedEnvVars 플러그인 필요, 없으면 None |
| `get_build_artifact_as_bytes(name, n, relativePath)` | bytes |
| `stop_build(name, n)` / `cancel_queue(qid)` | 없음 |
| `get_queue_info()` | `[{id, task:{name}, why, inQueueSince, stuck, blocked, actions[parameters]}]` |
| `get_nodes()` | `[{name, offline}]` |
| `get_node_info(name, depth)` | `executors[], oneOffExecutors[], monitorData{DiskSpaceMonitor,...}, offlineCauseReason, assignedLabels[]` (built-in 은 `(built-in)` 또는 `(master)`) |
| `enable_job` / `disable_job` | 없음 |
| `check_jenkinsfile_syntax(text)` | 오류 목록 (빈 리스트 = OK) |
| `get_plugins()` | `{(shortName, longName): {version,...}}` |
| `run_script(groovy)` | 관리자 전용 script console. **사용 금지** (스킬 범위 밖) |

## 4. REST 경로 모음

`tree=` 로 필드를 제한하면 응답이 수십 배 작아진다. `{0,N}` 은 배열 슬라이스.

```
api/json?tree=jobs[name,color,lastBuild[number,result,timestamp]]
api/json?tree=primaryView[name],views[name,url,jobs[name]]          # view 목록 (view 이름은 URL 인코딩: Team%20A)
view/<VIEW>/api/json?tree=jobs[name,fullName,color]                # 특정 view 의 잡 (중첩 view 는 view/A/view/B)
job/<J>/api/json?tree=builds[number,result,building,timestamp,duration]{0,20}
job/<J>/<N>/api/json?tree=result,building,actions[parameters[name,value],causes[shortDescription]]
job/<J>/<N>/consoleText                                   # 전체 로그 (plain)
job/<J>/<N>/logText/progressiveText?start=<offset>        # 증분 로그, 헤더 X-Text-Size / X-More-Data
job/<J>/<N>/wfapi/describe                                 # 스테이지
job/<J>/<N>/execution/node/<stageId>/wfapi/describe       # 스테이지 내 스텝 (stageFlowNodes)
job/<J>/<N>/execution/node/<nodeId>/wfapi/log             # 스텝 로그 {text(html-escaped), hasMore}
job/<J>/<N>/testReport/api/json?tree=failCount,passCount,suites[cases[className,name,status,errorDetails]]
job/<J>/<N>/artifact/<relativePath>
job/<J>/config.xml
computer/api/json?depth=1&tree=computer[displayName,offline,offlineCauseReason,numExecutors,executors[currentExecutable[url]],oneOffExecutors[currentExecutable[url]]]
computer/(built-in)/api/json?depth=1                       # monitorData: 디스크/메모리/응답시간
queue/api/json
pipeline-model-converter/validateJenkinsfile   (POST jenkinsfile=<text>)
blue/rest/organizations/jenkins/pipelines/<J>/runs/<N>/nodes/     # Blue Ocean 노드(스테이지/병렬) 그래프
blue/rest/organizations/jenkins/pipelines/<J>/runs/<N>/nodes/<id>/steps/   # 스텝 + 로그 링크
```

Blue Ocean(1.27) 이 설치되어 있어 병렬 브랜치 구조가 필요하면 위 경로가 wfapi 보다 낫다. 그 외엔 wfapi 로 충분.

## 5. color → 상태 / 예외

| color | 의미 |
|---|---|
| blue / red / yellow | SUCCESS / FAILURE / UNSTABLE |
| aborted / notbuilt / disabled / grey | ABORTED / 빌드 없음 / 비활성 / 알 수 없음 |
| `*_anime` 접미사 | 현재 실행 중 (앞부분은 직전 결과) |

wfapi stage status: `SUCCESS, FAILED, UNSTABLE, ABORTED, IN_PROGRESS, NOT_EXECUTED, PAUSED_PENDING_INPUT`.
build result: `SUCCESS, FAILURE, UNSTABLE, ABORTED, NOT_BUILT`, 실행 중이면 `result: null, building: true`.
