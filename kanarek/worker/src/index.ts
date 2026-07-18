/**
 * kanarek news Worker
 *
 * Routes
 *   GET /?feeds=<url,url,...>&limit=20
 *     -> { items: [{ title, link, summary, image, date, source, author }], count, fetched }
 *     Fetches/parses RSS, Atom, RDF, and JSON Feed (via feedsmith), merges,
 *     de-dupes, sorts newest-first. Conditional GET via a weak ETag over the
 *     item set (304 when nothing changed).
 *
 *   GET /discover?url=<page>
 *     -> { feeds: [{ url, title, type }], count }
 *     Finds a site's native feed when it isn't obvious: reads
 *     <link rel="alternate" type="application/rss+xml|atom+xml"> from the page
 *     head, and (only if none are advertised) probes a few common feed paths.
 *
 *   GET /scrape?url=<page>[&item=<sel>&title=<sel>&link=<sel>&image=<sel>&summary=<sel>]
 *     -> Atom XML
 *     Turns a site WITHOUT a native feed into Atom, extracted at the edge with
 *     HTMLRewriter (no DOM, no headless browser). With no selectors it
 *     auto-detects the repeating item block. Emits Atom (not JSON) on purpose,
 *     so the resulting /scrape URL drops into the app's feed list and works in
 *     both on-device and backend modes, and round-trips through OPML unchanged.
 *
 *   GET /?feeds=...&format=atom|rss|jsonfeed
 *     -> Atom/RSS XML, or a spec JSON Feed 1.1 document (application/feed+json),
 *     of the same merged, deduped, sorted item set.
 *     Purely additive: default (no ?format=, or format=json) is byte-identical
 *     to the JSON path above, untouched. Lets the merged output itself be
 *     subscribed to in an external reader.
 *
 *   GET /stations/search?q=<n>&country=<cc>&tag=<genre>&limit=<n>
 *     -> { stations: [{ name, streamUrl, logoUrl, groupTitle }], count, fetched }
 *     Proxies station search to the Radio Browser API (radio-browser.info, ~50k+
 *     community-checked internet radio stations, no key required) so the app's
 *     station-search dialog isn't limited to the hand-bundled seed playlists.
 *     At least one of q/country/tag is required. Broken streams are filtered
 *     server-side (hidebroken=true) and results are ranked by click popularity.
 *
 *   GET /health -> { ok: true }
 *
 * Cloudflare infra, all free-tier safe:
 *   - Cache API (caches.default): fast per-colo layer in front of every route.
 *   - Workers KV (optional binding SCRAPE_KV): durable cross-colo layer for
 *     /discover and /scrape so a cold cache doesn't re-hit origin sites. Writes
 *     are gated to cache-miss + non-empty + TTL'd, to stay well under the free
 *     1k-writes/day cap; if the binding is absent the code degrades to Cache-API
 *     only. No D1/R2/Browser-Rendering/AI: scrape config lives in the URL, so the
 *     Worker stays stateless and within CPU limits.
 */

import { generateAtomFeed, generateRssFeed, generateJsonFeed, parseFeed as parseFeedSmith } from "feedsmith";

export interface Env {
  /** Optional comma-separated default feeds when the request omits ?feeds= */
  DEFAULT_FEEDS?: string;
  /** Optional comma-separated allowlist of host suffixes. Empty = allow any. */
  ALLOWED_HOSTS?: string;
  /** Optional KV namespace for durable discover/scrape caching. Absent = Cache-API only. */