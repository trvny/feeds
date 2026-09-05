"""A generator that fetches images must also emit them.

This bug class has landed three times: daily_digest (16.08.2026), then xai,
openai, claude and nexusmods_news (PR #274, 22.08.2026), then hackerone and
olx_group (25.08.2026). The shape is always identical - the generator calls
``enrich_entries``, the picture is fetched from someone else's server, written
into the entry dict and saved to the cache, and then the Atom builder never
renders it. Readers see nothing, and the entry is now marked as resolved so the
picture is never looked up again.

Counting imports of ``article_image`` cannot see this and never could: the
enrichment arrives through ``enrich.py`` and ``multi_rss.py``. What settles it
is whether the generator that *asks* for an image also *emits* one - either in
its own file, or in the builder it delegates to. Delegation is common here
(``anthropic`` hands its entries to ``_anthropic_base.generate_atom_feed``),
so the check follows it rather than treating it as a miss.
"""

import ast
import unittest
from pathlib import Path

GENERATORS = Path(__file__).resolve().parents[1] / "feed_generators"

# Builders a generator may hand its entries to instead of assembling the feed
# itself. Reaching one of these means the media question is answered there.
DELEGATING_CALLS = ("generate_atom_feed", "run")


def parse_all() -> dict[str, ast.AST]:
    return {
        path.stem: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in sorted(GENERATORS.glob("*.py"))
    }


def direct_calls(tree: ast.AST) -> set[str]:
    """Every function name called in the module, bare or attribute."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def delegates_to(tree: ast.AST, modules: set[str]) -> set[str]:
    """Local modules whose builder this module calls, e.g. ``anthropic.generate_atom_feed``."""
    targets: set[str] = set()
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in modules:
                    aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in modules:
            # ``from multi_rss import run`` - the name lands bare in this module.
            for alias in node.names:
                if alias.name in DELEGATING_CALLS:
                    targets.add(node.module)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and node.func.attr in DELEGATING_CALLS:
            resolved = aliases.get(owner.id)
            if resolved:
                targets.add(resolved)
    return targets


class ImageEmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.trees = parse_all()
        cls.modules = set(cls.trees)
        cls.calls = {name: direct_calls(tree) for name, tree in cls.trees.items()}
        cls.delegates = {
            name: delegates_to(tree, cls.modules) for name, tree in cls.trees.items()
        }

    def emits_media(self, module: str, seen: frozenset[str] = frozenset()) -> bool:
        if module in seen or module not in self.calls:
            return False
        if "add_entry_media" in self.calls[module]:
            return True
        return any(
            self.emits_media(target, seen | {module})
            for target in self.delegates[module]
        )

    def test_every_enriching_generator_also_emits_media(self):
        offenders = [
            name
            for name in sorted(self.modules)
            if "enrich_entries" in self.calls[name] and not self.emits_media(name)
        ]
        self.assertEqual(
            offenders,
            [],
            "these generators fetch images and then drop them at write time; add "
            "setup_feed_extensions(fg) and add_entry_media(fe, entry.get('image')) "
            "to their builder: " + ", ".join(offenders),
        )

    def test_every_media_emitting_generator_declares_the_namespace(self):
        # add_entry_media() no-ops unless setup_feed_extensions() ran on the
        # parent feed, and a silent no-op looks exactly like a working feed.
        offenders = [
            name
            for name in sorted(self.modules)
            if "add_entry_media" in self.calls[name]
            and "setup_feed_extensions" not in self.calls[name]
        ]
        self.assertEqual(offenders, [], ", ".join(offenders))


if __name__ == "__main__":
    unittest.main()
