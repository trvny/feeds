# Repository

Monorepo:
- `feedseek/`: Python feed generators and static reader.
- `kanarek/`: Android app and Cloudflare Worker.

## Workflow

- Check `main` and open PRs before duplicating work.
- Run the narrow relevant tests; report anything not run.
- Keep PR descriptions and changelogs brief.
- Address actionable Codex review findings before merge.

## Code Review Rules

- Flag consequential correctness, security, data-loss, or compatibility risks.
- Respect the `feedseek/` and `kanarek/` boundary; cross-project changes need a clear reason.
- Leave formatting and deterministic checks to CI.
