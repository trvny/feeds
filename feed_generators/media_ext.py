"""feedgen extension for the MRSS elements feedgen's built-in ``media``
extension doesn't cover: ``media:community``, ``media:license``, and
``media:embed``.

feedgen (feedgen/ext/media.py) implements ``media:content``,
``media:thumbnail``, and ``media:group`` -- the elements most readers key off
for images. It does not implement the rest of the MRSS 1.5.1 vocabulary. This
module fills in three more entry-level elements, registered under a separate
extension key (``media_full``) so it coexists with the built-in ``media``
extension: both declare the same ``xmlns:media`` namespace/prefix, and since
they write different child elements there's no conflict. Load both:

    fg.load_extension("media")                       # content/thumbnail/group
    fg.register_extension("media_full", MediaFullExtension, MediaFullEntryExtension)

Reference: https://www.rssboard.org/media-rss (MRSS 1.5.1).
"""

from feedgen.ext.base import BaseEntryExtension, BaseExtension
from feedgen.util import xml_elem

MEDIA_NS = "http://search.yahoo.com/mrss/"


class MediaFullExtension(BaseExtension):
    """Feed-level half of the extension. No feed-level fields needed for
    community/license/embed (all three are item-level in the MRSS spec), but
    the namespace declaration must come from *some* registered extension."""

    def extend_ns(self):
        return {"media": MEDIA_NS}


class MediaFullEntryExtension(BaseEntryExtension):
    """Entry-level media:community / media:license / media:embed / enclosure."""

    def __init__(self):
        self.__community = None
        self.__license = None
        self.__embed = None
        self.__enclosure = None

    # -- enclosure (format-aware; bypasses a feedgen 1.0.0 bug) -----------
    def enclosure(self, url=None, mime_type=None, length=None, replace=True):
        """Get or set a media enclosure.

        feedgen 1.0.0's FeedEntry.atom_entry() has a variable-shadowing bug
        in its link-rendering loop (feedgen/entry.py, the `for link in
        self.__atom_link` block reassigns `link` to the new XML element
        before reading `link.get('rel')`), which silently drops rel/type/
        length from every entry-level <link> -- including the one
        fe.enclosure()/fe.link(rel='enclosure') is supposed to produce. The
        result renders as a bare, unlabeled <link href="..."/>, which a
        spec-compliant Atom reader treats as a *second alternate link* (an
        undesirable outcome for an image), not an enclosure. Rather than
        depend on that path, this method renders the enclosure link (Atom)
        or <enclosure> element (RSS) directly, so it works regardless of the
        upstream bug.

        :param url: URL of the media object.
        :param mime_type: MIME type of the media object.
        :param length: size in bytes (defaults to "0" when unknown, which is
            valid per both specs -- the real size just isn't advertised).
        """
        if url is not None:
            if replace or self.__enclosure is None:
                self.__enclosure = {}
            self.__enclosure["url"] = url
            if mime_type is not None:
                self.__enclosure["type"] = mime_type
            self.__enclosure["length"] = str(length) if length is not None else "0"
        return self.__enclosure

    # -- media:community -------------------------------------------------
    def community(self, star_rating=None, statistics=None, replace=True):
        """Get or set media:community.

        :param star_rating: dict with any of ``count``, ``average``, ``min``,
            ``max`` (all rendered as ``media:starRating`` attributes).
        :param statistics: dict with any of ``views``, ``favorites``
            (rendered as ``media:statistics`` attributes).
        :param replace: replace existing data (default) vs. leave untouched
            when called with no arguments (pure getter).
        """
        if star_rating is not None or statistics is not None:
            if replace or self.__community is None:
                self.__community = {}
            if star_rating is not None:
                self.__community["starRating"] = star_rating
            if statistics is not None:
                self.__community["statistics"] = statistics
        return self.__community

    # -- media:license ----------------------------------------------------
    def license(self, text=None, type=None, href=None, replace=True):
        """Get or set media:license (e.g. a Creative Commons license).

        :param text: license name, rendered as the element's text content.
        :param type: MIME type of the license description (optional).
        :param href: URL to the full license text.
        """
        if text is not None or href is not None:
            if replace or self.__license is None:
                self.__license = {}
            if text is not None:
                self.__license["text"] = text
            if type is not None:
                self.__license["type"] = type
            if href is not None:
                self.__license["href"] = href
        return self.__license

    # -- media:embed --------------------------------------------------------
    def embed(self, url=None, width=None, height=None, params=None, replace=True):
        """Get or set media:embed -- a player/embed URL plus optional
        media:param children (e.g. autoplay flags).

        :param url: URL of the embeddable player.
        :param width: player width in pixels.
        :param height: player height in pixels.
        :param params: dict of name -> value rendered as media:param children.
        """
        if url is not None:
            if replace or self.__embed is None:
                self.__embed = {}
            self.__embed["url"] = url
            if width is not None:
                self.__embed["width"] = str(width)
            if height is not None:
                self.__embed["height"] = str(height)
            if params is not None:
                self.__embed["params"] = params
        return self.__embed

    # -- rendering ----------------------------------------------------------
    def extend_atom(self, entry):
        if self.__enclosure:
            enc = xml_elem("link", entry)
            enc.set("rel", "enclosure")
            enc.set("href", self.__enclosure["url"])
            if self.__enclosure.get("type"):
                enc.set("type", self.__enclosure["type"])
            enc.set("length", self.__enclosure["length"])

        if self.__community:
            community = xml_elem("{%s}community" % MEDIA_NS, entry)
            star = self.__community.get("starRating")
            if star:
                star_el = xml_elem("{%s}starRating" % MEDIA_NS, community)
                for attr in ("count", "average", "min", "max"):
                    if star.get(attr) is not None:
                        star_el.set(attr, str(star[attr]))
            stats = self.__community.get("statistics")
            if stats:
                stats_el = xml_elem("{%s}statistics" % MEDIA_NS, community)
                for attr in ("views", "favorites"):
                    if stats.get(attr) is not None:
                        stats_el.set(attr, str(stats[attr]))

        if self.__license:
            license_el = xml_elem("{%s}license" % MEDIA_NS, entry)
            if self.__license.get("type"):
                license_el.set("type", self.__license["type"])
            if self.__license.get("href"):
                license_el.set("href", self.__license["href"])
            if self.__license.get("text"):
                license_el.text = self.__license["text"]

        if self.__embed:
            embed_el = xml_elem("{%s}embed" % MEDIA_NS, entry)
            embed_el.set("url", self.__embed["url"])
            if self.__embed.get("width"):
                embed_el.set("width", self.__embed["width"])
            if self.__embed.get("height"):
                embed_el.set("height", self.__embed["height"])
            for name, value in (self.__embed.get("params") or {}).items():
                param_el = xml_elem("{%s}param" % MEDIA_NS, embed_el)
                param_el.set("name", name)
                param_el.text = str(value)

        return entry

    def extend_rss(self, item):
        # RSS <enclosure> is its own element (url/length/type attributes),
        # not a <link rel="enclosure">, so it can't reuse extend_atom's
        # rendering for that one field. The other three (community/license/
        # embed) are identical media:* elements in both formats.
        if self.__enclosure:
            enc = xml_elem("enclosure", item)
            enc.set("url", self.__enclosure["url"])
            enc.set("length", self.__enclosure["length"])
            if self.__enclosure.get("type"):
                enc.set("type", self.__enclosure["type"])

        saved_enclosure, self.__enclosure = self.__enclosure, None
        self.extend_atom(item)
        self.__enclosure = saved_enclosure
        return item
