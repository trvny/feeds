# Kanarek Cloudflare Worker

The Worker lives in `kanarek/worker/`. It is an optional accelerator and state
backend; the Android app must still parse feeds on-device when no backend URL is
configured.

Read these files before changing Worker behavior:

- `kanarek/worker/src/index.ts` for routes and runtime behavior;
- `kanarek/worker/wrangler.jsonc` for bindings, vars, compatibility date, and
  deployment identity;
- `kanarek/worker/package.json` for supported commands;
- active Worker CI and deployment workflows under `.github/workflows/`.

Do not duplicate binding IDs, account IDs, database UUIDs, default-feed lists,
or compatibility dates in this reference. They change, and Wrangler
configuration is the deployment source of truth.

## Load-bearing behavior

### Optional backend

Feed proxying and state features may improve the app, but a missing Worker must
not disable on-device feed parsing. State routes that require an absent binding
should fail clearly and locally rather than crashing unrelated feed routes.

### Per-source isolation

Fetch and parse each source under its own error boundary. A timeout, invalid
feed, or parser error from one source must not abort the merged response from
other working sources.

### Conditional requests

- Derive the ETag from stable item content, not the volatile fetch time.
- Handle `If-None-Match` according to the implementation's supported weak-tag
  comparison.
- Return a bodyless `304` for unchanged content.
- Keep device caching behavior compatible with the Worker response.
- Expose required cache headers through CORS when the app needs to read them.

Run the tests whenever ETag, cache-key, timestamp, or response-shape logic
changes.

### Discovery and scraping

Discovery should prefer declared RSS/Atom alternatives and use bounded fallback
probes. Scraping must remain host-restricted, time-bounded, and cached. Scraped
content should enter the same normalized feed path as native feeds rather than
creating a second app-specific item contract.

### State and pairing

Treat D1-backed state and pairing as a separate capability. Preserve validation,
device isolation, migration compatibility, and graceful behavior when the
binding is unavailable. Do not expose pairing secrets or device state in logs.

### Shared defaults

When the app and Worker intentionally carry the same default feed set, update
both source files in one logical change and test both halves. Determine the
current files and values from source; do not trust a list copied into a skill.

## Configuration and secrets

- Keep public vars and bindings in `wrangler.jsonc` when appropriate.
- Keep secret values in Cloudflare secret storage.
- Never write Cloudflare account identifiers, namespace IDs, database IDs,
  tokens, or private deployment metadata into skills, examples, PR comments, or
  client code.
- Do not rename live Worker, KV, D1, or R2 resources as a side effect of a code
  change. A rename or migration requires an explicit plan and remote-state
  verification.

## Validation

From `kanarek/worker/`:

```bash
npm ci
npm run typecheck
npm test
```

Use `npm run dev` for an authorized local smoke test when bindings and fixtures
permit it.

## Deployment

Use the repository's Wrangler configuration and deployment workflow, or
`npm run deploy` when an explicit manual deployment is requested and the current
environment is authenticated. Do not reconstruct a multipart Workers API deploy
from remembered bindings, and do not bypass migrations or environment-specific
configuration.

After deployment, observe the workflow or Wrangler result and smoke-test the
changed routes. A successful commit or typecheck alone is not deployment proof.
Report which live checks were and were not performed.
