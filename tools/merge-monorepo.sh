#!/usr/bin/env bash
# Scala travino/feedy do tego repo jako monorepo (feedget/ + feedseek/).
# Uruchamiany przez .github/workflows/monorepo-merge.yml na runnerze (ma gita +
# git-filter-repo + GITHUB_TOKEN). Pcha gałąź `monorepo` i otwiera PR.
#
# WAŻNE: runner z GITHUB_TOKEN nie może pisać w .github/workflows/. Dlatego
# workflowy feedy lądują w feedget/ci-import/ (poza .github/workflows) — przenosi
# je do roota konektor, który ma workflow scope. Tu nie ruszamy root .github/workflows/*.
set -euo pipefail

INCOMING=feedy
BRANCH=monorepo

git config user.name  'github-actions[bot]'
git config user.email 'github-actions[bot]@users.noreply.github.com'
git switch -c "$BRANCH"

echo "== feedy -> feedget/ (z historią; workflowy feedy -> feedget/ci-import/) =="
git clone --no-tags "https://github.com/travino/$INCOMING.git" /tmp/$INCOMING
git -C /tmp/$INCOMING filter-repo --path-rename .github/workflows/:ci-import/
git -C /tmp/$INCOMING filter-repo --force --to-subdirectory-filter feedget

echo "== feeds -> feedseek/ =="
mkdir -p feedseek
for p in Makefile cache docs feed_generators feeds.yaml feeds pyproject.toml requirements.txt site; do
  [ -e "$p" ] && git mv "$p" "feedseek/$p"
done
git mv README.md feedseek/README.md
git add -A
git commit -m "chore: przenieś generatory do feedseek/ (monorepo prep)"

echo "== wciągam feedget z historią =="
git remote add incoming /tmp/$INCOMING
git fetch incoming
git merge --allow-unrelated-histories --no-edit incoming/main

# duplikaty: zostaje root LICENSE i root dependabot
git rm -q  --ignore-unmatch feedget/LICENSE
git rm -rq --ignore-unmatch feedget/.github

echo "== scalony dependabot + root README =="
mkdir -p .github
cat > .github/dependabot.yml <<'YML'
version: 2
updates:
  - package-ecosystem: pip
    directory: /feedseek
    schedule: { interval: weekly }
  - package-ecosystem: gradle
    directory: /feedget
    schedule: { interval: weekly }
    groups:
      androidx:
        patterns: ["androidx*"]
      kotlin:
        patterns: ["org.jetbrains.kotlin*"]
  - package-ecosystem: npm
    directory: /feedget/worker
    schedule: { interval: weekly }
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }
YML

cat > README.md <<'MD'
# travino/feeds — monorepo

Producent i konsument feedów w jednym repo.

| katalog | co to | stack |
|---|---|---|
| [`feedseek/`](feedseek/) | generatory RSS/Atom — scrapują strony bez feedów, CI co 2 h, publikacja na GitHub Pages | Python (uv) |
| [`feedget/`](feedget/) | natywny widget + apka Android do czytania feedów, plus worker RSS→JSON na krawędzi | Kotlin/Compose · Cloudflare Worker (TS) |

Oba scrapują „strona → Atom": `feedseek` wsadowo w CI, `feedget/worker` on-demand
na krawędzi (`/discover` + `/scrape`). Historia obu projektów zachowana.

Workflowy feedget czekają w `feedget/ci-import/` na przeniesienie do `.github/workflows/`.
MD

git add -A
git commit -m "chore: monorepo — scalony dependabot, root README; workflowy feedget w feedget/ci-import/"

echo "== push + PR =="
git push -u origin "$BRANCH"
gh pr create --base main --head "$BRANCH" \
  --title "Monorepo: feedget/ (apka) + feedseek/ (generatory)" \
  --body "$(cat <<'PR'
Scala `travino/feedy` do `feedget/` (z pełną historią) i przenosi generatory do `feedseek/`.

### Zrobione na runnerze
- feedy → `feedget/` przez `git filter-repo` (historia zachowana)
- generatory feeds → `feedseek/` (`git mv`, blame idzie za renamem)
- scalony `.github/dependabot.yml` (pip@feedseek, gradle@feedget, npm@feedget/worker, actions)
- nowy root `README.md`
- workflowy feedy odłożone w `feedget/ci-import/` (runner nie może pisać w `.github/workflows/`)

### Dokończy konektor (osobno, ma workflow scope)
- przeniesienie `feedget/ci-import/*` → `.github/workflows/` + `working-directory: feedget`/`feedget/worker` i `paths:` filtry
- przepięcie `update-feeds.yml` i `deploy-pages.yml` na `feedseek/` (output Pages w `public/` bez zmian → URL-e feedów przeżywają)
- `feedget/docs/HISTORY.md` ze streszczeniem feedy

### Po merge (ręcznie, z apki)
- Settings → Pages: potwierdź źródło = GitHub Actions, URL bez zmian
- `travino/feedy` → Settings → Archive (historia zostaje w archiwum)
PR
)"
echo "GOTOWE"
