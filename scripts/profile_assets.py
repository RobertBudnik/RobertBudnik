"""
Generuje grafiki SVG do README (koncept „ssh / OSI”), każdą w wersji -dark i -light:

    hero      – okno ssh: whoami, imię, radar sieci, pasek z danymi
    osi       – „Stos, który rozbieram”: 7 warstw modelu OSI ze statusem nauki
    tracks    – trzy kafle: Linux, Python, Security
    tools     – siatka narzędzi z monogramami
    projects  – listing `ls -la ~/projects` z publicznych repozytoriów
    certs     – certyfikaty i kursy z data/certs.json (aktualizuje też alt w README)
    activity  – fala kontrybucji z ostatnich 365 dni
    contact   – `ping robert` z dużym adresem e-mail

GitHub nie wczytuje czcionek w SVG, więc cały tekst jest zamieniany na ścieżki
(Geologica i JetBrains Mono, wycinki w assets/fonts).

Użycie:
    python scripts/profile_assets.py                              # wszystko, prawdziwe dane
    python scripts/profile_assets.py --static                     # bez projektów i aktywności
    python scripts/profile_assets.py --sample --out /tmp/podglad  # przykładowe dane (tylko podgląd)
"""

import argparse
import datetime as dt
import json
import math
import os
import random
import re
import sys
import urllib.request
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
CERTS = ROOT / "data" / "certs.json"
USERNAME = os.environ.get("GH_USERNAME", "RobertBudnik")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# --- dane ------------------------------------------------------------------

# Status: "UCZĘ SIĘ" (wiersz aktywny) albo "NASTĘPNE".
OSI_LAYERS = [
    ("L7", "Aplikacji", "DNS · DHCP · HTTP", "UCZĘ SIĘ"),
    ("L6", "Prezentacji", "kodowanie · szyfrowanie TLS", "NASTĘPNE"),
    ("L5", "Sesji", "sesje · uwierzytelnianie", "NASTĘPNE"),
    ("L4", "Transportowa", "TCP / UDP · porty · analiza ruchu", "UCZĘ SIĘ"),
    ("L3", "Sieciowa", "adresacja IP · podsieci · routing", "UCZĘ SIĘ"),
    ("L2", "Łącza danych", "MAC · ARP · VLAN", "NASTĘPNE"),
    ("L1", "Fizyczna", "media · okablowanie", "NASTĘPNE"),
]
ACTIVE = "UCZĘ SIĘ"

TRACKS = [
    ("$ uname -s", "Linux", "Terminal, uprawnienia, procesy i usługi, skrypty Bash."),
    (">>> import", "Python", "Automatyzacja, skrypty narzędziowe, praca z API."),
    ("# harden", "Security", "Bezpieczeństwo sieci, hardening systemów, narzędzia do analizy."),
]

TOOLS = [("Py", "Python"), ("C+", "C++"), ("$_", "Bash"), ("Lx", "Linux"), ("Gt", "Git"), ("VS", "VS Code")]

HERO_FACTS = [
    ("LOKALIZACJA", "Poznań, PL"),
    ("STUDIA", "Informatyka · CDV"),
    ("KIERUNEK", "Cybersecurity"),
    ("STATUS", "Szukam stażu"),
]
TAGLINE = "Uczę się bronić sieci i systemów, a każdy krok dokumentuję w projektach."
EMAIL_USER, EMAIL_DOMAIN = "robertbudnik30", "@gmail.com"
PING = "64 bytes from robert: icmp_seq=1 ttl=64 · szukam stażu w cyberbezpieczeństwie i sieciach"

MONTHS = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]

# --- motywy ----------------------------------------------------------------

THEMES = {
    "dark": {
        "bg": "#07080a", "card": "#0f1114", "deep": "#0b0d10", "line": "#23272f", "soft": "#1c2027",
        "text": "#e6e8eb", "strong": "#f2f3f5", "muted": "#8a919c", "dim": "#7d848f",
        "accent": "#3fe0a6", "accent_text": "#3fe0a6",
        "node_line": "#3a404a", "dot": "#2b313a", "dash": "#343a44",
        "active_bg": "#14181d", "active_line": "#2b313a", "bar": "#5c636e",
    },
    "light": {
        "bg": "#f4f5f7", "card": "#ffffff", "deep": "#f7f8fa", "line": "#dfe2e7", "soft": "#e9ebef",
        "text": "#0f1114", "strong": "#07080a", "muted": "#5b626d", "dim": "#656c77",
        # #0d9f6e do grafiki, ciemniejszy odcień do drobnego tekstu (kontrast ≥ 4.5:1)
        "accent": "#0d9f6e", "accent_text": "#087a54",
        "node_line": "#c3c8cf", "dot": "#d5d9df", "dash": "#c3c8cf",
        "active_bg": "#f2f4f6", "active_line": "#d5d9df", "bar": "#a3a9b2",
    },
}

W = 900
PAD = 32
RADIUS = 22


# --- tekst jako ścieżki ----------------------------------------------------

def fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class Face:
    def __init__(self, *files):
        self.fonts = [TTFont(FONTS / f) for f in files]
        self.upm = self.fonts[0]["head"].unitsPerEm
        self.cmaps = [f.getBestCmap() for f in self.fonts]
        self.glyphsets = [f.getGlyphSet() for f in self.fonts]

    def glyph(self, ch):
        for cmap, gs in zip(self.cmaps, self.glyphsets):
            if ord(ch) in cmap:
                return gs[cmap[ord(ch)]], gs
        return self.glyph("?")

    def width(self, text, size, tracking=0.0):
        scale = size / self.upm
        return sum(self.glyph(c)[0].width * scale for c in text) + tracking * size * max(len(text) - 1, 0)

    def path(self, text, size, x, y, fill, tracking=0.0, anchor="start", extra=""):
        if anchor == "middle":
            x -= self.width(text, size, tracking) / 2
        elif anchor == "end":
            x -= self.width(text, size, tracking)
        scale = size / self.upm
        parts = []
        for ch in text:
            g, gs = self.glyph(ch)
            pen = SVGPathPen(gs, ntos=fmt)
            g.draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
            if pen.getCommands():
                parts.append(pen.getCommands())
            x += g.width * scale + tracking * size
        if not parts:
            return ""
        return f'<path fill="{fill}"{extra} d="{" ".join(parts)}"/>'


def geo(weight):
    return Face(f"geologica-{weight}-latin.ttf", f"geologica-{weight}-latin-ext.ttf")


G900, G600, G400, G300 = geo(900), geo(600), geo(400), geo(300)
MONO, MONO_M = Face("jetbrainsmono-400.ttf"), Face("jetbrainsmono-500.ttf")


def wrap(face, text, size, max_width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if line and face.width(test, size) > max_width:
            lines.append(line)
            line = word
        else:
            line = test
    return lines + ([line] if line else [])


def clip(face, text, size, max_width):
    if face.width(text, size) <= max_width:
        return text
    while text and face.width(text + "…", size) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def fit(face, text, size, max_width, tracking=0.0):
    while face.width(text, size, tracking) > max_width and size > 8:
        size -= 1
    return size


# --- elementy wspólne ------------------------------------------------------

def svg(height, label, body, style=""):
    style = f"<style>{style}</style>\n" if style else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" '
        f'role="img" aria-label="{esc(label)}">\n<title>{esc(label)}</title>\n{style}{body}\n</svg>\n'
    )


def card(height, t, fill=None, x=0, w=W):
    return (f'<rect x="{x + 0.5}" y="0.5" width="{w - 1}" height="{height - 1}" rx="{RADIUS}" '
            f'fill="{fill or t["card"]}" stroke="{t["line"]}"/>')


def title(t, text, right=None):
    out = [G900.path(text, 26, PAD, 58, t["strong"], tracking=-0.02)]
    if right:
        out.append(MONO.path(right, 13, W - PAD, 56, t["dim"], anchor="end"))
    return out


def prompt(t, cmd, size, x, y):
    """`❯ polecenie` – strzałka w akcencie, polecenie w muted."""
    return [MONO_M.path("❯", size, x, y, t["accent"]),
            MONO.path(cmd, size, x + MONO.width("❯ ", size), y, t["muted"])]


# --- grafiki ---------------------------------------------------------------

def hero(t):
    h = 448
    cx, cy, r = 730, 206, 132
    body = [
        '<defs><clipPath id="c"><rect x="0.5" y="0.5" width="899" height="447" rx="22"/></clipPath>'
        f'<radialGradient id="g" cx="{cx}" cy="{cy}" r="{r}" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{t["accent"]}" stop-opacity="0.35"/>'
        f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0.12"/></radialGradient></defs>',
        card(h, t, fill=t["bg"]),
        '<g clip-path="url(#c)">',
        f'<rect width="{W}" height="44" fill="{t["card"]}"/>',
        f'<rect y="44" width="{W}" height="1" fill="{t["soft"]}"/>',
        "</g>",
    ]
    body += [f'<circle cx="{x}" cy="22" r="5" fill="{t["dot"]}"/>' for x in (24, 42, 60)]
    body.append(MONO.path("robert@budnik — ssh — 10.0.0.1", 13, W / 2, 27, t["dim"], anchor="middle"))
    body.append(MONO.path("online", 13, W - 24, 27, t["accent_text"], anchor="end"))
    body.append(f'<circle cx="{fmt(W - 24 - MONO.width("online", 13) - 11)}" cy="22.5" r="4" fill="{t["accent"]}"/>')

    # lewa kolumna
    body += prompt(t, "whoami", 15, 40, 98)
    size, track = 84, -0.035
    body.append(G900.path("ROBERT", size, 37, 180, t["strong"], tracking=track))
    body.append(G900.path("BUDNIK", size, 37, 180 + size * 0.9, t["strong"], tracking=track))
    cur_x = 37 + G900.width("BUDNIK", size, track) + 12
    base = 180 + size * 0.9
    body.append(f'<rect class="cursor" x="{fmt(cur_x)}" y="{fmt(base - 61)}" width="30" height="61" fill="{t["accent"]}"/>')
    for i, line in enumerate(wrap(G300, TAGLINE, 19, 440)):
        body.append(G300.path(line, 19, 40, 300 + i * 26, t["muted"]))

    # radar
    for rr in (r / 4, r / 2, r * 3 / 4, r):
        body.append(f'<circle cx="{cx}" cy="{cy}" r="{fmt(rr)}" fill="none" stroke="{t["line"]}"/>')
    body.append(f'<path d="M{cx - r} {cy}H{cx + r}M{cx} {cy - r}V{cy + r}" stroke="{t["line"]}"/>')
    a0, a1 = math.radians(-60), 0.0
    sweep = (f'M{cx} {cy}L{fmt(cx + r * math.cos(a0))} {fmt(cy + r * math.sin(a0))}'
             f'A{r} {r} 0 0 1 {fmt(cx + r * math.cos(a1))} {fmt(cy + r * math.sin(a1))}Z')
    body.append(f'<g class="sweep"><path d="{sweep}" fill="url(#g)" opacity="0.9"/>'
                f'<path d="M{cx} {cy}H{cx + r}" stroke="{t["accent"]}" stroke-opacity="0.6"/></g>')
    nodes = [(cx - 82, cy - 64), (cx + 34, cy - 96), (cx + 92, cy - 18), (cx + 54, cy + 76), (cx - 70, cy + 58)]
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2)]
    for a, b in edges:
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        body.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{t["node_line"]}"/>')
    for i, (x, y) in enumerate(nodes):
        if i == 2:
            continue
        body.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{t["bg"]}" stroke="{t["muted"]}" stroke-width="1.5"/>')
    ax, ay = nodes[2]
    body.append(f'<circle class="pulse" cx="{ax}" cy="{ay}" r="26" fill="none" stroke="{t["accent"]}" stroke-width="1.5"/>')
    body.append(f'<circle cx="{ax}" cy="{ay}" r="5" fill="{t["accent"]}"/>')
    body.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="{t["strong"]}"/>')
    body.append(MONO.path("10.0.0.0/24 · 6 hosts", 12, W - 28, 362, t["dim"], anchor="end"))

    # dolny pasek
    top = 374
    body.append(f'<rect y="{top}" width="{W}" height="1" fill="{t["soft"]}" clip-path="url(#c)"/>')
    cw = W / len(HERO_FACTS)
    for i, (label, value) in enumerate(HERO_FACTS):
        x = i * cw
        if i:
            body.append(f'<rect x="{fmt(x)}" y="{top}" width="1" height="{h - top}" fill="{t["soft"]}"/>')
        body.append(MONO.path(label, 12, x + 24, top + 28, t["dim"], tracking=0.12))
        body.append(G600.path(value, 16, x + 24, top + 54, t["text"]))

    style = (
        f".sweep{{transform-origin:{cx}px {cy}px;animation:spin 6s linear infinite}}"
        ".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2.4s ease-out infinite}"
        ".cursor{animation:blink 1.1s steps(1) infinite}"
        "@keyframes spin{to{transform:rotate(360deg)}}"
        "@keyframes pulse{from{transform:scale(.23);opacity:.9}to{transform:scale(1);opacity:0}}"
        "@keyframes blink{50%{opacity:0}}"
        "@media (prefers-reduced-motion:reduce){.sweep,.pulse,.cursor{animation:none}.pulse{opacity:0}}"
    )
    label = (f"robert@budnik — ssh — 10.0.0.1 · online. ❯ whoami: Robert Budnik. {TAGLINE} "
             + " · ".join(f"{k.capitalize()}: {v}" for k, v in HERO_FACTS))
    return svg(h, label, "\n".join(body), style)


def osi(t):
    row_h, gap, top = 46, 8, 84
    h = top + len(OSI_LAYERS) * (row_h + gap) - gap + 26
    body = [card(h, t)] + title(t, "Stos, który rozbieram", "model OSI · warstwa po warstwie")
    for i, (layer, name, topics, status) in enumerate(OSI_LAYERS):
        y = top + i * (row_h + gap)
        on = status == ACTIVE
        fill, stroke = (t["active_bg"], t["active_line"]) if on else ("none", t["soft"])
        body.append(f'<rect x="24.5" y="{y + 0.5}" width="{W - 49}" height="{row_h - 1}" rx="12" fill="{fill}" stroke="{stroke}"/>')
        base = y + row_h / 2 + 5
        body.append(MONO_M.path(layer, 14, 46, base, t["accent_text"] if on else t["dim"]))
        body.append(G600.path(name, 16, 98, base + 0.5, t["strong"] if on else t["dim"]))
        body.append(MONO.path(topics, 13, 290, base, t["muted"] if on else t["dim"]))
        pw = MONO.width(status, 12, 0.08) + 26
        px = W - 24 - 14 - pw
        body.append(f'<rect x="{fmt(px)}" y="{y + 11.5}" width="{fmt(pw)}" height="23" rx="11.5" fill="none" '
                    f'stroke="{t["accent"] if on else t["line"]}"/>')
        body.append(MONO.path(status, 12, px + 13, y + 27.5, t["accent_text"] if on else t["dim"], tracking=0.08))
    label = "Stos, który rozbieram (model OSI): " + "; ".join(f"{l} {n} – {tp} – {s.lower()}" for l, n, tp, s in OSI_LAYERS)
    return svg(h, label, "\n".join(body))


def tracks(t):
    gap = 16
    tw = (W - 2 * gap) / 3
    inner = tw - 48
    descs = [wrap(G300, d, 15, inner) for _, _, d in TRACKS]
    h = 112 + max(len(d) for d in descs) * 22 + 10
    body = []
    for i, ((cmd, name, _), lines) in enumerate(zip(TRACKS, descs)):
        x = i * (tw + gap)
        body.append(card(h, t, x=x, w=tw))
        body.append(MONO.path(cmd, 13, x + 24, 42, t["accent_text"]))
        body.append(G900.path(name, 26, x + 23, 82, t["strong"], tracking=-0.02))
        for j, line in enumerate(lines):
            body.append(G300.path(line, 15, x + 24, 112 + j * 22, t["muted"]))
    label = " · ".join(f"{c} → {n}: {d}" for c, n, d in TRACKS)
    return svg(h, label, "\n".join(body))


def tools(t):
    gap, top, th = 12, 84, 104
    tw = (W - 2 * 24 - 5 * gap) / 6
    h = top + th + 24
    body = [card(h, t)] + title(t, "Narzędzia")
    for i, (mono, name) in enumerate(TOOLS):
        x = 24 + i * (tw + gap)
        body.append(f'<rect x="{fmt(x + 0.5)}" y="{top + 0.5}" width="{fmt(tw - 1)}" height="{th - 1}" rx="14" fill="{t["deep"]}" stroke="{t["line"]}"/>')
        body.append(f'<rect x="{fmt(x + 16.5)}" y="{top + 16.5}" width="39" height="39" rx="9" fill="{t["card"]}" stroke="{t["line"]}"/>')
        body.append(MONO_M.path(mono, 14, x + 36, top + 41, t["text"], anchor="middle"))
        body.append(G600.path(name, 14, x + 16, top + 84, t["text"]))
    return svg(h, "Narzędzia: " + ", ".join(n for _, n in TOOLS), "\n".join(body))


def projects(t, repos, total=None):
    size, lh = 14, 26
    cw = MONO.width("x", size)
    cols = int((W - 2 * 24 - 2 * 24) / cw)
    lines = []  # lista segmentów (tekst, kolor)
    lines.append(None)  # prompt
    total_count = len(repos) if total is None else total
    lines.append([(f"total {total_count}", t["dim"])])
    if not repos:
        lines.append([("# pierwsze projekty z cyberbezpieczeństwa są w przygotowaniu", t["dim"])])
    for r in repos:
        name = (r["name"] + "/")[:24]
        tech = ", ".join(dict.fromkeys(x for x in [r.get("language")] + list(r.get("topics") or [])[:2] if x)) or "—"
        tech = tech[:18] if len(tech) <= 18 else tech[:17] + "…"
        name_w = max(min(max(len(x["name"]) + 1 for x in repos), 24), 8)
        left = f"drwxr-xr-x  robert  "
        desc_w = cols - len(left) - name_w - 2 - 2 - len(tech)
        desc = (r.get("description") or "—").replace("\n", " ")
        desc = desc if len(desc) <= desc_w else desc[: max(desc_w - 1, 0)].rstrip() + "…"
        lines.append([(left, t["dim"]), (name.ljust(name_w + 2), t["accent_text"]),
                      (desc.ljust(desc_w + 2), t["text"]), (tech, t["dim"])])
    lines.append("cursor")

    top = 84
    term_h = 24 + len(lines) * lh + 10
    h = top + term_h + 24
    body = [card(h, t)] + title(t, "Projekty", "~/projects")
    body.append(f'<rect x="24.5" y="{top + 0.5}" width="{W - 49}" height="{term_h - 1}" rx="14" fill="{t["deep"]}" stroke="{t["soft"]}"/>')
    x0 = 48
    for i, segs in enumerate(lines):
        y = top + 24 + (i + 1) * lh - 8
        if segs is None:
            body += prompt(t, "ls -la ~/projects", size, x0, y)
        elif segs == "cursor":
            body.append(MONO_M.path("❯", size, x0, y, t["accent"]))
            body.append(f'<rect class="cursor" x="{fmt(x0 + 2 * cw)}" y="{y - 13}" width="{fmt(cw)}" height="17" fill="{t["accent"]}"/>')
        else:
            col = 0
            for text, color in segs:
                body.append(MONO.path(text.rstrip(), size, x0 + col * cw, y, color))
                col += len(text)
    label = "Projekty: ls -la ~/projects – " + (
        "; ".join(f"{r['name']}: {r.get('description') or ''}" for r in repos) if repos
        else "total 0, pierwsze projekty z cyberbezpieczeństwa są w przygotowaniu")
    style = ".cursor{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}" \
            "@media (prefers-reduced-motion:reduce){.cursor{animation:none}}"
    return svg(h, label, "\n".join(body), style)


def certs(t, items):
    gap, top, sh = 12, 84, 104
    sw = (W - 2 * 24 - 2 * gap) / 3
    slots = items + [None] * (max(3, math.ceil(len(items) / 3) * 3) - len(items))
    rows = math.ceil(len(slots) / 3)
    h = top + rows * (sh + gap) - gap + 24
    body = [card(h, t)] + title(t, "Certyfikaty i kursy", "~/certs")
    for i, item in enumerate(slots):
        x = 24 + (i % 3) * (sw + gap)
        y = top + (i // 3) * (sh + gap)
        no = f"SLOT {i + 1:02d}"
        if item is None:
            body.append(f'<rect x="{fmt(x + 0.5)}" y="{y + 0.5}" width="{fmt(sw - 1)}" height="{sh - 1}" rx="14" fill="none" '
                        f'stroke="{t["dash"]}" stroke-dasharray="6 5"/>')
            body.append(MONO.path(no, 12, x + 20, y + 30, t["dim"], tracking=0.08))
            body.append(G600.path("[pierwszy certyfikat]" if i == 0 else "[kolejny kurs]", 16, x + 20, y + 60, t["muted"]))
            body.append(MONO.path("[wydawca · rok]", 12, x + 20, y + 84, t["dim"]))
            continue
        done = str(item.get("status", "")).strip().lower() == "ukończony"
        body.append(f'<rect x="{fmt(x + 0.5)}" y="{y + 0.5}" width="{fmt(sw - 1)}" height="{sh - 1}" rx="14" fill="{t["deep"]}" stroke="{t["line"]}"/>')
        body.append(MONO.path(no, 12, x + 20, y + 30, t["dim"], tracking=0.08))
        if done:
            body.append(MONO_M.path("✓", 16, x + sw - 20, y + 31, t["accent_text"], anchor="end"))
        else:
            body.append(MONO.path(str(item.get("status") or "w trakcie"), 12, x + sw - 20, y + 30, t["dim"], anchor="end"))
        body.append(G600.path(clip(G600, str(item.get("name", "")), 16, sw - 40), 16, x + 20, y + 60, t["strong"]))
        meta = " · ".join(str(v) for v in (item.get("issuer"), item.get("year")) if v)
        body.append(MONO.path(clip(MONO, meta, 12, sw - 40), 12, x + 20, y + 84, t["dim"]))
    return svg(h, certs_alt(items), "\n".join(body))


def certs_alt(items):
    """Opis grafiki certyfikatów – trafia do SVG i do atrybutu alt w README."""
    if not items:
        return "Certyfikaty i kursy: lista w przygotowaniu (3 puste sloty)"
    parts = []
    for c in items:
        meta = ", ".join(str(v) for v in (c.get("issuer"), c.get("year")) if v)
        status = c.get("status") or "w trakcie"
        parts.append(f"{c.get('name', '')}" + (f" ({meta})" if meta else "") + f" – {status}")
    return "Certyfikaty i kursy: " + "; ".join(parts)


def update_readme_certs_alt(items):
    """Podmienia alt obrazka certs-light.svg w README na aktualną listę."""
    readme = ROOT / "README.md"
    if not readme.exists():
        return
    content = readme.read_text(encoding="utf-8")
    new = re.sub(r'<img alt="[^"]*" src="assets/certs-light\.svg"',
                 lambda _: f'<img alt="{esc(certs_alt(items))}" src="assets/certs-light.svg"', content)
    if new != content:
        readme.write_text(new, encoding="utf-8")
        print(f"zapisano {readme} (alt certyfikatów)")


def activity(t, days):
    counts = [c for _, c in days]
    total, active, peak = sum(counts), sum(1 for c in counts if c), max(counts) if counts else 0
    rec_i = max(range(len(counts)), key=lambda i: (counts[i], i)) if peak else None

    def date_pl(d):
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"

    top, h = 84, 388
    body = [card(h, t)] + title(t, "Aktywność", "ostatnie 365 dni")
    body.append(f'<rect x="24.5" y="{top + 0.5}" width="{W - 49}" height="{h - top - 24 - 1}" rx="14" fill="{t["deep"]}" stroke="{t["soft"]}"/>')
    stats = [(str(total), "kontrybucje w ostatnim roku"),
             (str(peak), f"rekordowy dzień · {date_pl(days[rec_i][0])}" if peak else "rekordowy dzień"),
             (str(active), "aktywne dni")]
    x = 52
    for num, lab in stats:
        body.append(G900.path(num, 50, x - 2, top + 72, t["strong"], tracking=-0.03))
        body.append(G300.path(lab, 14, x, top + 96, t["muted"]))
        x += max(G900.width(num, 50, -0.03), G300.width(lab, 14)) + 56

    left, right = 52, W - 52
    mid, amp = top + 192, 44
    for gy in (mid - amp, mid, mid + amp):
        body.append(f'<rect x="{left}" y="{gy}" width="{right - left}" height="1" fill="{t["soft"]}"/>')
    step = (right - left) / max(len(days), 1)
    bw = max(step * 0.6, 1)
    for i, c in enumerate(counts):
        if not c:
            continue
        x = left + i * step + (step - bw) / 2
        hh = max(3.0, c / peak * amp * 2)
        color = t["accent"] if i == rec_i else t["bar"]
        body.append(f'<rect x="{fmt(x)}" y="{fmt(mid - hh / 2)}" width="{fmt(bw)}" height="{fmt(hh)}" rx="{fmt(bw / 2)}" fill="{color}"/>')
    if rec_i is not None:
        rx = left + rec_i * step + step / 2
        lab = f"rekord: {peak}"
        lw = MONO.width(lab, 12)
        lx = min(max(rx - lw / 2, left), right - lw)
        body.append(MONO.path(lab, 12, lx, mid - amp - 10, t["accent_text"]))
    for i, (d, _) in enumerate(days):
        if d.day == 1:
            x = left + i * step
            if x < right - 24:
                body.append(MONO.path(MONTHS[d.month - 1], 12, x, mid + amp + 30, t["dim"]))
    label = (f"Aktywność, ostatnie 365 dni: {total} kontrybucji, rekordowy dzień {peak}"
             + (f" ({date_pl(days[rec_i][0])})" if peak else "") + f", {active} aktywnych dni")
    return svg(h, label, "\n".join(body))


def contact(t):
    h = 214
    body = [card(h, t)]
    body += prompt(t, "ping robert", 15, PAD, 54)
    size = fit(G900, EMAIL_USER + EMAIL_DOMAIN, 60, W - 2 * PAD, -0.035)
    body.append(G900.path(EMAIL_USER, size, PAD - 2, 132, t["strong"], tracking=-0.035))
    dx = PAD - 2 + G900.width(EMAIL_USER, size, -0.035) - 0.035 * size
    body.append(G900.path(EMAIL_DOMAIN, size, dx, 132, t["dim"], tracking=-0.035))
    ping_size = fit(MONO, PING, 13, W - 2 * PAD)
    body.append(MONO.path(PING, ping_size, PAD, 178, t["dim"]))
    return svg(h, f"❯ ping robert – {EMAIL_USER}{EMAIL_DOMAIN} – {PING}", "\n".join(body))


# --- dane z GitHuba --------------------------------------------------------

def fetch_days():
    """Kalendarz kontrybucji z GraphQL; zapasowo z publicznej strony profilu."""
    if TOKEN:
        query = (
            'query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{'
            "weeks{contributionDays{date contributionCount}}}}}}"
        )
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": {"login": USERNAME}}).encode(),
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
            days = [(dt.date.fromisoformat(d["date"]), d["contributionCount"]) for wk in weeks for d in wk["contributionDays"]]
            return sorted(days)[-365:]
        except Exception as e:  # noqa: BLE001
            print(f"GraphQL niedostępne ({e}), próbuję strony profilu.")

    url = f"https://github.com/users/{USERNAME}/contributions"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "profile-assets"}), timeout=30) as resp:
        html = resp.read().decode("utf-8")
    tips = dict(re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', html))
    days = []
    for tag in re.findall(r"<td\b[^>]*\bdata-date=[^>]*>", html):
        date = re.search(r'data-date="([^"]+)"', tag).group(1)
        cid = re.search(r'\bid="([^"]+)"', tag)
        m = re.match(r"\s*(\d+) contribution", tips.get(cid.group(1), "") if cid else "")
        days.append((dt.date.fromisoformat(date), int(m.group(1)) if m else 0))
    if not days:
        raise RuntimeError("Nie udało się odczytać kalendarza kontrybucji.")
    return sorted(days)[-365:]


def fetch_repos():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from update_projects import MAX_PROJECTS, fetch_public_repos, filter_repos
    repos = filter_repos(fetch_public_repos())
    visible = repos[:MAX_PROJECTS]
    print(f"Projekty do SVG: total={len(repos)}, pokazuję={len(visible)}")
    return visible, len(repos)


def load_certs():
    if not CERTS.exists():
        return []
    data = json.loads(CERTS.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        sys.exit("data/certs.json musi zawierać listę obiektów.")
    return data


# --- przykładowe dane (tylko podgląd) --------------------------------------

def sample_days():
    rnd = random.Random(7)
    today = dt.date.today()
    return [(today - dt.timedelta(days=364 - i), rnd.choice([0, 0, 1, 2, 3, 5, 9]) if rnd.random() < 0.4 else 0)
            for i in range(365)]


SAMPLE_REPOS = [
    {"name": "przyklad-skaner-portow", "description": "Przykładowy opis – prosty skaner portów TCP z raportem do pliku.",
     "language": "Python", "topics": ["networking"]},
    {"name": "przyklad-hardening", "description": "Przykład: skrypty utwardzające świeżą instalację Linuksa, bardzo długi opis do przycięcia na końcu wiersza.",
     "language": "Shell", "topics": []},
]
SAMPLE_CERTS = [
    {"name": "Przykładowy kurs sieci komputerowych", "issuer": "Wydawca", "year": 2026, "status": "ukończony"},
    {"name": "Przykładowy kurs Linuxa", "issuer": "Wydawca", "year": 2026, "status": "w trakcie"},
]


# --- zapis -----------------------------------------------------------------

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")
        print(f"zapisano {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="katalog wyjściowy (domyślnie assets/)")
    ap.add_argument("--static", action="store_true", help="bez projektów i aktywności (nie potrzebują sieci)")
    ap.add_argument("--sample", action="store_true", help="przykładowe dane – tylko z --out, do podglądu")
    args = ap.parse_args()
    if args.sample and not args.out:
        sys.exit("--sample wymaga --out, żeby przykładowe dane nie trafiły do assets/.")
    out = Path(args.out) if args.out else ROOT / "assets"

    cert_items = SAMPLE_CERTS if args.sample else load_certs()
    if not args.out:
        update_readme_certs_alt(cert_items)
    for mode, t in THEMES.items():
        write(out / f"hero-{mode}.svg", hero(t))
        write(out / f"osi-{mode}.svg", osi(t))
        write(out / f"tracks-{mode}.svg", tracks(t))
        write(out / f"tools-{mode}.svg", tools(t))
        write(out / f"certs-{mode}.svg", certs(t, cert_items))
        write(out / f"contact-{mode}.svg", contact(t))
        if args.sample:
            write(out / f"certs-empty-{mode}.svg", certs(t, []))
            write(out / f"projects-empty-{mode}.svg", projects(t, []))

    if args.static:
        return
    if args.sample:
        repos = SAMPLE_REPOS
        total_repos = len(SAMPLE_REPOS)
    else:
        repos, total_repos = fetch_repos()
    for mode, t in THEMES.items():
        write(out / f"projects-{mode}.svg", projects(t, repos, total=total_repos))
    try:
        days = sample_days() if args.sample else fetch_days()
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Brak danych aktywności: {e}")
    for mode, t in THEMES.items():
        write(out / f"activity-{mode}.svg", activity(t, days))


if __name__ == "__main__":
    main()
