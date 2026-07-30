"""Invoke one feed generator and translate its ``main`` result to an exit code.

This adapter keeps generator execution isolated while enforcing the project
contract centrally. Older scripts use either ``main(full=False)`` or
``main(full_reset=False)`` and a few forgot to propagate returned failures from
their ``__main__`` blocks. Running through this module makes those failures
visible without requiring every historical generator to be edited at once.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from feedgen.entry import FeedEntry


def freeze_missing_dates(entries, *, date_field="date", fallback=None):
    """Return entries with missing dates stamped once for cache persistence."""
    first_seen = fallback or datetime.now(timezone.utc)
    frozen = []
    for entry in entries:
        if entry.get(date_field) is not None:
            frozen.append(entry)
            continue
        repaired = dict(entry)
        repaired[date_field] = first_seen
        frozen.append(repaired)
    return frozen


@contextmanager
def freeze_merged_entry_dates() -> Iterator[None]:
    """Prevent cache-based generators from persisting permanently undated rows.

    Most generators merge dictionaries through ``utils.merge_entries`` before
    saving their JSON cache. Wrap that merge while a generator is imported and
    run, assigning one first-seen timestamp to new or historical rows whose
    scraper supplied no date. The saved cache freezes the value on subsequent
    runs. Entries with real dates remain untouched.
    """
    import utils

    original_merge_entries = utils.merge_entries
    first_seen = datetime.now(timezone.utc)

    def merge_entries_with_dates(
        new_entries,
        cached_entries,
        id_field="link",
        date_field="date",
    ):
        return original_merge_entries(
            freeze_missing_dates(
                new_entries,
                date_field=date_field,
                fallback=first_seen,
            ),
            freeze_missing_dates(
                cached_entries,
                date_field=date_field,
                fallback=first_seen,
            ),
            id_field=id_field,
            date_field=date_field,
        )

    utils.merge_entries = merge_entries_with_dates
    try:
        yield
    finally:
        utils.merge_entries = original_merge_entries


@contextmanager
def preserve_atom_publication_dates() -> Iterator[None]:
    """Use ``published`` when Feedgen would invent an entry ``updated`` value.

    Feedgen initializes every new Atom entry with the current time because
    ``updated`` is required by the Atom specification. Track calls to its public
    ``updated(...)`` setter while a generator runs. Immediately before
    serialization, replace only the untouched constructor default with the
    entry's publication date. Explicit update timestamps, including changing
    weather forecasts, remain intact.
    """
    original_updated = FeedEntry.updated
    original_atom_entry = FeedEntry.atom_entry

    def tracked_updated(self, updated=None):
        if updated is not None:
            self._feedseek_explicit_updated = True
        return original_updated(self, updated)

    def atom_entry_with_stable_default(self, extensions=True):
        if not getattr(self, "_feedseek_explicit_updated", False):
            published = self.published()
            if published is not None:
                original_updated(self, published)
        return original_atom_entry(self, extensions=extensions)

    FeedEntry.updated = tracked_updated
    FeedEntry.atom_entry = atom_entry_with_stable_default
    try:
        yield
    finally:
        FeedEntry.updated = original_updated
        FeedEntry.atom_entry = original_atom_entry


@contextmanager
def isolated_argv(script: Path, *, full: bool = False) -> Iterator[None]:
    """Expose only generator arguments while importing and running its module."""
    previous = sys.argv
    sys.argv = [str(script), *(["--full"] if full else [])]
    try:
        yield
    finally:
        sys.argv = previous


def load_module(script: Path):
    module_name = f"feedseek_generator_{script.stem}"
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load generator: {script}")
    module = importlib.util.module_from_spec(spec)
    # Some decorators and runtime type helpers resolve their module through
    # sys.modules while the file is executing, so register it before exec.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def result_succeeded(result: object) -> bool:
    """Normalize historical generator result conventions."""
    if result is None:
        return True
    if isinstance(result, bool):
        return result
    if isinstance(result, int):
        return result == 0
    return True


def invoke(script: Path, *, full: bool = False) -> bool:
    with (
        freeze_merged_entry_dates(),
        preserve_atom_publication_dates(),
        isolated_argv(script, full=full),
    ):
        module = load_module(script)
        main = getattr(module, "main", None)
        if not callable(main):
            raise RuntimeError(f"Generator does not expose main(): {script}")
        main_func = cast(Callable[..., object], main)

        parameters = inspect.signature(main_func).parameters
        if not parameters:
            result = main_func()
        elif "full" in parameters:
            result = main_func(full=full)
        elif "full_reset" in parameters:
            result = main_func(full_reset=full)
        else:
            result = main_func(full)

    return result_succeeded(result)


def cli() -> int:
    parser = argparse.ArgumentParser(description="Invoke one feed generator")
    parser.add_argument("script", type=Path)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    return 0 if invoke(args.script.resolve(), full=args.full) else 1


if __name__ == "__main__":
    try:
        sys.exit(cli())
    except Exception as exc:
        print(f"Generator invocation failed: {exc}", file=sys.stderr)
        raise
