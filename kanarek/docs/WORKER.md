# Kanarek Worker

The Worker source and production deployment moved to the standalone [trvny/kanarek](https://github.com/trvny/kanarek) repository.

This `trvny/feeds/kanarek` tree is a temporary frozen Android release/signing mirror and no longer contains or deploys the Worker. For current routes, bindings, deployment instructions and tests, use:

- [`trvny/kanarek/worker`](https://github.com/trvny/kanarek/tree/main/worker)
- [`trvny/kanarek/docs/WORKER.md`](https://github.com/trvny/kanarek/blob/main/docs/WORKER.md)

The live backend remains `https://kanarek.travny.workers.dev` and is deployed from `trvny/kanarek` through Cloudflare Workers Builds.
