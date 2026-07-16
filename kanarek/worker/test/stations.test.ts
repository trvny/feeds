import { describe, it, expect } from "vitest";
import { mapRadioBrowserStations } from "../src/index";

describe("mapRadioBrowserStations", () => {
  it("drops rows without a resolved stream URL", () => {
    const out = mapRadioBrowserStations([
      { name: "No stream" },
      { name: "Has stream", url_resolved: "http://ok" },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].streamUrl).toBe("http://ok");
  });

  it("falls back to 'Untitled station' for a blank/missing name", () => {
    const out = mapRadioBrowserStations([
      { url_resolved: "http://x" },
      { name: "   ", url_resolved: "http://y" },
    ]);
    expect(out[0].name).toBe("Untitled station");
    expect(out[1].name).toBe("Untitled station");
  });

  it("takes the first tag as groupTitle and trims whitespace", () => {
    const out = mapRadioBrowserStations([
      { name: "A", url_resolved: "http://x", tags: " jazz , chill " },
    ]);
    expect(out[0].groupTitle).toBe("jazz");
  });

  it("groupTitle is null when tags is absent or empty", () => {
    const out = mapRadioBrowserStations([{ name: "A", url_resolved: "http://x", tags: "" }]);
    expect(out[0].groupTitle).toBeNull();

    const noTags = mapRadioBrowserStations([{ name: "A", url_resolved: "http://x" }]);
    expect(noTags[0].groupTitle).toBeNull();
  });

  it("logoUrl is favicon or null", () => {
    const withFavicon = mapRadioBrowserStations([
      { name: "A", url_resolved: "http://x", favicon: "http://logo.png" },
    ]);
    expect(withFavicon[0].logoUrl).toBe("http://logo.png");

    const withoutFavicon = mapRadioBrowserStations([{ name: "A", url_resolved: "http://x" }]);
    expect(withoutFavicon[0].logoUrl).toBeNull();
  });

  it("caps name to 120 chars and group to 40 chars", () => {
    const longName = "x".repeat(200);
    const longTag = "y".repeat(100);
    const out = mapRadioBrowserStations([
      { name: longName, url_resolved: "http://x", tags: longTag },
    ]);
    expect(out[0].name).toHaveLength(120);
    expect(out[0].groupTitle).toHaveLength(40);
  });
});
