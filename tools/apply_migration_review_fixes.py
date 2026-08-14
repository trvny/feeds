#!/usr/bin/env python3
"""One-shot fixes for the Feedseek root migration review."""

from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def replace(pathname: str, old: str, new: str) -> None:
    path = ROOT / pathname
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing replacement in {pathname}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    replace(
        "site/make_favicon.py",
        'ROOT = Path(__file__).resolve().parents[2]\nICONS = ROOT / "assets" / "icons"\nOUTPUT = ROOT / "feedseek" / "public" / "favicon.ico"',
        'ROOT = Path(__file__).resolve().parents[1]\nICONS = ROOT / "assets" / "icons"\nOUTPUT = ROOT / "public" / "favicon.ico"',
    )

    replace("feed_generators/jsonfeed.py", "import json\nimport os\nfrom datetime", "import json\nfrom datetime")
    replace("feed_generators/jsonfeed.py", "from utils import large_icon", "from utils import REPO_SLUG, large_icon")
    replace(
        "feed_generators/jsonfeed.py",
        'REPO_SLUG = os.getenv("RSS_REPO_SLUG") or os.getenv("GITHUB_REPOSITORY") or "trvny/feedseek"\n_FEED_URL_TMPL',
        "_FEED_URL_TMPL",
    )

    replace("feed_generators/normalize_feed_self_links.py", "import logging\nimport os\nimport re", "import logging\nimport re")
    replace(
        "feed_generators/normalize_feed_self_links.py",
        "logger = logging.getLogger(__name__)",
        "from utils import REPO_SLUG\n\nlogger = logging.getLogger(__name__)",
    )
    replace(
        "feed_generators/normalize_feed_self_links.py",
        'REPO_SLUG = os.getenv("RSS_REPO_SLUG") or os.getenv("GITHUB_REPOSITORY") or "trvny/feedseek"\nCURRENT_PREFIX = f"https://raw.githubusercontent.com/{REPO_SLUG}/main/feeds/"\nLEGACY_PREFIX = "https://raw.githubusercontent.com/trvny/feedseek/main/feedseek/feeds/"\nLEGACY_PREFIXES = (LEGACY_PREFIX, "https://raw.githubusercontent.com/trvny/feedseek/main/feeds/")',
        'CURRENT_PREFIX = f"https://raw.githubusercontent.com/{REPO_SLUG}/main/feeds/"\nLEGACY_PREFIX = "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/"\nLEGACY_PREFIXES = (\n    LEGACY_PREFIX,\n    "https://raw.githubusercontent.com/trvny/feeds/main/feeds/",\n    f"https://raw.githubusercontent.com/{REPO_SLUG}/main/feedseek/feeds/",\n)',
    )

    replace("feed_generators/esa.py", "from multi_rss import run", "from multi_rss import run\nfrom utils import REPO_SLUG")
    replace(
        "feed_generators/esa.py",
        'ICON_URL = "https://raw.githubusercontent.com/trvny/feedseek/main/assets/icons/esa.png"',
        'ICON_URL = f"https://raw.githubusercontent.com/{REPO_SLUG}/main/assets/icons/esa.png"',
    )

    registry = ROOT / "tests/test_registry_docs.py"
    text = registry.read_text(encoding="utf-8")
    text, count = re.subn(
        r'HERE = Path\(__file__\)\.resolve\(\)\nNESTED_ROOT = HERE\.parents\[2\]\nROOT = .*?\nFEEDSEEK = .*?\n',
        'HERE = Path(__file__).resolve()\nROOT = HERE.parents[1]\nFEEDSEEK = ROOT\n',
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("registry root block not found")
    registry.write_text(text, encoding="utf-8")

    replace(
        ".github/workflows/mega-linter.yml",
        "Makefile pyproject.toml uv.lock feeds.yaml feed_generators/ tests/ site/ docs/ README.md README_pl.md",
        "Makefile pyproject.toml uv.lock feeds.yaml feed_generators/ tests/ tools/ site/ docs/ .github/skills/ README.md README_pl.md",
    )
    replace(
        ".github/linters/.mega-linter.yml",
        'FILTER_REGEX_EXCLUDE: "(feeds/|cache/|public/|kanarek/|assets/icons/|package-lock\\\\.json)"',
        'FILTER_REGEX_EXCLUDE: "(^feeds/|^cache/|^public/|^kanarek/|^feeds-proxy/|^assets/icons/|package-lock\\\\.json)"',
    )

    readme = ROOT / "README_pl.md"
    text = readme.read_text(encoding="utf-8")
    new_tree = """```text
feedseek/
├── feed_generators/   # generatory i wspólne narzędzia
├── feeds/             # wygenerowane XML/JSON
├── site/              # GitHub Pages + czytnik
├── feeds-proxy/       # pomocniczy Worker Cloudflare
├── feedseek/feeds/    # zgodność ze starymi klientami Kanarka
└── .github/workflows/ # generowanie, publikacja i testy
```"""
    text, count = re.subn(
        r"(?s)(## Układ repozytorium\n\n)```text\n.*?\n```",
        lambda match: match.group(1) + new_tree,
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("README_pl repository tree not found")
    text = text.replace("`feedseek/README.md` i `docs/`", "`README.md` i `docs/`")
    text = text.replace("trvny.github.io/feeds/", "trvny.github.io/feedseek/")
    readme.write_text(text, encoding="utf-8")

    for pathname in (
        ".github/skills/feedseek/SKILL.md",
        ".github/skills/feedseek/references/add-feed.md",
        ".github/skills/feedseek/references/fix.md",
        ".github/skills/feedseek/references/review.md",
    ):
        path = ROOT / pathname
        text = path.read_text(encoding="utf-8")
        for old, new in (
            ("trvny/feeds/feedseek", "trvny/feedseek"),
            ("From `feedseek/`:", "From the repository root:"),
            ("from `feedseek/`", "from the repository root"),
            ("`feedseek/feeds.yaml`", "`feeds.yaml`"),
            ("`feedseek/feed_generators/", "`feed_generators/"),
            ("`feedseek/tests/", "`tests/"),
            ("`feedseek/tools/", "`tools/"),
            ("`feedseek/docs/", "`docs/"),
            ("`feedseek/README.md`", "`README.md`"),
            ("cd feedseek\n", ""),
        ):
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    build = ROOT / "site/build_site.py"
    text = build.read_text(encoding="utf-8").replace(
        ">github.com/trvny/feeds</a>", ">github.com/trvny/feedseek</a>"
    )
    build.write_text(text, encoding="utf-8")

    compat = ROOT / "tools/sync_legacy_feed_paths.py"
    compat.write_text(
        '''#!/usr/bin/env python3
"""Mirror released Kanarek default feeds at their historical raw paths."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "feeds"
TARGET = ROOT / "feedseek" / "feeds"
NAMES = (
    "pap", "reuters", "wikipedia_pl", "daily_digest", "daily_quote",
    "jbzd", "beatport_top100", "cloudflare",
)


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    expected: set[str] = set()
    for name in NAMES:
        for suffix in ("xml", "json"):
            source = SOURCE / f"feed_{name}.{suffix}"
            if source.exists():
                target = TARGET / source.name
                shutil.copyfile(source, target)
                expected.add(target.name)
    for path in TARGET.glob("feed_*.*"):
        if path.name not in expected:
            path.unlink()


if __name__ == "__main__":
    main()
''',
        encoding="utf-8",
    )

    workflow = ROOT / ".github/workflows/update-feeds.yml"
    text = workflow.read_text(encoding="utf-8")
    marker = """      - name: Regenerate docs/sources.md
        continue-on-error: true
        working-directory: .
        run: uv run --locked feed_generators/docs_sources.py"""
    addition = marker + """

      - name: Sync legacy Kanarek feed paths
        working-directory: .
        run: python3 tools/sync_legacy_feed_paths.py"""
    if marker not in text:
        raise SystemExit("update-feeds insertion point not found")
    text = text.replace(marker, addition, 1)
    text = text.replace(
        "git add feeds cache docs/sources.md",
        "git add feeds feedseek/feeds cache docs/sources.md",
    )
    workflow.write_text(text, encoding="utf-8")

    agents = ROOT / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    text = text.replace(
        "- `feeds-proxy/`: supporting Cloudflare Worker that remains in this repository.\n",
        "- `feeds-proxy/`: supporting Cloudflare Worker that remains in this repository.\n"
        "- `feedseek/feeds/`: compatibility mirror for raw URLs embedded in released Kanarek clients; generated by `tools/sync_legacy_feed_paths.py`, never edit it by hand.\n",
    )
    agents.write_text(text, encoding="utf-8")

    source = ROOT / "feeds"
    target = ROOT / "feedseek/feeds"
    target.mkdir(parents=True, exist_ok=True)
    names = (
        "pap", "reuters", "wikipedia_pl", "daily_digest", "daily_quote",
        "jbzd", "beatport_top100", "cloudflare",
    )
    expected: set[str] = set()
    for name in names:
        for suffix in ("xml", "json"):
            src = source / f"feed_{name}.{suffix}"
            if src.exists():
                dst = target / src.name
                shutil.copyfile(src, dst)
                expected.add(dst.name)
    for path in target.glob("feed_*.*"):
        if path.name not in expected:
            path.unlink()


if __name__ == "__main__":
    main()
