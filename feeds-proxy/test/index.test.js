import assert from "node:assert/strict";
import test from "node:test";

import worker from "../src/index.js";

const proxyRequest = (target, init) =>
  new Request(`https://proxy.test/?url=${encodeURIComponent(target)}`, init);

async function withFetch(mockFetch, run) {
  const original = globalThis.fetch;
  globalThis.fetch = mockFetch;
  try {
    return await run();
  } finally {
    globalThis.fetch = original;
  }
}

test("forwards valid HTTPS feeds with cache and security headers", async () => {
  let seenUrl;
  let seenInit;

  await withFetch(async (url, init) => {
    seenUrl = String(url);
    seenInit = init;
    return new Response("<rss/>", {
      status: 200,
      headers: { "content-type": "application/rss+xml" },
    });
  }, async () => {
    const response = await worker.fetch(proxyRequest("https://example.com/feed.xml"));

    assert.equal(response.status, 200);
    assert.equal(await response.text(), "<rss/>");
    assert.equal(response.headers.get("content-type"), "application/rss+xml");
    assert.equal(response.headers.get("cache-control"), "public, max-age=900");
    assert.equal(response.headers.get("access-control-allow-origin"), "*");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(seenUrl, "https://example.com/feed.xml");
    assert.equal(seenInit.redirect, "manual");
    assert.equal(seenInit.headers["user-agent"], "feedseek-reader/2.0");
  });
});

test("follows relative redirects and revalidates the target", async () => {
  const calls = [];

  await withFetch(async (url) => {
    calls.push(String(url));
    if (calls.length === 1) {
      return new Response(null, { status: 302, headers: { location: "/final.xml" } });
    }
    return new Response("done", { status: 200 });
  }, async () => {
    const response = await worker.fetch(proxyRequest("https://example.com/start"));

    assert.equal(response.status, 200);
    assert.equal(await response.text(), "done");
    assert.deepEqual(calls, [
      "https://example.com/start",
      "https://example.com/final.xml",
    ]);
  });
});

test("rejects non-HTTPS and private-looking targets before fetching", async () => {
  let calls = 0;

  await withFetch(async () => {
    calls += 1;
    return new Response("unexpected");
  }, async () => {
    const http = await worker.fetch(proxyRequest("http://example.com/feed"));
    const privateHost = await worker.fetch(proxyRequest("https://127.0.0.1/feed"));

    assert.equal(http.status, 400);
    assert.equal(await http.text(), "bad url");
    assert.equal(privateHost.status, 403);
    assert.equal(await privateHost.text(), "blocked host");
    assert.equal(calls, 0);
  });
});

test("rejects redirects to blocked hosts", async () => {
  await withFetch(async () =>
    new Response(null, { status: 302, headers: { location: "https://localhost/private" } }),
  async () => {
    const response = await worker.fetch(proxyRequest("https://example.com/start"));

    assert.equal(response.status, 502);
    assert.equal(await response.text(), "blocked host");
    assert.equal(response.headers.get("cache-control"), "no-store");
  });
});

test("rejects responses over the declared size limit", async () => {
  await withFetch(async () =>
    new Response("x", { headers: { "content-length": String(2 * 1024 * 1024 + 1) } }),
  async () => {
    const response = await worker.fetch(proxyRequest("https://example.com/huge"));

    assert.equal(response.status, 502);
    assert.equal(await response.text(), "response too large");
    assert.equal(response.headers.get("cache-control"), "no-store");
  });
});

test("keeps upstream errors uncached", async () => {
  await withFetch(async () => new Response("missing", { status: 404 }), async () => {
    const response = await worker.fetch(proxyRequest("https://example.com/missing"));

    assert.equal(response.status, 404);
    assert.equal(await response.text(), "missing");
    assert.equal(response.headers.get("cache-control"), "no-store");
  });
});

test("maps upstream timeouts to a 502", async () => {
  const timeout = Object.assign(new Error("timed out"), { name: "TimeoutError" });

  await withFetch(async () => {
    throw timeout;
  }, async () => {
    const response = await worker.fetch(proxyRequest("https://example.com/slow"));

    assert.equal(response.status, 502);
    assert.equal(await response.text(), "upstream timeout");
  });
});

test("answers preflight and rejects non-GET methods", async () => {
  const options = await worker.fetch(new Request("https://proxy.test/", { method: "OPTIONS" }));
  const post = await worker.fetch(new Request("https://proxy.test/", { method: "POST" }));

  assert.equal(options.status, 204);
  assert.equal(options.headers.get("access-control-allow-methods"), "GET, OPTIONS");
  assert.equal(post.status, 405);
  assert.equal(await post.text(), "method not allowed");
  assert.equal(post.headers.get("cache-control"), "no-store");
});
