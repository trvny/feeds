# Kanarek Worker

The Cloudflare Worker is optional. Without a configured backend, the Android app continues to fetch and parse ordinary RSS/Atom feeds on-device.

The Worker adds shared edge parsing and caching, feed discovery, HTML-to-Atom scraping, clean article extraction, station search, logo lookup, and optional synchronized state through D1.

## Deploy

Run from `kanarek/worker/`:

```bash
npm install
npx wrangler deploy
```

Wrangler prints the deployed `workers.dev` URL. Paste it into Kanarek's **Backend URL** setting.

## Routes

### Combined feeds

```text
GET /?feeds=<url,url,...>&limit=20
```

Returns merged, de-duplicated, newest-first JSON:

```json
{
  "items": [
    {
      "title": "...",
      "link": "...",
      "summary": "...",
      "image": "...",
      "date": "...",
      "source": "...",
      "author": "..."
    }
  ],
  "count": 1,
  "fetched": "..."
}
```

The same item set can be exported for external readers:

```text
GET /?feeds=<url,url,...>&format=atom
GET /?feeds=<url,url,...>&format=rss
GET /?feeds=<url,url,...>&format=jsonfeed
```

Omitting `format`, or using `format=json`, keeps the regular app-facing JSON response.

### Feed discovery

```text
GET /discover?url=<page>
```

Looks for advertised RSS/Atom links. When none are present, it probes common feed paths such as `/feed`, `/rss`, and `/atom.xml`.

### HTML scraping

```text
GET /scrape?url=<page>[&item=<css>&title=<css>&link=<css>&image=<css>&summary=<css>]
```

Converts a page without a native feed into Atom using Cloudflare `HTMLRewriter`. With no selectors it attempts to detect the repeating item block automatically.

The result is deliberately Atom, so the generated URL behaves like any other feed in on-device mode, Worker mode, and OPML import/export.

### Clean article extraction

```text
GET /article?url=<article>
```

Returns inert article text with metadata. JSON-LD `articleBody` is preferred; the HTML fallback keeps article paragraphs and removes scripts, forms, frames, trackers, navigation, advertisements, newsletter prompts, and related-content containers.

`ARTICLE_ALLOWED_HOSTS` is an exact operator-controlled host allowlist. An empty value disables the endpoint, and redirects must remain on the allowlist.

### Station directory

```text
GET /stations/search?q=<name>&country=<ISO2>&tag=<genre>&limit=30
```

Proxies the community Radio Browser directory, filters broken streams, and maps results to Kanarek's station model.

### Channel logos

```text
GET /logos?ids=<tvg-id,tvg-id,...>
```

Resolves missing station logos from the iptv-org channel catalog. Existing playlist logos are left unchanged.

### State and pairing

When `STATE_DB` is configured, the Worker exposes per-device read state, subscriptions, and pairing routes:

```text
/state/read
/state/subs
/pair
/pair/<code>
```

Without the D1 binding these routes return a service-unavailable response and the rest of the Worker continues to operate.

### Health

```text
GET /health
```

Returns `{ "ok": true }`.

## Conditional GET and caching

The combined feed response carries a weak `ETag` calculated from the item set, not from the per-request `fetched` timestamp. A matching `If-None-Match` request receives `304 Not Modified` with no body.

The Worker uses Cloudflare Cache API as the fast per-location cache. The optional `SCRAPE_KV` binding provides a durable cross-location cache for `/discover` and `/scrape`.

KV writes happen only after a cache miss, require a non-empty result, and use a TTL. The Worker remains functional with Cache API alone.

## Configuration

Worker variables and bindings are configured in `worker/wrangler.jsonc`:

- `DEFAULT_FEEDS`: comma-separated fallback feeds when the request omits `feeds`.
- `ALLOWED_HOSTS`: optional host allowlist for feeds, discovery, and scraping.
- `ARTICLE_ALLOWED_HOSTS`: exact host allowlist for clean-reader extraction.
- `SCRAPE_KV`: optional KV namespace for durable discovery/scrape caching.
- `STATE_DB`: optional D1 database for read state, subscriptions, and pairing.

The app's default feed list and the Worker's `DEFAULT_FEEDS` must remain synchronized.

## Security and limits

- Only HTTP and HTTPS source URLs are accepted.
- Feed, page, and article reads are bounded by byte, timeout, redirect, and item limits.
- One failed source is isolated from the remaining feed batch.
- Clean-reader hosts use an exact allowlist.
- Scraping does not use a headless browser.

Further reading:

- [Architecture](ARCHITECTURE.md)
- [Development](DEVELOPMENT.md)
- [Project history](HISTORY.md)
