import { describe, expect, it } from "vitest";
import { fetchOutbound, hostAllowed, readCapped } from "../src/index";

describe("readCapped", () => {
  it("returns at most the configured byte count", async () => {
    const response = new Response("abcdefgh");
    expect(await readCapped(response, 4)).toBe("abcd");
  });

  it("keeps a body smaller than the cap unchanged", async () => {
    const response = new Response("abc");
    expect(await readCapped(response, 4)).toBe("abc");
  });
});

describe("hostAllowed boundary matching", () => {
  const env = { ALLOWED_HOSTS: "example.com, .foo.org." };

  it("allows the exact host and real subdomains", () => {
    expect(hostAllowed("example.com", env)).toBe(true);
    expect(hostAllowed("news.example.com", env)).toBe(true);
    expect(hostAllowed("RADIO.FOO.ORG.", env)).toBe(true);
  });

  it("does not treat a lookalike suffix as a subdomain", () => {
    expect(hostAllowed("notexample.com", env)).toBe(false);
    expect(hostAllowed("evilfoo.org", env)).toBe(false);
  });
});

describe("outbound URL hardening", () => {
  it("blocks local names and literal IP addresses even without an allowlist", () => {
    const env = {};
    expect(hostAllowed("localhost", env)).toBe(false);
    expect(hostAllowed("api.localhost", env)).toBe(false);
    expect(hostAllowed("router.lan", env)).toBe(false);
    expect(hostAllowed("127.0.0.1", env)).toBe(false);
    expect(hostAllowed("[::1]", env)).toBe(false);
    expect(hostAllowed("example.com", env)).toBe(true);
  });

  it("validates the destination of every redirect", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => new Response(null, {
      status: 302,
      headers: { location: "http://127.0.0.1/private" },
    });
    try {
      await expect(fetchOutbound("https://example.com/feed", {}, {})).rejects.toThrow("host not allowed");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
