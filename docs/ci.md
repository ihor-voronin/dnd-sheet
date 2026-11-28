# CI/CD: GitHub Actions, rules for main, auto-deploy

The repository is public, so GitHub Actions, branch rules and environments with
approvals are free and have no minute limit. Cloudflare and git-crypt are free too.
Only the VPS costs money.

## How a change flows

```
branch ──► PR into main ──► CI: pre-commit · backend · frontend · diff-coverage ──► squash-merge
                                                                                        │
                    https://dnd.voronin.app ◄── deploy.yml ◄── CI on main is green ◄────┘
                    README badges ◄── badges branch ◄── the badges job
```

1. Work happens in a branch; locally pre-commit checks each commit (RUN.md § 5.1).
2. PR into `main`: CI runs four checks. Merging is allowed only when all are green.
3. Squash-merge: one commit per PR in `main`; its message is the PR title.
4. The push to `main` runs CI again; when it's green, `deploy.yml` deploys the site and
   the `badges` job refreshes the coverage and test numbers in the README.

## Pipelines

### `.github/workflows/ci.yml` — PRs into main and pushes to main

| Check | What it does | Secrets |
| --- | --- | --- |
| **pre-commit** | PR title (≤ 100 characters, no WIP); the same hooks as locally, on changed files (all files on push): ruff, prettier, eslint, tsc, shellcheck, terraform fmt, `uv lock`, trufflehog, "secrets and corpus are encrypted" | none |
| **backend** | unlocks the corpus (git-crypt), builds the test Docker image (`Dockerfile`, target `test`: the production environment plus the uv dev group) and runs all backend tests with coverage (fails below 80%) + import contracts, the PostgreSQL ones against a `postgres:18.7-alpine` service container (a skipped PostgreSQL test fails the job, [docs/database.md](database.md)); uploads the coverage report | `GIT_CRYPT_KEY` |
| **frontend** | `npm ci`, types, ESLint (0 warnings), vitest with coverage (fails below 80% of lines or statements), build, the glossary check (`test_terminology.py`, Python only); uploads the coverage report | none |
| **diff-coverage** | PRs only: [diff-cover](https://github.com/Bachmann1234/diff_cover) over the reports that exist — the lines the PR adds or changes must be ≥ 80% covered; the per-file table goes to the run summary | none |
| **badges** | pushes to `main` only: `scripts/coverage_badges.py` turns the reports into shields.io JSON and force-pushes them to the `badges` branch (one commit, no history) | `GITHUB_TOKEN` (contents: write) |

Backend tests are meaningless without the corpus (90 fail, 369 are skipped), so the
corpus is stored in git encrypted and CI unlocks it with the key.

**Only what changed, on PRs.** A `changes` job looks at the PR's files:

| Changed | Runs |
| --- | --- |
| `backend/`, `content/`, `scripts/`, `pyproject.toml`, `uv.lock` | backend |
| `frontend/` | frontend (with the glossary check) |
| `contract/`, `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml` | both |
| anything else (docs, deploy, README) | neither |

A job that doesn't run is *skipped*, and GitHub counts a skipped required check as passed,
so a frontend-only PR doesn't wait for the backend's Docker build. `diff-coverage` checks
the reports that exist. On `main` (after the merge) everything always runs.

## Coverage

| What | Gate | Where it's set |
| --- | --- | --- |
| backend, whole | ≥ 80% of lines | `[tool.coverage.report] fail_under` in `backend/pyproject.toml` |
| frontend, whole | ≥ 80% of lines and of statements | `coverage.thresholds` in `frontend/vitest.config.ts` |
| new code of a PR | ≥ 80% of added and changed lines, backend and frontend together | `diff-coverage` job, `--fail-under 80` |

The whole-project gate keeps the level from sliding; the new-code gate keeps every PR
honest without punishing it for old gaps. A PR that touches no measured code (docs,
config, scripts) passes the new-code gate as is.

Locally:

```powershell
uv run pytest backend --cov --cov-config=backend/pyproject.toml --cov-report=xml:coverage/backend.xml
cd frontend; npm run test:coverage; cd ..
uvx diff-cover coverage/backend.xml frontend/coverage/cobertura-coverage.xml --compare-branch origin/main --fail-under 80
```

Frontend tests render the real screens; `fetch` is answered from
`frontend/src/test/tape.json.gz` — API responses recorded from the real backend by
`scripts/record_frontend_tape.py` (needs the unlocked corpus). Book text in the tape is
scrubbed: words become "lorem", numbers, dice and markdown stay. Re-record the tape
when an API response changes shape.

Badges in the README read `https://raw.githubusercontent.com/ihor-voronin/dnd-sheet/badges/*.json`;
until the first green CI on `main` after this change the branch doesn't exist and the
badges say "resource not found".

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

Two rulesets. GitHub applies both, and a bypass in one doesn't lift the rules of the other.

[`.github/rulesets/main.json`](../.github/rulesets/main.json) — how a change gets in.
Nobody bypasses it, the owner included:

| Rule | Why |
| --- | --- |
| changes only through a PR | no unchecked code reaches main |
| required checks `pre-commit`, `backend`, `frontend`, `diff-coverage` | merge only on green CI and covered new code |
| branch must be up to date with main | checks ran on exactly what gets merged |
| all PR conversations resolved | nothing gets lost |
| squash-merge only, linear history | one commit per change, no merge commits |
| no force-push or deletion of main | history can't be rewritten |
| 0 required approvals | you can't approve your own PR; with a second contributor — 1 |

[`.github/rulesets/main-merge.json`](../.github/rulesets/main-merge.json) — who lets it in.
It blocks every update of main ("Restrict updates"); the only bypass is the Repository
admin role, and only through a PR (`bypass_mode: pull_request`). In a personal
repository the owner is the only admin — collaborators get write at most — so only the
owner merges, and still only a PR that passed every rule of `main.json`. A collaborator
can open PRs and push to their branches, but the Merge button stays disabled for them.

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
2. **Rulesets for main** — Settings → Rules → Rulesets → New ruleset → Import a
   ruleset, once for `.github/rulesets/main.json` and once for
   `.github/rulesets/main-merge.json`. When the file changes (a new required check
   such as `diff-coverage`), edit the existing ruleset: Settings → Rules → Rulesets →
   main → Require status checks → Add checks.
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
