#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { inflateRawSync } from "node:zlib";

const TEXT_EXTENSIONS = new Set([".md", ".markdown", ".txt", ".html", ".json", ".csv", ".xml", ".yaml", ".yml"]);

function printHelp() {
  console.log(`Docmost API helper

Usage:
  node docmost-api.mjs <command> [options]

Auth:
  DOCMOST_URL or DOCMOST_BASE_URL
  DOCMOST_AUTH_TOKEN

  Fallback login:
  DOCMOST_EMAIL
  DOCMOST_PASSWORD

Global:
  --env <file>                 Load key=value env file
  --json                       Print raw JSON where supported

Commands:
  health
  version
  search --query <text> [--space-id <id>] [--limit 20] [--offset 0]
  suggest --query <text>
  spaces [--limit 50] [--cursor <cursor>]
  pages --space-id <id> [--parent-page-id <id>]
  get-page (--page-id <id> | --url <copy-link>) [--format markdown|html|json] [--content] [--json]
  create-page --space-id <id> --title <title> [--parent-page-id <id>] [--content <text> | --file <path>]
  update-page (--page-id <id> | --url <copy-link>) [--title <title>] [--content <text> | --file <path>] [--format markdown] [--operation replace|append|prepend]
  delete-page (--page-id <id> | --url <copy-link>) --yes
  restore-page (--page-id <id> | --url <copy-link>)
  import-page --space-id <id> --file <path> [--parent-page-id <id>]
  export-page (--page-id <id> | --url <copy-link>) [--format markdown|html]
  export-space --space-id <id> [--format markdown|html] [--include-attachments]
  upload-file (--page-id <id> | --url <copy-link>) --file <path>
  raw --method GET|POST --endpoint <api/path> [--body '{"key":"value"}']

Examples:
  node docmost-api.mjs search --query "API 명세서"
  node docmost-api.mjs get-page --url "https://docs/s/x/p/title-AbCd" --format markdown
  node docmost-api.mjs update-page --page-id AbCd --file page.md --operation replace
`);
}

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      out._.push(token);
      continue;
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      out[key] = true;
      continue;
    }
    out[key] = next;
    i += 1;
  }
  return out;
}

function loadEnvFile(filePath) {
  const resolved = path.resolve(filePath);
  const text = fs.readFileSync(resolved, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [key, ...rest] = trimmed.split("=");
    if (!process.env[key.trim()]) {
      process.env[key.trim()] = rest.join("=").trim();
    }
  }
}

function required(args, name) {
  const value = args[name];
  if (value === undefined || value === true || value === "") {
    throw new Error(`Missing required option: --${name}`);
  }
  return value;
}

function optionalInt(args, name, fallback) {
  if (args[name] === undefined || args[name] === true) return fallback;
  const value = Number.parseInt(args[name], 10);
  if (Number.isNaN(value)) throw new Error(`--${name} must be an integer`);
  return value;
}

function readContentArg(args) {
  if (args.file) return fs.readFileSync(path.resolve(args.file), "utf8");
  if (args.content !== undefined && args.content !== true) return args.content;
  return undefined;
}

function parseCopyLink(url) {
  const parsed = new URL(url);
  const finalSegment = parsed.pathname.replace(/\/$/, "").split("/").pop();
  if (!finalSegment) throw new Error(`Cannot extract page slug from URL: ${url}`);
  const slugId = finalSegment.split("-").pop();
  if (!slugId) throw new Error(`Cannot extract page slug from URL: ${url}`);
  return { baseUrl: `${parsed.protocol}//${parsed.host}`, pageId: slugId };
}

function targetPage(args) {
  if (args.url && args.url !== true) return parseCopyLink(args.url);
  if (args["page-id"] && args["page-id"] !== true) return { pageId: args["page-id"] };
  throw new Error("Provide --page-id or --url");
}

function trimApiEndpoint(endpoint) {
  return endpoint.replace(/^\/+/, "").replace(/^api\//, "");
}

function printJson(value) {
  console.log(JSON.stringify(value, null, 2));
}

function unwrap(resp) {
  return resp?.data ?? resp;
}

function extractText(node) {
  if (!node) return "";
  if (typeof node === "string") return node;
  const parts = [];
  if (node.text) parts.push(node.text);
  if (Array.isArray(node.content)) {
    for (const child of node.content) {
      const text = extractText(child);
      if (text) parts.push(text);
    }
  }
  return parts.join(" ");
}

function formatPage(page) {
  const lines = [
    `Title: ${page.title || "Untitled"}`,
    `ID: ${page.id || ""}`,
    `Slug: ${page.slugId || ""}`,
    `Space ID: ${page.spaceId || ""}`,
    `Created: ${page.createdAt || ""}`,
    `Updated: ${page.updatedAt || ""}`,
  ];
  if (page.parentPageId) lines.push(`Parent: ${page.parentPageId}`);
  return lines.filter((line) => !line.endsWith(": ")).join("\n");
}

function extractZipTexts(zipBuffer) {
  const files = [];
  let eocdOffset = -1;
  for (let i = zipBuffer.length - 22; i >= 0; i -= 1) {
    if (zipBuffer.readUInt32LE(i) === 0x06054b50) {
      eocdOffset = i;
      break;
    }
  }
  if (eocdOffset < 0) return files;

  const cdOffset = zipBuffer.readUInt32LE(eocdOffset + 16);
  const cdEntries = zipBuffer.readUInt16LE(eocdOffset + 10);
  let pos = cdOffset;

  for (let i = 0; i < cdEntries; i += 1) {
    if (zipBuffer.readUInt32LE(pos) !== 0x02014b50) break;
    const compMethod = zipBuffer.readUInt16LE(pos + 10);
    const compSize = zipBuffer.readUInt32LE(pos + 20);
    const uncompSize = zipBuffer.readUInt32LE(pos + 24);
    const nameLen = zipBuffer.readUInt16LE(pos + 28);
    const extraLen = zipBuffer.readUInt16LE(pos + 30);
    const commentLen = zipBuffer.readUInt16LE(pos + 32);
    const localHeaderOffset = zipBuffer.readUInt32LE(pos + 42);
    const fileName = zipBuffer.subarray(pos + 46, pos + 46 + nameLen).toString("utf8");
    const localNameLen = zipBuffer.readUInt16LE(localHeaderOffset + 26);
    const localExtraLen = zipBuffer.readUInt16LE(localHeaderOffset + 28);
    const dataStart = localHeaderOffset + 30 + localNameLen + localExtraLen;
    const ext = path.extname(fileName).toLowerCase();

    try {
      if (TEXT_EXTENSIONS.has(ext)) {
        if (compMethod === 0 && uncompSize > 0) {
          files.push({ name: fileName, content: zipBuffer.subarray(dataStart, dataStart + uncompSize).toString("utf8") });
        } else if (compMethod === 8 && compSize > 0) {
          files.push({ name: fileName, content: inflateRawSync(zipBuffer.subarray(dataStart, dataStart + compSize)).toString("utf8") });
        }
      }
    } catch {
      // Skip files that cannot be decoded as text.
    }

    pos += 46 + nameLen + extraLen + commentLen;
  }
  return files;
}

class DocmostClient {
  constructor(baseUrl, authToken, email, password) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.authToken = authToken || "";
    this.email = email || "";
    this.password = password || "";
  }

  switchBaseUrl(baseUrl) {
    const normalized = baseUrl.replace(/\/$/, "");
    if (this.baseUrl === normalized) return;
    this.baseUrl = normalized;
    if (!process.env.DOCMOST_AUTH_TOKEN) this.authToken = "";
  }

  async ensureAuth(requiredForCommand = true) {
    if (this.authToken) return;
    if (!requiredForCommand) return;
    if (!this.email || !this.password) {
      throw new Error("Missing auth. Set DOCMOST_AUTH_TOKEN or DOCMOST_EMAIL/DOCMOST_PASSWORD.");
    }
    const resp = await fetch(`${this.baseUrl}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email: this.email, password: this.password }),
    });
    if (!resp.ok) {
      throw new Error(`Login failed (${resp.status}): ${await resp.text()}`);
    }
    const setCookie = resp.headers.get("set-cookie") || "";
    const match = setCookie.match(/authToken=([^;]+)/);
    if (!match) {
      throw new Error("Login succeeded but authToken cookie was not returned.");
    }
    this.authToken = match[1];
  }

  headers(json = true) {
    const headers = { Accept: "application/json" };
    if (json) headers["Content-Type"] = "application/json";
    if (this.authToken) headers.Cookie = `authToken=${this.authToken}`;
    return headers;
  }

  async get(endpoint, { auth = true } = {}) {
    await this.ensureAuth(auth);
    const resp = await fetch(`${this.baseUrl}/api/${trimApiEndpoint(endpoint)}`, {
      method: "GET",
      headers: this.headers(false),
    });
    return this.parseResponse(resp, endpoint);
  }

  async post(endpoint, body = {}, { auth = true } = {}) {
    await this.ensureAuth(auth);
    const resp = await fetch(`${this.baseUrl}/api/${trimApiEndpoint(endpoint)}`, {
      method: "POST",
      headers: this.headers(true),
      body: JSON.stringify(body),
    });
    return this.parseResponse(resp, endpoint);
  }

  async postBinary(endpoint, body = {}) {
    await this.ensureAuth(true);
    const resp = await fetch(`${this.baseUrl}/api/${trimApiEndpoint(endpoint)}`, {
      method: "POST",
      headers: this.headers(true),
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`API ${endpoint} failed (${resp.status}): ${await resp.text()}`);
    return Buffer.from(await resp.arrayBuffer());
  }

  async postMultipart(endpoint, formData) {
    await this.ensureAuth(true);
    const resp = await fetch(`${this.baseUrl}/api/${trimApiEndpoint(endpoint)}`, {
      method: "POST",
      headers: this.headers(false),
      body: formData,
    });
    return this.parseResponse(resp, endpoint);
  }

  async parseResponse(resp, endpoint) {
    if (!resp.ok) throw new Error(`API ${endpoint} failed (${resp.status}): ${await resp.text()}`);
    const text = await resp.text();
    if (!text) return {};
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
}

function makeClient(args) {
  if (args.env && args.env !== true) loadEnvFile(args.env);
  const baseUrl = process.env.DOCMOST_URL || process.env.DOCMOST_BASE_URL;
  if (!baseUrl) throw new Error("Missing DOCMOST_URL or DOCMOST_BASE_URL.");
  return new DocmostClient(
    baseUrl,
    process.env.DOCMOST_AUTH_TOKEN,
    process.env.DOCMOST_EMAIL,
    process.env.DOCMOST_PASSWORD,
  );
}

async function resolvePageAndMaybeSwitch(client, args) {
  const target = targetPage(args);
  if (target.baseUrl) client.switchBaseUrl(target.baseUrl);
  return target.pageId;
}

async function command(client, cmd, args) {
  switch (cmd) {
    case "health": {
      printJson(await client.get("health", { auth: false }));
      return;
    }
    case "version": {
      printJson(await client.post("version", {}, { auth: false }));
      return;
    }
    case "search": {
      const resp = await client.post("search", {
        query: required(args, "query"),
        spaceId: args["space-id"],
        limit: optionalInt(args, "limit", 20),
        offset: optionalInt(args, "offset", 0),
      });
      if (args.json) printJson(resp);
      else {
        const items = resp.data?.items || resp.items || [];
        for (const [i, item] of items.entries()) {
          const page = item.title ? item : item.page || item;
          console.log(`${i + 1}. ${page.title || "Untitled"} (${page.id || page.slugId || ""})`);
          if (item.highlight) console.log(`   ${item.highlight}`);
        }
      }
      return;
    }
    case "suggest": {
      printJson(await client.post("search/suggest", { query: required(args, "query") }));
      return;
    }
    case "spaces": {
      const resp = await client.post("spaces", {
        limit: optionalInt(args, "limit", 50),
        cursor: args.cursor === true ? undefined : args.cursor,
      });
      if (args.json) printJson(resp);
      else {
        for (const sp of resp.data?.items || []) {
          console.log(`${sp.name} | ${sp.id} | ${sp.slug}`);
        }
        if (resp.data?.meta?.nextCursor) console.log(`Next cursor: ${resp.data.meta.nextCursor}`);
      }
      return;
    }
    case "pages": {
      const body = {};
      if (args["space-id"]) body.spaceId = args["space-id"];
      if (args["parent-page-id"]) body.pageId = args["parent-page-id"];
      if (!body.spaceId && !body.pageId) throw new Error("Provide --space-id or --parent-page-id");
      const resp = await client.post("pages/sidebar-pages", body);
      if (args.json) printJson(resp);
      else {
        for (const pg of resp.data?.items || []) {
          console.log(`${pg.title || "Untitled"} | ${pg.id} | ${pg.slugId || ""}${pg.hasChildren ? " | has children" : ""}`);
        }
      }
      return;
    }
    case "get-page": {
      const pageId = await resolvePageAndMaybeSwitch(client, args);
      const body = { pageId };
      if (args.format && args.format !== true) body.format = args.format;
      const resp = await client.post("pages/info", body);
      const page = unwrap(resp);
      if (args.json) printJson(page);
      else {
        console.log(formatPage(page));
        if (args.content || args.format) {
          const content = typeof page.content === "string" ? page.content : extractText(page.content);
          if (content) console.log(`\n${content}`);
        }
      }
      return;
    }
    case "create-page": {
      const body = { spaceId: required(args, "space-id"), title: required(args, "title") };
      if (args["parent-page-id"]) body.parentPageId = args["parent-page-id"];
      const resp = await client.post("pages/create", body);
      const page = unwrap(resp);
      const content = readContentArg(args);
      if (content !== undefined) {
        await client.post("pages/update", {
          pageId: page.id,
          content,
          format: args.format || "markdown",
          operation: args.operation || "replace",
        });
      }
      if (args.json) printJson(page);
      else console.log(`Created page\n${formatPage(page)}`);
      return;
    }
    case "update-page": {
      const pageId = await resolvePageAndMaybeSwitch(client, args);
      const results = [];
      if (args.title && args.title !== true) {
        await client.post("pages/update", { pageId, title: args.title });
        results.push("title");
      }
      const content = readContentArg(args);
      if (content !== undefined) {
        await client.post("pages/update", {
          pageId,
          content,
          format: args.format || "markdown",
          operation: args.operation || "replace",
        });
        results.push("content");
      }
      if (!results.length) throw new Error("Nothing to update. Provide --title, --content, or --file.");
      console.log(`Updated ${results.join(", ")} for page ${pageId}`);
      return;
    }
    case "delete-page": {
      if (!args.yes) throw new Error("delete-page requires --yes");
      const pageId = await resolvePageAndMaybeSwitch(client, args);
      printJson(await client.post("pages/delete", { pageId }));
      return;
    }
    case "restore-page": {
      const pageId = await resolvePageAndMaybeSwitch(client, args);
      printJson(await client.post("pages/restore", { pageId }));
      return;
    }
    case "import-page": {
      const filePath = path.resolve(required(args, "file"));
      const form = new FormData();
      form.append("file", new Blob([fs.readFileSync(filePath)], { type: "text/markdown" }), path.basename(filePath));
      form.append("spaceId", required(args, "space-id"));
      if (args["parent-page-id"]) form.append("parentPageId", args["parent-page-id"]);
      printJson(await client.postMultipart("pages/import", form));
      return;
    }
    case "export-page": {
      const pageId = await resolvePageAndMaybeSwitch(client, args);
      const buffer = await client.postBinary("pages/export", {
        pageId,
        format: args.format || "markdown",
      });
      const files = extractZipTexts(buffer);
      if (!files.length) {
        console.error("Export returned no text files.");
        return;
      }
      console.log(files.map((f) => `--- ${f.name} ---\n${f.content}`).join("\n\n"));
      return;
    }
    case "export-space": {
      const buffer = await client.postBinary("spaces/export", {
        spaceId: required(args, "space-id"),
        format: args.format || "markdown",
        includeAttachments: Boolean(args["include-attachments"]),
      });
      const files = extractZipTexts(buffer);
      console.log(files.map((f) => `--- ${f.name} ---\n${f.content}`).join("\n\n"));
      return;
    }
    case "upload-file": {
      const pageId = await resolvePageAndMaybeSwitch(client, args);
      const pageInfo = unwrap(await client.post("pages/info", { pageId }));
      const filePath = path.resolve(required(args, "file"));
      const form = new FormData();
      form.append("file", new Blob([fs.readFileSync(filePath)]), path.basename(filePath));
      form.append("pageId", pageInfo.id || pageId);
      const uploaded = unwrap(await client.postMultipart("files/upload", form));
      const fileUrl = `/api/files/${uploaded.id}/${uploaded.fileName}`;
      const isImage = (uploaded.mimeType || "").startsWith("image/");
      const markdown = isImage ? `![${path.basename(filePath)}](${fileUrl})` : `[${path.basename(filePath)}](${fileUrl})`;
      await client.post("pages/update", { pageId: pageInfo.id || pageId, content: markdown, format: "markdown", operation: "append" });
      printJson(uploaded);
      return;
    }
    case "raw": {
      const method = (args.method || "POST").toUpperCase();
      const endpoint = required(args, "endpoint");
      const body = args.body && args.body !== true ? JSON.parse(args.body) : {};
      const resp = method === "GET" ? await client.get(endpoint) : await client.post(endpoint, body);
      printJson(resp);
      return;
    }
    default:
      throw new Error(`Unknown command: ${cmd}`);
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || args.h || !args._.length) {
    printHelp();
    return;
  }
  const cmd = args._[0];
  const client = makeClient(args);
  await command(client, cmd, args);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});

