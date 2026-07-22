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

from models import FeedConfig, FeedType, load_feed_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_feed(feed_name: str, config: FeedConfig, full: bool = False) -> bool:
    """Run one generator in a subprocess and relay all captured diagnostics."""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.script)
    cmd = [sys.executable, script_path]
    if full:
        cmd.append("--full")

    logger.info("Running %s: %s", feed_name, script_path)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

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


def run_all_feeds(
    skip_selenium: bool = False,
    selenium_only: bool = False,
    feed: str | None = None,
    full: bool = False,
) -> int:
    """Run generators from the registry and return a truthful process status."""
    registry, skipped_configs = load_feed_registry(return_skipped=True)

    if feed:
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
        return 0 if run_feed(feed, config, full=full) else 1

    failed_scripts: list[str] = []
    successful_scripts: list[str] = []
    skipped_scripts: list[str] = []

    for name, config in sorted(registry.items()):
        if not config.enabled:
            logger.info("Skipping disabled feed: %s", name)
            skipped_scripts.append(name)
            continue

        is_selenium = config.type == FeedType.SELENIUM
        if skip_selenium and is_selenium:
            logger.info("Skipping Selenium generator: %s", name)
            skipped_scripts.append(name)
            continue
        if selenium_only and not is_selenium:
            logger.info("Skipping non-Selenium generator: %s", name)
            skipped_scripts.append(name)
            continue

        if run_feed(name, config, full=full):
            successful_scripts.append(name)
        else:
            failed_scripts.append(name)

    logger.info("\n%s", "=" * 60)
    logger.info("Feed Generation Summary:")
    logger.info("  Successful: %d", len(successful_scripts))
    logger.info("  Failed: %d", len(failed_scripts))
    logger.info("  Skipped (disabled/filtered): %d", len(skipped_scripts))
    logger.info("  Invalid configs (skipped): %d", len(skipped_configs))

    if failed_scripts:
        logger.error("\nFailed feeds:")
        for name in failed_scripts:
            logger.error("  ✗ %s", name)
    if skipped_configs:
        logger.error("\nInvalid feed configs in feeds.yaml:")
        for name in skipped_configs:
            logger.error("  ⚠ %s", name)
    if skipped_scripts:
        logger.info("\nSkipped feeds:")
        for name in skipped_scripts:
            logger.info("  ○ %s", name)
    logger.info("%s\n", "=" * 60)

    return 1 if failed_scripts or skipped_configs else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RSS feed generators")
    parser.add_argument(
        "--skip-selenium",
        action="store_true",
        help="Skip Selenium-based generators",
    )
    parser.add_argument(
        "--selenium-only",
        action="store_true",
        help="Run only Selenium-based generators",
    )
    parser.add_argument("--feed", type=str, help="Run one feed by registry name")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Pass --full to generators",
    )
    args = parser.parse_args()

    if args.skip_selenium and args.selenium_only:
        logger.error("Cannot use both --skip-selenium and --selenium-only")
        sys.exit(1)

    sys.exit(
        run_all_feeds(
            skip_selenium=args.skip_selenium,
            selenium_only=args.selenium_only,
            feed=args.feed,
            full=args.full,
        )
    )
