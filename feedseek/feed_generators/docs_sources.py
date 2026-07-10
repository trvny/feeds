#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate ``docs/sources.md`` — the per-feed list of concrete source links.

Why this is a registry, not a pure scraper of the generators: many generators
build their source URLs procedurally (Google-News query strings, weather API
endpoints, release-note pages assembled in code, aggregators that import a
sibling module's parser). A naive "parse the SOURCES list" pass would silently
drop those and produce an *incomplete* doc. So the source-of-truth data lives
in the ``REGISTRY`` below, and this script:

  * pulls the canonical feed set (and each feed's ``blog_url``) from
    ``feeds.yaml`` so the doc can never list a feed that isn't published;
  * renders the grouped Markdown (favicons, per-feed feed_<n>.xml link, counts,
    TOC) deterministically;
  * runs a DRIFT CHECK: for every generator that *does* expose a static
    ``SOURCES`` / ``RSS_SOURCES`` / ``NATIVE_FEEDS`` list literal, it AST-parses
    the URLs and warns when the generator lists a URL the REGISTRY doesn't
    mention (or vice-versa) — so editing a generator surfaces a TODO here;
  * warns when a feed in ``feeds.yaml`` has no REGISTRY entry (it still gets
    emitted under "Inne", using its blog_url, so nothing vanishes silently).

Run from the ``feed_generators/`` dir:  ``python3 docs_sources.py``
Add ``--check`` to only report drift / coverage and exit non-zero on problems
(no file write) — handy as a CI guard.
"""

import argparse
import ast
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # feedseek/
FEEDS_YAML = ROOT / "feeds.yaml"
OUT = ROOT / "docs" / "sources.md"

# Generator module-level names that hold a list of (label, url[, cap]) tuples.
LIST_NAMES = ("SOURCES", "RSS_SOURCES", "NATIVE_FEEDS", "FEED_SOURCES")

# ---------------------------------------------------------------------------
# REGISTRY: feed_key -> (display title, [(label, url), ...])
# Edit here when a generator's sources change (drift check will remind you).
# ---------------------------------------------------------------------------
REGISTRY = {
# ---- Polska: rząd i informacje ----
"govpl_news": ("gov.pl — administracja rządowa", [
    ("KPRM / wydarzenia", "https://www.gov.pl/web/premier/wydarzenia"),
    ("Profil Zaufany", "https://www.gov.pl/web/profilzaufany/aktualnosci"),
    ("Baza wiedzy", "https://www.gov.pl/web/baza-wiedzy/aktualnosci"),
    ("Min. Cyfryzacji", "https://www.gov.pl/web/cyfryzacja/wiadomosci"),
    ("Min. Zdrowia", "https://www.gov.pl/web/zdrowie/wiadomosci"),
    ("MON", "https://www.gov.pl/web/obrona-narodowa/aktualnosci5"),
    ("MSZ", "https://www.gov.pl/web/dyplomacja/aktualnosci"),
    ("RCB", "https://www.gov.pl/web/rcb/komunikaty"),
    ("UOKiK (RSS)", "https://uokik.gov.pl/feed"),
    ("UOKiK EN (RSS)", "https://uokik.gov.pl/en/feed"),
    ("Prezydent RP (via Google News)", "https://news.google.com/rss/search?q=site:prezydent.pl&hl=pl&gl=PL&ceid=PL:pl"),
]),
"pap": ("PAP — Polska Agencja Prasowa", [
    ("PAP Mediaroom", "https://pap-mediaroom.pl/rss.xml"),
    ("Nauka w Polsce", "https://naukawpolsce.pl/all/rss.xml"),
    ("PAP Zdrowie", "https://zdrowie.pap.pl/rss.xml"),
    ("Serwis Samorzadowy", "https://samorzad.pap.pl/rss.xml"),
    ("PAP Biznes", "https://biznes.pap.pl/rss"),
    ("EuroPAP News", "https://europapnews.pap.pl/rss.xml"),
    ("Dzieje.pl", "https://dzieje.pl/rss.xml"),
]),
"tvp": ("TVP", [
    ("TVP platform API", "https://www.tvp.pl/api/platform"),
    ("TVP Info (RSS)", "http://www.tvp.info/tvp.info/rss+xml.php"),
    ("TVP Sport (RSS)", "https://sport.tvp.pl/rss"),
    ("TVP / informacje", "https://www.tvp.pl/83939255/informacje"),
    ("TVP / aktualnosci", "https://www.tvp.pl/85859082/aktualnosci"),
    ("TVP / aktualnosci", "https://www.tvp.pl/44233674/aktualnosci"),
    ("TVP / moto", "https://www.tvp.pl/82263271/moto"),
]),
"spidersweb": ("Spider's Web (grupa)", [
    ("Spider's Web", "https://spidersweb.pl/api/post/feed/feed-gn"),
    ("Rozrywka SW", "https://rozrywka.spidersweb.pl/api/feed/feed-gn"),
    ("Autoblog SW", "https://autoblog.spidersweb.pl/api/feed/feed-gn"),
    ("Bizblog SW", "https://bizblog.spidersweb.pl/api/feed/feed-gn"),
    ("Bezprawnik", "https://bezprawnik.pl/api/feed-gn/"),
]),
# ---- Świat: newsy ----
"reuters": ("Reuters (via Google News)", [
    ("allinurl:reuters.com", "https://news.google.com/rss/search?q=when:7d+allinurl:reuters.com&hl=en-US&gl=US&ceid=US:en"),
    ("site:reuters.com", "https://news.google.com/rss/search?q=when:7d+site:reuters.com&hl=en-US&gl=US&ceid=US:en"),
    ("reuters.com", "https://news.google.com/rss/search?q=reuters.com&hl=en-US&gl=US&ceid=US:en"),
]),
"euronews": ("Euronews", [
    ("Euronews (per-level Atom RSS)", "https://www.euronews.com/rss?format=atom&level={level}&name={name}"),
]),
# ---- AI / LLM ----
"anthropic": ("Anthropic", [
    ("News", "https://www.anthropic.com/news"),
    ("Research", "https://www.anthropic.com/research"),
    ("Engineering", "https://www.anthropic.com/engineering"),
    ("Red team", "https://red.anthropic.com/"),
]),
"claude": ("Claude", [
    ("Code — what's new (RSS)", "https://code.claude.com/docs/en/whats-new/rss.xml"),
    ("Code — changelog (RSS)", "https://code.claude.com/docs/en/changelog/rss.xml"),
    ("Cowork changelog (RSS)", "https://claude.com/docs/cowork/changelog/rss.xml"),
    ("Support — release notes", "https://support.claude.com/en/articles/12138966-release-notes"),
    ("Platform — release notes", "https://platform.claude.com/docs/en/release-notes/overview.md"),
    ("Platform — system prompts", "https://platform.claude.com/docs/en/release-notes/system-prompts.md"),
    ("Status (Atom)", "https://status.claude.com/history.atom"),
]),
"openai": ("OpenAI", [
    ("News (RSS)", "https://openai.com/news/rss.xml"),
    ("Engineering (RSS)", "https://openai.com/news/engineering/rss.xml"),
    ("Product release notes (RSS)", "https://openai.com/products/release-notes/rss.xml"),
    ("Developers (RSS)", "https://developers.openai.com/rss.xml"),
    ("Codex changelog (RSS)", "https://developers.openai.com/codex/changelog/rss.xml"),
    ("Apps SDK changelog", "https://developers.openai.com/apps-sdk/changelog"),
    ("API docs changelog", "https://developers.openai.com/api/docs/changelog"),
]),
"xai": ("xAI", [
    ("News", "https://x.ai/news"),
    ("Build changelog", "https://x.ai/build/changelog"),
    ("Dev release notes", "https://docs.x.ai/developers/release-notes.md"),
]),
"aibridge": ("AI-bridge (laby + newslettery AI)", [
    ("Thinking Machines", "https://thinkingmachines.ai/blog/index.xml"),
    ("Ollama", "https://ollama.com/blog/rss.xml"),
    ("Mistral", "https://mistral.ai/rss.xml"),
    ("Interconnected", "https://interconnected.org/home/feed"),
    ("AI Clock (Substack)", "https://aiclock.substack.com/feed"),
    ("Glama — blog", "https://glama.ai/blog/rss.xml"),
    ("Glama — release notes", "https://glama.ai/release-notes"),
    ("Answer.AI", "https://www.answer.ai/index.xml"),
    ("CrewClaw", "https://crewclaw.com/blog"),
    ("Groq (blog/newsroom/changelog + GitHub Atom)", "https://groq.com/blog"),
    ("Perplexity (hub/changelog/research + docs RSS)", "https://www.perplexity.ai/hub/blog"),
    ("DeepLearning.AI — The Batch + blog", "https://www.deeplearning.ai/the-batch/"),
]),
"skillsllm": ("SkillsLLM (MCP / Claude Skills)", [
    ("Model Context Protocol blog", "https://blog.modelcontextprotocol.io/index.xml"),
    ("FastMCP changelog (RSS)", "https://gofastmcp.com/changelog/rss.xml"),
    ("Claude Plugin Hub", "https://claudepluginhub.com/feed.xml"),
    ("SkillsLLM (news + blog sitemap)", "https://skillsllm.com/"),
    ("Claude Skills Hub", "https://claudeskills.info/"),
    ("Desktop Commander", "https://desktopcommander.app/"),
    ("MCP Servers blog", "https://blog.mcpservers.org/"),
]),
# ---- Tech / vendorzy oprogramowania ----
"microsoft": ("Microsoft (blogi)", [
    ("Official blog", "https://blogs.microsoft.com/feed/"),
    ("On the Issues", "https://blogs.microsoft.com/on-the-issues/feed/"),
    ("Research", "https://www.microsoft.com/en-us/research/feed/"),
    ("Microsoft Source", "https://news.microsoft.com/source/feed/"),
    ("Source EMEA (PL)", "https://news.microsoft.com/source/emea/feed/?lang=pl"),
    ("Signal", "https://news.microsoft.com/signal/feed"),
    ("Unlocked (PL)", "https://unlocked.microsoft.com/pl/feed/"),
    ("Microsoft 365 blog", "https://www.microsoft.com/en-us/microsoft-365/blog/feed/"),
    ("DevBlogs", "https://devblogs.microsoft.com/feed"),
    ("Developer changelog", "https://developer.microsoft.com/api/changelog/rss"),
    ("Tech Community", "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/Community"),
]),
"microsoft_updates": ("Microsoft — aktualizacje Windows/Office", [
    ("Windows release health", "https://learn.microsoft.com/en-us/windows/release-health/windows-message-center"),
    ("Outlook (new) release notes", "https://learn.microsoft.com/en-us/officeupdates/release-notes-outlook-new"),
    ("Outlook mobile release notes", "https://learn.microsoft.com/en-us/officeupdates/release-notes-outlook-mobile"),
    ("ODT release history", "https://learn.microsoft.com/en-us/officeupdates/odt-release-history"),
    ("Copilot 365 release notes", "https://learn.microsoft.com/en-us/microsoft-365/copilot/release-notes?tabs=all"),
    ("support.microsoft.com Windows (via rss-bridge)", "https://support.microsoft.com/en-us/windows"),
]),
"cloudflare": ("Cloudflare", [
    ("Blog (RSS)", "https://blog.cloudflare.com/rss"),
    ("Changelog (RSS)", "https://developers.cloudflare.com/changelog/rss/index.xml"),
    ("Community (top RSS)", "https://community.cloudflare.com/top.rss"),
    ("Research", "https://research.cloudflare.com"),
]),
"docker": ("Docker", [
    ("Blog (RSS)", "https://www.docker.com/feed/"),
    ("Desktop release notes", "https://docs.docker.com/desktop/release-notes/"),
    ("Engine release notes", "https://docs.docker.com/engine/release-notes/"),
    ("Docker Hub release notes", "https://docs.docker.com/docker-hub/release-notes/"),
    ("Platform release notes", "https://docs.docker.com/platform-release-notes/"),
    ("DHI release notes", "https://docs.docker.com/dhi/release-notes/platform/"),
    ("Newsroom", "https://www.docker.com/company/newsroom/"),
]),
"gitlab": ("GitLab", [
    ("Blog (Atom)", "https://about.gitlab.com/atom.xml"),
    ("Press", "https://about.gitlab.com/press/"),
    ("What's new", "https://about.gitlab.com/whats-new/"),
    ("Releases (RSS)", "https://docs.gitlab.com/releases/releases.xml"),
    ("Patch releases (RSS)", "https://docs.gitlab.com/releases/patch-releases.xml"),
]),
"mozilla": ("Mozilla", [
    ("Mozilla blog", "https://blog.mozilla.org/feed/"),
    ("Nightly blog", "https://blog.nightly.mozilla.org/feed/"),
    ("Add-ons blog", "https://addons.mozilla.org/blog/feed.xml"),
    ("Hacks", "https://hacks.mozilla.org/feed/"),
    ("Thunderbird", "https://blog.thunderbird.net/feed/"),
    ("Planet Mozilla (Atom)", "https://planet.mozilla.org/atom.xml"),
    ("Firefox Nightly notes", "https://www.firefox.com/en-US/firefox/nightly/notes/feed/"),
    ("SpiderMonkey", "https://spidermonkey.dev/feed.xml"),
    ("Connect (forum RSS)", "https://connect.mozilla.org/bnzry48543/rss/Community?interaction.style=forum"),
    ("Firefox release notes + security advisories", "https://www.mozilla.org/en-US/security/advisories/"),
]),
"google": ("Google (blogi)", [
    ("Google blog (RSS)", "https://blog.google/rss/"),
    ("Google blog PL", "https://blog.google/intl/pl-pl/rss/"),
    ("Workspace Updates", "https://workspaceupdates.googleblog.com/atom.xml"),
    ("Developers blog", "https://developers.googleblog.com/feed/"),
    ("Android Developers", "https://android-developers.googleblog.com/atom.xml"),
    ("Chrome for Devs", "https://developer.chrome.com/static/blog/feed.xml"),
    ("Chromium", "https://blog.chromium.org/atom.xml"),
    ("Firebase", "https://firebase.blog/rss.xml"),
    ("Search Central", "https://developers.google.com/search/updates/search_docs_updates.rss"),
    ("Search status (Atom)", "https://status.search.google.com/en/feed.atom?hl=pl"),
    ("Waze", "https://blog.google/waze/rss/"),
    ("Google Research", "https://research.google/blog/rss/"),
    ("DeepMind", "https://deepmind.google/blog/rss.xml"),
    ("Google Cloud blog", "https://cloudblog.withgoogle.com/rss/"),
    ("Cloud press", "https://www.googlecloudpresscorner.com/press-releases?pagetemplate=rss"),
    ("Workspace updates (Feedburner)", "https://feeds.feedburner.com/GoogleAppsUpdates"),
    ("Analytics/Marketing Platform", "https://blog.google/products/marketingplatform/analytics/rss/"),
    ("Antigravity blog", "https://antigravity.google/blog"),
    ("Gemini CLI changelogs", "https://geminicli.com/docs/changelogs/"),
    ("Gemini API changelog", "https://ai.google.dev/gemini-api/docs/changelog"),
    ("GCP release notes", "https://docs.cloud.google.com/feeds/gcp-release-notes.xml"),
    ("Workspace release notes", "https://developers.google.com/feeds/workspace-release-notes.xml"),
    ("(+ Marketplace/Calendar/Docs/… release-note feeds)", "https://developers.google.com/feeds/marketplace-release-notes.xml"),
]),
"apple": ("Apple", [
    ("Newsroom PL (RSS)", "https://www.apple.com/pl/newsroom/rss-feed.rss"),
    ("Developer news (RSS)", "https://developer.apple.com/news/rss/news.rss"),
    ("Developer releases (RSS)", "https://developer.apple.com/news/releases/rss/releases.rss"),
]),
"sony": ("Sony", [
    ("Sony global (RSS)", "https://www.sony.co.jp/en/assets_revamp2025/xml/en/rss_new.xml"),
    ("PlayStation press", "https://sonyinteractive.com/en/news/press-releases/"),
    ("Sony corporate (RSS)", "https://sony.mediaroom.com/index.php?s=2429&pagetemplate=rss"),
    ("PlayStation Blog (Feedburner)", "https://feeds.feedburner.com/psblog"),
    ("Sony Music PL", "https://www.sonymusic.pl/feed/"),
    ("Sony Music PL newsroom", "https://newsroom.sonymusic.pl/rss"),
    ("Sony EU community (wallpapers)", "https://community.sony.pl/sonyeu1/rss/board?board.id=wallpaper_world"),
]),
"lenovo": ("Lenovo", [
    ("News (RSS)", "https://news.lenovo.com/feed/"),
    ("Lenovo24 PL", "https://lenovo24.pl/rss.xml"),
    ("Lenovo Gaming PL", "https://lenovogaming.pl/feed/"),
    ("CDRT blog", "https://blog.lenovocdrt.com/feed.xml"),
]),
"canva": ("Canva", [
    ("Newsroom", "https://www.canva.com/newsroom/news/"),
    ("Learn", "https://www.canva.com/learn/"),
]),
"youtube": ("YouTube", [
    ("Blog (RSS)", "https://blog.youtube/rss/"),
    ("Blog (feed)", "https://blog.youtube/feed/"),
    ("Trends", "https://www.youtube.com/trends/discover/"),
]),
"meta_newsroom": ("Meta / Facebook / Instagram", [
    ("Meta blog (RSS)", "https://www.meta.com/blog/rss/"),
    ("About FB", "https://about.fb.com/feed/"),
    ("Engineering", "https://engineering.fb.com/feed/"),
    ("Meta AI blog", "https://ai.meta.com/blog/"),
    ("Meta AI (Olshansk mirror)", "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_meta_ai.xml"),
    ("Messenger changelog", "https://developers.facebook.com/documentation/business-messaging/messenger-platform/changelog/rss/"),
    ("WhatsApp changelog", "https://developers.facebook.com/documentation/business-messaging/whatsapp/changelog/rss/"),
    ("WhatsApp Flows changelog", "https://developers.facebook.com/documentation/business-messaging/whatsapp/flows/changelog/rss/"),
    ("Developers blog", "https://developers.facebook.com/blog"),
    ("Meta for Devs blog", "https://developers.meta.com/resources/blog/"),
    ("Instagram blog", "https://about.instagram.com/blog"),
]),
"saas": ("SaaS / dev-tooling (zbiorczy)", [
    ("HashiCorp blog + HCP changelog", "https://www.hashicorp.com/blog/feed.xml"),
    ("Svelte", "https://svelte.dev/blog/rss.xml"),
    ("Vercel (Atom)", "https://vercel.com/atom"),
    ("Vercel changelog (RSS)", "https://vercel.com/changelog/rss.xml"),
    ("Chat SDK", "https://chat-sdk.dev/rss.xml"),
    ("Flags SDK", "https://flags-sdk.dev/rss.xml"),
    ("Workflow SDK", "https://workflow-sdk.dev/rss.xml"),
    ("AI SDK Elements", "https://elements.ai-sdk.dev/rss.xml"),
    ("Apify", "https://blog.apify.com/rss/"),
    ("Zapier", "https://zapier.com/blog/feeds/latest/"),
    ("Postman (blog + press)", "https://blog.postman.com/feed/"),
    ("Exa (changelog RSS + sitemap)", "https://exa.ai/docs/changelog/rss.xml"),
    ("Home Assistant (Atom)", "https://www.home-assistant.io/atom.xml"),
    ("Xweather (blog + API/MCP changelog)", "https://www.xweather.com/blog"),
    ("Bitly (blog + press + MCP changelog)", "https://bitly.com/blog/"),
    ("Common Ninja", "https://www.commoninja.com/blog"),
]),
"hackerone": ("HackerOne", [
    ("Blog", "https://www.hackerone.com/blog"),
    ("Newsroom", "https://www.hackerone.com/company/newsroom"),
]),
"creativecommons": ("Creative Commons", [
    ("Blog (RSS)", "https://creativecommons.org/feed/"),
]),
"x_changelog": ("X (Twitter) — changelog", [
    ("docs.x.com changelog", "https://docs.x.com/changelog"),
]),
# ---- Pogoda ----
"openweather": ("OpenWeather", [
    ("Forecast API (5-day)", "https://api.openweathermap.org/data/2.5/forecast"),
]),
"visualcrossing": ("Visual Crossing", [
    ("Timeline Weather API", "https://weather.visualcrossing.com/VisualCrossingWebServices/"),
]),
"open_meteo": ("Open-Meteo", [
    ("Forecast API", "https://api.open-meteo.com/v1/forecast"),
    ("Air Quality API", "https://air-quality-api.open-meteo.com/v1/air-quality"),
    ("Satellite radiation API", "https://satellite-api.open-meteo.com/v1/archive"),
]),
"accuweather": ("AccuWeather", [
    ("News sitemap", "https://www.accuweather.com/sitemaps_v2/articles/news/"),
    ("Corporate press (RSS)", "https://name.accuweather.com/corporate/feed/"),
    ("API change log", "https://apidev.accuweather.com/developers/change-log"),
]),
"imgw": ("IMGW-PIB", [
    ("Dane publiczne API", "https://danepubliczne.imgw.pl/"),
]),
# ---- Gaming ----
"steam": ("Steam", [
    ("News feed", "https://store.steampowered.com/feeds/news"),
]),
"ea": ("EA", [
    ("News", "https://www.ea.com/pl-pl/news"),
    ("Technology", "https://www.ea.com/technology"),
    ("EA Sports news", "https://www.ea.com/pl-pl/ea-studios/ea-sports/news"),
    ("SEED", "https://www.ea.com/seed"),
    ("EA Sports FC 26", "https://www.ea.com/pl/games/ea-sports-fc/fc-26/news"),
]),
"bethesda": ("Bethesda", [
    ("Bethesda news", "https://bethesda.net/pl-PL/news"),
    ("Elder Scrolls news", "https://elderscrolls.bethesda.net/pl-PL/news"),
    ("Fallout news API", "https://fallout.bethesda.net/_api/v1/components/news?locale=pl"),
]),
"nexusmods_news": ("Nexus Mods", [
    ("News", "https://www.nexusmods.com/news"),
]),
# ---- Motoryzacja ----
"lexus_newsroom": ("Lexus", [
    ("Pressroom US (Atom)", "https://pressroom.lexus.com/feed/atom/"),
    ("Newsroom EU", "https://newsroom.lexus.eu/feed/"),
    ("Discover Lexus (sitemap)", "https://discoverlexus.com/sitemap.xml"),
    ("Lexus Polska news", "https://www.lexus-polska.pl/discover-lexus/news"),
]),
"toyota_global": ("Toyota", [
    ("Pressroom US", "https://pressroom.toyota.com/feed/"),
    ("Newsroom EU", "https://newsroom.toyota.eu/feed/"),
    ("Global Toyota (RSS)", "https://global.toyota/export/en/allnews_rss.xml"),
    ("Toyota Times", "https://toyotatimes.jp/en/feed.xml"),
    ("Toyota Connected", "https://www.toyotaconnected.com/insights"),
    ("Toyota Research Institute (via Google News)", "https://news.google.com/rss/search?q=%22Toyota+Research+Institute%22&hl=en-US&gl=US&ceid=US:en"),
]),
# ---- Bank ----
"pekao": ("Bank Pekao", [
    ("pekao.com.pl (via Google News)", "https://news.google.com/rss/search?q=when:14d+site:pekao.com.pl"),
    ("media.pekao.com.pl (via Google News)", "https://news.google.com/rss/search?q=when:14d+site:media.pekao.com.pl"),
    ("Media — informacje prasowe", "https://media.pekao.com.pl/informacje-prasowe"),
    ("Aktualnosci", "https://www.pekao.com.pl/o-banku/aktualnosci.html"),
    ("Private Banking", "https://www.pekao.com.pl/private-banking/"),
]),
# ---- Kosmos / nauka / gov US ----
"nasa": ("NASA", [
    ("NASA (RSS)", "https://www.nasa.gov/feed/"),
    ("Blogs", "https://www.nasa.gov/blogs/feed/"),
    ("Science", "https://science.nasa.gov/feed/"),
    ("Launch schedule", "https://www.nasa.gov/event-type/launch-schedule/feed/"),
    ("Image of the day", "https://www.nasa.gov/feeds/iotd-feed"),
    ("APOD", "https://apod.com/feed.rss"),
]),
"esa": ("ESA", [
    ("Our Activities", "https://www.esa.int/rssfeed/Our_Activities"),
    ("Newsroom", "https://www.esa.int/rssfeed/Newsroom"),
    ("Corporate news", "https://www.esa.int/rssfeed/About_Us/Corporate_news"),
    ("Week in images", "https://www.esa.int/rssfeed/About_Us/Week_in_images"),
    ("Webb news", "https://feeds.feedburner.com/esawebb/news/"),
    ("Webb images", "https://feeds.feedburner.com/esawebb/images/"),
    ("Hubble news", "https://feeds.feedburner.com/hubble_news/"),
    ("Hubble images", "https://esahubble.org/images/feed/"),
]),
"usgov": ("Rząd USA", [
    ("Dept. of War", "https://www.war.gov/DesktopModules/ArticleCS/RSS.ashx"),
    ("NSA", "https://www.nsa.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=1282&max=20"),
    ("NOAA", "https://www.noaa.gov/rss.xml"),
    ("USA.gov blog", "https://www.usa.gov/blog"),
    ("GSA blog", "https://www.gsa.gov/blog"),
    ("GSA news releases", "https://www.gsa.gov/about-gsa/newsroom/news-releases"),
    ("FBI press releases", "https://www.fbi.gov/news/press-releases/rss.xml"),
    ("FBI stories", "https://www.fbi.gov/news/stories/rss.xml"),
    ("Army news (via Google News)", "https://news.google.com/rss/search?q=site:army.mil/news+when:30d&hl=en-US&gl=US&ceid=US:en"),
]),
"wikipedia_pl": ("Wikipedia / Wikimedia PL", [
    ("Wikipedia PL featured feeds", "https://pl.wikipedia.org/w/api.php?action=featuredfeed&feedformat=atom"),
    ("Wikimedia Commons featured", "https://commons.wikimedia.org/w/api.php?action=featuredfeed"),
    ("Wikimedia Polska", "https://wikimedia.pl/feed/"),
    ("Wikimedia Diff PL", "https://diff.wikimedia.org/pl/feed/"),
]),
# ---- Radio / muzyka ----
"trojka": ("Polskie Radio Trójka", [
    ("Czytaj wiecej", "https://trojka.polskieradio.pl/czytaj-wiecej"),
]),
"czworka": ("Polskie Radio Czwórka", [
    ("Czwórka", "https://www.polskieradio.pl/10,czworka"),
]),
"foobar2000_news": ("foobar2000", [
    ("News", "https://www.foobar2000.org/news"),
    ("Changelog", "https://www.foobar2000.org/changelog"),
    ("Changelog (Android)", "https://www.foobar2000.org/changelog-android"),
    ("Changelog (Encoder Pack)", "https://www.foobar2000.org/changelog-encoderpack"),
]),
"ra": ("Resident Advisor", [
    ("Magazine", "https://ra.co/magazine"),
    ("Features", "https://ra.co/features"),
    ("Music", "https://ra.co/music"),
]),
"beatport_top100": ("Beatport Top 100", [
    ("Top 100 (__NEXT_DATA__)", "https://www.beatport.com/top-100"),
]),
# ---- Rozrywka / memy ----
"cheezburger": ("Cheezburger Network", [
    ("Cheezburger", "https://www.cheezburger.com/rss"),
    ("FAIL Blog", "https://failblog.cheezburger.com/rss"),
    ("CheezCake", "https://cheezcake.cheezburger.com/rss"),
    ("Memebase", "https://memebase.cheezburger.com/rss"),
    ("I Can Has Cheezburger", "https://icanhas.cheezburger.com/rss"),
    ("Geek Universe", "https://geek.cheezburger.com/rss"),
]),
"memedroid": ("Memedroid", [
    ("Homepage (scrape)", "https://www.memedroid.com/"),
]),
"9gag": ("9GAG", [
    ("Homepage (scrape)", "https://9gag.com/"),
]),
"jbzd": ("Jbzd", [
    ("Homepage (scrape)", "https://jbzd.com.pl/"),
]),
"4chan": ("4chan", [
    ("JSON API (a.4cdn.org)", "https://a.4cdn.org"),
    ("Blog", "https://blog.4chan.org/feed/"),
]),
# ---- Ogłoszenia ----
"olx": ("OLX Group", [
    ("OLX blog", "https://blog.olx.pl/feed/"),
    ("OLX Zawodowo", "https://www.olx.pl/zawodowo/feed/"),
    ("Otomoto news", "https://www.otomoto.pl/news/feed"),
    ("Otodom wiadomości", "https://www.otodom.pl/wiadomosci/feed/"),
    ("Otodom media", "https://media.otodom.pl/feed"),
]),
# ---- Userscripts ----
"userscripts": ("Userscripts / Greasemonkey", [
    ("Greasy Fork (Atom)", "https://sleazyfork.org/scripts.atom?sort=updated"),
    ("Greasespot", "https://www.greasespot.net/feeds/posts/default"),
    ("Violentmonkey", "https://violentmonkey.github.io/posts/"),
    ("Tampermonkey changelog", "https://www.tampermonkey.net/changelog.php"),
]),
# ---- Codzienne ----
"daily_digest": ("Daily Digest", [
    ("ZenQuotes (quote of the day)", "https://zenquotes.io/api/today"),
    ("ViewBits — useless fact", "https://api.viewbits.com/v1/uselessfacts?mode=today"),
    ("ViewBits — life hack", "https://api.viewbits.com/v1/lifehacks?mode=today"),
    ("ViewBits — fortune cookie", "https://api.viewbits.com/v1/fortunecookie?mode=today"),
    ("ViewBits — headlines", "https://api.viewbits.com/v1/headlines"),
]),
"daily_quote": ("Daily Quote", [
    ("Gist — 11k cytatów", "https://gist.github.com/trvny/167d2271e3cf7d21e118aa7d906a7d2c"),
    ("Wikiquote API (linki autorów)", "https://en.wikiquote.org/w/api.php"),
]),
}
# grouping: feed_key order within each themed section
GROUPS = [
 ("🇵🇱 Polska — rząd i informacje", ["govpl_news","pap","tvp","spidersweb"]),
 ("🌍 Świat — newsy", ["reuters","euronews"]),
 ("🤖 AI / LLM", ["anthropic","claude","openai","xai","aibridge","skillsllm"]),
 ("💻 Tech / vendorzy oprogramowania", ["microsoft","microsoft_updates","cloudflare","docker","gitlab","mozilla","google","apple","sony","lenovo","canva","youtube","meta_newsroom","saas","hackerone","creativecommons","x_changelog"]),
 ("🌦️ Pogoda", ["openweather","visualcrossing","open_meteo","accuweather","imgw"]),
 ("🎮 Gaming", ["steam","ea","bethesda","nexusmods_news"]),
 ("🚗 Motoryzacja", ["lexus_newsroom","toyota_global"]),
 ("🏦 Bank", ["pekao"]),
 ("🚀 Kosmos / nauka / rząd USA", ["nasa","esa","usgov","wikipedia_pl"]),
 ("🎵 Radio / muzyka", ["trojka","czworka","foobar2000_news","ra","beatport_top100"]),
 ("😂 Rozrywka / memy", ["cheezburger","memedroid","9gag","jbzd","4chan"]),
 ("🛒 Ogłoszenia", ["olx"]),
 ("🧩 Userscripts", ["userscripts"]),
 ("📅 Codzienne", ["daily_digest","daily_quote"]),
]

# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def fav(url: str) -> str:
    host = urlparse(url).netloc or url
    return f"![](https://www.google.com/s2/favicons?domain={host}&sz=16) "


def load_yaml_feeds() -> dict:
    data = yaml.safe_load(FEEDS_YAML.read_text(encoding="utf-8")) or {}
    out = {}
    for key, cfg in (data.get("feeds") or {}).items():
        out[str(key)] = (cfg or {}).get("blog_url", "")
    return out


def generator_urls(feed_key: str) -> set:
    """AST-parse a generator's static source-list literals -> set of URLs.

    Returns an empty set when the script is missing or builds its sources
    procedurally (no parseable list literal)."""
    # feeds.yaml binds key -> script filename; re-read it once for the mapping.
    data = yaml.safe_load(FEEDS_YAML.read_text(encoding="utf-8")) or {}
    script = ((data.get("feeds") or {}).get(feed_key) or {}).get("script")
    if not script:
        return set()
    path = HERE / script
    if not path.exists():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    urls = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id in LIST_NAMES for t in node.targets):
            continue
        for s in ast.walk(node.value):
            if isinstance(s, ast.Constant) and isinstance(s.value, str) and s.value.startswith("http"):
                urls.add(s.value)
    return urls


def _norm(u: str) -> str:
    return u.rstrip("/").split("?")[0].split("#")[0]


def drift_report(registry_keys, yaml_feeds):
    """Warn on generator<->registry URL drift and feed<->registry coverage."""
    problems = 0
    # coverage
    for key in yaml_feeds:
        if key not in REGISTRY:
            print(f"[coverage] feeds.yaml feed '{key}' has no REGISTRY entry "
                  f"-> emitted under 'Inne' with blog_url only", file=sys.stderr)
            problems += 1
    for key in registry_keys:
        if key not in yaml_feeds:
            print(f"[coverage] REGISTRY feed '{key}' is not in feeds.yaml (stale?)",
                  file=sys.stderr)
            problems += 1
    # url drift, only for feeds whose generator exposes a static list
    for key in registry_keys:
        if key not in yaml_feeds:
            continue
        gen = {_norm(u) for u in generator_urls(key)}
        if not gen:
            continue  # procedural sources; nothing reliable to diff
        reg = {_norm(u) for _, u in REGISTRY[key][1]}
        # a generator URL is "covered" if it matches, or is a prefix/suffix of,
        # any registry URL (handles aggregated labels pointing at a base URL).
        def covered(g):
            return any(g == r or g in r or r in g for r in reg)
        missing = [u for u in sorted(gen) if not covered(u)]
        if missing:
            problems += 1
            print(f"[drift] '{key}': generator lists URL(s) not reflected in "
                  f"REGISTRY:", file=sys.stderr)
            for u in missing:
                print(f"          + {u}", file=sys.stderr)
    return problems


def build_markdown(yaml_feeds) -> str:
    grouped = {g: keys for g, keys in GROUPS}
    known = {k for _, keys in GROUPS for k in keys}
    # any yaml feed not in a group and not in registry -> Inne bucket
    extras = [k for k in yaml_feeds if k not in known]
    out = []
    out.append("# Źródła feedów\n")
    out.append("Konkretne linki źródłowe wchodzące w skład każdego generowanego "
               "feeda — źródło prawdy to `REGISTRY` w `feed_generators/docs_sources.py`, "
               "spięte z `feeds.yaml`. Feedy zbiorcze (`aibridge`, `saas`, `skillsllm`, "
               "`pap`, `esa`, `google` itd.) łączą wiele źródeł w jeden strumień Atom.\n")
    out.append("> Plik generowany: `python3 feed_generators/docs_sources.py`. "
               "Nie edytuj ręcznie — zmień `REGISTRY` w generatorze.\n")

    render_keys = [(g, [k for k in keys if k in yaml_feeds or k in REGISTRY])
                   for g, keys in GROUPS]
    if extras:
        render_keys.append(("🗂️ Inne", extras))

    nfeeds = sum(len(ks) for _, ks in render_keys)
    nsrc = sum(len(REGISTRY[k][1]) if k in REGISTRY else 1
               for _, ks in render_keys for k in ks)
    out.append(f"**{nfeeds} feedów · {nsrc} źródeł**\n")

    out.append("## Spis grup\n")
    for g, ks in render_keys:
        if ks:
            out.append(f"- {g}")
    out.append("")

    for gtitle, keys in render_keys:
        keys = [k for k in keys if k]
        if not keys:
            continue
        out.append(f"## {gtitle}\n")
        for k in keys:
            if k in REGISTRY:
                title, srcs = REGISTRY[k]
            else:
                blog = yaml_feeds.get(k, "")
                title, srcs = k, [("Strona (źródła budowane w generatorze)", blog or "https://example.com")]
            primary = srcs[0][1]
            out.append(f"### {fav(primary)}{title}")
            out.append(f"`{k}` · [feed_{k}.xml](../feeds/feed_{k}.xml)\n")
            for label, url in srcs:
                out.append(f"- {fav(url)}{label} — <{url}>")
            out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Generate docs/sources.md")
    ap.add_argument("--check", action="store_true",
                    help="report drift/coverage and exit non-zero on problems; no write")
    args = ap.parse_args()

    yaml_feeds = load_yaml_feeds()
    problems = drift_report(set(REGISTRY), yaml_feeds)

    if args.check:
        if problems:
            print(f"\n{problems} issue(s) found.", file=sys.stderr)
            return 1
        print("docs/sources.md is in sync with feeds.yaml and generators.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_markdown(yaml_feeds), encoding="utf-8")
    nfeeds = sum(1 for _, ks in GROUPS for _ in ks)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(REGISTRY)} feeds in registry"
          + (f", {problems} drift/coverage warning(s)" if problems else "") + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
