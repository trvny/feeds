"""Invoke one feed generator and translate its ``main`` result to an exit code.

This adapter keeps generator execution isolated while enforcing the project
contract centrally. Older scripts use either ``main(full=False)`` or
``main(full_reset=False)`` and a few forgot to propagate a returned ``False``
from their ``__main__`` blocks. Running through this module makes those failures
visible without requiring every historical generator to be edited at once.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
from pathlib import Path


def load_module(script: Path):
    spec = importlib.util.spec_from_file_location(f"feedseek_generator_{script.stem}", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load generator: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(script: Path, *, full: bool = False) -> bool:
    module = load_module(script)
    main = getattr(module, "main", None)
    if not callable(main):
        raise RuntimeError(f"Generator does not expose main(): {script}")

    parameters = inspect.signature(main).parameters
    if not parameters:
        result = main()
    elif "full" in parameters:
        result = main(full=full)
    elif "full_reset" in parameters:
        result = main(full_reset=full)
    else:
        result = main(full)

    # None remains compatible with old scripts that complete successfully but
    # do not return explicitly. An explicit False is always a failed generation.
    return result is not False


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
