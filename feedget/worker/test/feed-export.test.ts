import { describe, it, expect } from "vitest";
import { renderMergedFeed, parseFeed, type NewsItem } from "../src/index";

const items: NewsItem[] = [
  {
    title: "First & foremost",
    link: "https://example.com/a",
    summary: "Body one",
    image: "https://img.example.com/a.jpg",
    date: "2020-01-01T00:00:00.000Z",
    source: "Example News",
  },
  {
    title: "Second",
    link: "https://example.com/b",
    summary: "Body two",
    image: null,
    date: "2020-01-02T00:00:00.000Z",
    source: "Example News",
  },
];

describe("renderMergedFeed (format=atom|rss)", () => {
  it("emits well-formed Atom that the existing parser round-trips", () => {
    const res = renderMergedFeed(items, "atom", new URL("https://feedy-news.travny.workers.dev/?feeds=x&format=atom"));
    expect(res.headers.get("content-type")).toContain("application/atom+xml");

    // renderMergedFeed doesn't set cache-control/etag itself — handleFeeds adds those, mirroring the JSON path.
    expect(res.headers.get("cache-control")).toBeNull();

    // no-op await needed since Response is sync here, but keep the shape consistent with async test helpers
    return res.text().then((xml) => {
      expect(xml).toContain("<feed");
      const parsed = parseFeed(xml);
      expect(parsed.length).toBe(2);
      expect(parsed[0].title).toBe("First & foremost");
      expect(parsed[0].link).toBe("https://example.com/a");
    });
  });

  it("emits well-formed RSS 2.0", async () => {
    const res = renderMergedFeed(items, "rss", new URL("https://feedy-news.travny.workers.dev/?feeds=x&format=rss"));
    expect(res.headers.get("content-type")).toContain("application/rss+xml");
    const xml = await res.text();
    expect(xml).toContain("<rss");
    const parsed = parseFeed(xml);
    expect(parsed.length).toBe(2);
    expect(parsed[1].title).toBe("Second");
  });

  it("carries CORS headers so an external reader served cross-origin can read it", () => {
    const res = renderMergedFeed(items, "atom", new URL("https://feedy-news.travny.workers.dev/?feeds=x&format=atom"));
    expect(res.headers.get("access-control-allow-origin")).toBe("*");
  });
});
