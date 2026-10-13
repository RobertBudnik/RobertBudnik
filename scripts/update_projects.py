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

USERNAME = os.environ.get("GH_USERNAME", "RobertBudnik")
README = os.environ.get("README_PATH", "README.md")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_PROJECTS = 6

START = "<!-- PROJECTS:START -->"
END = "<!-- PROJECTS:END -->"

def fetch_public_repos():
    url = f"https://api.github.com/users/{USERNAME}/repos?type=owner&sort=pushed&per_page=100"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def pick(repos):
    out = []
    for r in repos:
        if r.get("private") or r.get("visibility", "public") != "public":
            continue
        if r.get("fork") or r.get("archived"):
            continue
        if r["name"].lower() == USERNAME.lower():
            continue
        out.append(r)
    return out[:MAX_PROJECTS]


PICTURE = """<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/projects-dark.svg">
  <img alt="{alt}" src="assets/projects-light.svg" width="100%">
</picture>"""


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

    block = f"{START}\n{render(pick(fetch_public_repos()))}\n{END}"
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, content, flags=re.S)

    if new != content:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)
        print("README zaktualizowane.")
    else:
        print("Bez zmian.")


if __name__ == "__main__":
    main()
