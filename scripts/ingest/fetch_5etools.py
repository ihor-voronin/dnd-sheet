"""Fetch one 5e.tools data file into content/raw/<dir>/.

5e.tools serves data/*.json only with a browser User-Agent plus a Referer from
the site; a bare urllib request gets 403. TLS here goes through Python's OpenSSL
(curl/schannel fails with SEC_E_NO_CREDENTIALS in this sandbox).
"""
import sys
import urllib.request
from pathlib import Path

def _repo_root() -> Path:
    """Walk up from this file until the directory that holds content/ as repo root."""
    for cand in Path(__file__).resolve().parents:
        if (cand / "content" / "raw").is_dir():
            return cand
    raise SystemExit("repo root with content/raw not found")


ROOT = _repo_root()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def fetch(rel_url, dest):
    req = urllib.request.Request(
        "https://5e.tools/data/" + rel_url,
        headers={"User-Agent": UA, "Referer": "https://5e.tools/adventure.html",
                 "Accept": "*/*"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return len(body)


def main():
    # pairs on the command line: <url-rel-path> <dest-rel-path>
    args = sys.argv[1:]
    for i in range(0, len(args), 2):
        url_rel, dest_rel = args[i], args[i + 1]
        dest = ROOT / dest_rel
        try:
            size = fetch(url_rel, dest)
            print(f"OK {url_rel} -> {dest_rel} ({size // 1024} KB)")
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {url_rel}: {exc}")


if __name__ == "__main__":
    main()
