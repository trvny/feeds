#!/usr/bin/env python3
"""Generate ``docs/sources.md`` — the per-feed list of concrete source links.

This used to carry a hand-written ``REGISTRY`` of every feed's sources, ~540
lines of it, kept in step with the generators by a drift warning. It drifted
anyway: it covered 69 of 92 feeds, and 14 of those entries listed one source for
a generator that had many. ``euronews`` was the worst — a single entry holding
the unformatted template ``...&level={level}&name={name}``, a URL that resolves
to nothing, while the generator actually pulls 14 real ones.

So the registry is gone and the generators are the source of truth. The old
docstring argued a registry was unavoidable because many generators build their
URLs procedurally (query strings, formatted templates, endpoints assembled in
code) and "a naive parse-the-SOURCES-list pass would silently drop those". That
is true of *AST parsing*, which is what the drift check did — and it is exactly
why the euronews template showed up verbatim. It is not true of *importing* the
module: import runs the construction, so ``.format()`` templates arrive fully
resolved. Every generator was checked to import cleanly with no side effects
(they define constants and functions; ``main()`` only runs under ``__main__``).
AST parsing stays as a fallback for a module that fails to import.

Display names come from each feed's own ``<title>``, so there is no third copy
of the naming to drift either — and they are consistently at or below the length
used in README.md ("AI-bridge" rather than "AI-bridge (combined AI sources)").

A new feed therefore needs no entry here at all: it appears with its full source
list as soon as it is in ``feeds.yaml``.

Run from the ``feed_generators/`` dir:  ``python3 docs_sources.py``
Add ``--check`` to report coverage without writing the file.
"""

import argparse
import ast
import contextlib
import importlib
import io
import sys
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # feedseek/
FEEDS_YAML = ROOT / "feeds.yaml"
FEEDS_DIR = ROOT / "feeds"
OUT = ROOT / "docs" / "sources.md"
ATOM = "{http://www.w3.org/2005/Atom}"

# Generator module-level names that hold a list of (label, url[, cap]) tuples.
LIST_NAMES = ("SOURCES", "RSS_SOURCES", "NATIVE_FEEDS", "FEED_SOURCES")

# fmt: off
# grouping: feed_key order within each themed section
GROUPS = [
    ("🇵🇱 Polska — rząd i informacje", ["govpl_news", "pap", "tvp", "spidersweb"]),
    ("🌍 Świat — newsy", ["reuters", "euronews", "europa", "geopolitics"]),
    ("🤖 AI / LLM", ["anthropic", "claude", "openai", "xai", "aibridge", "skillsllm"]),
    ("💻 Tech / vendorzy oprogramowania", ["microsoft", "microsoft_updates", "cloudflare", "docker", "gitlab", "github", "mozilla", "google", "apple", "sony", "lenovo", "canva", "youtube", "meta_newsroom", "saas", "hackerone", "creativecommons", "x_changelog"]),
    ("🌦️ Pogoda", ["openweather", "visualcrossing", "open_meteo", "accuweather", "imgw"]),
    ("🎮 Gaming", ["steam", "ea", "bethesda", "nexusmods_news", "lichess"]),
    ("🚗 Motoryzacja", ["lexus_newsroom", "toyota_global"]),
    ("🏦 Bank", ["pekao"]),
    ("🚀 Kosmos / nauka / rząd USA", ["nasa", "esa", "usgov", "wikipedia_pl"]),
    ("🎵 Radio / muzyka", ["trojka", "czworka", "foobar2000_news", "ra", "beatport_top100", "audio", "radios"]),
    ("😂 Rozrywka / memy", ["cheezburger", "memedroid", "9gag", "jbzd", "4chan"]),
    ("🛒 Ogłoszenia", ["olx"]),
    ("🧩 Userscripts", ["userscripts"]),
    ("📅 Codzienne", ["daily_digest", "daily_quote", "wotd", "datime"]),
]
# fmt: on


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------


def load_yaml_feeds() -> dict:
    """feed_key -> {'blog_url': ..., 'script': ...} straight from feeds.yaml.

    feeds.yaml stays the canonical feed set, so the doc can never list a feed
    that is not published.
    """
    data = yaml.safe_load(FEEDS_YAML.read_text(encoding="utf-8")) or {}
    return {
        str(key): {
            "blog_url": (cfg or {}).get("blog_url", ""),
            "script": (cfg or {}).get("script", ""),
        }
        for key, cfg in (data.get("feeds") or {}).items()
    }


def feed_title(feed_key: str) -> str:
    """The feed's own <title>, which is the shortest accurate name available."""
    path = FEEDS_DIR / f"feed_{feed_key}.xml"
    if not path.exists():
        return feed_key
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return feed_key
    # Atom puts <title> on the root; RSS nests it under <channel>.
    title = root.findtext(f"{ATOM}title") or root.findtext("channel/title") or ""
    return title.strip() or feed_key


# ---------------------------------------------------------------------------
# source extraction
# ---------------------------------------------------------------------------


def _label_for(url: str) -> str:
    """Readable label for a bare URL: host, plus a hint of what it selects.

    Google-News-backed generators differ only in the query string, so the host
    alone would render several identical-looking lines.
    """
    parts = urlparse(url)
    host = parts.netloc or url
    if parts.query:
        for field in ("q", "name", "domain"):
            marker = f"{field}="
            for chunk in parts.query.split("&"):
                if chunk.startswith(marker):
                    value = chunk[len(marker) :].replace("+", " ")
                    return f"{host} ({value})" if value else host
    tail = parts.path.strip("/").split("/")[-1]
    return f"{host} ({tail})" if tail and "." not in tail else host


def _pairs_from_value(value) -> list:
    """(label, url) pairs from a source list.

    Handles both shapes generators use: (label, url[, cap]) tuples, and a plain
    list of URL strings (reuters, google, xai and friends), which the tuple-only
    reading skipped and pushed onto the blog_url fallback.
    """
    if not isinstance(value, (list, tuple)):
        return []
    pairs = []
    for item in value:
        if isinstance(item, str) and item.startswith("http"):
            pairs.append((_label_for(item), item))
            continue
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        label, url = item[0], item[1]
        if isinstance(label, str) and isinstance(url, str) and url.startswith("http"):
            pairs.append((label.strip() or urlparse(url).netloc, url))
    return pairs


def sources_by_import(script: str) -> list:
    """Import the generator and read its resolved source tuples.

    Import rather than AST-parse so procedurally built URLs (``.format()``
    templates, query strings assembled in code) arrive as the real thing.
    Generator output during import is swallowed: several call setup_logging()
    at module level and would otherwise scribble over this script's stdout.
    """
    module_name = script.removesuffix(".py")
    if not module_name:
        return []
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            module = importlib.import_module(module_name)
    except Exception as exc:  # a broken generator must not sink the whole doc
        print(f"[warn] could not import {script}: {exc}", file=sys.stderr)
        return []

    pairs, seen = [], set()
    # Sorted attribute order keeps the rendered doc stable between runs.
    for attr in sorted(vars(module)):
        if attr.startswith("_") or not attr.isupper():
            continue
        for label, url in _pairs_from_value(getattr(module, attr)):
            if url not in seen:
                seen.add(url)
                pairs.append((label, url))
    return pairs


def sources_by_ast(script: str) -> list:
    """Fallback for a module that will not import: static list literals only."""
    path = HERE / script
    if not path.exists():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    urls, seen = [], set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id in LIST_NAMES for t in node.targets):
            continue
        for sub in ast.walk(node.value):
            if (
                isinstance(sub, ast.Constant)
                and isinstance(sub.value, str)
                and sub.value.startswith("http")
                and sub.value not in seen
            ):
                seen.add(sub.value)
                urls.append((urlparse(sub.value).netloc or sub.value, sub.value))
    return urls


def collect_sources(feed_key: str, cfg: dict) -> tuple:
    """Return (pairs, origin). Falls back to the feed's own site.

    A single-source scraper (czworka, jbzd, openweather, …) legitimately has
    nothing to list but the site it scrapes, so blog_url is the right answer
    rather than a gap.
    """
    script = cfg.get("script", "")
    pairs = sources_by_import(script)
    if pairs:
        return pairs, "generator"
    pairs = sources_by_ast(script)
    if pairs:
        return pairs, "ast"
    blog = cfg.get("blog_url", "")
    if blog:
        return [("Strona źródłowa", blog)], "blog_url"
    return [], "none"


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def fav(url: str) -> str:
    host = urlparse(url).netloc or url
    return f"![](https://www.google.com/s2/favicons?domain={host}&sz=16) "


def render_plan(yaml_feeds: dict) -> list:
    """[(group title, [feed_key, ...])] — grouped first, leftovers under Inne."""
    grouped = {k for _, keys in GROUPS for k in keys}
    plan = [(title, [k for k in keys if k in yaml_feeds]) for title, keys in GROUPS]
    extras = sorted(k for k in yaml_feeds if k not in grouped)
    if extras:
        plan.append(("🗂️ Inne", extras))
    return [(title, keys) for title, keys in plan if keys]


def build_markdown(yaml_feeds: dict, collected: dict) -> str:
    plan = render_plan(yaml_feeds)
    n_feeds = sum(len(keys) for _, keys in plan)
    n_sources = sum(len(collected[k][0]) for _, keys in plan for k in keys)

    out = ["# Źródła feedów\n"]
    out.append(
        "Konkretne linki źródłowe wchodzące w skład każdego generowanego feeda. "
        "Listy są czytane wprost z generatorów, a nazwy z `<title>` samych feedów, "
        "więc nic tu nie trzeba dopisywać ręcznie przy nowym feedzie. Feedy zbiorcze "
        "(`aibridge`, `saas`, `skillsllm`, `pap`, `esa`, `google` itd.) łączą wiele "
        "źródeł w jeden strumień Atom.\n"
    )
    out.append(
        "> Plik generowany: `python3 feed_generators/docs_sources.py`. "
        "Nie edytuj ręcznie — zmień źródła w generatorze.\n"
    )
    out.append(f"{n_feeds} feedów · {n_sources} źródeł\n")

    out.append("## Spis grup\n")
    out.extend(f"- {title}" for title, _ in plan)
    out.append("")

    for title, keys in plan:
        out.append(f"## {title}\n")
        for key in keys:
            pairs, _ = collected[key]
            primary = pairs[0][1] if pairs else yaml_feeds[key].get("blog_url", "")
            out.append(f"### {fav(primary)}{feed_title(key)}")
            out.append(f"`{key}` · [feed_{key}.xml](../feeds/feed_{key}.xml)\n")
            for label, url in pairs:
                out.append(f"- {fav(url)}{label} — <{url}>")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def coverage_report(yaml_feeds: dict, collected: dict) -> int:
    """Report feeds with nothing better than their blog_url. Not a failure:
    single-source scrapers are supposed to look like that."""
    fallbacks = sorted(k for k, (_, origin) in collected.items() if origin != "generator")
    empty = sorted(k for k, (pairs, _) in collected.items() if not pairs)
    print(f"{len(yaml_feeds)} feedów w feeds.yaml", file=sys.stderr)
    print(
        f"{len(yaml_feeds) - len(fallbacks)} z listą źródeł z generatora, "
        f"{len(fallbacks)} tylko z blog_url",
        file=sys.stderr,
    )
    if fallbacks:
        print(f"  blog_url: {', '.join(fallbacks)}", file=sys.stderr)
    if empty:
        print(f"[error] bez jakiegokolwiek źródła: {', '.join(empty)}", file=sys.stderr)
    return len(empty)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate docs/sources.md")
    parser.add_argument(
        "--check", action="store_true", help="report coverage only, write nothing"
    )
    args = parser.parse_args()

    sys.path.insert(0, str(HERE))
    yaml_feeds = load_yaml_feeds()
    collected = {key: collect_sources(key, cfg) for key, cfg in yaml_feeds.items()}

    problems = coverage_report(yaml_feeds, collected)
    if args.check:
        return 1 if problems else 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" explicitly: the default translates to CRLF on Windows, so a
    # local run and a CI run would rewrite every line of a file that is
    # committed, burying the real change in whitespace churn.
    OUT.write_text(
        build_markdown(yaml_feeds, collected), encoding="utf-8", newline="\n"
    )
    print(f"wrote {OUT}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
