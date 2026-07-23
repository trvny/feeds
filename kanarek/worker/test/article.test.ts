import { describe, expect, it } from "vitest";
import {
  cleanBlocks,
  extractJsonLdArticle,
  isSafeArticleUrl,
  pickBestArticleCandidate,
} from "../src/article";

describe("clean article extraction", () => {
  it("prefers a JSON-LD article body and keeps metadata", () => {
    const schema = JSON.stringify({
      "@type": "NewsArticle",
      headline: "A clean headline",
      author: { name: "Jan Kowalski" },
      image: "/hero.jpg",
      articleBody: [
        "Pierwszy długi akapit opisuje najważniejsze wydarzenia i zawiera wystarczająco dużo tekstu, aby stanowić prawdziwą treść artykułu.",
        "Drugi akapit rozwija temat, dodaje kontekst oraz kolejne informacje potrzebne czytelnikowi.",
        "Trzeci akapit domyka materiał bez reklam, przycisków udostępniania ani elementów nawigacyjnych.",
      ].join("\n\n"),
    });
    const html = `<html><head><script type="application/ld+json">${schema}</script></head></html>`;

    const article = extractJsonLdArticle(html, "https://example.com/news/1");
    expect(article?.title).toBe("A clean headline");
    expect(article?.author).toBe("Jan Kowalski");
    expect(article?.image).toBe("https://example.com/hero.jpg");
    expect(article?.content).toContain("Drugi akapit");
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
  it("accepts ordinary public web URLs", () => {
    expect(isSafeArticleUrl("https://news.example.org/story", "example.org")).toBe(true);
  });

  it.each([
    "file:///etc/passwd",
    "http://localhost/admin",
    "http://127.0.0.1/private",
    "http://[::1]/private",
    "https://user:password@example.org/story",
    "https://router.local/status",
  ])("rejects unsafe target %s", (url) => {
    expect(isSafeArticleUrl(url)).toBe(false);
  });

  it("enforces the optional host allowlist", () => {
    expect(isSafeArticleUrl("https://news.example.org/story", "trusted.net")).toBe(false);
    expect(isSafeArticleUrl("https://sub.trusted.net/story", ".trusted.net")).toBe(true);
  });
});
