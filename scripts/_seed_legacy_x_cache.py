from pathlib import Path

xai = Path("feed_generators/xai.py")
text = xai.read_text(encoding="utf-8")
anchor = (
    "# --------------------------------------------------------------------------- #\n"
    "# Orchestration\n"
    "# --------------------------------------------------------------------------- #\n"
)
helper = '''def _seed_legacy_x_api_cache(cached):
    """Migrate the old standalone X API cache on the first grouped run."""
    if any(entry.get("source") == "X API changelog" for entry in cached):
        return cached

    legacy = deserialize_entries(
        load_cache("x_changelog").get("entries", []), date_field="date"
    )
    if not legacy:
        return cached

    for entry in legacy:
        entry["source"] = "X API changelog"
    logger.info("Migrating %d entries from the legacy X API cache", len(legacy))
    merged = merge_entries(legacy, cached, id_field="link", date_field="date")
    return _cap_x_api_history(merged)


'''
if "def _seed_legacy_x_api_cache(" not in text:
    text = text.replace(anchor, helper + anchor)

old = '''    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")

    known_links = {e["link"] for e in cached}
'''
new = '''    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")
        cached = _seed_legacy_x_api_cache(cached)

    known_links = {e["link"] for e in cached}
'''
if old not in text:
    raise SystemExit("xAI cache initialization anchor not found")
text = text.replace(old, new, 1)
xai.write_text(text, encoding="utf-8")

Path("tests/test_xai_legacy_cache.py").write_text('''import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import xai


class XaiLegacyCacheTests(unittest.TestCase):
    def test_legacy_cache_is_seeded_when_grouped_cache_has_no_x_api(self):
        legacy = {
            "entries": [
                {
                    "title": "Legacy X API update",
                    "link": "https://docs.x.com/changelog#legacy",
                    "date": "2026-08-01T00:00:00+00:00",
                    "description": "Legacy update",
                }
            ]
        }
        with patch.object(xai, "load_cache", return_value=legacy):
            seeded = xai._seed_legacy_x_api_cache([])

        self.assertEqual(len(seeded), 1)
        self.assertEqual(seeded[0]["source"], "X API changelog")

    def test_existing_grouped_x_api_skips_legacy_cache(self):
        cached = [
            {
                "title": "Current X API update",
                "link": "https://docs.x.com/changelog#current",
                "source": "X API changelog",
            }
        ]
        with patch.object(xai, "load_cache") as load_cache:
            seeded = xai._seed_legacy_x_api_cache(cached)

        load_cache.assert_not_called()
        self.assertIs(seeded, cached)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")
