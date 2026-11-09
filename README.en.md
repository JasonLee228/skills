# skills

Personal agent skills. Each skill starts at `skills/<name>/SKILL.md`. The skill documents are written in Korean.

| Skill | Description |
|---|---|
| [document-driven-development](skills/document-driven-development/README.md) | Document-driven development: the plan keeps the approved contract and reasons, the implementation record keeps the current state and real evidence. Includes roadmap-based task numbers, approval gates, sub-agent delegation and acceptance, and verification, review and stage rules |

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

After the copy, check that the relative links in `SKILL.md` (`references/`, `templates/`) came with it.

## License

[MIT](LICENSE)
