# GitHub Copilot adapter

Use `AGENTS.md` as the repository-wide source of truth. Apply the nearest path-specific `.github/instructions/*.instructions.md` when one matches the changed files.

For code review:
- Focus on concrete regressions introduced by the PR: correctness, security/privacy, data loss, races/lifecycle/resource leaks, compatibility, and violations of repository contracts.
- Treat CI, build, lint, and test failures as actionable only when they are caused by the diff.
- Avoid generic style or preference comments already enforced by formatters or linters unless they reveal a real defect.
- Do not nitpick documentation-only, formatting, or cosmetic changes unless they are factually wrong, break generated/validated content, or create security/release risk.
- Prefer one precise comment per root cause. State the impact and the smallest useful fix.
- Keep suggestions non-blocking; reserve blocking findings for concrete merge-risk defects.
- If there are no actionable findings, do not invent nits or filler praise.
- Write review comments in concise English.