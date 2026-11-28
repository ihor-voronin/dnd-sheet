# Several projects on one VPS → vps-infra

The plan moved to its own repository, **ihor-voronin/vps-infra**, as the owner decided on
2026-11-28. That repository owns the server, DNS, the shared Caddy, the shared PostgreSQL,
backups and the deploy every project uses.

- [docs/platform.md](https://github.com/ihor-voronin/vps-infra/blob/main/docs/platform.md): who owns what, secrets (DB passwords in git-crypt
  in both repositories), adding and removing projects, and moving dnd-sheet over in 8 steps.
- [docs/deploys.md](https://github.com/ihor-voronin/vps-infra/blob/main/docs/deploys.md): how migrations run, how dnd-sheet deploys, and how
  other projects deploy.

Until the move, dnd-sheet still deploys as described in [deploy.md](deploy.md).
