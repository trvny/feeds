# feeds-status MCP

A remote [MCP](https://modelcontextprotocol.io) server that reports the health of
the [feeds](https://github.com/travino/feeds) project — ~50 hourly-generated
Atom/RSS feeds. Runs as a Cloudflare Worker on the **free tier**: no bindings, no
token, pure outbound fetch.

## Why it exists (token economy)

"Are my feeds healthy?" used to mean pulling feed XML into the chat and eyeballing
it. This server does the fetching and parsing at the edge and returns a compact
verdict — entry counts and build times, not raw XML.

## The tool

### `feeds_status`

Two modes, chosen by whether you name a feed:

**Overview** (no args) — cheap, always works:

- **pipeline** pass/fail, read from the Actions status-**badge SVG** (CDN, so no
  API rate limit). Commit age is intentionally ignored: feeds only re-commit when
  content changes, so a healthy hourly run with nothing new makes no commit.
- **directory cross-check** of `feeds.yaml` against the committed `feeds/` dir to
  flag MISSING or suspiciously-tiny files. Best-effort: it uses the
  unauthenticated GitHub contents API (60 req/hr per IP), so from a shared Worker
  IP it may be unavailable — the overview degrades to pipeline + registry count.

**Deep** (`name` or `names[]`) — fetches each feed's XML and classifies it:

| verdict | meaning |
|---|---|
| `ok` | parses, has entries, recently built |
| `stale` | file build time older than `stale_hours` (default 6) |
| `empty` | 0 entries (the generator should never publish this) |
| `broken` | non-200 or unparseable |

`names` is capped at 40 per call to stay under the Worker's 50-subrequest limit.

| arg | type | default | meaning |
|---|---|---|---|
| `name` | string | — | deep-check one feed (e.g. `anthropic`) |
| `names` | string[] | — | deep-check several (capped 40) |
| `stale_hours` | number | `6` | build-age threshold for `stale` |

Output is human text plus `structuredContent`.

## Deploy

```bash
npm install
npx wrangler login      # one-time
npm run deploy
```

Auto-deploy on push to `mcp/**` is wired via `.github/workflows/mcp-deploy.yml`,
which reuses repo secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` —
add them to the feeds repo if they aren't already there.

## Connect in Claude

Settings → Connectors → Add custom connector → paste the Worker URL. No auth
(read-only, public data). Then ask: *"feeds overview"* or *"deep-check the AI feeds"*.

## Local dev

```bash
npm run dev          # wrangler dev
npm run typecheck    # tsc --noEmit
```
