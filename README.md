# skills

개인 에이전트 스킬 모음이다. 각 스킬은 `skills/<name>/SKILL.md`로 시작한다. English: [README.en.md](README.en.md)

| 스킬 | 설명 |
|---|---|
| [document-driven-development](skills/document-driven-development/README.md) | 설계 문서로 승인된 계약을, 구현 기록으로 실제 증거를 남기는 문서 주도 개발 절차. 로드맵 기반 Task 번호, 승인 게이트, SubAgent 위임·수용, 검증·리뷰·stage 규칙 포함 |
| [java-testability-guardrails](skills/java-testability-guardrails/SKILL.md) | 테스트 편의로 Java 접근제한자를 넓히거나 테스트 전용 helper·`@VisibleForTesting`을 추가하지 않게 막는 규칙 |
| [java-comment-reviewer](skills/java-comment-reviewer/SKILL.md) | Java 변경분의 Javadoc·inline comment·논리적 빈 줄을 readonly로 검토. 기준 규칙 2종을 `references/`에 동봉 |
| [docmost-api](skills/docmost-api/SKILL.md) | Docmost REST API를 MCP 없이 직접 호출하는 Node 스크립트와 엔드포인트 참조. 페이지·스페이스·댓글·공유·파일 처리 |
| [api-documentation-manager](skills/api-documentation-manager/SKILL.md) | 백엔드(Spring 등) 컨트롤러 소스를 분석해 Docusaurus API 명세 문서를 신규 작성·업데이트·리팩토링 |
| [pyjenkins](skills/pyjenkins/SKILL.md) | python-jenkins 기반 CLI로 Jenkins 잡 실행·대기·실패 진단·콘솔 로그·스테이지 분석·노드/큐 점검. 자격증명은 `~/.config/pyjenkins.json` |

## 설치

스킬 폴더를 에이전트가 읽는 skills 디렉터리에 복사한다.

```bash
git clone https://github.com/JasonLee228/skills.git
```

| 대상 | 경로 |
|---|---|
| Claude Code (프로젝트) | `<project>/.claude/skills/<name>/` |
| Claude Code (전역) | `~/.claude/skills/<name>/` |
| Cursor | `<project>/.cursor/skills/<name>/` |
| Codex | `~/.codex/skills/<name>/` |

```bash
cp -r skills/skills/document-driven-development ~/.claude/skills/
```

복사 뒤 `SKILL.md`의 상대 링크(`references/`, `templates/`, `scripts/`)가 함께 왔는지 확인한다. `pyjenkins`는 `uv`(또는 `python-jenkins` 설치), `docmost-api`는 Node 18+가 필요하다.

## 라이선스

[MIT](LICENSE)
