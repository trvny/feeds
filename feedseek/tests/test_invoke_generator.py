import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from invoke_generator import invoke  # noqa: E402


class InvokeGeneratorTests(unittest.TestCase):
    def _script(self, source: str) -> Path:
        directory = Path(tempfile.mkdtemp())
        path = directory / "generator.py"
        path.write_text(source, encoding="utf-8")
        return path

    def test_explicit_false_is_a_failed_generation(self):
        script = self._script("def main(full=False):\n    return False\n")
        self.assertFalse(invoke(script))

    def test_none_remains_backward_compatible_success(self):
        script = self._script("def main():\n    pass\n")
        self.assertTrue(invoke(script))

    def test_integer_exit_statuses_are_normalized(self):
        success = self._script("def main():\n    return 0\n")
        failure = self._script("def main():\n    return 1\n")
        self.assertTrue(invoke(success))
        self.assertFalse(invoke(failure))

    def test_full_reset_signature_is_supported(self):
        script = self._script(
            "def main(full_reset=False):\n"
            "    return full_reset\n"
        )
        self.assertTrue(invoke(script, full=True))
        self.assertFalse(invoke(script, full=False))

    def test_generator_receives_isolated_argv(self):
        script = self._script(
            "import argparse\n"
            "def main():\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--full', action='store_true')\n"
            "    return 0 if parser.parse_args().full else 1\n"
        )
        self.assertTrue(invoke(script, full=True))
        self.assertFalse(invoke(script, full=False))

    def test_decorators_can_resolve_dynamic_module(self):
        script = self._script(
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Item:\n"
            "    value: int\n"
            "def main():\n"
            "    return Item(1).value == 1\n"
        )
        self.assertTrue(invoke(script))


if __name__ == "__main__":
    unittest.main()
