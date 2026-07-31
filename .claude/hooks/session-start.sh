#!/bin/bash
# SessionStart hook: install dependencies so tests and linters work in
# Claude Code on the web. Local sessions are left alone.
#
# Covers the parts of the monorepo with checks that run outside Docker:
#   feedseek/        uv sync      -> python -m unittest discover -s tests
#                                    uv run feed_generators/validate_feeds.py
#                                    uv run ruff check
#   kanarek/worker/  npm ci       -> npm run typecheck, npm test (vitest)
#   feeds-proxy/     npm install  -> npm run typecheck
#
# Not set up here:
#   - kanarek/app (Android): needs the Android SDK for compileSdk 37 plus a
#     Gradle distribution, a multi-GB download that Android CI already covers.
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
(cd feedseek && "$UV" python install 3.14 && "$UV" sync)

# npm ci: the image's npm is older than the one that wrote the lockfile, and
# `npm install` would strip its `libc` fields and leave the tree dirty.
echo "==> kanarek/worker: npm ci"
(cd kanarek/worker && npm ci --no-audit --no-fund)

# feeds-proxy has no committed lockfile and Worker CI installs it the same way,
# so resolve from package.json but skip writing a lockfile the repo would then
# carry as an untracked file.
echo "==> feeds-proxy: npm install"
(cd feeds-proxy && npm install --no-package-lock --no-audit --no-fund)

# Generators run as scripts from feedseek/ and import siblings out of
# feed_generators/, so keep that importable from anywhere.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
	if [ -n "$UV_BIN_DIR" ]; then
		echo "export PATH=\"$UV_BIN_DIR:\$PATH\"" >>"$CLAUDE_ENV_FILE"
	fi
	echo "export PYTHONPATH=\"$PWD/feedseek:\${PYTHONPATH:-}\"" >>"$CLAUDE_ENV_FILE"
fi

echo "==> dependencies ready"
