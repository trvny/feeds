from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one marker in {path}, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_before(path, marker, block, sentinel):
    text = path.read_text(encoding="utf-8")
    if sentinel in text:
        return
    if marker not in text:
        raise RuntimeError(f"marker missing in {path}: {marker!r}")
    path.write_text(text.replace(marker, block + marker, 1), encoding="utf-8")


def patch_limits():
    replacements = {
        "feedseek/feed_generators/audio.py": ("max_entries=250,", "max_entries=260,"),
        "feedseek/feed_generators/microsoft.py": ("max_entries=300,", "max_entries=470,"),
        "feedseek/feed_generators/tvp.py": ("max_entries=250,", "max_entries=275,"),
        "feedseek/feed_generators/usgov.py": ("max_entries=300,", "max_entries=415,"),
    }
    for name, (old, new) in replacements.items():
        replace_once(ROOT / name, old, new)


def patch_github_generator():
    path = ROOT / "feedseek/feed_generators/github.py"
    text = path.read_text(encoding="utf-8")
    old_sources = '''SOURCES = [
    ("The GitHub Blog", "https://github.blog/feed/", 40),
    ("GitHub Changelog", "https://github.blog/changelog/feed/", 40),
    ("GitHub Engineering", "https://github.blog/engineering/feed/", 30),
    ("GitHub Security", "https://github.blog/security/feed/", 30),
    ("GitHub Open Source", "https://github.blog/open-source/feed/", 30),
    ("GitHub AI & ML", "https://github.blog/ai-and-ml/feed/", 30),
    ("GitHub Enterprise", "https://github.blog/enterprise-software/feed/", 20),
    ("GitHub Status", "https://www.githubstatus.com/history.atom", 25),
    ("Komi Store", "https://komistore.app/blog/feed.xml", 20),
]
'''
    new_sources = '''SOURCES = [
    ("GitHub Changelog", "https://github.blog/changelog/feed/", 40),
    ("GitHub Engineering", "https://github.blog/engineering/feed/", 30),
    ("GitHub Security", "https://github.blog/security/feed/", 30),
    ("GitHub Open Source", "https://github.blog/open-source/feed/", 30),
    ("GitHub AI & ML", "https://github.blog/ai-and-ml/feed/", 30),
    ("GitHub Enterprise", "https://github.blog/enterprise-software/feed/", 20),
    ("GitHub Status", "https://www.githubstatus.com/history.atom", 25),
    ("Komi Store", "https://komistore.app/blog/feed.xml", 20),
    ("The GitHub Blog", "https://github.blog/feed/", 40),
]
'''
    if new_sources not in text:
        if old_sources not in text:
            raise RuntimeError("GitHub SOURCES block changed unexpectedly")
        text = text.replace(old_sources, new_sources, 1)
    if 'refresh_sources=("GitHub Status",),' not in text:
        marker = "        sources=SOURCES,\n"
        if marker not in text:
            raise RuntimeError("GitHub run() sources marker missing")
        text = text.replace(marker, marker + '        refresh_sources=("GitHub Status",),\n', 1)
    path.write_text(text, encoding="utf-8")


def patch_multi_rss():
    path = ROOT / "feedseek/feed_generators/multi_rss.py"
    replace_once(
        path,
        "    sources=(),\n    extra_scrapers=(),\n",
        "    sources=(),\n    refresh_sources=(),\n    extra_scrapers=(),\n",
    )
    replace_once(
        path,
        '    known_links = {entry["link"] for entry in cached}\n',
        '    refresh_sources = set(refresh_sources)\n'
        '    known_links = {entry["link"] for entry in cached}\n',
    )
    old_loop = '''    for label, url, cap in sources:
        logger.info("Scraping %s ...", label)
        new_articles += scrape_feed(
            label, url, known_links, cap=cap, keep_html=keep_html
        )
'''
    new_loop = '''    for label, url, cap in sources:
        logger.info("Scraping %s ...", label)
        source_known_links = known_links
        if label in refresh_sources:
            source_known_links = known_links - {
                entry["link"] for entry in cached if entry.get("source") == label
            }
        scraped = scrape_feed(
            label, url, source_known_links, cap=cap, keep_html=keep_html
        )
        if label in refresh_sources and scraped:
            refreshed_links = {entry["link"] for entry in scraped}
            cached = [
                entry
                for entry in cached
                if not (
                    entry.get("source") == label
                    and entry["link"] in refreshed_links
                )
            ]
        new_articles += scraped
'''
    replace_once(path, old_loop, new_loop)


def patch_docs_registry():
    path = ROOT / "feedseek/feed_generators/docs_sources.py"
    text = path.read_text(encoding="utf-8")
    if "# fmt: off" not in text:
        text = text.replace(
            "# ---------------------------------------------------------------------------\n# REGISTRY: feed_key -> (display title, [(label, url), ...])\n",
            "# fmt: off\n# ---------------------------------------------------------------------------\n# REGISTRY: feed_key -> (display title, [(label, url), ...])\n",
            1,
        )
    if "# fmt: on\n\n# ---------------------------------------------------------------------------\n# rendering" not in text:
        text = text.replace(
            "]\n\n# ---------------------------------------------------------------------------\n# rendering",
            "]\n# fmt: on\n\n# ---------------------------------------------------------------------------\n# rendering",
            1,
        )
    path.write_text(text, encoding="utf-8")

    europa = '''"europa": ("Europa — instytucje europejskie", [
    ("Parlament Europejski (PL, Google News)", "https://news.google.com/rss/search?q=site:europarl.europa.eu/news&hl=pl&gl=PL&ceid=PL:pl"),
    ("Komisja Europejska (PL)", "https://ec.europa.eu/commission/presscorner/api/rss?language=pl"),
    ("European Commission (EN)", "https://ec.europa.eu/commission/presscorner/api/rss?language=en"),
    ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html"),
]),
'''
    insert_before(path, '"geopolitics":', europa, '"europa": (')

    github = '''"github": ("GitHub", [
    ("GitHub Changelog", "https://github.blog/changelog/feed/"),
    ("GitHub Engineering", "https://github.blog/engineering/feed/"),
    ("GitHub Security", "https://github.blog/security/feed/"),
    ("GitHub Open Source", "https://github.blog/open-source/feed/"),
    ("GitHub AI & ML", "https://github.blog/ai-and-ml/feed/"),
    ("GitHub Enterprise", "https://github.blog/enterprise-software/feed/"),
    ("GitHub Status", "https://www.githubstatus.com/history.atom"),
    ("Komi Store", "https://komistore.app/blog/feed.xml"),
    ("The GitHub Blog", "https://github.blog/feed/"),
]),
'''
    insert_before(path, '"mozilla":', github, '"github": (')

    audio = '''"audio": ("Audio.com.pl", [
    ("RSS — aktualności, muzyka i vademecum", "https://audio.com.pl/rss"),
    ("Testy sprzętu", "https://audio.com.pl/testy"),
]),
'''
    insert_before(path, "# ---- Rozrywka / memy ----", audio, '"audio": (')

    text = path.read_text(encoding="utf-8")
    stale = '    ("Firefox release notes + security advisories", "https://www.mozilla.org/en-US/security/advisories/"),\n'
    replacement = (
        '    ("Firefox desktop release metadata", "https://product-details.mozilla.org/1.0/firefox.json"),\n'
        '    ("Firefox Android release metadata", "https://product-details.mozilla.org/1.0/mobile_versions.json"),\n'
    )
    if stale in text:
        text = text.replace(stale, replacement, 1)
    elif "Firefox desktop release metadata" not in text:
        raise RuntimeError("stale Mozilla registry entry missing")

    text = text.replace(
        '("🌍 Świat — newsy", ["reuters","euronews","geopolitics"]),',
        '("🌍 Świat — newsy", ["reuters","euronews","europa","geopolitics"]),',
        1,
    )
    text = text.replace(
        '"docker","gitlab","mozilla"',
        '"docker","gitlab","github","mozilla"',
        1,
    )
    text = text.replace(
        '["trojka","czworka","foobar2000_news","ra","beatport_top100"]',
        '["trojka","czworka","foobar2000_news","ra","beatport_top100","audio"]',
        1,
    )
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_limits()
    patch_github_generator()
    patch_multi_rss()
    patch_docs_registry()
