#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-jenkins>=1.8",
#     "requests",
# ]
# ///
"""pyjenkins CLI - Jenkins helper built on python-jenkins.

Config (JSON): ~/.config/pyjenkins.json
  {"JENKINS_URL": "...", "JENKINS_USERNAME": "...", "JENKINS_API_TOKEN": "..."}
Override with --config PATH or $PYJENKINS_CONFIG.

  uv run jenkins_cli.py -h            global options + command list
  uv run jenkins_cli.py <cmd> -h      command options
  (uv installs python-jenkins on first run; plain `python3 jenkins_cli.py` also works if it is installed)

Exit codes: 0 ok / 1 error / 2 UNSTABLE / 3 FAILURE,ABORTED / 4 timeout (still running)
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import unicodedata
from urllib.parse import quote, unquote, urlsplit

import requests

try:
    import jenkins
except ImportError:  # pragma: no cover
    sys.stderr.write("python-jenkins not installed: run with `uv run jenkins_cli.py ...` or pip install --user python-jenkins\n")
    sys.exit(1)

CONFIG_DEFAULT = "~/.config/pyjenkins.json"
BUILD_ALIASES = {
    "last": "lastBuild", "lastbuild": "lastBuild",
    "lastfailed": "lastFailedBuild", "lastsuccessful": "lastSuccessfulBuild",
    "lastcompleted": "lastCompletedBuild", "laststable": "lastStableBuild",
    "lastunstable": "lastUnstableBuild", "lastunsuccessful": "lastUnsuccessfulBuild",
}
COLOR_STATUS = {
    "blue": "SUCCESS", "red": "FAILURE", "yellow": "UNSTABLE", "aborted": "ABORTED",
    "notbuilt": "NOT_BUILT", "disabled": "DISABLED", "grey": "UNKNOWN",
}
STATUS_ICON = {
    "SUCCESS": "✔", "FAILURE": "✖", "FAILED": "✖", "UNSTABLE": "⚠", "ABORTED": "■",
    "IN_PROGRESS": "▶", "RUNNING": "▶", "NOT_EXECUTED": "○", "NOT_BUILT": "○",
    "PAUSED_PENDING_INPUT": "⏸", "DISABLED": "-", "UNKNOWN": "?",
}
RESULT_EXIT = {"SUCCESS": 0, "UNSTABLE": 2}
DECLARATIVE_RE = re.compile(r"^\s*pipeline\s*\{", re.M)

# console lines that look like errors
ERR_LINE_RE = re.compile(
    r"(?i)(?:\[ERROR\]|\berror\b|\bexception\b|\bfail(?:ed|ure)?\b|\bfatal\b|\bpanic\b|traceback"
    r"|\bdenied\b|time[d ]?out|\baborted?\b|\bkilled\b|cannot find|could not|couldn't|unable to"
    r"|not found|no such|\brefused\b|unreachable|exit code [1-9]|npm ERR!|✖|✗|\bFAIL\b)"
)
ERR_NOISE_RE = re.compile(
    r"(?i)(?:^\[Pipeline\]|errors?[:=]\s*0\b|\b0 errors?\b|Failures: 0, Errors: 0|\bwarn(?:ing)?\b.*\b0 error"
    r"|error_?log|errorHandler|ErrorBoundary|on_?error|\.error\(|catch\s*\(|error-prone|fail-?fast|failsafe"
    r"|if .*fail|allowEmptyResults|--fail-on|FAILURE_OUTPUT|abortOnFailure|noFailOnError"
    r"|^\[ERROR\]\s*$|re-run Maven|For more information about the errors|\[Help \d+\]|To see the full stack trace|^\[ERROR\]\s*-+\s*$"
    r"|Finished: (?:FAILURE|ABORTED|UNSTABLE)$|# timeout=\d+|--timeout[= ]|timeout: \d+|timeoutMs)"
)
# (regex, hint) - matched against console + failed step logs
HINTS = [  # (regex, hint, scope)  scope: any = whole console, tail = last 80 console lines + failed step logs
    (r"script returned exit code (\d+)", "sh/bat 스텝이 0이 아닌 코드로 종료. 실제 원인은 그 스텝의 step log (diagnose 출력) 또는 `log --grep` 로 확인", "tail"),
    (r"cannot find symbol|COMPILATION ERROR|compilation failed|error TS\d+|SyntaxError|undefined: |cannot use .* as|: error: ", "컴파일/문법 오류. 파이프라인이 아니라 소스 코드 문제", "any"),
    (r"Tests run:.*(?:Failures|Errors): [1-9]|There are test failures|FAILED \(failures=|npm ERR! Test failed|--- FAIL:|\b[1-9]\d* failed\b", "테스트 실패. test-report 명령으로 실패 케이스 확인", "any"),
    (r"ImagePullBackOff|ErrImagePull|manifest unknown|not found: manifest|pull access denied|failed to pull image", "컨테이너 이미지 pull 실패. 이미지 이름/태그, 레지스트리 자격증명 확인", "any"),
    (r"Timeout has been exceeded|Timed out waiting|Cancelling nested steps due to timeout|Timeout expired", "timeout 스텝/옵션에 의해 중단. 느린 단계를 찾거나 timeout 값 검토", "any"),
    (r"Aborted by |Build was aborted|FlowInterruptedException|Finished: ABORTED", "사용자 또는 상위 로직(timeout, milestone, 새 빌드 등)에 의해 중단. status 의 aborted 항목 참고", "tail"),
    (r"Authentication failed|could not read Username|fatal: Authentication|403 Forbidden|401 Unauthorized|Permission denied \(publickey\)|unauthorized: authentication required", "인증/권한 오류. credentialsId, 토큰 만료, 저장소 권한 확인", "any"),
    (r"Could not resolve host|Connection refused|Connection timed out|UnknownHostException|Name or service not known|i/o timeout|TLS handshake", "네트워크 연결 오류. 대상 호스트/포트, 프록시, DNS 확인", "any"),
    (r"No space left on device|ENOSPC|Disk quota exceeded", "디스크 부족. node 명령으로 에이전트 디스크 확인, 캐시 볼륨 정리", "any"),
    (r"OOMKilled|OutOfMemoryError|Killed process|exit code 137|JavaScript heap out of memory", "메모리 부족(OOM). 컨테이너 resource limit / JVM·Node 힙 옵션 검토", "any"),
    (r"No such DSL method|MissingPropertyException|MissingMethodException|groovy\.lang\.|WorkflowScript: \d+|unexpected token|Unknown stage section", "Jenkinsfile(Groovy) 자체 오류. lint / config 명령으로 파이프라인 정의 점검", "any"),
    (r"Scripts not permitted|RejectedAccessException|UnapprovedUsageException", "In-process Script Approval 필요 (관리자가 Jenkins 관리 > In-process Script Approval 에서 승인)", "any"),
    (r"Still waiting to schedule task|There are no nodes with the label|Waiting for next available executor|Unschedulable|pod .*Pending", "에이전트 배정 실패 (K8s 파드 기동 대기 중 중단됨). nodes/queue 명령으로 라벨·파드 스케줄링 상태 확인", "tail"),
    (r"Error fetching remote repo|Couldn't find any revision to build|fatal: couldn't find remote ref|not a git repository", "Git 브랜치/리비전 조회 실패. 브랜치 이름, 저장소 URL 확인", "any"),
    (r"Failed to push|denied: requested access to the resource is denied|push access denied", "레지스트리/저장소 push 권한 오류", "any"),
    (r"Error from server \(|error validating|The connection to the server .* was refused|helm.*(?:Error|failed)|kubectl.*(?:error|Error)", "kubectl/helm 배포 단계 오류. 매니페스트/컨텍스트/네임스페이스 확인", "any"),
    (r"Cannot contact |Agent went offline during the build|ChannelClosedException|RemovedNodeCause|agent.*(?:offline|disconnected)|pod.*(?:Terminated|deleted)", "에이전트 연결 끊김. K8s 파드 종료/노드 재시작 여부 확인", "tail"),
    (r"input step|Input requested|Waiting for approval|PAUSED_PENDING_INPUT", "input 스텝에서 승인 대기 중. UI 에서 Proceed/Abort 필요", "tail"),
    (r"npm ERR! code E(?:ACCES|PERM|404|401)|ERESOLVE|peer dep", "npm 의존성/권한 오류", "any"),
    (r"Could not resolve dependencies|Could not find artifact|Non-resolvable|could not transfer artifact", "Maven/Gradle 의존성 해석 실패. 저장소 접근/캐시 확인", "any"),
]


class CliError(Exception):
    def __init__(self, msg, code=1):
        super().__init__(msg)
        self.code = code


# ----------------------------------------------------------------- formatting
def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def fmt_ts(ms):
    if not ms:
        return "-"
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def fmt_dur(ms):
    if ms is None:
        return "-"
    s = int(ms // 1000)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s" if s else f"{int(ms)}ms"


def icon(status):
    return STATUS_ICON.get(status or "", "?")


def dwidth(text):
    """Display width: CJK (wide/fullwidth) characters count as 2 columns."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def one_line(text, limit=0):
    text = " ".join((text or "").split())
    return text[:limit] if limit else text


def table(rows, headers):
    if not rows:
        return ["(none)"]
    rows = [[one_line("" if c is None else str(c)) for c in r] for r in rows]
    widths = [max(dwidth(str(h)), *(dwidth(r[i]) for r in rows)) for i, h in enumerate(headers)]
    pad = lambda c, w: str(c) + " " * max(0, w - dwidth(str(c)))
    line = lambda r: "  ".join(pad(c, w) for c, w in zip(r, widths)).rstrip()
    return [line(headers), line(["-" * w for w in widths])] + [line(r) for r in rows]


def split_lines(text):
    """Console text -> lines. Collapses \r progress overwrites like a terminal; count matches `wc -l`."""
    lines = (text or "").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [l.rstrip("\r").split("\r")[-1] for l in lines]


def clean_html(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or ""))


def build_status(bi):
    if bi is None:
        return "NOT_BUILT"
    if bi.get("building"):
        return "RUNNING"
    return bi.get("result") or "UNKNOWN"


BUILD_URL_ALIASES = {"lastBuild", "lastFailedBuild", "lastSuccessfulBuild", "lastCompletedBuild",
                     "lastStableBuild", "lastUnstableBuild", "lastUnsuccessfulBuild"}


def parse_job_ref(ref):
    """Accept a job name or any Jenkins URL/path and return (job_name, build_spec_or_None, host_or_None).

    Handles classic URLs (/job/a/job/b/12/console, /view/X/job/y/, lastFailedBuild/...),
    Blue Ocean UI (/blue/organizations/jenkins/a%2Fb/detail/b/12/pipeline) and
    Blue Ocean REST (/blue/rest/organizations/jenkins/pipelines/a/runs/12/).
    Folder segments become 'folder/job'. (Branch names containing '/' are not distinguishable from folders.)
    """
    ref = (ref or "").strip()
    if "://" not in ref and not ref.startswith("/"):
        return ref.strip("/"), None, None
    u = urlsplit(ref)
    segs = [unquote(x) for x in u.path.split("/") if x]
    job_parts, build = [], None
    if segs and segs[0] == "blue":
        rest = segs[1:]
        if rest[:1] == ["rest"]:
            rest = rest[1:]
        if "pipelines" in rest:  # REST: organizations/jenkins/pipelines/<name>[/runs/<n>]
            i = rest.index("pipelines")
            job_parts = rest[i + 1:i + 2]
            if "runs" in rest[i + 2:]:
                j = rest.index("runs", i + 2)
                build = rest[j + 1] if len(rest) > j + 1 else None
        elif "organizations" in rest:  # UI: organizations/jenkins/<name>[/detail/<leaf>/<n>/...]
            i = rest.index("organizations")
            job_parts = rest[i + 2:i + 3]
            if "detail" in rest[i + 3:]:
                j = rest.index("detail", i + 3)
                build = rest[j + 2] if len(rest) > j + 2 else None
        job_parts = [p for x in job_parts for p in x.split("/") if p]
    else:
        i, n = 0, len(segs)
        while i < n:
            if segs[i] == "job" and i + 1 < n:
                job_parts.append(segs[i + 1])
                i += 2
                continue
            if job_parts:  # first non-"job" segment after the job path
                build = segs[i]
                break
            i += 1  # skip prefixes such as view/<name>, user/..., etc.
    if not job_parts:
        if "view" in segs:
            raise CliError(f"URL points to a view, not a job. list its jobs with: jobs '{ref}'")
        raise CliError(f"cannot find a job in URL (no job path): {ref}")
    if build is not None and not (build.isdigit() or build in BUILD_URL_ALIASES):
        build = None  # e.g. 'console', 'configure', 'wfapi', 'lastBuild' handled above
    if build in BUILD_URL_ALIASES:
        build = build[:-5]  # lastFailedBuild -> lastFailed (resolve_build alias form)
    return "/".join(job_parts), build, (u.netloc or None)


def parse_view_ref(ref):
    """View name, or a view URL/path (/view/A/, nested /view/A/view/B/) -> 'A' / 'A/B'."""
    ref = (ref or "").strip()
    if "://" not in ref and not ref.startswith("/"):
        return ref.strip("/")
    segs = [unquote(x) for x in urlsplit(ref).path.split("/") if x]
    parts, i = [], 0
    while i < len(segs):
        if segs[i] == "view" and i + 1 < len(segs):
            parts.append(segs[i + 1])
            i += 2
            continue
        if segs[i] == "job":
            raise CliError(f"URL points to a job, not a view. use: job '{ref}'")
        if parts:
            break
        i += 1
    if not parts:
        raise CliError(f"cannot find a view in URL: {ref}")
    return "/".join(parts)


# ----------------------------------------------------------------- client
class Cli:
    def __init__(self, cfg, timeout):
        self.url = cfg["JENKINS_URL"].rstrip("/") + "/"
        self.server = jenkins.Jenkins(
            self.url, username=cfg["JENKINS_USERNAME"], password=cfg["JENKINS_API_TOKEN"], timeout=timeout
        )
        # NOTE: get_version()/get_info() bypass lazy auth on first call -> 403. whoami first.
        self.me = self.server.get_whoami()
        self._jobs = None
        self.ref_build = None  # build spec carried by the last job URL passed to resolve_job()

    # raw requests (crumb + auth handled by python-jenkins)
    def req(self, method, path, params=None, data=None):
        url = self.url + path.lstrip("/")
        return self.server.jenkins_request(requests.Request(method, url, params=params, data=data))

    def get_json(self, path, params=None):
        return self.req("GET", path, params).json()

    def get_text(self, path, params=None):
        return self.req("GET", path, params).text

    @staticmethod
    def job_path(name):
        return "job/" + "/job/".join(quote(p, safe="") for p in name.split("/"))

    # jobs ------------------------------------------------------------
    JOB_FIELDS = "name,fullName,color,_class,lastBuild[number,timestamp,result,building,duration]"

    @classmethod
    def jobs_tree(cls):
        f = cls.JOB_FIELDS
        return f"jobs[{f},jobs[{f},jobs[{f},jobs[{f}]]]]"

    @staticmethod
    def flatten_jobs(items):
        out = []

        def walk(lst):
            for j in lst:
                kids = j.get("jobs")
                if isinstance(kids, list):
                    walk(kids)
                else:
                    j.setdefault("fullName", j.get("name"))
                    out.append(j)

        walk(items or [])
        return out

    def all_jobs(self):
        if self._jobs is None:
            data = self.get_json("api/json", {"tree": self.jobs_tree()})
            self._jobs = self.flatten_jobs(data.get("jobs", []))
        return self._jobs

    # views -----------------------------------------------------------
    def views(self):
        if getattr(self, "_views", None) is None:
            v = "name,url,_class,description,jobs[name]"
            data = self.get_json("api/json", {"tree": f"primaryView[name],views[{v},views[{v},views[{v}]]]"})
            out = []

            def walk(lst, prefix):
                for x in lst:
                    path = prefix + [x["name"]]
                    out.append({"view": "/".join(path), "url": x.get("url"), "class": x.get("_class", "").split(".")[-1],
                                "description": one_line(x.get("description")), "jobs": len(x.get("jobs") or [])})
                    if isinstance(x.get("views"), list):
                        walk(x["views"], path)

            walk(data.get("views", []), [])
            self._views = out
            self._primary_view = (data.get("primaryView") or {}).get("name")
        return self._views

    def resolve_view(self, ref):
        name = parse_view_ref(ref)
        names = [v["view"] for v in self.views()]
        if name in names:
            return name
        ci = [n for n in names if n.lower() == name.lower()]
        if len(ci) == 1:
            return ci[0]
        sub = [n for n in names if name.lower() in n.lower()]
        if len(sub) == 1:
            eprint(f"note: view '{name}' -> '{sub[0]}'")
            return sub[0]
        if sub:
            raise CliError(f"ambiguous view '{name}'. candidates: {', '.join(sub)}")
        raise CliError(f"view not found: {name}. available: {', '.join(names)}")

    def view_jobs(self, view):
        path = "/".join("view/" + quote(p, safe="") for p in view.split("/"))
        data = self.get_json(f"{path}/api/json", {"tree": "name,description," + self.jobs_tree()})
        return self.flatten_jobs(data.get("jobs", [])), one_line(data.get("description"))

    def resolve_job(self, name):
        name, self.ref_build, host = parse_job_ref(name)
        if host and host.lower() != urlsplit(self.url).netloc.lower():
            eprint(f"warning: URL host '{host}' differs from configured Jenkins '{urlsplit(self.url).netloc}'; using configured server")
        if self.ref_build:
            eprint(f"note: URL carries build '{self.ref_build}' (used when no build argument is given)")
        names = [j["fullName"] for j in self.all_jobs()]
        if name in names:
            return name
        ci = [n for n in names if n.lower() == name.lower()]
        if len(ci) == 1:
            return ci[0]
        sub = [n for n in names if name.lower() in n.lower()]
        if len(sub) == 1:
            eprint(f"note: job '{name}' -> '{sub[0]}'")
            return sub[0]
        if sub:
            raise CliError(f"ambiguous job '{name}'. candidates: {', '.join(sub[:20])}")
        if self.server.job_exists(name):  # not in cached tree (deep folder etc.)
            return name
        raise CliError(f"job not found: {name}")

    def job_info(self, name, tree=None, depth=0):
        params = {"tree": tree} if tree else {"depth": depth}
        return self.get_json(f"{self.job_path(name)}/api/json", params)

    def param_defs(self, name):
        ji = self.job_info(name, tree="property[parameterDefinitions[name,type,description,defaultParameterValue[value],choices]]")
        out = []
        for p in ji.get("property", []):
            for d in p.get("parameterDefinitions", []) or []:
                out.append({
                    "name": d.get("name"),
                    "type": (d.get("type") or "").replace("ParameterDefinition", ""),
                    "default": (d.get("defaultParameterValue") or {}).get("value"),
                    "choices": d.get("choices"),
                    "description": d.get("description") or "",
                })
        return out

    # builds ----------------------------------------------------------
    def resolve_build(self, name, spec):
        if spec in (None, "") and self.ref_build:
            spec = self.ref_build
        spec = "last" if spec in (None, "") else str(spec)
        if re.fullmatch(r"-?\d+", spec):
            n = int(spec)
            if n > 0:
                return n
            builds = self.job_info(name, tree="builds[number]{0,50}").get("builds", [])
            idx = -n  # 0 or -1 => last, -2 => previous
            idx = max(idx - 1, 0) if n < 0 else 0
            if idx >= len(builds):
                raise CliError(f"{name}: only {len(builds)} builds")
            return builds[idx]["number"]
        key = BUILD_ALIASES.get(spec.lower().replace("_", "").replace("-", ""))
        if not key:
            raise CliError(f"bad build spec '{spec}' (number, -N, last, lastFailed, lastSuccessful, lastCompleted ...)")
        b = self.job_info(name, tree=f"{key}[number]").get(key)
        if not b:
            raise CliError(f"{name}: no {spec} build")
        return b["number"]

    def build_info(self, name, number, tree=None, depth=0):
        params = {"tree": tree} if tree else {"depth": depth}
        return self.get_json(f"{self.job_path(name)}/{number}/api/json", params)

    def stages(self, name, number):
        try:
            return self.get_json(f"{self.job_path(name)}/{number}/wfapi/describe")
        except jenkins.NotFoundException:
            return None

    def stage_nodes(self, name, number, stage_id):
        try:
            return self.get_json(f"{self.job_path(name)}/{number}/execution/node/{stage_id}/wfapi/describe")
        except jenkins.NotFoundException:
            return None

    def node_log(self, name, number, node_id):
        try:
            d = self.get_json(f"{self.job_path(name)}/{number}/execution/node/{node_id}/wfapi/log")
        except jenkins.NotFoundException:
            return "", False
        return clean_html(d.get("text", "")), bool(d.get("hasMore"))

    def console(self, name, number):
        return self.get_text(f"{self.job_path(name)}/{number}/consoleText")

    def computers(self):
        ex = "executors[idle,progress,currentExecutable[url,fullDisplayName,timestamp]]"
        tree = ("computer[displayName,description,offline,temporarilyOffline,offlineCauseReason,numExecutors,idle,"
                f"assignedLabels[name],{ex},oneOff{ex[0].upper() + ex[1:]}]")
        return self.get_json("computer/api/json", {"tree": tree})["computer"]


# ----------------------------------------------------------------- helpers
def build_summary(cli, job, n, bi=None):
    bi = bi or cli.build_info(job, n)
    st = build_status(bi)
    d = {"job": job, "number": n, "status": st, "url": bi.get("url"), "started": fmt_ts(bi.get("timestamp")),
         "duration": fmt_dur(bi.get("duration") if not bi.get("building") else (time.time() * 1000 - bi.get("timestamp", 0))),
         "description": bi.get("description"), "causes": [], "params": {}, "git": [], "aborted": [], "tests": None}
    for a in bi.get("actions", []) or []:
        cls = a.get("_class", "").split(".")[-1]
        if "causes" in a:
            descs = [c.get("shortDescription") for c in a["causes"] if c.get("shortDescription")]
            (d["aborted"] if "Interrupted" in cls else d["causes"]).extend(descs)
        if "parameters" in a:
            d["params"] = {p.get("name"): p.get("value") for p in a["parameters"]}
        if cls == "BuildData":
            rev = a.get("lastBuiltRevision") or {}
            d["git"].append({"sha": (rev.get("SHA1") or "")[:10], "branches": [b["name"] for b in rev.get("branch", [])],
                             "remote": ", ".join(a.get("remoteUrls", []))})
        if cls == "TestResultAction":
            d["tests"] = {"total": a.get("totalCount"), "failed": a.get("failCount"), "skipped": a.get("skipCount")}
    return d


def summary_lines(d):
    lines = [f"{icon(d['status'])} {d['job']} #{d['number']}  {d['status']}  started {d['started']}  took {d['duration']}",
             f"   url: {d['url']}"]
    if d.get("description"):
        lines.append(f"   desc: {d['description']}")
    if d["causes"]:
        lines.append(f"   cause: {'; '.join(d['causes'])}")
    if d["aborted"]:
        lines.append(f"   aborted: {'; '.join(d['aborted'])}")
    if d["params"]:
        lines.append("   params: " + ", ".join(f"{k}={str(v)[:60]!r}" for k, v in d["params"].items()))
    for g in d["git"]:
        lines.append(f"   git: {','.join(g['branches']) or '?'} @ {g['sha']}  {g['remote']}")
    if d["tests"]:
        t = d["tests"]
        lines.append(f"   tests: total {t['total']}  failed {t['failed']}  skipped {t['skipped']}")
    return lines


def stage_rows(st):
    rows = []
    for sg in st.get("stages", []):
        rows.append([icon(sg["status"]), sg["name"], sg["status"], fmt_dur(sg.get("durationMillis")), sg.get("id")])
    return rows


def failed_steps(cli, job, n, st, include_log=True, log_tail=40):
    """For each non-success stage return failed flow nodes (+log)."""
    out = []
    for sg in st.get("stages", []):
        if sg["status"] not in ("FAILED", "ABORTED", "UNSTABLE", "IN_PROGRESS", "PAUSED_PENDING_INPUT"):
            continue
        nd = cli.stage_nodes(job, n, sg["id"])
        if not nd:
            continue
        steps = []
        for fn in nd.get("stageFlowNodes", []):
            if fn["status"] in ("FAILED", "ABORTED", "UNSTABLE", "IN_PROGRESS", "PAUSED_PENDING_INPUT"):
                item = {"id": fn["id"], "name": fn["name"], "status": fn["status"], "duration": fmt_dur(fn.get("durationMillis")),
                        "error": (fn.get("error") or {}).get("message"), "log": None, "log_truncated": False}
                if include_log:
                    text, more = cli.node_log(job, n, fn["id"])
                    tl = split_lines(text)
                    item["log"] = "\n".join(tl[-log_tail:]) if log_tail else text
                    item["log_total_lines"] = len(tl)
                    item["log_truncated"] = more
                steps.append(item)
        out.append({"stage": sg["name"], "status": sg["status"], "error": (nd.get("error") or {}).get("message"), "steps": steps})
    return out


def error_lines(text, limit=25):
    hits = []
    for i, ln in enumerate(split_lines(text), 1):
        if ERR_LINE_RE.search(ln) and not ERR_NOISE_RE.search(ln):
            hits.append((i, ln.rstrip()[:300]))
    total = len(hits)
    if limit and total > limit:
        head = max(limit * 2 // 5, 1)
        hits = hits[:head] + [(None, f"... {total - limit} more ...")] + hits[-(limit - head):]
    return total, hits


def hints_for(console, step_logs, tail_lines=80):
    found = []
    tail = "\n".join(split_lines(console)[-tail_lines:] + [t for t in step_logs if t])
    for rx, hint, scope in HINTS:
        m = re.search(rx, console if scope == "any" else tail)
        if m:
            found.append({"match": m.group(0)[:80], "hint": hint})
    return found


def diagnose(cli, job, n, step_tail=40, err_limit=25, console_tail=15):
    bi = cli.build_info(job, n)
    d = build_summary(cli, job, n, bi)
    st = cli.stages(job, n)
    data = {"summary": d, "stages": [], "failed": [], "error_lines": [], "error_total": 0, "hints": [], "console_tail": [], "console_lines": 0}
    lines = summary_lines(d)
    if st:
        data["stages"] = [{"name": s["name"], "status": s["status"], "duration": fmt_dur(s.get("durationMillis")), "id": s["id"]} for s in st["stages"]]
        lines += ["-- stages"] + ["   " + l for l in table(stage_rows(st), ["", "STAGE", "STATUS", "TOOK", "ID"])]
        if not st.get("stages") and d["status"] not in ("SUCCESS", "RUNNING"):
            lines.append("   (no stage reached: ended during agent/pod startup or in pipeline setup - see console tail)")
    if d["status"] in ("SUCCESS",):
        lines.append("-- result SUCCESS: nothing to diagnose")
        return data, lines
    step_logs = []
    if st:
        data["failed"] = failed_steps(cli, job, n, st, include_log=True, log_tail=step_tail)
        for f in data["failed"]:
            lines.append(f"-- stage '{f['stage']}' {f['status']}" + (f"  error: {f['error']}" if f.get("error") else ""))
            for s in f["steps"]:
                lines.append(f"   step [{s['id']}] {s['name']}  {s['status']}  {s['duration']}" + (f"  error: {s['error']}" if s.get("error") else ""))
                if s.get("log"):
                    step_logs.append(s["log"])
                    note = f" (showing last {step_tail} of {s.get('log_total_lines')} lines" + (", server-truncated" if s["log_truncated"] else "") + ")"
                    lines.append(f"   step log{note}:")
                    lines += ["     | " + l for l in s["log"].splitlines()]
    console = cli.console(job, n)
    clines = split_lines(console)
    data["console_lines"] = len(clines)
    total, hits = error_lines(console, err_limit)
    data["error_total"], data["error_lines"] = total, [{"line": i, "text": t} for i, t in hits if i]
    if hits:
        lines.append(f"-- error-looking console lines ({min(total, err_limit)} of {total}; all: `log {job} {n} --errors --limit 0`)")
        lines += [(f"   L{i}: {t}" if i else f"   {t}") for i, t in hits]
    data["hints"] = hints_for(console, step_logs)
    if data["hints"]:
        lines.append("-- hints")
        lines += [f"   • {h['match']!r} -> {h['hint']}" for h in data["hints"]]
    tail = clines[-console_tail:]
    data["console_tail"] = tail
    lines.append(f"-- console tail (last {len(tail)} of {data['console_lines']} lines)")
    lines += ["   | " + l for l in tail]
    return data, lines


def stream_log(cli, job, n, start):
    r = cli.req("GET", f"{cli.job_path(job)}/{n}/logText/progressiveText", params={"start": start})
    if r.text:
        sys.stdout.write(r.text)
        sys.stdout.flush()
    return int(r.headers.get("X-Text-Size", start)), r.headers.get("X-More-Data", "").lower() == "true"


def wait_build(cli, job, n, timeout, poll, follow=False):
    t0 = time.time()
    seen = {}
    pos = 0
    while True:
        bi = cli.build_info(job, n, tree="building,result,duration,timestamp,url,estimatedDuration")
        if follow:
            pos, _ = stream_log(cli, job, n, pos)
        else:
            st = cli.stages(job, n)
            for sg in (st or {}).get("stages", []):
                if seen.get(sg["id"]) != sg["status"]:
                    seen[sg["id"]] = sg["status"]
                    eprint(f"  [{dt.datetime.now():%H:%M:%S}] {icon(sg['status'])} stage {sg['name']!r}: {sg['status']} ({fmt_dur(sg.get('durationMillis'))})")
        if not bi["building"]:
            if follow:
                stream_log(cli, job, n, pos)
            return bi
        if time.time() - t0 > timeout:
            raise CliError(f"timeout after {int(timeout)}s: {job} #{n} still running ({bi['url']}). "
                           f"resume with: wait {job} {n}", code=4)
        time.sleep(poll)


def parse_params(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            raise CliError(f"bad -p '{it}', expected KEY=VALUE")
        k, v = it.split("=", 1)
        if v.startswith("@") and os.path.isfile(v[1:]):
            v = open(v[1:], encoding="utf-8").read()
        out[k.strip()] = v
    return out


def trigger_and_wait(cli, job, params, args):
    defs = cli.param_defs(job)
    names = {d["name"] for d in defs}
    unknown = [k for k in params if k not in names]
    if unknown:
        eprint(f"warning: params not defined on job (Jenkins ignores them): {', '.join(unknown)}")
    send = dict(params)
    if defs and not send:
        send = {"delay": "0sec"}  # force buildWithParameters endpoint -> defaults applied
    if not args.json:
        shown = ", ".join(f"{k}={v[:60]!r}" for k, v in params.items()) or ("(job defaults)" if defs else "(no parameters)")
        print(f"triggering {job}  params: {shown}", flush=True)
    qid = cli.server.build_job(job, parameters=send or None)
    number = None
    why = None
    t0 = time.time()
    qwait = args.timeout if args.wait else 90
    while number is None:
        try:
            qi = cli.server.get_queue_item(qid)
        except jenkins.JenkinsException:
            raise CliError(f"queue item {qid} disappeared; check `builds {job}`")
        if qi.get("cancelled"):
            raise CliError(f"queue item {qid} was cancelled", code=3)
        ex = qi.get("executable") or {}
        if ex.get("number"):
            number = ex["number"]
            break
        if qi.get("why") != why:
            why = qi.get("why")
            eprint(f"  queued (id {qid}): {why}")
        if time.time() - t0 > qwait:
            raise CliError(f"queue id {qid} not started after {int(qwait)}s (why: {why}). check `queue` / `nodes`", code=4)
        time.sleep(min(args.poll, 5))
    url = f"{cli.url}{cli.job_path(job)}/{number}/"
    if not args.json:
        print(f"started {job} #{number}  {url}", flush=True)
    if not args.wait:
        return {"job": job, "number": number, "queue_id": qid, "url": url, "status": "RUNNING"}, [], 0
    bi = wait_build(cli, job, number, args.timeout, args.poll, follow=args.follow)
    status = build_status(bi)
    data = {"job": job, "number": number, "queue_id": qid, "url": url, "status": status, "duration": fmt_dur(bi.get("duration"))}
    lines = [f"{icon(status)} {job} #{number}  {status}  took {fmt_dur(bi.get('duration'))}  {url}"]
    code = RESULT_EXIT.get(status, 3)
    if status != "SUCCESS" and not args.no_diagnose:
        dd, dl = diagnose(cli, job, number)
        data["diagnose"] = dd
        lines += dl
    return data, lines, code


# ----------------------------------------------------------------- commands
def cmd_whoami(cli, a):
    me = cli.me
    ver = cli.server.get_version()
    jobs = cli.all_jobs()
    data = {"url": cli.url, "user": me.get("id"), "fullName": me.get("fullName"), "version": ver, "jobs": len(jobs),
            "running": sum(1 for j in jobs if (j.get("lastBuild") or {}).get("building"))}
    return data, [f"{data['url']}  Jenkins {ver}", f"user: {data['user']} ({data['fullName']})",
                  f"jobs: {data['jobs']}  running: {data['running']}"]


def cmd_jobs(cli, a):
    view, desc = None, ""
    if a.view:
        view = cli.resolve_view(a.view)
        jobs, desc = cli.view_jobs(view)
    else:
        jobs = cli.all_jobs()
    rx = re.compile(a.filter, re.I) if a.filter else None
    rows, data = [], []
    for j in jobs:
        lb = j.get("lastBuild")
        st = build_status(lb) if lb else color_status(j.get("color"))
        if "disabled" in (j.get("color") or ""):
            st = "DISABLED"
        if rx and not rx.search(j["fullName"]):
            continue
        if a.status and not status_match(a.status, st):
            continue
        data.append({"job": j["fullName"], "status": st, "last": (lb or {}).get("number"), "when": fmt_ts((lb or {}).get("timestamp")),
                     "duration": fmt_dur((lb or {}).get("duration")) if lb and not lb.get("building") else "-", "ts": (lb or {}).get("timestamp") or 0})
    data.sort(key=(lambda d: -d["ts"]) if a.sort == "time" else (lambda d: d["job"].lower()))
    total = len(data)
    if a.limit:
        data = data[:a.limit]
    for d in data:
        rows.append([icon(d["status"]), d["status"], d["job"], d["last"] or "-", d["when"], d["duration"]])
        d.pop("ts", None)
    lines = table(rows, ["", "STATUS", "JOB", "LAST#", "WHEN", "TOOK"])
    if view:
        lines.insert(0, f"view '{view}'" + (f" ({desc})" if desc else "") + f": {len(jobs)} job(s)")
    if a.limit and total > a.limit:
        lines.append(f"... {total - a.limit} more (use --limit 0 for all)")
    lines.append(f"{total} job(s)" + (" matched" if (rx or a.status) else ""))
    if a.json:
        return {"view": view, "description": desc, "jobs": data}, lines
    return data, lines


def color_status(color):
    if not color:
        return "UNKNOWN"
    if color.endswith("_anime"):
        return "RUNNING"
    return COLOR_STATUS.get(color, color.upper())


def status_match(want, st):
    want = want.lower()
    m = {"failed": "FAILURE", "failure": "FAILURE", "success": "SUCCESS", "ok": "SUCCESS", "unstable": "UNSTABLE",
         "aborted": "ABORTED", "running": "RUNNING", "building": "RUNNING", "disabled": "DISABLED", "notbuilt": "NOT_BUILT"}
    if want in ("bad", "broken", "notok"):
        return st in ("FAILURE", "UNSTABLE", "ABORTED")
    return m.get(want, want.upper()) == st


def cmd_views(cli, a):
    vs = cli.views()
    rows = [[v["view"] + (" (default)" if v["view"] == getattr(cli, "_primary_view", None) else ""), v["class"], v["jobs"], v["description"][:60], v["url"]] for v in vs]
    return vs, [f"views: {len(vs)}"] + table(rows, ["VIEW", "TYPE", "JOBS", "DESCRIPTION", "URL"])


def cmd_job(cli, a):
    job = cli.resolve_job(a.job)
    ji = cli.job_info(job, tree="description,disabled,buildable,inQueue,concurrentBuild,url,nextBuildNumber,healthReport[description,score],"
                                "lastBuild[number,result,building,timestamp,duration],lastSuccessfulBuild[number,timestamp],lastFailedBuild[number,timestamp],"
                                "lastStableBuild[number],lastCompletedBuild[number],builds[number,result,building,timestamp,duration]{0,10},"
                                "property[parameterDefinitions[name,type,defaultParameterValue[value],choices,description]]")
    defs = cli.param_defs(job) if any("parameterDefinitions" in p for p in ji.get("property", [])) else []
    data = {"job": job, "url": ji.get("url"), "description": ji.get("description"), "disabled": ji.get("disabled"), "inQueue": ji.get("inQueue"),
            "concurrentBuild": ji.get("concurrentBuild"), "nextBuildNumber": ji.get("nextBuildNumber"),
            "health": [h.get("description") for h in ji.get("healthReport", [])],
            "lastBuild": ji.get("lastBuild"), "lastSuccessfulBuild": (ji.get("lastSuccessfulBuild") or {}).get("number"),
            "lastFailedBuild": (ji.get("lastFailedBuild") or {}).get("number"), "params": defs,
            "recent": [{"number": b["number"], "status": build_status(b), "when": fmt_ts(b.get("timestamp")), "duration": fmt_dur(b.get("duration"))} for b in ji.get("builds", [])]}
    lb = ji.get("lastBuild") or {}
    lines = [f"{job}  ({'DISABLED' if ji.get('disabled') else 'enabled'}{', in queue' if ji.get('inQueue') else ''})  {ji.get('url')}"]
    if ji.get("description"):
        lines.append(f"   desc: {ji['description'][:300]}")
    lines.append(f"   last: #{lb.get('number', '-')} {build_status(lb) if lb else '-'} {fmt_ts(lb.get('timestamp'))}   "
                 f"lastSuccess: {'#' + str(data['lastSuccessfulBuild']) if data['lastSuccessfulBuild'] else '-'}   lastFailed: {'#' + str(data['lastFailedBuild']) if data['lastFailedBuild'] else '-'}   next: #{ji.get('nextBuildNumber')}")
    for h in data["health"]:
        lines.append(f"   health: {h}")
    if defs:
        lines.append("-- parameters")
        lines += ["   " + l for l in table([[d["name"], d["type"], str(d["default"])[:50], ("|".join(d["choices"]) if d["choices"] else "")[:40], d["description"][:50]] for d in defs],
                                          ["NAME", "TYPE", "DEFAULT", "CHOICES", "DESC"])]
    lines.append("-- recent builds")
    lines += ["   " + l for l in table([[icon(r["status"]), f"#{r['number']}", r["status"], r["when"], r["duration"]] for r in data["recent"]], ["", "#", "STATUS", "WHEN", "TOOK"])]
    return data, lines


def cmd_params(cli, a):
    job = cli.resolve_job(a.job)
    defs = cli.param_defs(job)
    if not defs:
        return [], [f"{job}: no parameters"]
    lines = table([[d["name"], d["type"], str(d["default"]), "|".join(d["choices"]) if d["choices"] else "", d["description"][:80]] for d in defs],
                  ["NAME", "TYPE", "DEFAULT", "CHOICES", "DESC"])
    return defs, lines


def cmd_builds(cli, a):
    job = cli.resolve_job(a.job)
    ji = cli.job_info(job, tree=f"builds[number,result,building,timestamp,duration,actions[causes[shortDescription]]]{{0,{a.limit}}}")
    data, rows = [], []
    for b in ji.get("builds", []):
        causes = [c.get("shortDescription") for act in b.get("actions", []) for c in act.get("causes", []) or []]
        st = build_status(b)
        data.append({"number": b["number"], "status": st, "when": fmt_ts(b.get("timestamp")), "duration": fmt_dur(b.get("duration")) if not b.get("building") else "-", "cause": "; ".join(causes)})
        rows.append([icon(st), f"#{b['number']}", st, data[-1]["when"], data[-1]["duration"], data[-1]["cause"][:60]])
    return data, [f"{job} recent builds:"] + table(rows, ["", "#", "STATUS", "WHEN", "TOOK", "CAUSE"])


def cmd_status(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    d = build_summary(cli, job, n)
    st = cli.stages(job, n)
    data = {"summary": d, "stages": [{"name": s["name"], "status": s["status"], "duration": fmt_dur(s.get("durationMillis"))} for s in (st or {}).get("stages", [])]}
    lines = summary_lines(d)
    if st:
        lines += ["-- stages"] + ["   " + l for l in table(stage_rows(st), ["", "STAGE", "STATUS", "TOOK", "ID"])]
    return data, lines


def cmd_stages(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    st = cli.stages(job, n)
    if not st:
        raise CliError(f"{job} #{n}: no stage data (not a pipeline build, or not started)")
    data = {"job": job, "number": n, "status": st.get("status"), "duration": fmt_dur(st.get("durationMillis")),
            "stages": [{"name": s["name"], "status": s["status"], "duration": fmt_dur(s.get("durationMillis")), "id": s["id"]} for s in st["stages"]]}
    lines = [f"{job} #{n}  {st.get('status')}  {fmt_dur(st.get('durationMillis'))}"] + table(stage_rows(st), ["", "STAGE", "STATUS", "TOOK", "ID"])
    if a.steps:
        detail = []
        for sg in st["stages"]:
            if a.steps == "failed" and sg["status"] in ("SUCCESS", "NOT_EXECUTED"):
                continue
            nd = cli.stage_nodes(job, n, sg["id"]) or {}
            steps = []
            lines.append(f"-- stage '{sg['name']}' {sg['status']}")
            for fn in nd.get("stageFlowNodes", []):
                err = (fn.get("error") or {}).get("message")
                steps.append({"id": fn["id"], "name": fn["name"], "status": fn["status"], "duration": fmt_dur(fn.get("durationMillis")), "error": err})
                lines.append(f"   [{fn['id']}] {icon(fn['status'])} {fn['name'][:70]}  {fn['status']}  {fmt_dur(fn.get('durationMillis'))}" + (f"  error: {err}" if err else ""))
                if a.log and fn["status"] not in ("SUCCESS", "NOT_EXECUTED"):
                    text, _ = cli.node_log(job, n, fn["id"])
                    lines += ["     | " + l for l in split_lines(text)[-a.log:]]
            detail.append({"stage": sg["name"], "status": sg["status"], "steps": steps})
        data["detail"] = detail
    return data, lines


def cmd_log(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    jp = cli.job_path(job)
    if a.follow:
        pos, more = 0, True
        while True:
            pos, more = stream_log(cli, job, n, pos)
            if not more:
                break
            time.sleep(a.poll)
        bi = cli.build_info(job, n, tree="result,building")
        return {"job": job, "number": n, "status": build_status(bi)}, []
    text = cli.console(job, n)
    if a.save:
        with open(os.path.expanduser(a.save), "w", encoding="utf-8") as f:
            f.write(text)
    all_lines = split_lines(text)
    total = len(all_lines)
    header = f"{job} #{n} console: {total} lines, {len(text)} bytes" + (f" (saved to {a.save})" if a.save else "")
    if a.errors:
        tot, hits = error_lines(text, a.limit)
        out = [(f"L{i}: {t}" if i else t) for i, t in hits]
        return {"job": job, "number": n, "total_lines": total, "error_total": tot, "errors": [{"line": i, "text": t} for i, t in hits if i]}, \
               [header, f"error-looking lines: showing {min(tot, a.limit) if a.limit else tot} of {tot}"] + out
    if a.grep:
        rx = re.compile(a.grep, re.I)
        idx = [i for i, l in enumerate(all_lines) if rx.search(l)]
        out, shown = [], set()
        for i in idx:
            for k in range(max(0, i - a.context), min(total, i + a.context + 1)):
                if k not in shown:
                    shown.add(k)
                    out.append(f"L{k + 1}{'>' if k == i else ':'} {all_lines[k][:400]}")
            if a.context and out and out[-1] != "--":
                out.append("--")
        note = ""
        if a.limit and len(idx) > a.limit:
            out = out[-(a.limit * (2 * a.context + 2)):]
            note = f" (showing last {a.limit}; --limit 0 for all)"
        return {"job": job, "number": n, "total_lines": total, "matches": len(idx), "lines": out}, [header, f"grep {a.grep!r}: {len(idx)} match(es){note}"] + out
    if a.full:
        sel = all_lines
    elif a.head:
        sel = all_lines[:a.head]
    else:
        sel = all_lines[-a.tail:] if a.tail else all_lines
    note = "" if len(sel) == total else f" (showing {'first' if a.head else 'last'} {len(sel)}; use --full / --save PATH / --grep for more)"
    return {"job": job, "number": n, "total_lines": total, "lines": sel}, [header + note] + sel


def cmd_diagnose(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    data, lines = diagnose(cli, job, n, step_tail=a.step_tail, err_limit=a.limit, console_tail=a.tail)
    return data, lines


def cmd_build(cli, a):
    job = cli.resolve_job(a.job)
    params = parse_params(a.param)
    data, lines, code = trigger_and_wait(cli, job, params, a)
    return data, lines, code


def cmd_rebuild(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    d = build_summary(cli, job, n)
    params = {k: ("" if v is None else str(v)) for k, v in d["params"].items()}
    for k, v in parse_params(a.param).items():
        params[k] = v
    eprint(f"rebuilding {job} #{n} with params: {params}")
    return trigger_and_wait(cli, job, params, a)


def cmd_wait(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    bi = wait_build(cli, job, n, a.timeout, a.poll, follow=a.follow)
    st = build_status(bi)
    data = {"job": job, "number": n, "status": st, "duration": fmt_dur(bi.get("duration")), "url": bi.get("url")}
    lines = [f"{icon(st)} {job} #{n}  {st}  took {fmt_dur(bi.get('duration'))}  {bi.get('url')}"]
    code = RESULT_EXIT.get(st, 3)
    if st != "SUCCESS" and not a.no_diagnose:
        dd, dl = diagnose(cli, job, n)
        data["diagnose"] = dd
        lines += dl
    return data, lines, code


def cmd_stop(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    bi = cli.build_info(job, n, tree="building,result,url")
    if not bi.get("building"):
        return {"job": job, "number": n, "status": build_status(bi)}, [f"{job} #{n} is not running ({build_status(bi)})"]
    cli.server.stop_build(job, n)
    time.sleep(2)
    bi = cli.build_info(job, n, tree="building,result,url")
    return {"job": job, "number": n, "status": build_status(bi)}, [f"stop requested: {job} #{n} -> {build_status(bi)}  {bi.get('url')}"]


def cmd_queue(cli, a):
    items = cli.server.get_queue_info()
    data, rows = [], []
    for it in items:
        params = {}
        for act in it.get("actions", []):
            if "parameters" in act:
                params = {p.get("name"): p.get("value") for p in act["parameters"]}
        d = {"id": it.get("id"), "job": (it.get("task") or {}).get("name"), "why": it.get("why"), "since": fmt_ts(it.get("inQueueSince")),
             "stuck": it.get("stuck"), "blocked": it.get("blocked"), "params": params}
        data.append(d)
        rows.append([d["id"], d["job"], d["since"], "STUCK" if d["stuck"] else ("blocked" if d["blocked"] else ""), (d["why"] or "")[:90]])
    return data, [f"queue: {len(items)} item(s)"] + table(rows, ["ID", "JOB", "SINCE", "", "WHY"])


def running_builds(cli):
    """Running builds keyed by URL. A pipeline occupies a flyweight slot on the built-in node plus a
    heavyweight executor on the agent; report the agent when there is one."""
    found = {}
    for c in cli.computers():
        builtin = c["displayName"] in ("Built-In Node", "master")
        for ex in (c.get("executors") or []) + (c.get("oneOffExecutors") or []):
            cur = ex.get("currentExecutable") or {}
            url = cur.get("url")
            m = re.search(r"/job/(.+?)/(\d+)/?$", url or "")
            if not m:
                continue
            if url in found and builtin:
                continue
            found[url] = {"job": m.group(1).replace("/job/", "/"), "number": int(m.group(2)), "node": c["displayName"],
                          "since": fmt_ts(cur.get("timestamp")), "elapsed": fmt_dur(time.time() * 1000 - cur["timestamp"]) if cur.get("timestamp") else "-",
                          "progress": ex.get("progress"), "url": url}
    return sorted(found.values(), key=lambda d: d["since"])


def cmd_running(cli, a):
    data = running_builds(cli)
    rows = [[f"{d['job']} #{d['number']}", d["node"], d["since"], d["elapsed"], f"{d['progress']}%" if d.get("progress", -1) >= 0 else ""] for d in data]
    return data, [f"running: {len(data)} build(s)"] + table(rows, ["BUILD", "NODE", "SINCE", "ELAPSED", "EST"])


def cmd_nodes(cli, a):
    data, rows = [], []
    for c in cli.computers():
        execs = c.get("executors") or []
        busy = sum(1 for e in execs if e.get("currentExecutable"))
        oneoff = sum(1 for e in (c.get("oneOffExecutors") or []) if e.get("currentExecutable"))
        state = "OFFLINE" if c.get("offline") else ("TEMP-OFFLINE" if c.get("temporarilyOffline") else "online")
        d = {"name": c["displayName"], "state": state, "busy": busy, "executors": c.get("numExecutors"), "oneoff": oneoff,
             "labels": [l["name"] for l in c.get("assignedLabels", []) if l["name"] != c["displayName"]], "offlineCause": c.get("offlineCauseReason") or ""}
        data.append(d)
        rows.append([("✖" if c.get("offline") else "●"), d["name"], state, f"{busy}/{c.get('numExecutors')}" + (f" +{oneoff} flyweight" if oneoff else ""),
                     ",".join(d["labels"])[:50], d["offlineCause"][:50]])
    return data, [f"nodes: {len(data)}"] + table(rows, ["", "NODE", "STATE", "BUSY", "LABELS", "OFFLINE CAUSE"])


def cmd_node(cli, a):
    name = a.name
    cands = [name]
    if name.lower() in ("master", "built-in", "built-in node", "(built-in)", "(master)"):
        cands = ["(built-in)", "(master)"]
    info = None
    for cnd in cands:
        try:
            info = cli.get_json(f"computer/{quote(cnd, safe='')}/api/json", {"depth": 1})
            break
        except jenkins.NotFoundException:
            continue
    if info is None:
        raise CliError(f"node not found: {name}")
    mon = info.get("monitorData") or {}
    d = {"name": info.get("displayName"), "offline": info.get("offline"), "temporarilyOffline": info.get("temporarilyOffline"),
         "offlineCause": info.get("offlineCauseReason"), "executors": info.get("numExecutors"), "idle": info.get("idle"),
         "labels": [l["name"] for l in info.get("assignedLabels", [])], "description": info.get("description"), "monitor": {}}
    for k, v in mon.items():
        key = k.split(".")[-1]
        if isinstance(v, dict):
            if "size" in v:
                d["monitor"][key] = f"{v['size'] / 2**30:.1f} GiB free" + (f" at {v.get('path')}" if v.get("path") else "")
            elif "availablePhysicalMemory" in v:
                d["monitor"][key] = f"phys {v['availablePhysicalMemory'] / 2**30:.1f}/{v['totalPhysicalMemory'] / 2**30:.1f} GiB, swap {v.get('availableSwapSpace', 0) / 2**30:.1f} GiB free"
            elif "average" in v:
                d["monitor"][key] = f"{v['average']} ms"
            elif "diff" in v:
                d["monitor"][key] = f"clock diff {v['diff']} ms"
        elif v is not None:
            d["monitor"][key] = str(v)[:80]
    d["running"] = [e["currentExecutable"].get("url") for e in (info.get("executors") or []) + (info.get("oneOffExecutors") or []) if e.get("currentExecutable")]
    lines = [f"{d['name']}  {'OFFLINE' if d['offline'] else 'online'}  executors {d['executors']}  idle={d['idle']}",
             f"   labels: {', '.join(d['labels'])}"]
    if d["offlineCause"]:
        lines.append(f"   offline cause: {d['offlineCause']}")
    for k, v in d["monitor"].items():
        lines.append(f"   {k}: {v}")
    for u in d["running"]:
        lines.append(f"   running: {u}")
    return d, lines


def parse_config_xml(xml):
    d = {"kind": "unknown", "inline_script": None, "scm": {}, "script_path": None, "lightweight": None, "disabled": None, "triggers": [], "params": [], "description": None}
    m = re.search(r'<definition class="([^"]+)"', xml)
    if m:
        cls = m.group(1)
        d["kind"] = "inline (CpsFlowDefinition)" if "CpsFlowDefinition" in cls else ("scm (CpsScmFlowDefinition)" if "Scm" in cls else cls)
    elif "<project>" in xml:
        d["kind"] = "freestyle"
    elif "multibranch" in xml.lower():
        d["kind"] = "multibranch"
    m = re.search(r"<script>(.*?)</script>", xml, re.S)
    if m:
        d["inline_script"] = html.unescape(m.group(1))
    m = re.search(r"<scriptPath>(.*?)</scriptPath>", xml)
    d["script_path"] = m.group(1) if m else None
    m = re.search(r"<lightweight>(.*?)</lightweight>", xml)
    d["lightweight"] = m.group(1) if m else None
    m = re.search(r"<disabled>(.*?)</disabled>", xml)
    d["disabled"] = m.group(1) if m else None
    m = re.search(r"<description>(.*?)</description>", xml, re.S)
    d["description"] = html.unescape(m.group(1)).strip() if m else None
    m = re.search(r"<scm class=\"([^\"]+)\".*?</scm>", xml, re.S)
    if m:
        blk = m.group(0)
        d["scm"] = {"class": m.group(1).split(".")[-1], "urls": re.findall(r"<url>(.*?)</url>", blk),
                    "branches": re.findall(r"<name>(.*?)</name>", blk), "credentialsId": (re.findall(r"<credentialsId>(.*?)</credentialsId>", blk) or [None])[0]}
    trig = re.search(r"<triggers>(.*?)</triggers>", xml, re.S)
    if trig:
        for t in re.findall(r"<([\w.]+Trigger)[ >](.*?)</\1>", trig.group(1), re.S):
            spec = re.search(r"<spec>(.*?)</spec>", t[1], re.S)
            d["triggers"].append({"type": t[0].split(".")[-1], "spec": spec.group(1).strip() if spec else ""})
        if not d["triggers"]:
            d["triggers"] = [{"type": x, "spec": ""} for x in re.findall(r"<([\w.]+)\b", trig.group(1))[:5]]
    for p in re.findall(r"<(hudson\.model\.\w+ParameterDefinition|[\w.]*ParameterDefinition)>(.*?)</\1>", xml, re.S):
        nm = re.search(r"<name>(.*?)</name>", p[1])
        dv = re.search(r"<defaultValue>(.*?)</defaultValue>", p[1], re.S)
        d["params"].append({"name": nm.group(1) if nm else "?", "type": p[0].split(".")[-1].replace("ParameterDefinition", ""), "default": html.unescape(dv.group(1)) if dv else None})
    return d


def cmd_config(cli, a):
    job = cli.resolve_job(a.job)
    xml = cli.server.get_job_config(job)
    if a.save:
        with open(os.path.expanduser(a.save), "w", encoding="utf-8") as f:
            f.write(xml)
    if a.xml:
        return {"job": job, "xml": xml}, [xml]
    d = parse_config_xml(xml)
    d["job"] = job
    if a.jenkinsfile:
        if d["inline_script"]:
            return d, [d["inline_script"]]
        return d, [f"{job}: pipeline script comes from SCM, not inline", f"   repo: {', '.join(d['scm'].get('urls', []))}",
                   f"   branches: {', '.join(d['scm'].get('branches', []))}", f"   scriptPath: {d['script_path']}   credentialsId: {d['scm'].get('credentialsId')}"]
    lines = [f"{job}  kind: {d['kind']}  disabled: {d['disabled']}" + (f"  (xml saved to {a.save})" if a.save else "")]
    if d["description"]:
        lines.append(f"   desc: {d['description'][:200]}")
    if d["scm"]:
        lines.append(f"   scm: {d['scm'].get('class')} {', '.join(d['scm'].get('urls', []))}  branches={', '.join(d['scm'].get('branches', []))}  "
                     f"scriptPath={d['script_path']}  lightweight={d['lightweight']}  credentialsId={d['scm'].get('credentialsId')}")
    if d["triggers"]:
        lines.append("   triggers: " + "; ".join(f"{t['type']} {t['spec']}".strip() for t in d["triggers"]))
    if d["params"]:
        lines.append("   params(xml): " + ", ".join(f"{p['name']}({p['type']})={str(p['default'])[:30]!r}" for p in d["params"]))
    if d["inline_script"]:
        sc = d["inline_script"]
        lines.append(f"-- inline pipeline script ({sc.count(chr(10)) + 1} lines; `config {job} --jenkinsfile` for full text)")
        lines += ["   | " + l for l in sc.splitlines()[:a.head]]
        if sc.count("\n") + 1 > a.head:
            lines.append("   | ...")
        libs = re.findall(r"@Library\(['\"]([^'\"]+)", sc)
        if libs:
            lines.append(f"   shared libraries: {', '.join(libs)}")
        style = "declarative" if DECLARATIVE_RE.search(sc) else "scripted"
        lines.append(f"   style: {style}")
    return d, lines


def cmd_lint(cli, a):
    src = a.target
    if os.path.isfile(os.path.expanduser(src)):
        text = open(os.path.expanduser(src), encoding="utf-8").read()
        label = src
    else:
        job = cli.resolve_job(src)
        d = parse_config_xml(cli.server.get_job_config(job))
        if not d["inline_script"]:
            raise CliError(f"{job}: script is in SCM ({d['script_path']}); pass the Jenkinsfile path instead")
        text, label = d["inline_script"], f"job {job} (inline script)"
    if not DECLARATIVE_RE.search(text):
        eprint("note: the Jenkins linter validates Declarative pipelines only; scripted pipelines will be reported as errors")
    errs = cli.server.check_jenkinsfile_syntax(text)
    flat = []
    for e in errs:
        v = e.get("error") if isinstance(e, dict) else e
        for x in (v if isinstance(v, list) else [v]):
            x = str(x)
            if "Jenkinsfile content" in x and "did not contain the 'pipeline' step" in x or x.startswith("Jenkinsfile content"):
                x = "not a Declarative pipeline (no top-level `pipeline {}` block); scripted pipelines cannot be linted server-side"
            flat.append(x[:400])
    if not flat:
        return {"target": label, "ok": True, "errors": []}, [f"{label}: OK (declarative syntax valid)"]
    return {"target": label, "ok": False, "errors": flat}, [f"{label}: {len(flat)} error(s)"] + [f"   ✖ {x}" for x in flat]


def cmd_test_report(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    try:
        rep = cli.get_json(f"{cli.job_path(job)}/{n}/testReport/api/json",
                           {"tree": "failCount,passCount,skipCount,totalCount,suites[name,cases[className,name,status,duration,errorDetails,errorStackTrace]]"})
    except jenkins.NotFoundException:
        return {"job": job, "number": n, "report": None}, [f"{job} #{n}: no test report"]
    failed = []
    for s in rep.get("suites", []):
        for c in s.get("cases", []):
            if c.get("status") in ("FAILED", "REGRESSION"):
                failed.append({"test": f"{c.get('className')}.{c.get('name')}", "status": c["status"], "duration": c.get("duration"),
                               "error": (c.get("errorDetails") or "").strip().splitlines()[:1], "trace": (c.get("errorStackTrace") or "")[:a.trace] if a.trace else ""})
    passed = rep.get("passCount", 0)
    data = {"job": job, "number": n, "total": rep.get("totalCount", passed + rep.get("failCount", 0) + rep.get("skipCount", 0)), "passed": passed,
            "failed": rep.get("failCount"), "skipped": rep.get("skipCount"), "failures": failed[:a.limit] if a.limit else failed}
    lines = [f"{job} #{n} tests: total {data['total']}  passed {passed}  failed {data['failed']}  skipped {data['skipped']}"]
    for f in data["failures"]:
        lines.append(f"   ✖ {f['test']}  ({f['status']})" + (f": {f['error'][0][:200]}" if f["error"] else ""))
        if f["trace"]:
            lines += ["     | " + l for l in f["trace"].splitlines()]
    if a.limit and len(failed) > a.limit:
        lines.append(f"   ... {len(failed) - a.limit} more failures (--limit 0 for all)")
    return data, lines


def cmd_changes(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    bi = cli.build_info(job, n, tree="changeSets[kind,items[commitId,msg,author[fullName],timestamp,affectedPaths]],culprits[fullName]")
    data = []
    for cs in bi.get("changeSets", []):
        for it in cs.get("items", []):
            data.append({"sha": (it.get("commitId") or "")[:10], "author": (it.get("author") or {}).get("fullName"), "when": fmt_ts(it.get("timestamp")),
                         "msg": (it.get("msg") or "").strip().splitlines()[0][:120] if it.get("msg") else "", "files": len(it.get("affectedPaths", []))})
    rows = [[d["sha"], d["author"], d["when"], d["files"], d["msg"]] for d in data]
    lines = [f"{job} #{n} changes: {len(data)} commit(s)" + (f"  culprits: {', '.join(c['fullName'] for c in bi.get('culprits', []))}" if bi.get("culprits") else "")]
    return data, lines + table(rows, ["SHA", "AUTHOR", "WHEN", "FILES", "MESSAGE"])


def cmd_artifacts(cli, a):
    job = cli.resolve_job(a.job)
    n = cli.resolve_build(job, a.build)
    bi = cli.build_info(job, n, tree="artifacts[fileName,relativePath],url")
    arts = bi.get("artifacts", [])
    data = [{"file": x["fileName"], "path": x["relativePath"], "url": f"{bi['url']}artifact/{x['relativePath']}"} for x in arts]
    lines = [f"{job} #{n}: {len(arts)} artifact(s)"] + [f"   {d['path']}  {d['url']}" for d in data]
    if a.download:
        os.makedirs(os.path.expanduser(a.download), exist_ok=True)
        for d in data:
            dest = os.path.join(os.path.expanduser(a.download), d["path"].replace("/", "_"))
            with open(dest, "wb") as f:
                f.write(cli.server.get_build_artifact_as_bytes(job, n, d["path"]))
            d["saved"] = dest
            lines.append(f"   saved -> {dest}")
    return data, lines


def cmd_cancel_queue(cli, a):
    cli.server.cancel_queue(a.id)
    left = [it["id"] for it in cli.server.get_queue_info()]
    ok = a.id not in left
    return {"id": a.id, "cancelled": ok}, [f"queue item {a.id}: {'cancelled' if ok else 'still in queue'}"]


def cmd_enable(cli, a):
    job = cli.resolve_job(a.job)
    (cli.server.disable_job if a.cmd == "disable" else cli.server.enable_job)(job)
    dis = cli.job_info(job, tree="disabled").get("disabled")
    return {"job": job, "disabled": dis}, [f"{job}: {'DISABLED' if dis else 'enabled'}"]


def cmd_api(cli, a):
    path = a.path.lstrip("/")
    data = parse_params(a.data) if a.data else None
    r = cli.req("POST" if a.post or data else "GET", path, data=data)
    ct = r.headers.get("Content-Type", "")
    if "json" in ct:
        try:
            j = r.json()
            return j, [json.dumps(j, ensure_ascii=False, indent=2)[:a.max]]
        except ValueError:
            pass
    return {"status": r.status_code, "text": r.text[:a.max]}, [f"HTTP {r.status_code} {ct}", r.text[:a.max]]


# ----------------------------------------------------------------- main
def load_config(path):
    p = os.path.expanduser(path or os.environ.get("PYJENKINS_CONFIG") or CONFIG_DEFAULT)
    if not os.path.isfile(p):
        raise CliError(f"config not found: {p}\nexpected JSON: {{\"JENKINS_URL\": \"https://...\", \"JENKINS_USERNAME\": \"...\", \"JENKINS_API_TOKEN\": \"...\"}}")
    with open(p, encoding="utf-8") as f:
        cfg = json.load(f)
    # accept lowercase / alternate keys too
    norm = {k.upper(): v for k, v in cfg.items()}
    alias = {"URL": "JENKINS_URL", "USER": "JENKINS_USERNAME", "USERNAME": "JENKINS_USERNAME", "JENKINS_USER": "JENKINS_USERNAME",
             "TOKEN": "JENKINS_API_TOKEN", "API_TOKEN": "JENKINS_API_TOKEN", "JENKINS_TOKEN": "JENKINS_API_TOKEN", "PASSWORD": "JENKINS_API_TOKEN"}
    for k, v in list(norm.items()):
        norm.setdefault(alias.get(k, k), v)
    missing = [k for k in ("JENKINS_URL", "JENKINS_USERNAME", "JENKINS_API_TOKEN") if not norm.get(k)]
    if missing:
        raise CliError(f"config {p} missing keys: {', '.join(missing)}")
    return norm


def build_parser():
    p = argparse.ArgumentParser(prog="jenkins_cli.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help=f"config JSON path (default {CONFIG_DEFAULT})")
    p.add_argument("--json", action="store_true", help="machine-readable JSON on stdout")
    p.add_argument("--http-timeout", type=float, default=60, help="per-request timeout seconds")
    sp = p.add_subparsers(dest="cmd", required=True, metavar="<cmd>")

    def add(name, fn, help, **kw):
        s = sp.add_parser(name, help=help, description=help, **kw)
        s.set_defaults(fn=fn)
        return s

    def job_build(s, build_help="build number | -N | last | lastFailed | lastSuccessful | lastCompleted (default last)"):
        s.add_argument("job", help="job name (folder/job) or any Jenkins URL of the job/build; case-insensitive / unique-substring match allowed")
        s.add_argument("build", nargs="?", help=build_help)

    def wait_opts(s):
        s.add_argument("--timeout", type=float, default=1800, help="max seconds to wait (default 1800)")
        s.add_argument("--poll", type=float, default=10, help="poll interval seconds (default 10)")
        s.add_argument("--follow", action="store_true", help="stream console output while waiting instead of stage progress")
        s.add_argument("--no-diagnose", action="store_true", help="do not print failure diagnosis when result != SUCCESS")

    add("whoami", cmd_whoami, "connection check: user, Jenkins version, job count")
    s = add("jobs", cmd_jobs, "list jobs with last-build status; optionally only those in a view")
    s.add_argument("view", nargs="?", help="view name or view URL (e.g. https://host/view/Team%%20A/); omit for all jobs")
    s.add_argument("--filter", "-f", help="regex on job name (case-insensitive)")
    s.add_argument("--status", "-s", help="failed|success|unstable|aborted|running|disabled|notbuilt|bad (bad = failed+unstable+aborted)")
    s.add_argument("--sort", choices=["name", "time"], default="name", help="sort by name or last build time (desc)")
    s.add_argument("--limit", "-n", type=int, default=0, help="max rows (0 = all)")
    add("views", cmd_views, "list views (dashboards) and how many jobs each contains")
    s = add("job", cmd_job, "job details: state, parameters, health, recent builds")
    s.add_argument("job")
    s = add("params", cmd_params, "build parameters of a job")
    s.add_argument("job")
    s = add("builds", cmd_builds, "recent build history of a job")
    s.add_argument("job")
    s.add_argument("--limit", "-n", type=int, default=15)
    s = add("status", cmd_status, "build summary (result, cause, params, git, stages)")
    job_build(s)
    s = add("stages", cmd_stages, "pipeline stages of a build (wfapi); --steps for step-level detail")
    job_build(s)
    s.add_argument("--steps", nargs="?", const="failed", choices=["failed", "all"], help="show steps of failed (default) or all stages")
    s.add_argument("--log", type=int, metavar="N", help="with --steps: include last N log lines of non-success steps")
    s = add("log", cmd_log, "console log of a build (default: last 200 lines)")
    job_build(s)
    s.add_argument("--tail", type=int, default=200, help="last N lines (default 200, 0 = all)")
    s.add_argument("--head", type=int, help="first N lines")
    s.add_argument("--full", action="store_true", help="entire log")
    s.add_argument("--grep", "-g", help="regex (case-insensitive) with -C context")
    s.add_argument("-C", "--context", type=int, default=2)
    s.add_argument("--errors", action="store_true", help="only error-looking lines")
    s.add_argument("--limit", type=int, default=60, help="max matches for --errors/--grep (0 = all)")
    s.add_argument("--save", metavar="PATH", help="write full log to file")
    s.add_argument("--follow", action="store_true", help="stream a running build's log until it finishes")
    s.add_argument("--poll", type=float, default=3)
    s = add("diagnose", cmd_diagnose, "why did a build fail: failed stage/step + step log + error lines + hints")
    job_build(s, "build number | last | lastFailed ... (default last)")
    s.add_argument("--step-tail", type=int, default=40, help="log lines per failed step (default 40)")
    s.add_argument("--limit", type=int, default=25, help="error-looking lines to show (default 25)")
    s.add_argument("--tail", type=int, default=15, help="console tail lines (default 15)")
    s = add("build", cmd_build, "trigger a build, wait for it, diagnose on failure (exit 0/2/3/4)")
    s.add_argument("job")
    s.add_argument("-p", "--param", action="append", metavar="KEY=VALUE", help="build parameter (repeatable; VALUE=@file reads a file)")
    s.add_argument("--no-wait", dest="wait", action="store_false", help="return once the build number is known")
    wait_opts(s)
    s = add("rebuild", cmd_rebuild, "re-run a build with the same parameters (override with -p)")
    job_build(s)
    s.add_argument("-p", "--param", action="append", metavar="KEY=VALUE")
    s.add_argument("--no-wait", dest="wait", action="store_false")
    wait_opts(s)
    s = add("wait", cmd_wait, "wait for a running build to finish, diagnose on failure")
    job_build(s)
    wait_opts(s)
    s = add("stop", cmd_stop, "abort a running build")
    job_build(s)
    add("queue", cmd_queue, "build queue (what is waiting and why)")
    add("running", cmd_running, "currently running builds and their agents")
    add("nodes", cmd_nodes, "agent nodes: online/offline, executor usage, labels")
    s = add("node", cmd_node, "one node's detail: disk/memory/clock monitors, running builds")
    s.add_argument("name", help="node name, or 'master' / 'built-in'")
    s = add("config", cmd_config, "pipeline definition: inline script or SCM source, triggers, params")
    s.add_argument("job")
    s.add_argument("--jenkinsfile", action="store_true", help="print only the inline pipeline script (or SCM pointer)")
    s.add_argument("--xml", action="store_true", help="raw config.xml")
    s.add_argument("--save", metavar="PATH", help="write config.xml to file")
    s.add_argument("--head", type=int, default=40, help="script preview lines in summary (default 40)")
    s = add("lint", cmd_lint, "validate a Declarative Jenkinsfile (file path or job name with inline script)")
    s.add_argument("target", help="Jenkinsfile path, or job name")
    s = add("test-report", cmd_test_report, "JUnit summary and failed test cases")
    job_build(s)
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--trace", type=int, default=0, help="chars of stack trace per failure (0 = none)")
    s = add("changes", cmd_changes, "SCM commits included in a build")
    job_build(s)
    s = add("artifacts", cmd_artifacts, "list (and optionally download) build artifacts")
    job_build(s)
    s.add_argument("--download", metavar="DIR")
    s = add("cancel-queue", cmd_cancel_queue, "cancel a queued (not yet started) item by queue id")
    s.add_argument("id", type=int)
    s = add("enable", cmd_enable, "enable a job")
    s.add_argument("job")
    s = add("disable", cmd_enable, "disable a job")
    s.add_argument("job")
    s = add("api", cmd_api, "raw REST call, path relative to server root (e.g. 'api/json?tree=jobs[name]')")
    s.add_argument("path")
    s.add_argument("--post", action="store_true")
    s.add_argument("-d", "--data", action="append", metavar="KEY=VALUE", help="form field (implies POST)")
    s.add_argument("--max", type=int, default=20000, help="max chars to print")
    return p


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    code = 0
    try:
        cfg = load_config(args.config)
        cli = Cli(cfg, args.http_timeout)
        res = args.fn(cli, args)
        data, lines = res[0], res[1]
        if len(res) > 2:
            code = res[2]
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        else:
            for l in lines:
                print(l)
    except CliError as e:
        eprint(f"ERROR: {e}")
        return e.code
    except jenkins.NotFoundException as e:
        eprint(f"ERROR: not found: {e}")
        return 1
    except jenkins.JenkinsException as e:
        msg = str(e)
        if "authentication failed" in msg.lower() or "[401]" in msg or "[403]" in msg:
            msg = msg.splitlines()[0] + "  (check JENKINS_USERNAME / JENKINS_API_TOKEN in the config file, or job permissions)"
        eprint(f"ERROR: {msg[:1500]}")
        return 1
    except requests.exceptions.HTTPError as e:
        body = (e.response.text or "")[:500] if e.response is not None else ""
        eprint(f"ERROR: HTTP {e.response.status_code if e.response is not None else '?'} {e}\n{body}")
        return 1
    except requests.exceptions.RequestException as e:
        eprint(f"ERROR: connection: {e}")
        return 1
    except KeyboardInterrupt:
        eprint("interrupted")
        return 130
    return code


if __name__ == "__main__":
    sys.exit(main())
