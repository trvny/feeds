import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import fourchan  # noqa: E402


class FourchanCapTests(unittest.TestCase):
    def test_main_sets_hard_per_source_publication_cap(self):
        with patch.object(fourchan, "run", return_value=True) as mocked_run:
            self.assertTrue(fourchan.main())

        kwargs = mocked_run.call_args.kwargs
        self.assertEqual(kwargs["per_source_cap"], {"": 20})
        self.assertEqual(kwargs["max_entries"], 200)


if __name__ == "__main__":
    unittest.main()
