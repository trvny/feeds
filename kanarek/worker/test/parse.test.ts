import { describe, it, expect } from "vitest";
import {
  parseFeed,
  decode,
  stripTags,
  normDate,
  dedupe,
  dedupeBy,
  etagMatches,
  absolutize,
  xmlEscape,
  hostAllowed,
  clamp,
  buildAtom,
  renderMergedJsonFeed,
  type NewsItem,
} from "../src/index";

describe("parseFeed (RSS)", () => {
  const rss = `<?xml version="1.0"?>
  <rss version="2.0"><channel>
    <title>Example News</title>
    <item>
      <title>First &amp; foremost</title>
      <link>https://example.com/a</link>
      <description><![CDATA[<p>Body <b>one</b></p>]]></description>
      <pubDate>Wed, 01 Jan 2020 00:00:00 +0000</pubDate>
      <enclosure url="https://img.example.com/a.jpg" type="image/jpeg"/>
    </item>
    <item>
      <title>Second</title>
      <link>https://example.com/b</link>
      <pubDate>Thu, 02 Jan 2020 00:00:00 +0000</pubDate>
    </item>
  </channel></rss>`;

  it("extracts items with decoded title, link, summary", () => {
    const items = parseFeed(rss);
    expect(items.length).toBe(2);
    expect(items[0].title).toBe("First & foremost");
    expect(items[0].link).toBe("https://example.com/a");
    expect(items[0].summary).toBe("Body one");
  });

  it("derives source from channel title", () => {
    expect(parseFeed(rss)[0].source).toBe("Example News");
  });

  it("normalizes pubDate to ISO 8601", () => {
    expect(parseFeed(rss)[0].date).toBe("2020-01-01T00:00:00.000Z");
  });

  it("picks the enclosure image", () => {
    expect(parseFeed(rss)[0].image).toBe("https://img.example.com/a.jpg");
  });

  it("drops items missing a title or link", () => {
    const broken = `<rss><channel><title>X</title>
      <item><link>https://x/1</link></item>
      <item><title>ok</title><link>https://x/2</link></item>
    </channel></rss>`;
    const items = parseFeed(broken);
    expect(items.map((i) => i.link)).toEqual(["https://x/2"]);
  });

  it("defaults author to null when the feed has no dc:creator", () => {
    expect(parseFeed(rss)[0].author).toBeNull();
  });
});

describe("parseFeed (RSS namespaces: dc:creator, content:encoded)", () => {
  const rss = `<?xml version="1.0"?>
  <rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Example News</title>
    <item>
      <title>Byline test</title>
      <link>https://example.com/a</link>
      <dc:creator>Jane Doe</dc:creator>
      <content:encoded><![CDATA[<p>Full <b>body</b> text</p>]]></content:encoded>
    </item>
  </channel></rss>`;

  it("reads dc:creator into author", () => {
    expect(parseFeed(rss)[0].author).toBe("Jane Doe");
  });

  it("falls back to content:encoded for summary when description is absent", () => {
    expect(parseFeed(rss)[0].summary).toBe("Full body text");
  });

  it("prefers description over content:encoded when both are present", () => {
    const withDescription = rss.replace(
      "<dc:creator>Jane Doe</dc:creator>",
      "<dc:creator>Jane Doe</dc:creator><description>Short teaser</description>",
    );
    expect(parseFeed(withDescription)[0].summary).toBe("Short teaser");
  });
});

describe("parseFeed (Atom)", () => {
  const atom = `<?xml version="1.0"?>
  <feed xmlns="http://www.w3.org/2005/Atom">
    <title>Atom Source</title>
    <entry>
      <title>Hello</title>
      <link rel="alternate" href="https://atom.example/post"/>
      <summary>Short summary</summary>
      <updated>2021-06-15T12:00:00Z</updated>
      <media:content url="https://atom.example/p.png"/>
    </entry>
  </feed>`;

  it("reads entry, alternate link, summary, updated", () => {
    const items = parseFeed(atom);
    expect(items.length).toBe(1);
    expect(items[0].title).toBe("Hello");
    expect(items[0].link).toBe("https://atom.example/post");
    expect(items[0].summary).toBe("Short summary");
    expect(items[0].date).toBe("2021-06-15T12:00:00.000Z");
    expect(items[0].image).toBe("https://atom.example/p.png");
  });

  it("returns [] on garbage without throwing", () => {
    expect(parseFeed("not xml at all")).toEqual([]);
    expect(parseFeed("")).toEqual([]);
  });
});

describe("parseFeed (JSON Feed)", () => {
  const jf = JSON.stringify({
    version: "https://jsonfeed.org/version/1.1",
    title: "JSON Source",
    items: [
      {
        id: "urn:1",
        url: "https://jf.example/post",
        title: "JF Hello",
        content_html: "<p>Body <b>json</b></p>",
        date_published: "2026-07-01T00:00:00Z",
        image: "https://jf.example/i.png",
        authors: [{ name: "Someone" }],
      },
      { id: "urn:2", title: "no url -> dropped", content_text: "x" },
    ],
  });

  it("reads JSON Feed 1.1 items (feedseek .json siblings flow through the same path)", () => {
    const items = parseFeed(jf);
    expect(items.length).toBe(1); // second item has no url -> dropped
    expect(items[0].title).toBe("JF Hello");
    expect(items[0].link).toBe("https://jf.example/post");
    expect(items[0].summary).toBe("Body json");
    expect(items[0].date).toBe("2026-07-01T00:00:00.000Z");
    expect(items[0].image).toBe("https://jf.example/i.png");
    expect(items[0].source).toBe("JSON Source");
  });
});

describe("renderMergedJsonFeed", () => {
  it("emits a spec JSON Feed 1.1 document", async () => {
    const items: NewsItem[] = [
      { title: "A", link: "https://e/1", summary: "s", image: "https://e/i.png", date: "2026-07-01T00:00:00.000Z", source: "Src" },
    ];
    const res = renderMergedJsonFeed(items, new URL("https://w.example/?feeds=x&format=jsonfeed"));
    expect(res.headers.get("content-type")).toContain("application/feed+json");
    const doc = await res.json() as { version: string; items: Array<Record<string, unknown>> };
    expect(doc.version).toBe("https://jsonfeed.org/version/1.1");
    expect(doc.items[0]).toMatchObject({
      id: "https://e/1",
      url: "https://e/1",
      title: "A",
      content_html: "s",
      date_published: "2026-07-01T00:00:00.000Z",
      image: "https://e/i.png",
      authors: [{ name: "Src" }],
    });
  });
});

describe("decode", () => {
  it("decodes named, numeric and hex entities", () => {
    expect(decode("a &amp; b")).toBe("a & b");
    expect(decode("&lt;tag&gt; &quot;q&quot; &#39;a&#039;")).toBe("<tag> \"q\" 'a'");
    expect(decode("&#65;&#x42;")).toBe("AB");
  });
  it("decodes &amp; last so &amp;lt; survives as &lt;", () => {
    expect(decode("&amp;lt;")).toBe("&lt;");
  });
});

describe("stripTags", () => {
  it("removes tags and collapses whitespace", () => {
    expect(stripTags("<p>a</p>  <b>b</b>")).toBe(" a b ");
  });
});

describe("normDate", () => {
  it("returns ISO for valid dates, null for junk", () => {
    expect(normDate("Wed, 01 Jan 2020 00:00:00 +0000")).toBe("2020-01-01T00:00:00.000Z");
    expect(normDate("nonsense")).toBeNull();
    expect(normDate("")).toBeNull();
  });
});

describe("dedupe / dedupeBy", () => {
  it("dedupe keeps first by link, preserves order", () => {
    const mk = (link: string): NewsItem => ({ title: "t", link, summary: "", image: null, date: null, source: "s" });
    const out = dedupe([mk("x"), mk("y"), mk("x")]);
    expect(out.map((i) => i.link)).toEqual(["x", "y"]);
  });
  it("dedupeBy uses the key fn", () => {
    expect(dedupeBy([1, 2, 3, 4], (n) => String(n % 2))).toEqual([1, 2]);
  });
});

describe("etagMatches", () => {
  it("matches ignoring the weak prefix", () => {
    expect(etagMatches('W/"abc"', 'W/"abc"')).toBe(true);
    expect(etagMatches('"abc"', 'W/"abc"')).toBe(true);
  });
  it('handles "*" and comma lists', () => {
    expect(etagMatches("*", 'W/"anything"')).toBe(true);
    expect(etagMatches('W/"zzz", W/"abc"', 'W/"abc"')).toBe(true);
  });
  it("rejects a different tag", () => {
    expect(etagMatches('W/"abc"', 'W/"def"')).toBe(false);
  });
});

describe("absolutize", () => {
  it("resolves relative against base, leaves absolute, falls back on junk", () => {
    expect(absolutize("/p", "https://h.com/x")).toBe("https://h.com/p");
    expect(absolutize("https://o.com/p", "https://h.com")).toBe("https://o.com/p");
    expect(absolutize("::::", "::::")).toBe("::::");
  });
});

describe("xmlEscape", () => {
  it("escapes the five-ish XML specials it cares about", () => {
    expect(xmlEscape(`a & b < c > "q"`)).toBe("a &amp; b &lt; c &gt; &quot;q&quot;");
  });
});

describe("hostAllowed", () => {
  it("allows everything when the list is empty", () => {
    expect(hostAllowed("any.example", {})).toBe(true);
  });
  it("matches by suffix when a list is set", () => {
    const env = { ALLOWED_HOSTS: "example.com, foo.org" };
    expect(hostAllowed("news.example.com", env)).toBe(true);
    expect(hostAllowed("evil.net", env)).toBe(false);
  });
});

describe("clamp", () => {
  it("bounds to [lo, hi]", () => {
    expect(clamp(5, 1, 10)).toBe(5);
    expect(clamp(-1, 1, 10)).toBe(1);
    expect(clamp(99, 1, 10)).toBe(10);
  });
});

describe("buildAtom", () => {
  it("emits well-formed Atom with escaped, conditional fields", () => {
    const xml = buildAtom({
      title: "T & U",
      pageUrl: "https://p.example/",
      selfUrl: "https://w.example/scrape?url=p",
      updated: "2022-01-01T00:00:00.000Z",
      items: [
        { title: "One", link: "https://p.example/1", summary: "s", image: "https://p.example/1.png" },
        { title: "Two", link: "https://p.example/2", summary: "", image: null },
      ],
    });
    expect(xml).toContain('<feed xmlns="http://www.w3.org/2005/Atom"');
    expect(xml).toContain("<title>T &amp; U</title>");
    expect(xml).toContain('<link rel="alternate" href="https://p.example/1"/>');
    expect(xml).toContain('<media:content url="https://p.example/1.png"/>');
    // second item has no summary/image lines
    expect((xml.match(/<summary>/g) || []).length).toBe(1);
    expect((xml.match(/<media:content /g) || []).length).toBe(1);
  });
});
