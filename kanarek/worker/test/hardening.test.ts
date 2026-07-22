import { describe, expect, it } from "vitest";
import { hostAllowed, readCapped } from "../src/index";

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
