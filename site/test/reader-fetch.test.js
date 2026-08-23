import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../reader-fetch.js", import.meta.url), "utf8");

function makeContext(nativeFetch, cfg = {}) {
  const window = { fetch: nativeFetch };
  const context = vm.createContext({
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

test("limits feed tasks while preserving input order", async () => {
  const window = makeContext(async () => new Response("ok"));
  const { allSettledLimited } = window.FeedseekReaderUtils;
  let active = 0;
  let maxActive = 0;

  const results = await allSettledLimited(Array.from({ length: 30 }, (_, i) => i), 12, async item => {
    active += 1;
    maxActive = Math.max(maxActive, active);
    await new Promise(resolve => setTimeout(resolve, 5));
    active -= 1;
    return item * 2;
  });

  assert.equal(maxActive, 12);
  assert.deepEqual(
    results.map(result => [result.status, result.value]),
    Array.from({ length: 30 }, (_, i) => ["fulfilled", i * 2]),
  );
});

test("does not start queued tasks until a worker slot is free", async () => {
  const window = makeContext(async () => new Response("ok"));
  const { allSettledLimited } = window.FeedseekReaderUtils;
  const releases = [];
  const started = [];

  const run = allSettledLimited([0, 1, 2], 2, async item => {
    started.push(item);
    if (item < 2) await new Promise(resolve => releases.push(resolve));
    return item;
  });

  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(started, [0, 1]);
  releases.shift()();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(started, [0, 1, 2]);
  releases.shift()();
  await run;
});

test("preserves rejected results without stopping other tasks", async () => {
  const window = makeContext(async () => new Response("ok"));
  const { allSettledLimited } = window.FeedseekReaderUtils;
  const boom = new Error("boom");

  const results = await allSettledLimited(["a", "b", "c"], 2, async item => {
    if (item === "b") throw boom;
    return item.toUpperCase();
  });

  assert.equal(results[0].status, "fulfilled");
  assert.equal(results[0].value, "A");
  assert.equal(results[1].status, "rejected");
  assert.equal(results[1].reason, boom);
  assert.equal(results[2].status, "fulfilled");
  assert.equal(results[2].value, "C");
});

test("keeps same-origin proxy bypass unchanged", async () => {
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
