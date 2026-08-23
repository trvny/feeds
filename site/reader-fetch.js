(() => {
  const nativeFetch = window.fetch.bind(window);

  async function allSettledLimited(items, limit, task) {
    const results = new Array(items.length);
    let next = 0;
    const concurrency = Math.min(items.length, Math.max(1, Math.floor(limit) || 1));

    async function worker() {
      while (true) {
        const index = next++;
        if (index >= items.length) return;
        try {
          results[index] = { status: "fulfilled", value: await task(items[index], index) };
        } catch (reason) {
          results[index] = { status: "rejected", reason };
        }
      }
    }

    await Promise.all(Array.from({ length: concurrency }, () => worker()));
    return results;
  }

  window.FeedseekReaderUtils = { allSettledLimited };

  function configuredProxy() {
    try {
      return JSON.parse(localStorage.getItem("fs:cfg") || "{}").proxy || "";
    } catch {
      return "";
    }
  }

  window.fetch = (input, init) => {
    const inputUrl =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : "";
    const proxy = configuredProxy();

    if (proxy && inputUrl.startsWith(proxy)) {
      try {
        const requestUrl = new URL(inputUrl, document.baseURI);
        const target = requestUrl.searchParams.get("url");
        if (target) {
          const directUrl = new URL(target, document.baseURI);
          if (directUrl.origin === location.origin) {
            return nativeFetch(directUrl.href, init);
          }
        }
      } catch {
        // Keep the original request path for malformed custom proxy URLs.
      }
    }

    return nativeFetch(input, init);
  };
})();
