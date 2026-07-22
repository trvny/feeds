import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from invoke_generator import invoke


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

    def test_full_reset_signature_is_supported(self):
        script = self._script(
            "def main(full_reset=False):\n"
            "    return full_reset\n"
        )
        self.assertTrue(invoke(script, full=True))
        self.assertFalse(invoke(script, full=False))


if __name__ == "__main__":
    unittest.main()
