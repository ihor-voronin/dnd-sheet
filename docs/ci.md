# CI/CD: GitHub Actions, rules for main, auto-deploy

The repository is public, so GitHub Actions, branch rules and environments with
approvals are free and have no minute limit. Cloudflare and git-crypt are free too.
Only the VPS costs money.

## How a change flows

```
branch ──► PR into main ──► CI: pre-commit · backend · frontend ──► squash-merge
                                                                        │
                          https://dnd.voronin.app ◄── deploy.yml ◄──────┘ (CI on main is green)
```

1. Work happens in a branch; locally pre-commit checks each commit (RUN.md § 5.1).
2. PR into `main`: CI runs three checks. Merging is allowed only when all are green.
3. Squash-merge: one commit per PR in `main`; its message is the PR title.
4. The push to `main` runs CI again; when it's green, `deploy.yml` deploys the site.

## Pipelines

### `.github/workflows/ci.yml` — PRs into main and pushes to main

| Check | What it does | Secrets |
| --- | --- | --- |
| **pre-commit** | PR title (≤ 100 characters, no WIP); the same hooks as locally, on changed files (all files on push): ruff, prettier, eslint, tsc, shellcheck, terraform fmt, trufflehog, "secrets and corpus are encrypted" | none |
| **backend** | unlocks the corpus (git-crypt), builds the test Docker image (`Dockerfile`, target `test`) and runs all backend tests + import contracts — the production image plus dev dependencies | `GIT_CRYPT_KEY` |
| **frontend** | `npm ci`, types, ESLint (0 warnings), build | none |

Backend tests are meaningless without the corpus (90 fail, 369 are skipped), so the
corpus is stored in git encrypted and CI unlocks it with the key.

### `.github/workflows/deploy.yml` — after green CI on main

- triggered by `workflow_run` (CI on `main`, push, success) or by hand
  (Actions → Deploy → Run workflow, only from `main`);
- unlocks secrets and the corpus, builds the image (GitHub Actions layer cache),
  runs `scripts/deploy_app.py` — the same script `deploy.ps1` uses;
- `production` environment with a link to the site; deploys never overlap.

Terraform doesn't run in CI: infrastructure changes rarely and by hand
(`deploy.ps1 -Infra`, docs/deploy.md).

There is no automatic rollback: if the new version doesn't become healthy the deploy
fails, but the container has already been replaced. Roll back by reverting the PR (the
next deploy restores the old version) or by re-running an earlier successful Deploy run.

## Rules for main

Defined in [`.github/rulesets/main.json`](../.github/rulesets/main.json):

| Rule | Why |
| --- | --- |
| changes only through a PR | no unchecked code reaches main |
| required checks `pre-commit`, `backend`, `frontend` | merge only on green CI |
| branch must be up to date with main | checks ran on exactly what gets merged |
| all PR conversations resolved | nothing gets lost |
| squash-merge only, linear history | one commit per change, no merge commits |
| no force-push or deletion of main | history can't be rewritten |
| 0 required approvals | you can't approve your own PR; with a second contributor — 1 |

## One-time setup in GitHub

1. **`GIT_CRYPT_KEY` secret** — Settings → Secrets and variables → Actions →
   New repository secret. The value is the git-crypt key in base64:

   ```powershell
   git-crypt export-key deploy\local\git-crypt.key
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("deploy\local\git-crypt.key"))
   Remove-Item deploy\local\git-crypt.key
   ```

   This key opens everything encrypted (deploy secrets and the corpus) — put it only
   into the GitHub secret. Secrets are not passed to PRs from forks.
2. **Ruleset for main** — Settings → Rules → Rulesets → New ruleset → Import a
   ruleset → `.github/rulesets/main.json`.
3. **`production` environment** — appears after the first deploy. In
   Settings → Environments → production you can limit deploys to `main` and
   optionally add yourself as a Required reviewer (every deploy waits for a click).
4. **Private vulnerability reporting** — Settings → Code security → enable it, so the
   "Found a vulnerability" button on `#/bugs` works.

## What's free and where the limits are

| What | Limit |
| --- | --- |
| GitHub Actions | public repository — no minute limit on standard runners |
| Actions cache (Docker layers, pre-commit) | 10 GB per repository, old entries are evicted automatically |
| rulesets, environments | free for public repositories |
| Cloudflare DNS, Let's Encrypt | free |
| RackNerd VPS | paid (yearly plan) |
