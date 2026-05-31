"""Pydantic models for feed configuration and settings."""

import logging
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class FeedType(StrEnum):
    REQUESTS = "requests"
    SELENIUM = "selenium"


class FeedConfig(BaseModel):
    """Configuration for a single feed generator."""

    script: str
    type: FeedType
    blog_url: str
    enabled: bool = True

    @field_validator("script")
    @classmethod
    def script_must_exist(cls, v: str) -> str:
        script_path = Path(__file__).parent / v
        if not script_path.exists():
            msg = f"Script not found: {v}"
            raise ValueError(msg)
        return v


class GlobalSettings(BaseSettings):
    """Project-wide settings, overridable via RSS_ env vars.

    Example: RSS_REPO_SLUG=oborchers/rss-feeds overrides the default.
    """

    model_config = {"env_prefix": "RSS_"}

    repo_slug: str = "Olshansk/rss-feeds"


def load_feed_registry(return_skipped: bool = False):
    """Load and validate feeds.yaml.

    Invalid entries are logged and skipped rather than aborting the whole
    load, so one malformed config can never take down every other feed.

    Args:
        return_skipped: If True, return ``(feeds, skipped_names)`` instead of
            just ``feeds``. Defaults to False for backward compatibility.

    Returns:
        Dict mapping feed name to validated FeedConfig (valid entries only),
        or ``(dict, list[str])`` when ``return_skipped`` is True.

    Raises:
        FileNotFoundError: If feeds.yaml is missing.
    """
    registry_path = Path(__file__).parent.parent / "feeds.yaml"
    if not registry_path.exists():
        msg = f"Feed registry not found: {registry_path}"
        raise FileNotFoundError(msg)

    with open(registry_path) as f:
        data = yaml.safe_load(f) or {}

    feeds: dict[str, FeedConfig] = {}
    skipped: list[str] = []
    for name, config in data.get("feeds", {}).items():
        try:
            feeds[name] = FeedConfig(**config)
        except ValidationError as e:
            skipped.append(name)
            errors = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
            )
            logger.error(
                "Skipping invalid feed config '%s' in feeds.yaml (%s)", name, errors
            )

    if skipped:
        logger.warning(
            "Loaded %d feed(s); skipped %d invalid: %s",
            len(feeds),
            len(skipped),
            ", ".join(skipped),
        )

    if return_skipped:
        return feeds, skipped
    return feeds
