# Architecture

## Core Sections (Required)

### 1) Architectural Style

- Primary style: registry-driven batch pipeline with source adapters and a shared normalization/enrichment core, plus a static publication layer and a small edge proxy.
- Why this classification: `feeds.yaml` declares adapters; `run_all_feeds.py` dispatches them independently; shared helpers merge/cache/enrich/render; `site/build_site.py` publishes the results; `feeds-proxy` is separately deployed.
- Primary constraints: one bad source must not stop the rest, last-known-good output must survive failures, published entry identity/dates should remain stable, and upstream feeds may be improved rather than passed through unchanged.

### 2) System Flow

```text
feeds.yaml -> models.py -> run_all_feeds.py -> invoke_generator.py -> source generator
          -> normalize/merge/cache/enrich -> Feedgen XML -> JSON Feed 1.1 sidecar
          -> site/build_site.py -> GitHub Pages -> optional feeds-proxy -> browser reader
```

1. `models.py` validates registry entries and skips malformed entries without aborting the whole registry.
2. `run_all_feeds.py` starts each enabled generator in its own subprocess with a per-generator timeout.
3. Source modules fetch native feeds, APIs or pages and convert them into shared entry dictionaries; `multi_rss.py` is the main reusable native-feed aggregation path.
4. Shared code normalizes URLs/titles, refreshes cached metadata, deduplicates, preserves durable IDs, allocates fair source share and enriches links/images.
5. Feedgen writes Atom/RSS atomically; `jsonfeed.py` parses the just-written XML and emits a JSON Feed 1.1 sibling, keeping XML as the rendering source of truth.
6. The Pages builder copies selected feed artifacts and builds the directory/reader assets. The browser reader can route cross-origin fetches through the separately deployed Worker.

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `models.py` + `feeds.yaml` | Registry schema and source selection | Parsing/rendering logic | `feed_generators/models.py` |
| `run_all_feeds.py` + `invoke_generator.py` | Isolation, timeouts, adapter compatibility and global run status | Source-specific parsing | `feed_generators/run_all_feeds.py`, `feed_generators/invoke_generator.py` |
| `multi_rss.py` + `utils.py` | Shared ingestion, normalization, cache, dedupe, fair allocation and feed output | Source-specific editorial rules | `feed_generators/multi_rss.py`, `feed_generators/utils.py` |
| `entry_identity.py` + `entry_refresh.py` | Durable reader identity and safe metadata refresh | Network access | `feed_generators/entry_identity.py`, `feed_generators/entry_refresh.py` |
| `enrich.py` | Optional, bounded URL/image enrichment | Feed-fatal behavior | `feed_generators/enrich.py` |
| `jsonfeed.py` | JSON Feed 1.1 projection from published XML | Independent re-derivation from source data | `feed_generators/jsonfeed.py` |
| `site/` | Static publication and browser UX | Generator orchestration | `site/build_site.py`, `site/reader.js` |
| `feeds-proxy/` | Bounded HTTPS proxy for browser CORS gaps | Source generation | `feeds-proxy/src/index.js` |

### 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| Adapter per source | `feed_generators/*.py`, `feeds.yaml` | Isolate source quirks behind a common `main()` contract |
| Bulkhead/failure isolation | `run_all_feeds.py` | A hung or broken source costs its own feed, not the whole run |
| Last-known-good + atomic replace | `utils.write_atomically`, generator empty-result guards | Prevent partial/empty artifacts replacing valid output |
| Cache-backed enrichment | `enrich.py`, `article_image.py`, `google_news.py` | Pay network lookup cost once and keep enrichment non-fatal |
| Durable identity seed | `entry_identity.py`, `invoke_generator.py` | Avoid reader-visible duplicates when URLs later change |
| Fair-share allocator | `utils.allocate_fair_share()` | Prevent prolific sources starving quiet sources in combined feeds |
| Derived sidecar | `jsonfeed.py` | Keep XML and JSON representations aligned without two generation paths |

### 5) Known Architectural Risks

- `feed_generators/utils.py` is a 958-line shared module and monkey-patches Feedgen file writers. Its blast radius is high even though tests cover many invariants.
- Source adapters are not uniformly migrated to the shared `multi_rss` path, so behavior can differ across historical generators.
- JSON Feed sidecars exist for every currently enabled feed, but `validate_feeds.py` still treats missing/malformed JSON as advisory rather than a publication gate.

### 6) Evidence

- `feeds.yaml`
- `feed_generators/run_all_feeds.py`
- `feed_generators/invoke_generator.py`
- `feed_generators/multi_rss.py`
- `feed_generators/utils.py`
- `feed_generators/jsonfeed.py`
- `site/build_site.py`
- `feeds-proxy/src/index.js`
