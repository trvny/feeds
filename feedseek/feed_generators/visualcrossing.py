"""Visual Crossing daily forecast feed generator.

Turns the Visual Crossing Timeline API into a daily Atom feed with forecasts,
air-quality details, and weather alerts. The API query location stays
configurable, while public entry titles use a separate coarse location label so
a precise address is never exposed in notifications.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import pytz
from feedgen.feed import FeedGenerator

from utils import (
    fetch_page,
    get_feeds_dir,
    load_cache,
    sanitize_xml,
    save_cache,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "visualcrossing"

API_KEY = os.getenv("VISUALCROSSING_API_KEY", "").strip()
LOCATION = os.getenv("VISUALCROSSING_LOCATION", "32-500 Kasztanowa").strip()
PUBLIC_LOCATION = os.getenv(
    "VISUALCROSSING_PUBLIC_LOCATION", "Chrzanów 32-500"
).strip()
UNITS = os.getenv("VISUALCROSSING_UNITS", "metric").strip().lower()
LANG = os.getenv("VISUALCROSSING_LANG", "pl").strip().lower()

BASE_URL = (
    "https://weather.visualcrossing.com/VisualCrossingWebServices/"
    "rest/services/timeline"
)

EXTRA_ELEMENTS = ",".join(
    f"add:{element}"
    for element in (
        "aqieur",
        "aqielement",
        "pm1",
        "pm2p5",
        "pm10",
        "o3",
        "no2",
        "so2",
        "co",
        "lightningrisk",
    )
)

AQI_EUR_LEVELS = {
    "pl": {
        1: "bardzo dobra",
        2: "dobra",
        3: "umiarkowana",
        4: "zła",
        5: "bardzo zła",
        6: "ekstremalnie zła",
    },
    "en": {
        1: "good",
        2: "fair",
        3: "moderate",
        4: "poor",
        5: "very poor",
        6: "extremely poor",
    },
}

TEMP_UNIT = {"metric": "°C", "us": "°F", "uk": "°C", "base": "K"}.get(
    UNITS, "°C"
)
WIND_UNIT = {
    "metric": "km/h",
    "us": "mph",
    "uk": "mph",
    "base": "m/s",
}.get(UNITS, "km/h")
PRECIP_UNIT = {"metric": "mm", "us": "in", "uk": "mm", "base": "mm"}.get(
    UNITS, "mm"
)

MAX_ENTRIES = 45

PL_WEEKDAYS = [
    "poniedziałek",
    "wtorek",
    "środa",
    "czwartek",
    "piątek",
    "sobota",
    "niedziela",
]
PL_MONTHS = [
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
]

LABELS = {
    "pl": {
        "temp": "Temperatura",
        "minmax": "Min/Maks",
        "feels": "Odczuwalna",
        "precip_prob": "Szansa opadów",
        "precip": "Opady",
        "snow": "Śnieg",
        "wind": "Wiatr",
        "gust": "porywy",
        "humidity": "Wilgotność",
        "uv": "Indeks UV",
        "cloud": "Zachmurzenie",
        "sunrise": "Wschód słońca",
        "sunset": "Zachód słońca",
        "alert": "Ostrzeżenie pogodowe",
        "aqi": "Jakość powietrza (AQI EU)",
        "aqi_dominant": "dominuje",
        "pm": "Pyły",
        "gases": "Gazy",
        "lightning": "Ryzyko burz",
    },
}
DEFAULT_LABELS = {
    "temp": "Temperature",
    "minmax": "Min/Max",
    "feels": "Feels like",
    "precip_prob": "Chance of precipitation",
    "precip": "Precipitation",
    "snow": "Snow",
    "wind": "Wind",
    "gust": "gusts",
    "humidity": "Humidity",
    "uv": "UV index",
    "cloud": "Cloud cover",
    "sunrise": "Sunrise",
    "sunset": "Sunset",
    "alert": "Weather alert",
    "aqi": "Air quality (EU AQI)",
    "aqi_dominant": "dominant",
    "pm": "Particulates",
    "gases": "Gases",
    "lightning": "Lightning risk",
}
L = LABELS.get(LANG, DEFAULT_LABELS)


def fetch_timeline(retries: int = 3, backoff: float = 2.0):
    """Fetch the Timeline forecast JSON for LOCATION, or None on failure."""
    if not API_KEY:
        logger.error(
            "VISUALCROSSING_API_KEY is not set. Export it locally or add it as "
            "a GitHub Actions secret; skipping to preserve the last good feed."
        )
        return None

    location = urllib.parse.quote(LOCATION, safe="")
    params = urllib.parse.urlencode(
        {
            "unitGroup": UNITS,
            "include": "days,alerts",
            "elements": EXTRA_ELEMENTS,
            "key": API_KEY,
            "lang": LANG,
            "contentType": "json",
        }
    )
    url = f"{BASE_URL}/{location}/today/next6days?{params}"
    safe_url = url.replace(API_KEY, "***")

    for attempt in range(1, retries + 1):
        try:
            return json.loads(fetch_page(url))
        except Exception as exc:
            logger.warning(
                "Timeline fetch failed for %s (attempt %d/%d): %s",
                safe_url,
                attempt,
                retries,
                exc,
            )
            if attempt < retries:
                time.sleep(backoff * attempt)
    return None


def _r(value) -> str:
    """Round a number for display, dropping a trailing .0."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return str(int(round(number)))


def _loc_slug() -> str:
    return urllib.parse.quote(LOCATION.lower().replace(" ", ""), safe="")


def _pl_date(local_date: datetime) -> str:
    if LANG == "pl":
        return (
            f"{PL_WEEKDAYS[local_date.weekday()]}, "
            f"{local_date.day} {PL_MONTHS[local_date.month - 1]}"
        )
    return local_date.strftime("%a %d %b")


def _public_title(text: str, *, alert: bool = False) -> str:
    prefix = f"⚠️ {PUBLIC_LOCATION}" if alert else PUBLIC_LOCATION
    return f"{prefix} — {text}"


def _redact_cached_location(entry: dict) -> dict:
    """Replace a previously cached precise address with the public label."""
    redacted = entry.copy()
    title = str(redacted.get("title") or "")
    if " — " not in title:
        return redacted

    if redacted.get("kind") == "alert" or title.startswith("⚠️ "):
        _, detail = title.removeprefix("⚠️ ").split(" — ", 1)
        redacted["title"] = _public_title(detail, alert=True)
    else:
        _, detail = title.split(" — ", 1)
        redacted["title"] = _public_title(detail)
    return redacted


def _air_quality_lines(day: dict) -> list[str]:
    lines = []
    aqi = day.get("aqieur")
    if aqi is not None:
        level = AQI_EUR_LEVELS.get(LANG, AQI_EUR_LEVELS["en"]).get(
            int(aqi), ""
        )
        dominant = (
            (day.get("aqielement") or "")
            .replace("pm2p5", "PM2.5")
            .replace("pm10", "PM10")
            .replace("pm1", "PM1")
            .replace("o3", "O₃")
            .replace("no2", "NO₂")
            .replace("so2", "SO₂")
            .replace("co", "CO")
            .replace(",", ", ")
        )
        text = f"{L['aqi']}: {int(aqi)}/6"
        if level:
            text += f" ({level})"
        if dominant:
            text += f" — {L['aqi_dominant']}: {dominant}"
        lines.append(f"<li>{text}</li>")

    particulate = [
        f"{name} {_r(day[key])}"
        for key, name in (
            ("pm1", "PM1"),
            ("pm2p5", "PM2.5"),
            ("pm10", "PM10"),
        )
        if day.get(key) is not None
    ]
    if particulate:
        lines.append(f"<li>{L['pm']}: {' · '.join(particulate)} µg/m³</li>")

    gases = [
        f"{name} {_r(day[key])}"
        for key, name in (
            ("o3", "O₃"),
            ("no2", "NO₂"),
            ("so2", "SO₂"),
            ("co", "CO"),
        )
        if day.get(key) is not None
    ]
    if gases:
        lines.append(f"<li>{L['gases']}: {' · '.join(gases)} µg/m³</li>")

    risk = day.get("lightningrisk")
    if risk:
        lines.append(f"<li>{L['lightning']}: {_r(risk)}%</li>")
    return lines


def build_day_entries(data: dict) -> list[dict]:
    tz = timezone(timedelta(hours=float(data.get("tzoffset", 0))))
    link = (
        "https://www.visualcrossing.com/weather-history/"
        + urllib.parse.quote(LOCATION)
    )

    entries = []
    for day in data.get("days", []):
        date_str = day["datetime"]
        local_date = datetime.fromisoformat(date_str).replace(tzinfo=tz)

        conditions = (day.get("conditions") or "").strip()
        description = (day.get("description") or conditions or "").strip()
        temp_high, temp_low = day.get("tempmax"), day.get("tempmin")
        feels_high = day.get("feelslikemax")
        feels_low = day.get("feelslikemin")
        precip_probability = day.get("precipprob") or 0
        precip = day.get("precip") or 0
        snow = day.get("snow") or 0
        wind = day.get("windspeed") or 0
        gust = day.get("windgust") or 0
        humidity = day.get("humidity") or 0
        uv = day.get("uvindex")
        cloud = day.get("cloudcover")
        sunrise = day.get("sunrise", "")[:5]
        sunset = day.get("sunset", "")[:5]

        title = sanitize_xml(
            f"{_pl_date(local_date)}: {conditions or '—'}, "
            f"{_r(temp_low)}–{_r(temp_high)}{TEMP_UNIT}"
        )

        lines = []
        if description:
            lines.append(f"<p>{description}</p>")
        lines.append("<ul>")
        lines.append(
            f"<li>{L['minmax']}: {_r(temp_low)}{TEMP_UNIT} / "
            f"{_r(temp_high)}{TEMP_UNIT}</li>"
        )
        if feels_low is not None and feels_high is not None:
            lines.append(
                f"<li>{L['feels']}: {_r(feels_low)}{TEMP_UNIT} / "
                f"{_r(feels_high)}{TEMP_UNIT}</li>"
            )
        lines.append(
            f"<li>{L['precip_prob']}: {_r(precip_probability)}%</li>"
        )
        if precip:
            lines.append(
                f"<li>{L['precip']}: {precip:.1f} {PRECIP_UNIT}</li>"
            )
        if snow:
            lines.append(f"<li>{L['snow']}: {snow:.1f} {PRECIP_UNIT}</li>")
        lines.append(
            f"<li>{L['wind']}: {_r(wind)} {WIND_UNIT} "
            f"({L['gust']} {_r(gust)} {WIND_UNIT})</li>"
        )
        lines.append(f"<li>{L['humidity']}: {_r(humidity)}%</li>")
        if uv is not None:
            lines.append(f"<li>{L['uv']}: {_r(uv)}</li>")
        if cloud is not None:
            lines.append(f"<li>{L['cloud']}: {_r(cloud)}%</li>")
        if sunrise and sunset:
            lines.append(
                f"<li>{L['sunrise']}: {sunrise} · "
                f"{L['sunset']}: {sunset}</li>"
            )
        lines.extend(_air_quality_lines(day))
        lines.append("</ul>")
        description_html = sanitize_xml("\n".join(lines))

        entries.append(
            {
                "guid": f"urn:visualcrossing:{_loc_slug()}:{date_str}",
                "title": _public_title(title),
                "link": link,
                "description": description_html,
                "date": local_date,
                "updated": datetime.now(pytz.UTC),
                "kind": "day",
                "summary_hash": hashlib.sha1(
                    (title + description_html).encode("utf-8"),
                    usedforsecurity=False,
                ).hexdigest(),
            }
        )
    return entries


def build_alert_entries(data: dict) -> list[dict]:
    tz = timezone(timedelta(hours=float(data.get("tzoffset", 0))))
    entries = []
    for alert in data.get("alerts", []) or []:
        event = (alert.get("event") or L["alert"]).strip()
        headline = (alert.get("headline") or "").strip()
        body = (alert.get("description") or "").strip()
        onset = alert.get("onset") or alert.get("date") or ""
        try:
            when = (
                datetime.fromisoformat(onset).replace(tzinfo=tz)
                if onset
                else datetime.now(tz)
            )
        except ValueError:
            when = datetime.now(tz)

        raw = (event + headline + body + str(onset)).encode("utf-8")
        parts = []
        if headline:
            parts.append(f"<p><strong>{sanitize_xml(headline)}</strong></p>")
        if body:
            parts.append(f"<p>{sanitize_xml(body)}</p>")
        description_html = "\n".join(parts) or sanitize_xml(event)

        entries.append(
            {
                "guid": (
                    f"urn:visualcrossing:{_loc_slug()}:alert:"
                    f"{hashlib.sha256(raw).hexdigest()[:16]}"
                ),
                "title": _public_title(sanitize_xml(event), alert=True),
                "link": alert.get("link")
                or "https://www.visualcrossing.com/",
                "description": description_html,
                "date": when,
                "updated": datetime.now(pytz.UTC),
                "kind": "alert",
                "summary_hash": hashlib.sha256(
                    (event + description_html).encode("utf-8")
                ).hexdigest(),
            }
        )
    return entries


def merge_forecast(new_entries: list[dict], cached: list[dict]) -> list[dict]:
    by_guid = {entry["guid"]: entry for entry in cached}
    for entry in new_entries:
        old = by_guid.get(entry["guid"])
        if old and old.get("summary_hash") == entry["summary_hash"]:
            entry["updated"] = old.get("updated", entry["updated"])
        by_guid[entry["guid"]] = entry
    return sort_posts_for_feed(list(by_guid.values()), date_field="date")


def _deserialize(cached: list[dict]) -> list[dict]:
    entries = []
    for entry in cached:
        converted = _redact_cached_location(entry)
        for field in ("date", "updated"):
            if isinstance(converted.get(field), str):
                try:
                    converted[field] = datetime.fromisoformat(
                        converted[field]
                    )
                except ValueError:
                    converted[field] = None
        entries.append(converted)
    return entries


def generate_atom_feed(
    entries: list[dict],
    data: dict | None = None,
    feed_name: str = FEED_NAME,
) -> FeedGenerator:
    del data
    feed = FeedGenerator()
    feed.id(f"urn:visualcrossing:{_loc_slug()}")
    feed.title("Visual Crossing")
    feed.subtitle(
        "Dzienna prognoza pogody (Visual Crossing)"
        if LANG == "pl"
        else "Daily forecast from the Visual Crossing Timeline API"
    )
    blog_url = (
        entries[0]["link"]
        if entries
        else "https://www.visualcrossing.com/"
    )
    setup_feed_links(feed, blog_url, feed_name)
    feed.language(LANG)
    feed.author(
        {
            "name": "Visual Crossing",
            "uri": "https://www.visualcrossing.com/",
        }
    )

    for entry in entries:
        feed_entry = feed.add_entry()
        feed_entry.id(entry["guid"])
        feed_entry.title(entry["title"])
        feed_entry.link(href=entry["link"])
        feed_entry.content(entry["description"], type="html")
        feed_entry.category(
            term="alert" if entry.get("kind") == "alert" else "weather"
        )
        if entry.get("date"):
            feed_entry.published(entry["date"])
        feed_entry.updated(entry.get("updated") or entry.get("date"))

    logger.info("Generated Atom feed")
    return feed


def save_atom_feed(feed: FeedGenerator, feed_name: str = FEED_NAME):
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    feed.atom_file(str(output_file), pretty=True)
    logger.info("Saved Atom feed to %s", output_file)
    return output_file


def main(full: bool = False) -> bool:
    data = fetch_timeline()
    if data is None:
        logger.error(
            "No forecast data — skipping write to preserve the last good feed"
        )
        return False

    new_entries = build_day_entries(data) + build_alert_entries(data)
    if not new_entries:
        logger.warning("Timeline returned no usable days — skipping write")
        return False

    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cache = load_cache(FEED_NAME)
        cached = _deserialize(cache.get("entries", []))

    merged = merge_forecast(new_entries, cached)
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]

    save_cache(FEED_NAME, merged)
    save_atom_feed(generate_atom_feed(merged, data))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Visual Crossing daily forecast Atom feed"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Ignore cache and rebuild from scratch",
    )
    arguments = parser.parse_args()
    sys.exit(0 if main(full=arguments.full) else 1)
