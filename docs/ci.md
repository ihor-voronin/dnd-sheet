# CI/CD: GitHub Actions, правила main, автодеплой

Репозиторій публічний — для нього GitHub Actions, правила гілок і середовища
з підтвердженням безкоштовні й без ліміту хвилин. Cloudflare і git-crypt теж
безкоштовні. Платний лише VPS.

## Як іде зміна

```
гілка ──► PR у main ──► CI: pre-commit · backend · frontend ──► squash-merge
                                                                    │
                          https://dnd.voronin.app ◄── deploy.yml ◄──┘ (CI на main зелений)
```

1. Робота — у гілці; локально коміти перевіряє pre-commit (RUN.md § 5.1).
2. PR у `main`: CI проганяє три перевірки. Злиття — лише коли всі зелені.
3. Squash-merge: у `main` один коміт на PR, його повідомлення — заголовок PR.
4. Push у `main` знову запускає CI; коли він зелений, `deploy.yml` деплоїть сайт.

## Пайплайни

### `.github/workflows/ci.yml` — PR у main і push у main

| Перевірка | Що робить | Секрети |
| --- | --- | --- |
| **pre-commit** | заголовок PR (≤ 100 символів, без WIP); ті самі хуки, що й локально, на змінених файлах (у push — на всіх): ruff, prettier, eslint, tsc, shellcheck, terraform fmt, trufflehog, gitlint-правила, «секрети й корпус лише зашифровані» | немає |
| **backend** | розблоковує корпус (git-crypt), збирає тестовий Docker-образ (`Dockerfile`, ціль `test`) і запускає всі тести бекенду + контракти імпортів — той самий образ, що й у продакшні, плюс dev-залежності | `GIT_CRYPT_KEY` |
| **frontend** | `npm ci`, типи, ESLint (0 попереджень), збірка | немає |

Без корпусу тести бекенду не мають сенсу (90 падають, 369 пропускаються), тому
корпус лежить у git зашифрованим, а CI розблоковує його ключем.

### `.github/workflows/deploy.yml` — після зеленого CI на main

- запускається подією `workflow_run` (CI на `main`, push, успіх) або вручну
  (Actions → Deploy → Run workflow, лише з `main`);
- розблоковує секрети й корпус, збирає образ (кеш шарів GitHub Actions),
  запускає `scripts/deploy_app.py` — той самий скрипт, що й `deploy.ps1`;
- середовище `production` з посиланням на сайт; деплої не перекривають один одного.

Terraform у CI не запускається: інфраструктура змінюється рідко й вручну
(`deploy.ps1 -Infra`, docs/deploy.md).

## Правила гілки main

Описані в [`.github/rulesets/main.json`](../.github/rulesets/main.json):

| Правило | Навіщо |
| --- | --- |
| лише через PR | у main не потрапляє неперевірений код |
| обовʼязкові перевірки `pre-commit`, `backend`, `frontend` | злиття тільки на зеленому CI |
| гілка має бути актуальною з main | перевірки проходили на тому, що й зіллється |
| усі коментарі в PR розвʼязані | нічого не загубилося |
| лише squash-merge, лінійна історія | один коміт на зміну, без merge-комітів |
| заборонено force-push і видалення main | історію не переписати |
| 0 обовʼязкових схвалень | власний PR схвалити не можна; з другим учасником — 1 |

## Налаштувати (один раз, у GitHub)

1. **Секрет `GIT_CRYPT_KEY`** — Settings → Secrets and variables → Actions →
   New repository secret. Значення — ключ git-crypt у base64:

   ```powershell
   git-crypt export-key deploy\local\git-crypt.key
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("deploy\local\git-crypt.key"))
   Remove-Item deploy\local\git-crypt.key
   ```

   Цей ключ відкриває все зашифроване (секрети деплою й корпус) — лише в секрет
   GitHub, нікуди більше. Секрети не потрапляють у PR із форків.
2. **Правило main** — Settings → Rules → Rulesets → New ruleset → Import a
   ruleset → `.github/rulesets/main.json`.
3. **Середовище `production`** — зʼявиться саме після першого деплою. У
   Settings → Environments → production можна обмежити деплой гілкою `main` і,
   за бажання, додати себе в Required reviewers (кожен деплой — кнопкою).

## Що безкоштовно і де межі

| Що | Межа |
| --- | --- |
| GitHub Actions | публічний репозиторій — без ліміту хвилин на стандартних раннерах |
| кеш Actions (шари Docker, pre-commit) | 10 ГБ на репозиторій, старе витісняється саме |
| rulesets, environments | безкоштовно для публічних репозиторіїв |
| Cloudflare DNS, Let's Encrypt | безкоштовно |
| VPS RackNerd | платно (річний тариф) |
