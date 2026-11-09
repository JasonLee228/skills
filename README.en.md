# skills

Personal agent skills. Each skill starts at `skills/<name>/SKILL.md`. The skill documents are written in Korean.

| Skill | Description |
|---|---|
| [document-driven-development](skills/document-driven-development/README.md) | Document-driven development: the plan keeps the approved contract and reasons, the implementation record keeps the current state and real evidence. Includes roadmap-based task numbers, approval gates, sub-agent delegation and acceptance, and verification, review and stage rules |
| [java-testability-guardrails](skills/java-testability-guardrails/SKILL.md) | Stops widening Java access modifiers or adding test-only helpers and `@VisibleForTesting` for test convenience |
| [java-comment-reviewer](skills/java-comment-reviewer/SKILL.md) | Read-only review of Javadoc, inline comments and logical blank lines in changed Java code. Ships its two base rule files in `references/` |
| [docmost-api](skills/docmost-api/SKILL.md) | Node script and endpoint reference to call the Docmost REST API directly, without MCP: pages, spaces, comments, shares, files |
| [api-documentation-manager](skills/api-documentation-manager/SKILL.md) | Reads backend (Spring etc.) controller source and creates, updates or refactors Docusaurus API spec documents |
| [pyjenkins](skills/pyjenkins/SKILL.md) | python-jenkins based CLI: run and wait for Jenkins jobs, diagnose failures, read console logs, analyze stages, check nodes and queue. Credentials in `~/.config/pyjenkins.json` |

## Install

Copy a skill folder into the skills directory your agent reads.

```bash
git clone https://github.com/JasonLee228/skills.git
```

| Target | Path |
|---|---|
| Claude Code (project) | `<project>/.claude/skills/<name>/` |
| Claude Code (global) | `~/.claude/skills/<name>/` |
| Cursor | `<project>/.cursor/skills/<name>/` |
| Codex | `~/.codex/skills/<name>/` |

```bash
cp -r skills/skills/document-driven-development ~/.claude/skills/
```

After the copy, check that the relative links in `SKILL.md` (`references/`, `templates/`, `scripts/`) came with it. `pyjenkins` needs `uv` (or `python-jenkins` installed); `docmost-api` needs Node 18+.

## License

[MIT](LICENSE)
