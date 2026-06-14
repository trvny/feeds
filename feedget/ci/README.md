# CI workflows (staging)

The bot that scaffolded this repo couldn't write to `.github/workflows/` (it lacked the
GitHub *workflows* permission), so the workflow files live here. To activate them:

```bash
mkdir -p .github/workflows
git mv ci/android-ci.yml ci/worker-ci.yml ci/release.yml .github/workflows/
git rm ci/README.md
git commit -m "Enable CI workflows"
git push
```

Or paste each file into the GitHub web UI under **Actions → New workflow → set up a workflow yourself**.

- **android-ci.yml** — build + lint the app, upload the debug APK as an artifact (push/PR to main).
- **worker-ci.yml** — typecheck the Cloudflare Worker when `worker/**` changes.
- **release.yml** — on a `v*` tag, build the APK and attach it to a GitHub Release.
