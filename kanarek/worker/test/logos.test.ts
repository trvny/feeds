import { describe, it, expect } from "vitest";
import { buildLogoMap, type IptvLogo } from "../src/index";

const mk = (p: Partial<IptvLogo>): IptvLogo => ({
  channel: "X.pl",
  feed: null,
  in_use: true,
  url: "https://e/x.png",
  ...p,
});

describe("buildLogoMap", () => {
  it("keeps one url per channel", () => {
    const m = buildLogoMap([mk({ channel: "A.pl", url: "a" }), mk({ channel: "B.pl", url: "b" })]);
    expect(m).toEqual({ "A.pl": "a", "B.pl": "b" });
  });

  it("prefers in_use over not-in-use", () => {
    const m = buildLogoMap([
      mk({ channel: "A.pl", in_use: false, url: "old" }),
      mk({ channel: "A.pl", in_use: true, url: "live" }),
    ]);
    expect(m["A.pl"]).toBe("live");
  });

  it("prefers channel-level (feed null) over feed-specific", () => {
    const m = buildLogoMap([
      mk({ channel: "A.pl", feed: "HD", url: "feed" }),
      mk({ channel: "A.pl", feed: null, url: "main" }),
    ]);
    expect(m["A.pl"]).toBe("main");
  });

  it("ranks PNG above SVG at equal in_use/feed", () => {
    const m = buildLogoMap([
      mk({ channel: "A.pl", format: "SVG", url: "svg" }),
      mk({ channel: "A.pl", format: "PNG", url: "png" }),
    ]);
    expect(m["A.pl"]).toBe("png");
  });

  it("breaks format ties by larger width", () => {
    const m = buildLogoMap([
      mk({ channel: "A.pl", format: "PNG", width: 200, url: "small" }),
      mk({ channel: "A.pl", format: "PNG", width: 1000, url: "big" }),
    ]);
    expect(m["A.pl"]).toBe("big");
  });

  it("skips entries missing channel or url", () => {
    const m = buildLogoMap([
      mk({ channel: "", url: "x" }),
      { channel: "A.pl", feed: null, in_use: true, url: "" } as IptvLogo,
      mk({ channel: "A.pl", url: "ok" }),
    ]);
    expect(m).toEqual({ "A.pl": "ok" });
  });
});
