# feedseek

- Python + `uv`; generators live in `feed_generators/`, sources in `feeds.yaml`.
- Keep source failures isolated, dedup stable, and unchanged entries from timestamp churn.
- Do not edit generated feeds or cache unless required.
- Test the touched generator, then run `make validate`.

## Code Review Rules

- Flag changes that can abort the batch, emit invalid RSS/Atom, or churn unchanged entries.
- Preserve normalized URL/title deduplication and per-source failure isolation.
