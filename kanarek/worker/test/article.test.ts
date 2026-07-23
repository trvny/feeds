import { describe, expect, it } from "vitest";
import {
  ArticleNoiseGate,
  canStartArticleCandidate,
  cleanBlocks,
  extractJsonLdArticle,
  isArticleNoiseRoot,
  isSafeArticleUrl,
  parseArticleAllowedHosts,
  pickBestArticleCandidate,
} from "../src/article";

describe("clean article extraction", () => {
  it("prefers a JSON-LD article body, strips markup, and keeps metadata", () => {
    const schema = JSON.stringify({
      "@type": "NewsArticle",
      headline: "A clean headline",
      author: { name: "Jan Kowalski" },
      image: "/hero.jpg",
      articleBody: [
        "<p>Pierwszy długi akapit opisuje najważniejsze wydarzenia i zawiera wystarczająco dużo tekstu, aby stanowić prawdziwą treść artykułu.</p>",
        "<script>window.alert('tracker')</script>",
        "<p>Drugi akapit rozwija temat, dodaje kontekst oraz kolejne informacje potrzebne czytelnikowi.</p>",
        "<p>Trzeci akapit domyka materiał bez reklam, przycisków udostępniania ani elementów nawigacyjnych.</p>",
      ].join(""),
    }).replace(/<\/script>/gi, "<\\/script>");
    const html = `<html><head><script type="application/ld+json">${schema}</script></head></html>`;

    const article = extractJsonLdArticle(html, "https://example.com/news/1");
    expect(article?.title).toBe("A clean headline");
    expect(article?.author).toBe("Jan Kowalski");
    expect(article?.image).toBe("https://example.com/hero.jpg");
    expect(article?.content).toContain("Drugi akapit");
    expect(article?.content).not.toContain("<p>");
    expect(article?.content).not.toContain("tracker");
  });

  it("removes common advertisement and subscription boilerplate", () => {
    const blocks = cleanBlocks([
      "Reklama",
      "Pierwszy właściwy akapit ma odpowiednią długość i zostaje w czytelnym artykule.",
      "Subscribe to our newsletter",
      "Pierwszy właściwy akapit ma odpowiednią długość i zostaje w czytelnym artykule.",
      "Drugi właściwy akapit również pozostaje, ponieważ wnosi nową treść do materiału.",
    ]);

    expect(blocks).toEqual([
      "Pierwszy właściwy akapit ma odpowiednią długość i zostaje w czytelnym artykule.",
      "Drugi właściwy akapit również pozostaje, ponieważ wnosi nową treść do materiału.",
    ]);
  });

  it("keeps capture blocked until every overlapping noise selector leaves", () => {
    const gate = new ArticleNoiseGate();

    gate.enter();
    gate.enter();
    expect(gate.isBlocked).toBe(true);
    expect(canStartArticleCandidate(gate)).toBe(false);
    gate.leave();
    expect(gate.isBlocked).toBe(true);
    expect(canStartArticleCandidate(gate)).toBe(false);
    gate.leave();
    expect(gate.isBlocked).toBe(false);
    expect(canStartArticleCandidate(gate)).toBe(true);
    gate.leave();
    expect(gate.isBlocked).toBe(false);
  });

  it("rejects noise containers that are article roots", () => {
    expect(isArticleNoiseRoot("article", null, "story related-card")).toBe(true);
    expect(isArticleNoiseRoot("article", "sponsored-story", "story")).toBe(true);
    expect(isArticleNoiseRoot("article", null, "story")).toBe(false);
  });

  it("does not recursively decode nested entities", () => {
    const [block] = cleanBlocks([
      "Bezpieczny tekst pokazuje zapis &amp;lt;script&amp;gt; dosłownie, zamiast dekodować go do znacznika HTML.",
    ]);

    expect(block).toContain("&lt;script&gt;");
    expect(block).not.toContain("<script>");
  });

  it("scores substantial article candidates above navigation fragments", () => {
    const best = pickBestArticleCandidate([
      { title: "Menu", blocks: ["Strona główna i najnowsze wiadomości z kraju"] },
      {
        title: "Reportaż",
        blocks: [
          "Pierwszy rozbudowany akapit reportażu zawiera wiele szczegółów i opisuje najważniejszy wątek całego materiału.",
          "Drugi rozbudowany akapit dodaje kontekst, wypowiedzi bohaterów oraz informacje niezbędne do zrozumienia historii.",
          "Trzeci akapit podsumowuje wydarzenia i wskazuje ich dalsze konsekwencje dla opisywanych osób.",
        ],
      },
    ]);

    expect(best?.title).toBe("Reportaż");
    expect(best?.blocks).toHaveLength(3);
  });
});

describe("article URL hardening", () => {
  it("fails closed without an explicit article host allowlist", () => {
    expect(isSafeArticleUrl("https://news.example.org/story")).toBe(false);
  });

  it("accepts only an exact trusted host", () => {
    expect(isSafeArticleUrl("https://news.example.org/story", "news.example.org")).toBe(true);
    expect(isSafeArticleUrl("https://news.example.org/story", "example.org")).toBe(false);
    expect(isSafeArticleUrl("https://sub.news.example.org/story", "news.example.org")).toBe(false);
  });

  it.each([
    "file:///etc/passwd",
    "http://localhost/admin",
    "http://127.0.0.1/private",
    "http://[::1]/private",
    "https://user:password@example.org/story",
    "https://router.local/status",
  ])("rejects unsafe target %s", (url) => {
    expect(isSafeArticleUrl(url, "example.org,localhost,127.0.0.1,router.local")).toBe(false);
  });

  it("drops unsafe and wildcard entries from the article allowlist", () => {
    expect([
      ...parseArticleAllowedHosts(
        "news.example.org, localhost, 127.0.0.1, router.local, *.example.org",
      ),
    ]).toEqual(["news.example.org"]);
  });
});
