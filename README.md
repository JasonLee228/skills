# skills

개인 에이전트 스킬 모음이다. 각 스킬은 `skills/<name>/SKILL.md`로 시작한다. English: [README.en.md](README.en.md)

| 스킬 | 설명 |
|---|---|
| [document-driven-development](skills/document-driven-development/README.md) | 설계 문서로 승인된 계약을, 구현 기록으로 실제 증거를 남기는 문서 주도 개발 절차. 로드맵 기반 Task 번호, 승인 게이트, SubAgent 위임·수용, 검증·리뷰·stage 규칙 포함 |

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

복사 뒤 `SKILL.md`의 상대 링크(`references/`, `templates/`)가 함께 왔는지 확인한다.

## 라이선스

[MIT](LICENSE)
