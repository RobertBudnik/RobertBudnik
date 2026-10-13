"""
Aktualizuje sekcję projektów w README.md na podstawie PUBLICZNYCH repozytoriów.

Bierze tylko repozytoria publiczne, własne (bez forków), niezarchiwizowane,
i pomija repo profilowe (RobertBudnik/RobertBudnik).
Podmienia treść między znacznikami:
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

CARD = (
    "https://github-readme-stats.shion.dev/api/pin/"
    "?username={user}&repo={repo}&hide_border=true&bg_color=161b22"
    "&title_color=e6edf3&text_color=8b949e&icon_color=8b949e"
)


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


def render(repos):
    if not repos:
        return (
            "```text\n"
            "> ls ~/projects\n"
            "  // w budowie — pierwsze projekty z cyberbezpieczeństwa już niedługo\n"
            "```"
        )
    cards = []
    for r in repos:
        img = CARD.format(user=USERNAME, repo=r["name"])
        cards.append(
            f'<a href="{r["html_url"]}"><img width="49%" src="{img}" alt="{r["name"]}"/></a>'
        )
    return '<p align="center">\n  ' + "\n  ".join(cards) + "\n</p>"


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
