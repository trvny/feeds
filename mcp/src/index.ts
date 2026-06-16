/**
 * feeds-status MCP server — Cloudflare Worker, free tier.
 *
 * Reports the health of the travino/feeds project: an hourly GitHub Action runs
 * ~50 Python generators and commits feeds/feed_<name>.xml, served from raw
 * GitHub. One tool, `feeds_status`, with two modes:
 *
 *   overview (no args) — cheap: pipeline pass/fail from the Actions status
 *     badge (CDN, no API rate limit), plus a best-effort cross-check of
 *     feeds.yaml against the committed feeds/ directory to flag MISSING or
 *     suspiciously-tiny files. No per-feed XML fetch, so it stays well under
 *     the free tier's 50-subrequest/request cap.
 *
 *   deep (name, or names[]) — fetch each named feed's XML and parse entry
 *     count, build time (feed-level <updated>), and newest entry date, then
 *     classify ok / stale / empty / broken. Capped to protect the subrequest
 *     budget.
 *
 * Everything is unauthenticated (the repo is public): raw.githubusercontent.com
 * for XML, the badge SVG for pipeline status, and a best-effort api.github.com
 * directory listing. No bindings, no token — zero cost.
 */

const OWNER = "travino";
const REPO = "feeds";
const WORKFLOW = "update-feeds.yml";
const RAW_BASE = `https://raw.githubusercontent.com/${OWNER}/${REPO}/main`;
const API_BASE = `https://api.github.com/repos/${OWNER}/${REPO}`;
const UA = "feeds-status-mcp (+https://github.com/travino/feeds)";

const PROTOCOL_VERSION = "2025-06-18";
const SERVER_INFO = { name: "feeds-status", version: "1.0.0" };
const FETCH_TIMEOUT_MS = 9_000;
const DEEP_CAP = 40; // keep total subrequests under the free-tier cap
const DEEP_CONCURRENCY = 6;

/** A feed whose file build time is older than this is flagged stale. */
const DEFAULT_STALE_HOURS = 6;
/** Files smaller than this are almost certainly broken/empty. */
const TINY_BYTES = 200;

const timeout = (ms: number) => AbortSignal.timeout(ms);
const ghHeaders: HeadersInit = { "User-Agent": UA, Accept: "application/vnd.github+json" };

// ---------------------------------------------------------------------------
// Tiny, dependency-free feed parsing (Workers has no DOMParser).
// ---------------------------------------------------------------------------

interface ParsedFeed {
  format: "atom" | "rss" | "unknown";
  entries: number;
  builtAt: string | null; // feed-level timestamp = when the generator last wrote
  newestEntry: string | null; // max entry date (informational)
}

const ageHours = (iso: string | null): number | null => {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : (Date.now() - t) / 3_600_000;
};

function parseFeed(xml: string): ParsedFeed {
  const isAtom = /<feed[\s>]/.test(xml);
  const isRss = /<rss[\s>]/.test(xml) || /<channel[\s>]/.test(xml);
  const format: ParsedFeed["format"] = isAtom ? "atom" : isRss ? "rss" : "unknown";

  const entryTag = isAtom ? "entry" : "item";
  const entries = (xml.match(new RegExp(`<${entryTag}[\\s>]`, "g")) ?? []).length;

  // Build time = the feed-level timestamp that appears before the first entry.
  const head = xml.split(new RegExp(`<${entryTag}[\\s>]`))[0] ?? xml;
  const builtAt = isAtom
    ? firstDate(head, ["updated", "published"])
    : firstDate(head, ["lastBuildDate", "pubDate"]);

  // Newest entry = max of all dated tags anywhere in the doc.
  const all = [...xml.matchAll(/<(updated|published|pubDate)>([^<]+)<\/\1>/g)].map((m) =>
    Date.parse(m[2].trim()),
  );
  const valid = all.filter((t) => !Number.isNaN(t));
  const newestEntry = valid.length ? new Date(Math.max(...valid)).toISOString() : null;

  return { format, entries, builtAt, newestEntry };
}

function firstDate(chunk: string, tags: string[]): string | null {
  for (const tag of tags) {
    const m = chunk.match(new RegExp(`<${tag}>([^<]+)</${tag}>`));
    if (m) return m[1].trim();
  }
  return null;
}

// ---------------------------------------------------------------------------
// Registry + directory helpers
// ---------------------------------------------------------------------------

/** Feed names from feeds.yaml (the 2-space-indented keys under `feeds:`). */
function parseRegistryNames(yaml: string): string[] {
  const names: string[] = [];
  let inFeeds = false;
  let skipBlock = false;
  let blockIndent = 0;
  for (const line of yaml.split("\n")) {
    if (/^feeds:\s*$/.test(line)) { inFeeds = true; continue; }
    if (!inFeeds) continue;
    const key = line.match(/^( {2})("?[\w]+"?|"[^"]+"):\s*$/);
    if (key) {
      skipBlock = false;
      blockIndent = key[1].length;
      names.push(key[2].replace(/"/g, ""));
      continue;
    }
    // Honor `enabled: false` inside the current block by dropping the last name.
    if (!skipBlock && /^\s+enabled:\s*false\b/.test(line) && line.search(/\S/) > blockIndent) {
      skipBlock = true;
      names.pop();
    }
  }
  return names;
}

interface DirEntry { name: string; size: number }

/**
 * Directory listing via the GitHub contents API. Best-effort: unauthenticated
 * api.github.com is limited to 60 req/hr per IP, and a Worker shares Cloudflare
 * egress IPs, so this can 403. On any failure we return null and the overview
 * simply omits the missing/tiny cross-check.
 */
async function listFeedFiles(): Promise<DirEntry[] | null> {
  try {
    const res = await fetch(`${API_BASE}/contents/feeds?ref=main`, {
      headers: ghHeaders,
      signal: timeout(FETCH_TIMEOUT_MS),
    });
    if (!res.ok) return null;
    const json = (await res.json()) as Array<{ name: string; size: number; type: string }>;
    return json.filter((f) => f.type === "file" && f.name.endsWith(".xml")).map((f) => ({ name: f.name, size: f.size }));
  } catch {
    return null;
  }
}

/**
 * Pipeline pass/fail from the Actions status-badge SVG. Served from GitHub's
 * CDN, not the rate-limited API, so it's reliable from a Worker. Commit age is
 * deliberately NOT used: feeds only re-commit when content changes (~every few
 * hours), so a healthy hourly run that finds nothing new produces no commit.
 */
async function pipelineStatus(): Promise<string> {
  try {
    const res = await fetch(`https://github.com/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/badge.svg`, {
      headers: { "User-Agent": UA },
      signal: timeout(FETCH_TIMEOUT_MS),
    });
    if (!res.ok) return `unknown (badge HTTP ${res.status})`;
    const m = (await res.text()).match(/<title>[^<]*-\s*([^<]+)<\/title>/);
    return m ? m[1].trim() : "unknown";
  } catch (e) {
    return `unknown (${e instanceof Error ? e.message : String(e)})`;
  }
}

async function mapWithConcurrency<T, R>(items: readonly T[], limit: number, fn: (item: T) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let i = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (i < items.length) {
      const idx = i++;
      out[idx] = await fn(items[idx]);
    }
  });
  await Promise.all(workers);
  return out;
}

// ---------------------------------------------------------------------------
// Modes
// ---------------------------------------------------------------------------

const fileFor = (name: string) => `feed_${name}.xml`;
const nameFromFile = (file: string) => file.replace(/^feed_/, "").replace(/\.xml$/, "");

interface OverviewReport {
  mode: "overview";
  checkedAt: string;
  pipeline: string;
  inventoryAvailable: boolean;
  totals: { registered: number; present: number; missing: number; tiny: number };
  missing: string[];
  tiny: string[];
}

async function overview(): Promise<OverviewReport> {
  const [yamlRes, files, pipeline] = await Promise.all([
    fetch(`${RAW_BASE}/feeds.yaml`, { signal: timeout(FETCH_TIMEOUT_MS) }),
    listFeedFiles(),
    pipelineStatus(),
  ]);
  const registered = yamlRes.ok ? parseRegistryNames(await yamlRes.text()) : [];

  let present = 0;
  let missing: string[] = [];
  let tiny: string[] = [];
  if (files) {
    const presentMap = new Map(files.map((f) => [nameFromFile(f.name), f.size]));
    present = presentMap.size;
    missing = registered.filter((n) => !presentMap.has(n)).sort();
    tiny = files.filter((f) => f.size < TINY_BYTES).map((f) => nameFromFile(f.name)).sort();
  }

  return {
    mode: "overview",
    checkedAt: new Date().toISOString(),
    pipeline,
    inventoryAvailable: files !== null,
    totals: { registered: registered.length, present, missing: missing.length, tiny: tiny.length },
    missing,
    tiny,
  };
}

type Verdict = "ok" | "stale" | "empty" | "broken";

interface FeedStatus {
  name: string;
  verdict: Verdict;
  entries: number;
  buildAgeHours: number | null;
  newestEntry: string | null;
  detail: string;
}

async function checkFeed(name: string, staleHours: number): Promise<FeedStatus> {
  try {
    const res = await fetch(`${RAW_BASE}/feeds/${fileFor(name)}`, { signal: timeout(FETCH_TIMEOUT_MS) });
    if (!res.ok) {
      return { name, verdict: "broken", entries: 0, buildAgeHours: null, newestEntry: null, detail: `HTTP ${res.status}` };
    }
    const parsed = parseFeed(await res.text());
    const buildAge = ageHours(parsed.builtAt);
    let verdict: Verdict = "ok";
    let detail = `${parsed.entries} entries, ${parsed.format}`;
    if (parsed.entries === 0) {
      verdict = "empty";
      detail = "0 entries";
    } else if (buildAge !== null && buildAge > staleHours) {
      verdict = "stale";
      detail = `built ${buildAge.toFixed(1)}h ago`;
    }
    return { name, verdict, entries: parsed.entries, buildAgeHours: buildAge, newestEntry: parsed.newestEntry, detail };
  } catch (e) {
    const err = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
    return { name, verdict: "broken", entries: 0, buildAgeHours: null, newestEntry: null, detail: err };
  }
}

interface DeepReport {
  mode: "deep";
  checkedAt: string;
  staleHours: number;
  summary: { total: number; ok: number; stale: number; empty: number; broken: number };
  feeds: FeedStatus[];
  truncated?: string;
}

async function deep(names: string[], staleHours: number): Promise<DeepReport> {
  let list = Array.from(new Set(names.map((n) => n.trim()).filter(Boolean)));
  let truncated: string | undefined;
  if (list.length > DEEP_CAP) {
    truncated = `checked first ${DEEP_CAP} of ${list.length} (subrequest budget)`;
    list = list.slice(0, DEEP_CAP);
  }
  const feeds = await mapWithConcurrency(list, DEEP_CONCURRENCY, (n) => checkFeed(n, staleHours));
  const count = (v: Verdict) => feeds.filter((f) => f.verdict === v).length;
  return {
    mode: "deep",
    checkedAt: new Date().toISOString(),
    staleHours,
    summary: { total: feeds.length, ok: count("ok"), stale: count("stale"), empty: count("empty"), broken: count("broken") },
    feeds,
    truncated,
  };
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderOverview(r: OverviewReport): string {
  const t = r.totals;
  const lines = [
    `feeds overview — pipeline: ${r.pipeline}  (${r.checkedAt})`,
  ];
  if (r.inventoryAvailable) {
    lines.push(`  files: ${t.present}/${t.registered} present, ${t.missing} missing, ${t.tiny} tiny`);
    if (r.missing.length) lines.push(`  MISSING: ${r.missing.join(", ")}`);
    if (r.tiny.length) lines.push(`  TINY:    ${r.tiny.join(", ")}`);
    if (!r.missing.length && !r.tiny.length) lines.push("  all registered feeds present and non-trivial");
  } else {
    lines.push(`  registry: ${t.registered} feeds (directory cross-check unavailable — GitHub API rate limit; deep-check feeds by name)`);
  }
  return lines.join("\n");
}

function renderDeep(r: DeepReport): string {
  const icon = (v: Verdict) => (v === "ok" ? "OK  " : v === "stale" ? "STALE" : v === "empty" ? "EMPTY" : "BROKEN");
  const s = r.summary;
  const lines = [
    `feeds deep — ${s.ok}/${s.total} ok, ${s.stale} stale, ${s.empty} empty, ${s.broken} broken  (${r.checkedAt})`,
    ...r.feeds.map((f) => `  [${icon(f.verdict)}] ${f.name.padEnd(18)} ${f.detail}`),
  ];
  if (r.truncated) lines.push(`  (${r.truncated})`);
  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Tool
// ---------------------------------------------------------------------------

const TOOLS = [
  {
    name: "feeds_status",
    description:
      "Health of the travino/feeds project (~50 hourly-generated Atom/RSS " +
      "feeds). Default (overview) is cheap: reports whether the hourly " +
      "update-feeds.yml pipeline is green and cross-checks feeds.yaml against " +
      "the committed feeds/ directory to flag MISSING or suspiciously-tiny " +
      "feed files. Pass name='anthropic' (or names=['anthropic','openai']) for " +
      "a deep check that fetches each feed's XML and classifies it ok / stale " +
      "(file build time older than stale_hours) / empty / broken. names is " +
      "capped to protect the Worker subrequest budget.",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", description: "Deep-check a single feed by registry name, e.g. 'anthropic'." },
        names: {
          type: "array",
          items: { type: "string" },
          description: "Deep-check several feeds. Capped at 40 per call.",
        },
        stale_hours: {
          type: "number",
          description: `Build-time age (hours) above which a feed is 'stale'. Default ${DEFAULT_STALE_HOURS}.`,
        },
      },
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
] as const;

async function runTool(args: { name?: string; names?: string[]; stale_hours?: number }): Promise<{ text: string; structured: object }> {
  const staleHours = typeof args.stale_hours === "number" && args.stale_hours > 0 ? args.stale_hours : DEFAULT_STALE_HOURS;
  const names = [...(args.name ? [args.name] : []), ...(args.names ?? [])];
  if (names.length) {
    const report = await deep(names, staleHours);
    return { text: renderDeep(report), structured: report };
  }
  const report = await overview();
  return { text: renderOverview(report), structured: report };
}

// ---------------------------------------------------------------------------
// JSON-RPC 2.0 over stateless Streamable HTTP
// ---------------------------------------------------------------------------

interface RpcRequest {
  jsonrpc: "2.0";
  id?: string | number | null;
  method: string;
  params?: Record<string, unknown>;
}

const ok = (id: RpcRequest["id"], result: unknown) => ({ jsonrpc: "2.0" as const, id, result });
const err = (id: RpcRequest["id"], code: number, message: string) => ({ jsonrpc: "2.0" as const, id, error: { code, message } });

async function handleRpc(req: RpcRequest): Promise<object | null> {
  switch (req.method) {
    case "initialize":
      return ok(req.id, { protocolVersion: PROTOCOL_VERSION, capabilities: { tools: {} }, serverInfo: SERVER_INFO });
    case "notifications/initialized":
    case "notifications/cancelled":
      return null;
    case "ping":
      return ok(req.id, {});
    case "tools/list":
      return ok(req.id, { tools: TOOLS });
    case "tools/call": {
      const name = (req.params?.name as string) ?? "";
      const args = (req.params?.arguments as Record<string, unknown>) ?? {};
      if (name !== "feeds_status") return err(req.id, -32602, `Unknown tool: ${name}`);
      try {
        const { text, structured } = await runTool({
          name: args.name as string | undefined,
          names: args.names as string[] | undefined,
          stale_hours: args.stale_hours as number | undefined,
        });
        return ok(req.id, { content: [{ type: "text", text }], structuredContent: structured, isError: false });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        return ok(req.id, { content: [{ type: "text", text: `feeds_status failed: ${msg}` }], isError: true });
      }
    }
    default:
      return err(req.id, -32601, `Method not found: ${req.method}`);
  }
}

const JSON_HEADERS = { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" };

export default {
  async fetch(request: Request): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Mcp-Session-Id, Mcp-Protocol-Version",
        },
      });
    }
    if (request.method === "GET") {
      return new Response("feeds-status MCP server. POST JSON-RPC to this endpoint.\n", {
        headers: { "Content-Type": "text/plain", "Access-Control-Allow-Origin": "*" },
      });
    }
    if (request.method !== "POST") {
      return new Response("Method not allowed.\n", { status: 405, headers: JSON_HEADERS });
    }

    let payload: unknown;
    try {
      payload = await request.json();
    } catch {
      return new Response(JSON.stringify(err(null, -32700, "Parse error")), { status: 200, headers: JSON_HEADERS });
    }

    if (Array.isArray(payload)) {
      const responses = (await Promise.all(payload.map((p) => handleRpc(p as RpcRequest)))).filter((r): r is object => r !== null);
      return new Response(responses.length ? JSON.stringify(responses) : "", { status: responses.length ? 200 : 202, headers: JSON_HEADERS });
    }
    const response = await handleRpc(payload as RpcRequest);
    return new Response(response ? JSON.stringify(response) : "", { status: response ? 200 : 202, headers: JSON_HEADERS });
  },
} satisfies ExportedHandler;
