import { describe, it, expect } from "vitest";
import { parseBearer, cleanIds, genPairCode } from "../src/index";

describe("parseBearer", () => {
  it("accepts a base64url token of valid length", () => {
    expect(parseBearer("Bearer abcdefghij_klmnopqrst-1")).toBe("abcdefghij_klmnopqrst-1");
  });
  it("rejects missing/short/malformed", () => {
    expect(parseBearer(null)).toBeNull();
    expect(parseBearer("Bearer short")).toBeNull();
    expect(parseBearer("abcdefghij_klmnopqrst-1")).toBeNull();
    expect(parseBearer("Bearer has spaces here")).toBeNull();
  });
});

describe("cleanIds", () => {
  it("dedupes, preserves order, caps length", () => {
    expect(cleanIds(["a", "b", "a", "c"], 10)).toEqual(["a", "b", "c"]);
    expect(cleanIds(["a", "b", "c", "d"], 2)).toEqual(["a", "b"]);
  });
  it("drops non-strings and empties", () => {
    expect(cleanIds(["a", "", null, 7, {}, "b"] as unknown, 10)).toEqual(["a", "b"]);
  });
  it("returns [] for non-arrays", () => {
    expect(cleanIds(undefined, 10)).toEqual([]);
    expect(cleanIds("nope" as unknown, 10)).toEqual([]);
  });
});

describe("genPairCode", () => {
  it("is 6 chars from the non-ambiguous alphabet", () => {
    const c = genPairCode(() => 0.5);
    expect(c).toHaveLength(6);
    expect(/^[0-9A-Z]{6}$/.test(c)).toBe(true);
    expect(/[01OIL]/.test(c)).toBe(false);
  });
});
