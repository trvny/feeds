#!/bin/bash
# SessionStart hook: install dependencies so tests and linters work in
# Claude Code on the web. Local sessions are left alone.
#
# Covers the parts of the repository with checks that run outside Docker:
#   .  (Feedseek)   uv sync  -> python -m unittest discover -s tests
#                               uv run feed_generators/validate_feeds.py
#                               uv run ruff check
#   feeds-proxy/    npm ci   -> npm run typecheck
#
# Not set up here:
#   - kanarek/app (temporary frozen release mirror): Android CI covers it.
#   - MegaLinter: the Lint workflow runs it as a Docker image, not reproducible
#     in this container. ruff is the local stand-in for the Python linters.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
	exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

# feedseek needs Python >= 3.14, which uv has to provide. The uv preinstalled
# in the image is old enough that its only 3.14 build is a release candidate,
# and rc typing internals break pydantic's forward-ref evaluation on import.
# Bootstrap a current uv from PyPI when the one on PATH has no stable 3.14.
has_stable_314() {
	"$1" python list --only-downloads 2>/dev/null |
		grep -qE 'cpython-3\.14\.[0-9]+-'
}

UV=uv
UV_BIN_DIR=""
if ! has_stable_314 uv; then
	UV_BIN_DIR="$HOME/.claude-tools/uv/bin"
	if ! { [ -x "$UV_BIN_DIR/uv" ] && has_stable_314 "$UV_BIN_DIR/uv"; }; then
		echo "==> bootstrapping a newer uv (no stable Python 3.14 in $(uv --version))"
		python3 -m pip install --quiet --upgrade --target "$HOME/.claude-tools/uv" uv
	fi
	UV="$UV_BIN_DIR/uv"
	export PATH="$UV_BIN_DIR:$PATH"
fi

echo "==> feedseek: uv sync"
"$UV" python install 3.14
"$UV" sync

# Match Worker CI and install exactly the committed lockfile graph.
echo "==> feeds-proxy: npm ci"
(cd feeds-proxy && npm ci --no-audit --no-fund)

# Generators run as scripts and import their siblings by bare name (utils,
# models, ...), so keep feed_generators/ importable from anywhere.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
	if [ -n "$UV_BIN_DIR" ]; then
		echo "export PATH=\"$UV_BIN_DIR:\$PATH\"" >>"$CLAUDE_ENV_FILE"
	fi
	echo "export PYTHONPATH=\"$PWD/feed_generators:\${PYTHONPATH:-}\"" >>"$CLAUDE_ENV_FILE"
fi

echo "==> dependencies ready"
