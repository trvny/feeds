(() => {
  const MAX_CONCURRENT_FETCHES = 12;
  const nativeFetch = window.fetch.bind(window);
  const queue = [];
  let active = 0;

  function abortReason(signal) {
    return signal.reason || new DOMException("The operation was aborted.", "AbortError");
  }

  function pump() {
    while (active < MAX_CONCURRENT_FETCHES && queue.length) {
      const job = queue.shift();
      if (job.signal?.aborted) {
        job.cleanup();
        job.reject(abortReason(job.signal));
        continue;
      }

      active += 1;
      job.cleanup();
      nativeFetch(job.input, job.init).then(job.resolve, job.reject).finally(() => {
        active -= 1;
        pump();
      });
    }
  }

  function limitedFetch(input, init) {
    const signal = init?.signal || (input instanceof Request ? input.signal : null);
    if (signal?.aborted) return Promise.reject(abortReason(signal));

    return new Promise((resolve, reject) => {
      const job = { input, init, signal, resolve, reject, cleanup: () => {} };
      if (signal) {
        const onAbort = () => {
          const index = queue.indexOf(job);
          if (index < 0) return;
          queue.splice(index, 1);
          job.cleanup();
          reject(abortReason(signal));
          pump();
        };
        signal.addEventListener("abort", onAbort, { once: true });
        job.cleanup = () => signal.removeEventListener("abort", onAbort);
      }
      queue.push(job);
      pump();
    });
  }

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
            return limitedFetch(directUrl.href, init);
          }
        }
      } catch {
        // Keep the original request path for malformed custom proxy URLs.
      }
    }

    return limitedFetch(input, init);
  };
})();
