"""Run feed generators listed in ``feeds.yaml``.

Generators run in isolated subprocesses so one failure never prevents the
remaining feeds from being attempted. The command exits non-zero when any
enabled generator fails or a registry entry is invalid; the workflow publishes
successful partial results before applying that final failure gate.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

from models import FeedConfig, load_feed_registry
from normalize_feed_self_links import normalize_feed_self_links

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Per-generator wall clock. Generators run one after another against a 69 minute
# job timeout, so a single child that hangs - a stalled DNS lookup, a native
# client ignoring its own socket timeout - costs every feed queued behind it,
# not just its own. A normal full pass over all 95 feeds takes ~12 minutes, so
# eight minutes for one generator is generous and still leaves the run able to
# finish. Losing one feed is fine: a generator that writes nothing leaves the
# last good file in place.
GENERATOR_TIMEOUT = float(os.environ.get("FEEDSEEK_GENERATOR_TIMEOUT", "480"))


def run_feed(feed_name: str, config: FeedConfig, full: bool = False) -> bool:
    """Run one generator in a subprocess and relay all captured diagnostics."""
    generators_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(generators_dir, config.script)
    invoker_path = os.path.join(generators_dir, "invoke_generator.py")
    cmd = [sys.executable, invoker_path, script_path]
    if full:
        cmd.append("--full")

    logger.info("Running %s: %s", feed_name, script_path)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=GENERATOR_TIMEOUT
        )
    except subprocess.TimeoutExpired as exc:
        # subprocess.run has already killed the child by this point.
        for stream, label in ((exc.stdout, "stdout"), (exc.stderr, "stderr")):
            if stream and stream.strip():
                logger.warning("[%s %s before timeout]\n%s", feed_name, label, stream.rstrip())
        logger.error(
            "Generator %s exceeded %.0fs and was killed; its feed keeps the last good file",
            feed_name,
            GENERATOR_TIMEOUT,
        )
        return False

    if result.stdout.strip():
        logger.info("[%s stdout]\n%s", feed_name, result.stdout.rstrip())
    if result.stderr.strip():
        log = logger.warning if result.returncode == 0 else logger.error
        log("[%s stderr]\n%s", feed_name, result.stderr.rstrip())

    if result.returncode == 0:
        logger.info("Successfully ran: %s", feed_name)
        return True

    logger.error("Generator %s exited with status %d", feed_name, result.returncode)
    return False


def normalize_generated_feeds() -> bool:
    """Normalize generated feed metadata after generators finish writing feeds."""
    try:
        changed = normalize_feed_self_links()
    except OSError as exc:
        logger.error("Could not normalize generated feed metadata: %s", exc)
        return False
    if changed:
        logger.info(
            "Normalized feed metadata in: %s",
            ", ".join(path.name for path in changed),
        )
    return True


def _run_named_feed(
    feed: str,
    registry: dict[str, FeedConfig],
    skipped_configs: list[str],
    *,
    full: bool,
) -> int:
    """Run one named feed after resolving registry state."""
    if feed not in registry:
        if feed in skipped_configs:
            logger.error("Feed '%s' has an invalid config in feeds.yaml", feed)
        else:
            logger.error(
                "Feed '%s' not found in registry. Available: %s",
                feed,
                ", ".join(sorted(registry)),
            )
        return 1

    config = registry[feed]
    if not config.enabled:
        logger.warning("Feed '%s' is disabled in feeds.yaml", feed)
        return 1

    run_ok = run_feed(feed, config, full=full)
    normalize_ok = normalize_generated_feeds()
    return 0 if run_ok and normalize_ok else 1


def _log_generation_summary(
    successful_scripts: list[str],
    failed_scripts: list[str],
    skipped_scripts: list[str],
    skipped_configs: list[str],
    *,
    normalization_ok: bool,
) -> None:
    """Log the batch outcome without adding branching to the runner."""
    logger.info("\n%s", "=" * 60)
    logger.info("Feed Generation Summary:")
    logger.info("  Successful: %d", len(successful_scripts))
    logger.info("  Failed: %d", len(failed_scripts))
    logger.info("  Skipped (disabled/filtered): %d", len(skipped_scripts))
    logger.info("  Invalid configs (skipped): %d", len(skipped_configs))
    logger.info("  Metadata normalization: %s", "ok" if normalization_ok else "failed")

    for heading, names, level, marker in (
        ("Failed feeds", failed_scripts, logger.error, "✗"),
        ("Invalid feed configs in feeds.yaml", skipped_configs, logger.error, "⚠"),
        ("Skipped feeds", skipped_scripts, logger.info, "○"),
    ):
        if not names:
            continue
        level("\n%s:", heading)
        for name in names:
            level("  %s %s", marker, name)
    logger.info("%s\n", "=" * 60)


def _run_registry(
    registry: dict[str, FeedConfig],
    skipped_configs: list[str],
    *,
    full: bool,
) -> int:
    """Run every enabled registry entry and report the aggregate status."""
    failed_scripts: list[str] = []
    successful_scripts: list[str] = []
    skipped_scripts: list[str] = []

    for name, config in sorted(registry.items()):
        if not config.enabled:
            logger.info("Skipping disabled feed: %s", name)
            skipped_scripts.append(name)
            continue
        target = successful_scripts if run_feed(name, config, full=full) else failed_scripts
        target.append(name)

    normalization_ok = normalize_generated_feeds()
    _log_generation_summary(
        successful_scripts,
        failed_scripts,
        skipped_scripts,
        skipped_configs,
        normalization_ok=normalization_ok,
    )
    return 1 if failed_scripts or skipped_configs or not normalization_ok else 0


def run_all_feeds(
    feed: str | None = None,
    full: bool = False,
) -> int:
    """Run generators from the registry and return a truthful process status."""
    registry, skipped_configs = load_feed_registry(return_skipped=True)
    if feed:
        return _run_named_feed(feed, registry, skipped_configs, full=full)
    return _run_registry(registry, skipped_configs, full=full)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RSS feed generators")
    parser.add_argument("--feed", type=str, help="Run one feed by registry name")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Pass --full to generators",
    )
    args = parser.parse_args()

    sys.exit(run_all_feeds(feed=args.feed, full=args.full))
