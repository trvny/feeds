import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../reader-fetch.js", import.meta.url), "utf8");

function makeContext(nativeFetch, cfg = {}) {
  const window = { fetch: nativeFetch };
  const context = vm.createContext({
    AbortController,
    DOMException,
    Request,
    URL,
    document: { baseURI: "https://reader.test/reader.html" },
    location: { origin: "https://reader.test" },
    localStorage: { getItem: key => key === "fs:cfg" ? JSON.stringify(cfg) : null },
    window,
  });
  vm.runInContext(source, context);
  return window;
}

test("caps concurrent reader fetches at 12", async () => {
  let active = 0;
  let maxActive = 0;
  const nativeFetch = async () => {
    active += 1;
    maxActive = Math.max(maxActive, active);
    await new Promise(resolve => setTimeout(resolve, 5));
    active -= 1;
    return new Response("ok");
  };
  const window = makeContext(nativeFetch);

  await Promise.all(Array.from({ length: 30 }, (_, i) => window.fetch(`https://example.com/${i}`)));

  assert.equal(maxActive, 12);
});

test("keeps same-origin proxy bypass behind the concurrency gate", async () => {
  const seen = [];
  const nativeFetch = async input => {
    seen.push(String(input));
    return new Response("ok");
  };
  const proxy = "https://proxy.test/?url=";
  const window = makeContext(nativeFetch, { proxy });
  const target = "https://reader.test/feed.xml";

  await window.fetch(proxy + encodeURIComponent(target));

  assert.deepEqual(seen, [target]);
});

test("drops an aborted queued fetch before it reaches the network", async () => {
  const releases = [];
  let started = 0;
  const nativeFetch = () => {
    started += 1;
    return new Promise(resolve => releases.push(() => resolve(new Response("ok"))));
  };
  const window = makeContext(nativeFetch);
  const blockers = Array.from({ length: 12 }, (_, i) => window.fetch(`https://example.com/${i}`));
  const controller = new AbortController();
  const queued = window.fetch("https://example.com/queued", { signal: controller.signal });

  assert.equal(started, 12);
  controller.abort();
  await assert.rejects(queued, error => error?.name === "AbortError");
  assert.equal(started, 12);

  releases.forEach(release => release());
  await Promise.all(blockers);
});
