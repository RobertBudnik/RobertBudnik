"""
Generuje grafiki SVG do README w wersji jasnej i ciemnej:
    assets/status-{light,dark}.svg    – plakietka „szukam stażu” z zieloną kropką
    assets/contact-{light,dark}.svg   – ciemny panel kontaktu z dużym e-mailem
    assets/activity-{light,dark}.svg  – fala kontrybucji z ostatnich 365 dni

GitHub nie wczytuje czcionek w SVG, więc cały tekst jest zamieniany na ścieżki
(Geologica, statyczne wycinki w assets/fonts).

Użycie:
    python scripts/profile_assets.py            # wszystko, dane aktywności z GitHuba
    python scripts/profile_assets.py --static   # tylko plakietka i kontakt
    python scripts/profile_assets.py --sample --out /tmp/podglad   # przykładowe dane
"""

import argparse
import datetime as dt
import json
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
USERNAME = os.environ.get("GH_USERNAME", "RobertBudnik")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

STATUS = "Szukam stażu: cyberbezpieczeństwo i sieci"
EMAIL = "robertbudnik30@gmail.com"
INSTAGRAM = "instagram.com/Budnik.jr_"

THEMES = {
    "light": {
        "bg": "#eef0f3", "card": "#f8f9fb", "text": "#0e1726", "muted": "#556070",
        "line": "#d3d9e1", "accent": "#3340f0", "signal": "#0d9f6e",
        # panel kontaktu jest ciemny w obu trybach
        "panel": "#0e1726", "panel_line": "#0e1726", "panel_text": "#e8ecf3", "panel_muted": "#97a3b8",
    },
    "dark": {
        "bg": "#0a0f1c", "card": "#111829", "text": "#e8ecf3", "muted": "#97a3b8",
        "line": "#253047", "accent": "#8c95ff", "signal": "#3fe0a6",
        "panel": "#111829", "panel_line": "#253047", "panel_text": "#e8ecf3", "panel_muted": "#97a3b8",
    },
}

MONTHS = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]


def fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


class Face:
    """Czcionka złożona z wycinków (latin + latin-ext), rysowana jako ścieżki."""

    def __init__(self, weight):
        self.fonts = [TTFont(FONTS / f"geologica-{weight}-{sub}.ttf") for sub in ("latin", "latin-ext")]
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
        w = sum(self.glyph(c)[0].width * scale for c in text)
        return w + tracking * size * max(len(text) - 1, 0)

    def path(self, text, size, x, y, fill, tracking=0.0, anchor="start"):
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
        return f'<path fill="{fill}" d="{" ".join(parts)}"/>'


HEAVY = Face("heavy")
LIGHT = Face("light")


def svg(width, height, label, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{label}">\n'
        f"<title>{label}</title>\n{body}\n</svg>\n"
    )


def fit(face, text, size, max_width, tracking=0.0):
    """Zmniejsza rozmiar tekstu, aż zmieści się w max_width."""
    while face.width(text, size, tracking) > max_width and size > 8:
        size -= 1
    return size


def status(t):
    size = 16
    w = round(LIGHT.width(STATUS, size) + 66)
    h = 42
    body = [
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="20.5" fill="{t["card"]}" stroke="{t["line"]}"/>',
        f'<circle cx="23" cy="21" r="5" fill="{t["signal"]}"/>',
        LIGHT.path(STATUS, size, 40, 26.5, t["text"]),
    ]
    return svg(w, h, STATUS, "\n".join(body))


def contact(t):
    w, h, pad = 900, 230, 56
    mail_size = fit(HEAVY, EMAIL, 58, w - 2 * pad, -0.04)
    body = [
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="32" fill="{t["panel"]}" stroke="{t["panel_line"]}"/>',
        LIGHT.path("Napisz do mnie", 20, pad, 72, t["panel_muted"]),
        HEAVY.path(EMAIL, mail_size, pad - 2, 140, t["panel_text"], tracking=-0.04),
        LIGHT.path(INSTAGRAM, 17, pad, 186, t["panel_muted"]),
    ]
    return svg(w, h, f"Kontakt: {EMAIL}", "\n".join(body))


def activity(t, days):
    """days: lista (date, count) z ostatnich 365 dni, od najstarszego."""
    w, h, pad = 900, 360, 48
    counts = [c for _, c in days]
    total = sum(counts)
    active = sum(1 for c in counts if c)
    peak = max(counts) if counts else 0
    rec_i = max(range(len(counts)), key=lambda i: (counts[i], i)) if peak else None

    def date_pl(d):
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"

    stats = [
        (str(total), "kontrybucje w ostatnim roku", t["text"]),
        (str(peak), f"rekordowy dzień · {date_pl(days[rec_i][0])}" if peak else "rekordowy dzień", t["signal"]),
        (str(active), "aktywne dni", t["text"]),
    ]
    body = [f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="28" fill="{t["card"]}" stroke="{t["line"]}"/>']
    col = (w - 2 * pad) / 3
    for i, (num, label, color) in enumerate(stats):
        x = pad + i * col
        body.append(HEAVY.path(num, 60, x - 2, 100, color, tracking=-0.04))
        body.append(LIGHT.path(label, 15, x, 128, t["muted"]))

    # fala: każdy dzień to pionowa kreska symetryczna względem osi
    mid, amp = 238, 62
    step = (w - 2 * pad) / max(len(days), 1)
    bw = max(step * 0.62, 1)
    bars = []
    for i, c in enumerate(counts):
        x = pad + i * step + (step - bw) / 2
        hh = max(2.0, (c / peak) * amp * 2) if peak else 2.0
        color = t["signal"] if i == rec_i else (t["accent"] if c else t["line"])
        bars.append(f'<rect x="{fmt(x)}" y="{fmt(mid - hh / 2)}" width="{fmt(bw)}" height="{fmt(hh)}" rx="{fmt(bw / 2)}" fill="{color}"/>')
    body.extend(bars)

    if rec_i is not None:
        rx = pad + rec_i * step + step / 2
        label = f"rekord: {peak}"
        lw = LIGHT.width(label, 13)
        lx = min(max(rx - lw / 2, pad), w - pad - lw)
        body.append(LIGHT.path(label, 13, lx, mid - amp - 12, t["signal"]))

    # podpisy miesięcy pod falą
    for i, (d, _) in enumerate(days):
        if d.day == 1:
            x = pad + i * step
            if x < w - pad - 20:
                body.append(LIGHT.path(MONTHS[d.month - 1], 12, x, mid + amp + 34, t["muted"]))

    label = f"Aktywność na GitHubie: {total} kontrybucji w ostatnim roku, rekord {peak} jednego dnia"
    return svg(w, h, label, "\n".join(body))


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


def sample_days():
    rnd = random.Random(7)
    today = dt.date.today()
    return [
        (today - dt.timedelta(days=364 - i), rnd.choice([0, 0, 0, 1, 2, 3, 5, 8]) if rnd.random() < 0.55 else 0)
        for i in range(365)
    ]


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")
        print(f"zapisano {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "assets"))
    ap.add_argument("--static", action="store_true", help="bez fali aktywności")
    ap.add_argument("--sample", action="store_true", help="przykładowe dane aktywności (podgląd)")
    args = ap.parse_args()
    out = Path(args.out)

    for mode, t in THEMES.items():
        write(out / f"status-{mode}.svg", status(t))
        write(out / f"contact-{mode}.svg", contact(t))

    if args.static:
        return
    try:
        days = sample_days() if args.sample else fetch_days()
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Brak danych aktywności: {e}")
    for mode, t in THEMES.items():
        write(out / f"activity-{mode}.svg", activity(t, days))


if __name__ == "__main__":
    main()
