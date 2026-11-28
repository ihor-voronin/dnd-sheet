#!/usr/bin/env python3
"""Deploy the app to the VPS — the same way from Windows and from GitHub Actions (Linux).

Infrastructure (DNS in Cloudflare, Docker, firewall, swap, backups) is set up by Terraform
(`deploy/terraform`, rarely and by hand). This script covers what changes with every
commit: the image, compose, Caddyfile, .env. There's no state like Terraform's here:
every run brings the server to what's in the repository, so CI doesn't have to
commit anything back.

    python scripts/deploy_app.py              # the dndsheet:local image is already built
    python scripts/deploy_app.py --build      # docker compose build app first

Steps:
1. the secrets are unlocked (deploy/secrets isn't git-crypt ciphertext);
2. the image: if the server already has the same one (the id in /opt/dndsheet/IMAGE_ID) — skip,
   otherwise `docker save` + gzip → scp → `docker load`;
3. compose.yml, Caddyfile (the domain from terraform.tfvars), .env from prod.env;
4. `docker compose up -d`, wait for healthy and for HTTPS through Caddy.
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
    print(f"[deploy] {message}", flush=True)  # noqa: T201 — a console script


def fail(message: str) -> None:
    sys.stderr.write(f"[deploy] error: {message}\n")
    sys.exit(1)


def read_tfvars(path: Path) -> dict[str, str]:
    """Simple `key = "value"` lines from terraform.tfvars."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r'\s*([a-z_]+)\s*=\s*"?([^"#]*?)"?\s*(#.*)?$', line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def ensure_unlocked() -> None:
    for path in (SECRETS / "prod.env", SECRETS / "ssh" / "id_ed25519", SECRETS / "terraform" / "terraform.tfvars"):
        if not path.exists():
            fail(f"{path.relative_to(ROOT)} is missing")
        if path.read_bytes()[: len(MAGIC)] == MAGIC:
            fail(f"{path.relative_to(ROOT)} is encrypted — run git-crypt unlock first (docs/deploy.md)")


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
            fail(f"on the server: {command}\n{result.stderr.decode('utf-8', 'replace')}")
        return result.stdout.decode("utf-8", "replace").strip()

    def put(self, local: Path, remote: str) -> None:
        result = subprocess.run(
            ["scp", *self.common, "-P", self.port, str(local), f"{self.target}:{remote}"], check=False
        )
        if result.returncode != 0:
            fail(f"scp {local.name} failed")

    def write(self, remote: str, content: str, mode: str = "644") -> None:
        self.run(f"cat > {remote} && chmod {mode} {remote}", stdin=content.replace("\r\n", "\n").encode("utf-8"))


def local_image_id(image: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image], capture_output=True, check=False
    )
    if result.returncode != 0:
        fail(f"no {image} image — build it: docker compose build app (or --build)")
    return result.stdout.decode().strip()


def ship_image(server: Server, image: str, image_id: str) -> None:
    if server.run(f"cat {REMOTE}/IMAGE_ID 2>/dev/null || true") == image_id:
        log("the server already has this image — not uploading")
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
            fail("docker save failed")
        log(f"uploading {archive.stat().st_size / 1024 / 1024:.0f} MB…")
        server.put(archive, "/tmp/dndsheet-image.tar.gz")
    server.run("docker load -i /tmp/dndsheet-image.tar.gz && rm -f /tmp/dndsheet-image.tar.gz")
    server.write(f"{REMOTE}/IMAGE_ID", image_id)
    log("image uploaded")


def wait_healthy(server: Server) -> None:
    for _ in range(45):
        status = server.run("docker inspect -f '{{.State.Health.Status}}' dndsheet-app 2>/dev/null || true")
        if status == "healthy":
            log("app: healthy")
            return
        time.sleep(2)
    sys.stderr.write(server.run(f"cd {REMOTE} && docker compose -f compose.yml logs --tail 60 app", check=False))
    fail("the app did not become healthy")


def wait_https(domain: str) -> None:
    url = f"https://{domain}/healthz"
    for _ in range(30):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 — https to our own domain
                if response.status == 200:
                    log(f"{url}: 200")
                    return
        except OSError:
            pass
        time.sleep(3)
    log(f"warning: {url} isn't responding yet (first certificate? docker logs dndsheet-caddy)")


def app_env(prod_env: str, domain: str) -> str:
    """prod.env + the site's public address (MCP and OAuth need it), unless prod.env sets its own."""
    if any(line.strip().startswith("DNDSHEET_PUBLIC_URL=") for line in prod_env.splitlines()):
        return prod_env
    return prod_env.rstrip("\n") + f"\nDNDSHEET_PUBLIC_URL=https://{domain}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", action="store_true", help="docker compose build app first")
    parser.add_argument("--image", default="dndsheet:local")
    args = parser.parse_args()

    ensure_unlocked()
    tfvars = read_tfvars(SECRETS / "terraform" / "terraform.tfvars")
    host, domain = tfvars.get("server_ip"), tfvars.get("domain")
    if not host or not domain:
        fail("terraform.tfvars has no server_ip or domain")

    key = SECRETS / "ssh" / "id_ed25519"
    if os.name != "nt":
        key.chmod(0o600)  # ssh refuses a key with wider permissions
    server = Server(host, tfvars.get("ssh_user", "root"), tfvars.get("ssh_port", "22"), key)

    if args.build:
        log("docker compose build app…")
        if subprocess.run(["docker", "compose", "build", "app"], cwd=ROOT, check=False).returncode != 0:
            fail("the image build failed")

    image_id = local_image_id(args.image)
    ship_image(server, args.image, image_id)

    caddyfile = (FILES / "Caddyfile.tftpl").read_text(encoding="utf-8")
    caddyfile = caddyfile.replace("${domain}", domain).replace("${server_ip}", host)
    server.write(f"{REMOTE}/compose.yml", (FILES / "compose.yml").read_text(encoding="utf-8"))
    server.write(f"{REMOTE}/Caddyfile", caddyfile)
    server.write(f"{REMOTE}/.env", app_env((SECRETS / "prod.env").read_text(encoding="utf-8"), domain), mode="600")

    log("docker compose up -d…")
    server.run(
        f"cd {REMOTE} && DNDSHEET_IMAGE={args.image} docker compose -f compose.yml up -d --remove-orphans"
        " && docker image prune -f >/dev/null"
        # If only the Caddyfile changed, the container isn't recreated, so reload the config explicitly.
        " && docker exec dndsheet-caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 || true"
    )
    wait_healthy(server)
    wait_https(domain)
    log(f"done: https://{domain}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
