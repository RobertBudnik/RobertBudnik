"""
Aktualizuje sekcję projektów w README.md na podstawie PUBLICZNYCH repozytoriów.

Bierze tylko repozytoria publiczne, własne (bez forków), niezarchiwizowane,
i pomija repo profilowe (RobertBudnik/RobertBudnik).
Wstawia obrazek projects-*.svg (rysowany przez profile_assets.py) i linki do repo
między znacznikami:
    <!-- PROJECTS:START -->
    <!-- PROJECTS:END -->
"""

import json
import os
import re
import sys
import urllib.request
from urllib.error import HTTPError, URLError

USERNAME = os.environ.get("GH_USERNAME", "RobertBudnik")
README = os.environ.get("README_PATH", "README.md")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_PROJECTS = 6
API_BASE = "https://api.github.com"

START = "<!-- PROJECTS:START -->"
END = "<!-- PROJECTS:END -->"


def _headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-updater",
    }
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    return headers


def _get_json(url):
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except HTTPError as e:
        details = ""
        if e.code in (401, 403):
            remaining = e.headers.get("X-RateLimit-Remaining")
            reset = e.headers.get("X-RateLimit-Reset")
            if remaining is not None:
                details = f" (rate limit remaining: {remaining}, reset: {reset})"
        raise RuntimeError(f"GitHub API błąd {e.code} dla {url}{details}") from e
    except URLError as e:
        raise RuntimeError(f"GitHub API niedostępne dla {url}: {e}") from e


def fetch_public_repos():
    repos = []
    page = 1
    while True:
        url = (
            f"{API_BASE}/users/{USERNAME}/repos"
            f"?type=owner&sort=pushed&per_page=100&page={page}"
        )
        batch = _get_json(url)
        if not isinstance(batch, list):
            raise RuntimeError(f"Nieoczekiwana odpowiedź GitHub API dla {url}: {batch!r}")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    print(f"Pobrano repozytoria użytkownika {USERNAME}: {len(repos)}")
    return repos


def filter_repos(repos):
    out = []
    for r in repos:
        if r.get("private") or r.get("visibility", "public") != "public":
            continue
        if r.get("fork") or r.get("archived"):
            continue
        if r["name"].lower() == USERNAME.lower():
            continue
        out.append(r)
    return out


def pick(repos, limit=MAX_PROJECTS):
    return filter_repos(repos)[:limit]


PICTURE = """<p><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/projects-dark.svg">
  <img alt="{alt}" src="assets/projects-light.svg" width="100%">
</picture></p>"""


def render(repos):
    """Obrazek z listingiem (rysuje go scripts/profile_assets.py) i linki pod nim."""
    if not repos:
        alt = "Projekty: ls -la ~/projects – total 0, pierwsze projekty z cyberbezpieczeństwa są w przygotowaniu"
        return PICTURE.format(alt=alt)
    alt = "Projekty: " + "; ".join(
        f"{r['name']}: {(r.get('description') or '').replace(chr(34), chr(39))}" for r in repos
    )
    links = " · ".join(f"[{r['name']}]({r['html_url']})" for r in repos)
    return PICTURE.format(alt=alt) + "\n\n" + links


def main():
    if not os.path.exists(README):
        sys.exit(f"Nie znaleziono pliku README: {README}")

    with open(README, encoding="utf-8") as f:
        content = f.read()

    if START not in content or END not in content:
        sys.exit("Brak znaczników PROJECTS:START / PROJECTS:END w README.md")

    try:
        all_public = filter_repos(fetch_public_repos())
    except RuntimeError as e:
        sys.exit(str(e))
    selected = all_public[:MAX_PROJECTS]
    print(
        f"Po filtracji: {len(all_public)} publicznych repozytoriów "
        f"(wyświetlane: {len(selected)})"
    )

    block = f"{START}\n{render(selected)}\n{END}"
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, content, flags=re.S)

    if new != content:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)
        print("README zaktualizowane.")
    else:
        print("Bez zmian.")


if __name__ == "__main__":
    main()
