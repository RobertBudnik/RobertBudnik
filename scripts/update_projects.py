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
import urllib.error
import urllib.request

USERNAME = os.environ.get("GH_USERNAME", "RobertBudnik")
README = os.environ.get("README_PATH", "README.md")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_PROJECTS = 6
PER_PAGE = 100

START = "<!-- PROJECTS:START -->"
END = "<!-- PROJECTS:END -->"


def log(msg):
    print(f"[update_projects] {msg}")


def _headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "robertbudnik-profile-sync",
    }
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    return headers


def _next_link(link_header):
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue
        if section.startswith("<") and ">" in section:
            return section[1:section.index(">")]
    return None


def _load_json(url):
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                raise RuntimeError(f"GitHub API zwróciło status HTTP {status} dla {url}")
            try:
                payload = json.load(resp)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"GitHub API zwróciło niepoprawny JSON dla {url}: {exc}") from exc
            if not isinstance(payload, list):
                raise RuntimeError(f"GitHub API zwróciło nieoczekiwany format danych dla {url}")
            return payload, _next_link(resp.headers.get("Link"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Błąd GitHub API HTTP {exc.code} podczas pobierania repozytoriów") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Błąd połączenia z GitHub API: {exc.reason}") from exc


def fetch_public_repos():
    url = (
        f"https://api.github.com/users/{USERNAME}/repos"
        f"?type=owner&sort=pushed&per_page={PER_PAGE}&page=1"
    )
    repos = []
    page = 1
    while url:
        page_repos, url = _load_json(url)
        repos.extend(page_repos)
        log(f"Pobrano stronę {page}: {len(page_repos)} repozytoriów (łącznie {len(repos)})")
        page += 1
    return repos


def filter_repos(repos):
    selected = []
    rejected = 0
    profile_full_name = f"{USERNAME}/{USERNAME}".lower()

    for r in repos:
        owner_login = ((r.get("owner") or {}).get("login") or "").lower()
        full_name = (r.get("full_name") or "").lower()
        name = (r.get("name") or "").lower()

        if r.get("private") or r.get("visibility", "public") != "public":
            rejected += 1
            continue
        if owner_login and owner_login != USERNAME.lower():
            rejected += 1
            continue
        if r.get("fork") or r.get("archived"):
            rejected += 1
            continue
        if full_name == profile_full_name or name == USERNAME.lower():
            rejected += 1
            continue

        selected.append(r)

    return selected[:MAX_PROJECTS], {
        "fetched": len(repos),
        "rejected": rejected,
        "selected": min(len(selected), MAX_PROJECTS),
        "eligible": len(selected),
    }


def pick(repos):
    selected, _ = filter_repos(repos)
    return selected


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
    with open(README, encoding="utf-8") as f:
        content = f.read()

    if START not in content or END not in content:
        sys.exit("Brak znaczników PROJECTS:START / PROJECTS:END w README.md")

    try:
        fetched = fetch_public_repos()
        repos, stats = filter_repos(fetched)
    except RuntimeError as exc:
        sys.exit(f"Synchronizacja projektów nieudana: {exc}")

    log(
        "Repozytoria: "
        f"pobrane={stats['fetched']}, odrzucone={stats['rejected']}, "
        f"kwalifikujące={stats['eligible']}, wybrane={stats['selected']}"
    )

    block = f"{START}\n{render(repos)}\n{END}"
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, content, flags=re.S)

    if new != content:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)
        log("README zaktualizowane.")
    else:
        log("Bez zmian w README.")


if __name__ == "__main__":
    main()
