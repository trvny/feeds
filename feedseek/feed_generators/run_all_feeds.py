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
from normalize_feed_self_links import normalize_feed_self_links

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_feed(feed_name: str, config: FeedConfig, full: bool = False) -> bool:
    """Run one generator in a subprocess and relay all captured diagnostics."""
    generators_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(generators_dir, config.script)
    invoker_path = os.path.join(generators_dir, "invoke_generator.py")
    cmd = [sys.executable, invoker_path, script_path]
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


def normalize_generated_feeds() -> bool:
    """Normalize legacy metadata paths after generators finish writing feeds."""
    try:
        changed = normalize_feed_self_links()
    except OSError as exc:
        logger.error("Could not normalize generated feed self links: %s", exc)
        return False
    if changed:
        logger.info(
            "Normalized Atom self links in: %s",
            ", ".join(path.name for path in changed),
        )
    return True


def backfill_json_sidecars() -> bool:
    """Write a JSON Feed sidecar for any XML that is missing or older than one.

    Generators that call utils.save_atom_feed get a sidecar for free. Roughly
    two dozen older ones shadow that helper with a local save_atom_feed and
    call feedgen's atom_file() directly, so they never produce one and
    validate_feeds.py reports JSON_MISSING for them forever. Regenerating from
    the committed XML here fixes every such feed in one place, including any
    future generator that writes its own XML. Never fails the run: the XML is
    the published artifact.
    """
    try:
        from jsonfeed import write_json_feed
        from utils import feedparser_entry_image, get_feeds_dir
    except ImportError as exc:
        logger.warning("JSON Feed sidecar backfill unavailable: %s", exc)
        return True

    written: list[str] = []
    for xml_path in sorted(get_feeds_dir().glob("feed_*.xml")):
        json_path = xml_path.with_suffix(".json")
        try:
            if json_path.exists() and json_path.stat().st_mtime >= xml_path.stat().st_mtime:
                continue
            name = xml_path.stem.removeprefix("feed_")
            write_json_feed(xml_path, name, entry_image=feedparser_entry_image)
            written.append(name)
        except Exception as exc:  # one bad feed never blocks the rest
            logger.warning("JSON Feed sidecar backfill failed for %s: %s", xml_path.name, exc)
    if written:
        logger.info("Backfilled %d JSON Feed sidecar(s): %s", len(written), ", ".join(written))
    return True


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
        run_ok = run_feed(feed, config, full=full)
        normalize_ok = normalize_generated_feeds()
        backfill_json_sidecars()
        return 0 if run_ok and normalize_ok else 1

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

    normalization_ok = normalize_generated_feeds()
    backfill_json_sidecars()

    logger.info("\n%s", "=" * 60)
    logger.info("Feed Generation Summary:")
    logger.info("  Successful: %d", len(successful_scripts))
    logger.info("  Failed: %d", len(failed_scripts))
    logger.info("  Skipped (disabled/filtered): %d", len(skipped_scripts))
    logger.info("  Invalid configs (skipped): %d", len(skipped_configs))
    logger.info("  Metadata normalization: %s", "ok" if normalization_ok else "failed")

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

    return 1 if failed_scripts or skipped_configs or not normalization_ok else 0


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
