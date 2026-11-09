# Docmost API Reference

## Auth

Primary mode follows `mcp-docmost`:

- `DOCMOST_URL` or `DOCMOST_BASE_URL`: Docmost base URL without `/api`
- `DOCMOST_AUTH_TOKEN`: Docmost auth token/JWT
- Request header: `Cookie: authToken=<token>`

Login fallback:

- `DOCMOST_EMAIL`
- `DOCMOST_PASSWORD`
- The helper calls `POST /api/auth/login`, extracts `authToken` from `Set-Cookie`, then uses the cookie for later requests.

Never echo secrets. If credentials are missing, ask user to set env vars or provide an env file path.

## Response Shape

Most Docmost endpoints return `{ success, status, data }`. List endpoints usually return `data.items` and `data.meta`.

## Naming Rules

MCP and CLI flags use snake_case or kebab-case. Docmost API payloads use camelCase.

- `space_id` / `--space-id` -> `spaceId`
- `page_id` / `--page-id` -> `pageId`
- `parent_page_id` / `--parent-page-id` -> `parentPageId`
- `include_child_pages` / `--include-child-pages` -> `includeChildPages`

## Copy Link Resolution

For `https://docs.example.com/s/space/p/page-title-K3aB9xZ1pQ`:

1. Use URL origin as base URL for that request.
2. Strip query and hash.
3. Take final path segment.
4. Use substring after the last `-` as slugId.
5. Send that slugId as `pageId`.

Docmost accepts slugId or UUID in most page endpoints. File upload can require UUID, so resolve with `pages/info` first.

## Page Content

Use `POST /api/pages/update` for title and body updates.

Title payload:

```json
{ "pageId": "...", "title": "New title" }
```

Markdown payload:

```json
{
  "pageId": "...",
  "content": "# Heading\n\nBody",
  "format": "markdown",
  "operation": "replace"
}
```

Default to `markdown` + `replace` unless user asks otherwise. Allowed operations are `replace`, `append`, and `prepend`.

## Create vs Import

`pages/create` creates a page shell. For rich markdown content, either create then update with markdown content, or use multipart `pages/import`.

Prefer `import-page` for one-shot markdown file publishing.

## Export

`pages/export` and `spaces/export` return zip bytes. The helper extracts text files from the archive and prints markdown/html contents.

## Destructive Operations

Require explicit user intent before `pages/delete`, `spaces/delete`, `groups/delete`, `shares/delete`, and member removal operations.

The helper requires `--yes` for built-in delete commands. For raw calls, confirm in the conversation first.

## MCP Mapping

Use `endpoints.json` for MCP tool name to REST endpoint mapping. It mirrors `mcp-docmost` v1 behavior.

## Unsupported in v1

This skill excludes Excalidraw generation/readback and direct WebSocket/Yjs editing. REST markdown update is sufficient for normal documentation work.

