#!/usr/bin/env python3
"""Деплой застосунку на VPS — однаково з Windows і з GitHub Actions (Linux).

Інфраструктуру (DNS у Cloudflare, Docker, файрвол, swap, бекапи) готує Terraform
(`deploy/terraform`, рідко й вручну). Цей скрипт — те, що змінюється з кожним
комітом: образ, compose, Caddyfile, .env. Стану, як у Terraform, тут немає:
кожен запуск доводить сервер до того, що в репозиторії, тож CI не мусить
нічого комітити назад.

    python scripts/deploy_app.py              # образ dndsheet:local уже зібраний
    python scripts/deploy_app.py --build      # спершу docker compose build app

Кроки:
1. секрети розблоковані (deploy/secrets — не шифр git-crypt);
2. образ: якщо на сервері вже цей самий (id у /opt/dndsheet/IMAGE_ID) — пропуск,
   інакше `docker save` + gzip → scp → `docker load`;
3. compose.yml, Caddyfile (домен з terraform.tfvars), .env з prod.env;
4. `docker compose up -d`, чекати healthy і HTTPS через Caddy.
"""

from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "deploy" / "secrets"
FILES = ROOT / "deploy" / "terraform" / "files"
REMOTE = "/opt/dndsheet"
MAGIC = b"\x00GITCRYPT\x00"


def log(message: str) -> None:
    print(f"[deploy] {message}", flush=True)  # noqa: T201 — консольний скрипт


def fail(message: str) -> None:
    sys.stderr.write(f"[deploy] помилка: {message}\n")
    sys.exit(1)


def read_tfvars(path: Path) -> dict[str, str]:
    """Прості рядки `ключ = "значення"` з terraform.tfvars."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r'\s*([a-z_]+)\s*=\s*"?([^"#]*?)"?\s*(#.*)?$', line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def ensure_unlocked() -> None:
    for path in (SECRETS / "prod.env", SECRETS / "ssh" / "id_ed25519", SECRETS / "terraform" / "terraform.tfvars"):
        if not path.exists():
            fail(f"немає {path.relative_to(ROOT)}")
        if path.read_bytes()[: len(MAGIC)] == MAGIC:
            fail(f"{path.relative_to(ROOT)} зашифрований — спершу git-crypt unlock (docs/deploy.md)")


class Server:
    def __init__(self, host: str, user: str, port: str, key: Path) -> None:
        self.target = f"{user}@{host}"
        self.common = ["-i", str(key), "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes"]
        self.port = port

    def run(self, command: str, *, stdin: bytes | None = None, check: bool = True) -> str:
        result = subprocess.run(
            ["ssh", *self.common, "-p", self.port, self.target, command],
            input=stdin,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            fail(f"на сервері: {command}\n{result.stderr.decode('utf-8', 'replace')}")
        return result.stdout.decode("utf-8", "replace").strip()

    def put(self, local: Path, remote: str) -> None:
        result = subprocess.run(
            ["scp", *self.common, "-P", self.port, str(local), f"{self.target}:{remote}"], check=False
        )
        if result.returncode != 0:
            fail(f"scp {local.name} не вдався")

    def write(self, remote: str, content: str, mode: str = "644") -> None:
        self.run(f"cat > {remote} && chmod {mode} {remote}", stdin=content.replace("\r\n", "\n").encode("utf-8"))


def local_image_id(image: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image], capture_output=True, check=False
    )
    if result.returncode != 0:
        fail(f"немає образу {image} — зберіть: docker compose build app (або --build)")
    return result.stdout.decode().strip()


def ship_image(server: Server, image: str, image_id: str) -> None:
    if server.run(f"cat {REMOTE}/IMAGE_ID 2>/dev/null || true") == image_id:
        log("образ на сервері вже цей — не завантажуємо")
        return
    with tempfile.TemporaryDirectory() as folder:
        archive = Path(folder) / "image.tar.gz"
        log("docker save + gzip…")
        with (
            subprocess.Popen(["docker", "save", image], stdout=subprocess.PIPE) as save,
            gzip.open(archive, "wb", 6) as out,
        ):
            assert save.stdout is not None
            shutil.copyfileobj(save.stdout, out, 1024 * 1024)
        if save.returncode != 0:
            fail("docker save не вдався")
        log(f"завантажуємо {archive.stat().st_size / 1024 / 1024:.0f} МБ…")
        server.put(archive, "/tmp/dndsheet-image.tar.gz")
    server.run("docker load -i /tmp/dndsheet-image.tar.gz && rm -f /tmp/dndsheet-image.tar.gz")
    server.write(f"{REMOTE}/IMAGE_ID", image_id)
    log("образ завантажено")


def wait_healthy(server: Server) -> None:
    for _ in range(45):
        status = server.run("docker inspect -f '{{.State.Health.Status}}' dndsheet-app 2>/dev/null || true")
        if status == "healthy":
            log("застосунок: healthy")
            return
        time.sleep(2)
    sys.stderr.write(server.run(f"cd {REMOTE} && docker compose -f compose.yml logs --tail 60 app", check=False))
    fail("застосунок не став healthy")


def wait_https(domain: str) -> None:
    url = f"https://{domain}/healthz"
    for _ in range(30):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 — https на власний домен
                if response.status == 200:
                    log(f"{url}: 200")
                    return
        except OSError:
            pass
        time.sleep(3)
    log(f"увага: {url} ще не відповідає (перший сертифікат? docker logs dndsheet-caddy)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", action="store_true", help="спершу docker compose build app")
    parser.add_argument("--image", default="dndsheet:local")
    args = parser.parse_args()

    ensure_unlocked()
    tfvars = read_tfvars(SECRETS / "terraform" / "terraform.tfvars")
    host, domain = tfvars.get("server_ip"), tfvars.get("domain")
    if not host or not domain:
        fail("у terraform.tfvars немає server_ip чи domain")

    key = SECRETS / "ssh" / "id_ed25519"
    if os.name != "nt":
        key.chmod(0o600)  # ssh відмовляється від ключа з ширшими правами
    server = Server(host, tfvars.get("ssh_user", "root"), tfvars.get("ssh_port", "22"), key)

    if args.build:
        log("docker compose build app…")
        if subprocess.run(["docker", "compose", "build", "app"], cwd=ROOT, check=False).returncode != 0:
            fail("збірка образу не вдалася")

    image_id = local_image_id(args.image)
    ship_image(server, args.image, image_id)

    caddyfile = (FILES / "Caddyfile.tftpl").read_text(encoding="utf-8")
    caddyfile = caddyfile.replace("${domain}", domain).replace("${server_ip}", host)
    server.write(f"{REMOTE}/compose.yml", (FILES / "compose.yml").read_text(encoding="utf-8"))
    server.write(f"{REMOTE}/Caddyfile", caddyfile)
    server.write(f"{REMOTE}/.env", (SECRETS / "prod.env").read_text(encoding="utf-8"), mode="600")

    log("docker compose up -d…")
    server.run(
        f"cd {REMOTE} && DNDSHEET_IMAGE={args.image} docker compose -f compose.yml up -d --remove-orphans"
        " && docker image prune -f >/dev/null"
        # Змінився лише Caddyfile — контейнер не перестворюється, тож конфіг перечитуємо явно.
        " && docker exec dndsheet-caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 || true"
    )
    wait_healthy(server)
    wait_https(domain)
    log(f"готово: https://{domain}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
