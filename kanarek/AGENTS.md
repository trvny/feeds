# kanarek

- `app/`: Kotlin/Compose Android. `worker/`: TypeScript/Cloudflare.
- Keep the Worker optional; blank backend must retain on-device feed parsing.
- Keep pure codecs and parsers Android-free.
- App tests: `./gradlew testPlayDebugUnitTest`.
- Worker tests: `cd worker && npm install && npm test`.

## Code Review Rules

- Flag changes that silently require the Worker, weaken host/redirect allowlists, or break cache/ETag fallback.
- Flag Android lifecycle, widget/player background, or persisted-format regressions.
