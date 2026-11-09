---
name: docmost-api
description: Use Docmost REST API directly without relying on MCP. Use when working with Docmost API, Docmost pages, spaces, comments, groups, shares, files, Docmost Copy link URLs, or when Docmost MCP is unavailable and documentation pages must be searched, created, read, updated, imported, exported, or deleted.
version: 1.0.0
---

# Docmost API

Use this skill to operate Docmost through REST API directly. Prefer MCP when user explicitly asks for MCP; otherwise this skill can stand alone.

## Quick Start

Use the helper script:

```bash
node <skill-dir>/scripts/docmost-api.mjs --help   # <skill-dir>: 이 스킬이 설치된 폴더, 예: ~/.claude/skills/docmost-api
```

Set credentials with environment variables:

```bash
DOCMOST_URL=https://docmost.example.com
DOCMOST_AUTH_TOKEN=<authToken>
```

`DOCMOST_BASE_URL` is also accepted as an alias for `DOCMOST_URL`.

Optional login fallback is supported:

```bash
DOCMOST_URL=https://docmost.example.com
DOCMOST_EMAIL=user@example.com
DOCMOST_PASSWORD=<password>
```

## Workflow

1. Read `reference.md` when task needs more than simple page CRUD.
2. Read `endpoints.json` when mapping MCP-style tool names to REST endpoints.
3. Use `scripts/docmost-api.mjs` for actual calls when possible.
4. For destructive commands, require explicit user intent and pass `--yes`.
5. Never print tokens or passwords.

## Common Commands

```bash
node scripts/docmost-api.mjs health
node scripts/docmost-api.mjs version
node scripts/docmost-api.mjs search --query "API 명세서"
node scripts/docmost-api.mjs spaces
node scripts/docmost-api.mjs pages --space-id <spaceId>
node scripts/docmost-api.mjs get-page --url <docmost-copy-link> --format markdown
node scripts/docmost-api.mjs create-page --space-id <spaceId> --title "Page title" --file page.md
node scripts/docmost-api.mjs update-page --url <docmost-copy-link> --file page.md --operation replace
node scripts/docmost-api.mjs import-page --space-id <spaceId> --file page.md
node scripts/docmost-api.mjs export-page --url <docmost-copy-link> --format markdown
```

## Page Rules

- Prefer `--url` or `--page-id` over title lookup. Copy link URLs are parsed to slugId.
- `pages/update` with content must include `format` and `operation`. Defaults are `markdown` and `replace`.
- Use `operation append` or `prepend` only when requested.
- For one-shot markdown page creation with rich content, `import-page` is often safest.
- `delete-page`, `delete-space`, and share revoke operations require explicit confirmation.

## Scope

This skill covers Docmost search, pages, spaces, comments, groups, shares, users, workspace, files, health, and version endpoints.

Excalidraw build/add/read is not included in v1. Use a dedicated Excalidraw workflow if needed.

