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
from pathlib import Path
from typing import cast


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
    with isolated_argv(script, full=full):
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
    parser = argparse.ArgumentParser(description="Invoke a feed generator")
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
