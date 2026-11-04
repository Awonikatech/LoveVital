"""Generates on-brand, local SVG product renders, category tiles and hero banners.

Every image is deterministic and lives under backend/static, so the demo never depends on
external image hosts. Run:  python -m scripts.generate_images
"""
from __future__ import annotations

import math
import os
import random

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

METALS = {
    "gold": ["#7A5518", "#C9A24D", "#FFF1C1", "#E8C873", "#8A6420"],
    "rose-gold": ["#7C4434", "#C98670", "#FFE1D3", "#E6A890", "#8E5240"],
    "silver": ["#3E3E3E", "#9A9A9A", "#F7F7F7", "#C8C8C8", "#5A5A5A"],
    "oxidised": ["#232323", "#5D5A55", "#B9B3A8", "#77726A", "#2E2C29"],
    "antique-gold": ["#5E4012", "#A7802F", "#E9D59A", "#C3A055", "#6B4B16"],
}
GEMS = {
    "ruby": ("#5E0A18", "#C2253F", "#FF8A9B"),
    "emerald": ("#05382A", "#138A63", "#7FF0C4"),
    "sapphire": ("#0C1D47", "#2950B5", "#9DB7FF"),
    "pearl": ("#C9BFAE", "#F6F0E6", "#FFFFFF"),
    "kundan": ("#B9A986", "#F4EEDC", "#FFFFFF"),
    "amethyst": ("#31164F", "#7B45B5", "#D4B5FF"),
    "onyx": ("#0B0B0B", "#2A2A2A", "#6E6E6E"),
    "topaz": ("#6A3E06", "#E19B2B", "#FFE2A8"),
}
BGS = {
    "ivory": ("#FFFDF8", "#F3E9D6"),
    "blush": ("#FFF9F7", "#F2DCD5"),
    "sage": ("#FBFDF8", "#E1E8DA"),
    "powder": ("#FAFCFF", "#E0E6EF"),
    "sand": ("#FFFCF6", "#EADBC2"),
    "champagne": ("#FFFDF9", "#EEDFCB"),
}


def defs(metal: str, gem: str, bg: str, uid: str, fabric: str | None = None, fabric2: str | None = None) -> str:
    m = METALS[metal]
    g = GEMS[gem]
    b = BGS[bg]
    f = fabric or "#B33A3A"
    f2 = fabric2 or shade(f, -0.25)
    return f"""<defs>
<radialGradient id="bg{uid}" cx="50%" cy="42%" r="75%"><stop offset="0" stop-color="{b[0]}"/><stop offset="1" stop-color="{b[1]}"/></radialGradient>
<linearGradient id="m{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{m[0]}"/><stop offset=".28" stop-color="{m[1]}"/><stop offset=".5" stop-color="{m[2]}"/><stop offset=".72" stop-color="{m[3]}"/><stop offset="1" stop-color="{m[4]}"/></linearGradient>
<linearGradient id="ms{uid}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="60" y2="60" spreadMethod="reflect"><stop offset="0" stop-color="{m[1]}"/><stop offset=".5" stop-color="{m[2]}"/><stop offset="1" stop-color="{m[3]}"/></linearGradient>
<linearGradient id="mv{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{m[2]}"/><stop offset=".35" stop-color="{m[3]}"/><stop offset=".7" stop-color="{m[1]}"/><stop offset="1" stop-color="{m[0]}"/></linearGradient>
<radialGradient id="g{uid}" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="{g[2]}"/><stop offset=".45" stop-color="{g[1]}"/><stop offset="1" stop-color="{g[0]}"/></radialGradient>
<radialGradient id="p{uid}" cx="35%" cy="30%" r="70%"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".6" stop-color="#F3EDE2"/><stop offset="1" stop-color="#C9BBA3"/></radialGradient>
<linearGradient id="f{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{shade(f, .12)}"/><stop offset=".55" stop-color="{f}"/><stop offset="1" stop-color="{f2}"/></linearGradient>
<linearGradient id="fv{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{shade(f, .08)}"/><stop offset="1" stop-color="{f2}"/></linearGradient>
<pattern id="pt{uid}" width="46" height="46" patternUnits="userSpaceOnUse"><circle cx="23" cy="23" r="3.2" fill="url(#m{uid})" opacity=".9"/><path d="M23 12 q4 7 0 11 q-4-4 0-11z M23 34 q4-7 0-11 q-4 4 0 11z M12 23 q7 4 11 0 q-4-4-11 0z M34 23 q-7 4-11 0 q4-4 11 0z" fill="url(#m{uid})" opacity=".55"/></pattern>
<pattern id="pd{uid}" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="11" cy="11" r="2" fill="{shade(f, .45)}" opacity=".55"/></pattern>
<filter id="sh{uid}" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#4A3418" flood-opacity=".22"/></filter>
<filter id="soft{uid}"><feGaussianBlur stdDeviation="18"/></filter>
</defs>"""


def shade(hex_color: str, amt: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if amt >= 0:
        r, g, b = (int(c + (255 - c) * amt) for c in (r, g, b))
    else:
        r, g, b = (int(c * (1 + amt)) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def frame(body: str, d: str, uid: str, w: int = 800, h: int = 1000, motif: bool = True) -> str:
    mandala = ""
    if motif:
        petals = "".join(
            f'<ellipse cx="400" cy="{470 - 330}" rx="34" ry="120" transform="rotate({a} 400 470)" fill="none" stroke="#B58B3C" stroke-width="1.2"/>'
            for a in range(0, 360, 20)
        )
        mandala = f'<g opacity=".07">{petals}<circle cx="400" cy="470" r="380" fill="none" stroke="#B58B3C" stroke-width="1.2"/><circle cx="400" cy="470" r="250" fill="none" stroke="#B58B3C"/></g>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{d}'
            f'<rect width="{w}" height="{h}" fill="url(#bg{uid})"/>{mandala}'
            f'<ellipse cx="{w/2}" cy="{h*0.9}" rx="{w*0.32}" ry="26" fill="#5B4322" opacity=".10" filter="url(#soft{uid})"/>'
            f"{body}</svg>")


# ------------------------------------------------------------------ jewellery primitives
def gem(cx, cy, r, uid, facet=True):
    s = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#g{uid})" stroke="url(#m{uid})" stroke-width="{max(2, r*.22):.1f}"/>'
    if facet and r > 9:
        s += f'<path d="M{cx-r*.55} {cy-r*.1} L{cx} {cy-r*.6} L{cx+r*.55} {cy-r*.1} L{cx} {cy+r*.55}Z" fill="#fff" opacity=".18"/>'
        s += f'<circle cx="{cx-r*.35}" cy="{cy-r*.38}" r="{r*.18}" fill="#fff" opacity=".75"/>'
    return s


def pearl(cx, cy, r, uid):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#p{uid})"/><circle cx="{cx-r*.35}" cy="{cy-r*.35}" r="{r*.25}" fill="#fff" opacity=".9"/>'


def jhumka(cx, top, uid, scale=1.0):
    s = scale
    out = [f'<g filter="url(#sh{uid})">']
    out.append(f'<circle cx="{cx}" cy="{top}" r="{40*s}" fill="url(#m{uid})"/>')
    for i in range(10):
        a = i * math.pi * 2 / 10
        out.append(f'<circle cx="{cx+math.cos(a)*30*s:.1f}" cy="{top+math.sin(a)*30*s:.1f}" r="{6*s:.1f}" fill="url(#mv{uid})" stroke="#6b4a14" stroke-width=".6"/>')
    out.append(gem(cx, top, 17 * s, uid))
    y = top + 40 * s
    for i in range(3):
        out.append(f'<circle cx="{cx}" cy="{y + 9*s + i*14*s:.1f}" r="{6*s:.1f}" fill="url(#m{uid})"/>')
    y += 48 * s
    w, h = 92 * s, 130 * s
    out.append(f'<path d="M{cx-12*s} {y} C{cx-30*s} {y+20*s} {cx-w} {y+h*.55} {cx-w} {y+h} L{cx+w} {y+h} C{cx+w} {y+h*.55} {cx+30*s} {y+20*s} {cx+12*s} {y}Z" fill="url(#m{uid})" stroke="#6b4a14" stroke-width="1.2"/>')
    for k, f in enumerate((0.35, 0.6, 0.82)):
        yy = y + h * f
        half = 12 * s + (w - 12 * s) * f ** 0.9
        out.append(f'<path d="M{cx-half:.1f} {yy:.1f} Q{cx} {yy+10*s:.1f} {cx+half:.1f} {yy:.1f}" fill="none" stroke="#6b4a14" stroke-width="{1.4*s:.1f}" opacity=".55"/>')
        n = 5 + k * 3
        for j in range(n):
            t = (j + .5) / n
            px = cx - half + 2 * half * t
            out.append(f'<circle cx="{px:.1f}" cy="{yy + 4*s + math.sin(t*math.pi)*6*s:.1f}" r="{3*s:.1f}" fill="#fff6d8" opacity=".85"/>')
    out.append(f'<path d="M{cx-w} {y+h} Q{cx} {y+h+26*s} {cx+w} {y+h}" fill="none" stroke="url(#m{uid})" stroke-width="{6*s:.1f}"/>')
    for j in range(11):
        t = j / 10
        px = cx - w + 2 * w * t
        py = y + h + math.sin(t * math.pi) * 13 * s + 14 * s
        out.append(f'<line x1="{px:.1f}" y1="{py-10*s:.1f}" x2="{px:.1f}" y2="{py:.1f}" stroke="url(#ms{uid})" stroke-width="{2*s:.1f}"/>')
        out.append(pearl(px, py + 8 * s, 8 * s, uid))
    out.append("</g>")
    return "".join(out)


def stud(cx, cy, uid, s=1.0):
    out = [f'<g filter="url(#sh{uid})">']
    for i in range(8):
        a = i * math.pi / 4
        out.append(f'<ellipse cx="{cx+math.cos(a)*38*s:.1f}" cy="{cy+math.sin(a)*38*s:.1f}" rx="{22*s}" ry="{14*s}" transform="rotate({i*45} {cx+math.cos(a)*38*s:.1f} {cy+math.sin(a)*38*s:.1f})" fill="url(#m{uid})" stroke="#6b4a14" stroke-width=".8"/>')
        out.append(pearl(cx + math.cos(a) * 40 * s, cy + math.sin(a) * 40 * s, 7 * s, uid))
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{30*s}" fill="url(#m{uid})"/>' + gem(cx, cy, 22 * s, uid))
    out.append("</g>")
    return "".join(out)


def chandbali(cx, top, uid, s=1.0):
    out = [f'<g filter="url(#sh{uid})">', f'<circle cx="{cx}" cy="{top}" r="{24*s}" fill="url(#m{uid})"/>', gem(cx, top, 13 * s, uid)]
    y0 = top + 40 * s
    out.append(f'<path d="M{cx-120*s} {y0+40*s} A{120*s} {120*s} 0 0 0 {cx+120*s} {y0+40*s} Q{cx} {y0+40*s+130*s} {cx-120*s} {y0+40*s}Z" fill="url(#m{uid})" stroke="#6b4a14" stroke-width="1.2"/>')
    out.append(f'<path d="M{cx-100*s} {y0+52*s} Q{cx} {y0+40*s+150*s} {cx+100*s} {y0+52*s}" fill="none" stroke="#6b4a14" stroke-opacity=".35" stroke-width="{2*s}" stroke-dasharray="{3*s} {5*s}"/>')
    for j in range(9):
        a = math.pi * (0.12 + 0.76 * j / 8)
        px, py = cx - math.cos(a) * 100 * s, y0 + 40 * s + math.sin(a) * 96 * s
        out.append(gem(px, py, 9 * s, uid, facet=False))
    for j in range(13):
        a = math.pi * (0.05 + 0.9 * j / 12)
        px, py = cx - math.cos(a) * 124 * s, y0 + 40 * s + math.sin(a) * 124 * s
        out.append(pearl(px, py + 12 * s, 7.5 * s, uid))
    out.append(f'<path d="M{cx} {top+24*s} L{cx} {y0+40*s+60*s}" stroke="url(#ms{uid})" stroke-width="{5*s}"/>')
    out.append(stud(cx, y0 + 40 * s + 30 * s, uid, .32 * s))
    out.append('<g/>')
    out.append("</g>")
    return "".join(out)


def hoop(cx, cy, uid, s=1.0):
    return (f'<g filter="url(#sh{uid})"><ellipse cx="{cx}" cy="{cy}" rx="{95*s}" ry="{110*s}" fill="none" stroke="url(#m{uid})" stroke-width="{20*s}"/>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="{95*s}" ry="{110*s}" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="{3*s}" stroke-dasharray="{6*s} {10*s}"/>'
            + "".join(gem(cx + math.cos(a) * 95 * s, cy + math.sin(a) * 110 * s, 8 * s, uid, False) for a in [math.pi * (0.2 + 0.6 * k / 6) for k in range(7)]) + "</g>")


def necklace(uid, style="choker", s=1.0):
    out = [f'<g filter="url(#sh{uid})">']
    cx, top, bottom = 400, 210, 600 if style == "choker" else 700
    pts = []
    n = 34
    for i in range(n + 1):
        t = i / n
        a = math.pi * t
        x = cx - math.cos(a) * 240 * s
        y = top + math.sin(a) * (bottom - top)
        pts.append((x, y))
    path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    out.append(f'<path d="{path}" fill="none" stroke="url(#m{uid})" stroke-width="{10*s}" stroke-linecap="round"/>')
    if style in ("choker", "kundan"):
        for i, (x, y) in enumerate(pts[2:-2]):
            if i % 2 == 0:
                out.append(f'<rect x="{x-14*s:.1f}" y="{y-14*s:.1f}" width="{28*s}" height="{28*s}" rx="{5*s}" transform="rotate(45 {x:.1f} {y:.1f})" fill="url(#m{uid})" stroke="#6b4a14" stroke-width=".8"/>')
                out.append(gem(x, y, 9 * s, uid, False))
                out.append(f'<line x1="{x:.1f}" y1="{y+16*s:.1f}" x2="{x:.1f}" y2="{y+30*s:.1f}" stroke="url(#ms{uid})" stroke-width="{2*s}"/>')
                out.append(pearl(x, y + 37 * s, 7 * s, uid))
    elif style == "layered":
        for layer in (1, 2):
            pts2 = [(cx - math.cos(math.pi * t / 40) * (240 - layer * 18) * s, top + math.sin(math.pi * t / 40) * (bottom - top + layer * 70)) for t in range(41)]
            for k, (x, y) in enumerate(pts2[1:-1]):
                out.append(pearl(x, y, 6.5 * s, uid) if k % 3 else f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{7*s}" fill="url(#m{uid})"/>')
    else:  # beaded / temple
        for k, (x, y) in enumerate(pts[1:-1]):
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{9*s}" fill="url(#m{uid})" stroke="#6b4a14" stroke-width=".6"/>')
    # centre pendant
    py = bottom + 10 * s
    out.append(f'<path d="M{cx} {py} C{cx-80*s} {py+30*s} {cx-70*s} {py+120*s} {cx} {py+170*s} C{cx+70*s} {py+120*s} {cx+80*s} {py+30*s} {cx} {py}Z" fill="url(#m{uid})" stroke="#6b4a14" stroke-width="1.2"/>')
    out.append(gem(cx, py + 78 * s, 34 * s, uid))
    for k in range(7):
        a = math.pi * (0.15 + 0.7 * k / 6)
        out.append(gem(cx - math.cos(a) * 58 * s, py + 78 * s + math.sin(a) * 66 * s - 10 * s, 7 * s, uid, False))
    for k in range(5):
        x = cx - 40 * s + k * 20 * s
        out.append(f'<line x1="{x}" y1="{py+150*s+abs(k-2)*-8*s}" x2="{x}" y2="{py+178*s}" stroke="url(#ms{uid})" stroke-width="{2*s}"/>' + pearl(x, py + 188 * s, 8 * s, uid))
    out.append("</g>")
    return "".join(out)


def pendant(uid, s=1.0):
    cx = 400
    chain = f'<path d="M150 150 Q400 720 650 150" fill="none" stroke="url(#ms{uid})" stroke-width="5" stroke-dasharray="9 5"/>'
    body = (f'<g filter="url(#sh{uid})"><circle cx="{cx}" cy="455" r="14" fill="none" stroke="url(#m{uid})" stroke-width="6"/>'
            f'<path d="M{cx} 470 C{cx-95} 520 {cx-80} 650 {cx} 720 C{cx+80} 650 {cx+95} 520 {cx} 470Z" fill="url(#m{uid})" stroke="#6b4a14" stroke-width="1.4"/>'
            f'<path d="M{cx} 495 C{cx-65} 535 {cx-55} 640 {cx} 690 C{cx+55} 640 {cx+65} 535 {cx} 495Z" fill="url(#g{uid})"/>'
            f'<path d="M{cx-30} 560 L{cx} 520 L{cx+30} 560 L{cx} 640Z" fill="#fff" opacity=".18"/><circle cx="{cx-20}" cy="550" r="9" fill="#fff" opacity=".7"/>'
            + "".join(gem(cx + math.cos(a) * 92, 600 + math.sin(a) * 120, 6, uid, False) for a in [math.pi * (-.4 + k * .2) for k in range(5)]) + "</g>")
    return chain + body


def bangles(uid, n=4, kada=False):
    out = [f'<g filter="url(#sh{uid})">']
    base = 640
    for i in range(n):
        cy = base - i * (70 if not kada else 0)
        sw = 46 if kada else 26
        out.append(f'<ellipse cx="400" cy="{cy}" rx="230" ry="78" fill="none" stroke="url(#mv{uid})" stroke-width="{sw}"/>')
        out.append(f'<ellipse cx="400" cy="{cy}" rx="230" ry="78" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="2" stroke-dasharray="2 12"/>')
        for k in range(13):
            a = math.pi * (0.06 + 0.88 * k / 12)
            out.append(gem(400 - math.cos(a) * 230, cy + math.sin(a) * 78, 7 if not kada else 11, uid, False))
        if kada:
            break
    out.append("</g>")
    return "".join(out)


def bracelet(uid, charms=True):
    out = [f'<g filter="url(#sh{uid})">']
    for k in range(28):
        a = 2 * math.pi * k / 28
        x, y = 400 + math.cos(a) * 220, 500 + math.sin(a) * 140
        out.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="18" ry="11" transform="rotate({math.degrees(a)+90:.0f} {x:.1f} {y:.1f})" fill="none" stroke="url(#m{uid})" stroke-width="6"/>')
    if charms:
        for k in range(7):
            a = math.pi * (0.15 + 0.7 * k / 6)
            x, y = 400 + math.cos(a) * 220, 500 + math.sin(a) * 140
            out.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y+30:.1f}" stroke="url(#ms{uid})" stroke-width="3"/>')
            out.append(gem(x, y + 44, 15, uid) if k % 2 else f'<path d="M{x:.1f} {y+62:.1f} l-16 -16 a10 10 0 0 1 16 -12 a10 10 0 0 1 16 12z" fill="url(#m{uid})"/>')
    out.append("</g>")
    return "".join(out)


def ring(uid, cx=400, cy=560, s=1.0):
    return (f'<g filter="url(#sh{uid})"><ellipse cx="{cx}" cy="{cy}" rx="{150*s}" ry="{60*s}" fill="none" stroke="url(#mv{uid})" stroke-width="{24*s}"/>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="{150*s}" ry="{60*s}" fill="none" stroke="#fff" stroke-opacity=".3" stroke-width="{3*s}"/>'
            f'<path d="M{cx-70*s} {cy-55*s} L{cx-40*s} {cy-150*s} L{cx+40*s} {cy-150*s} L{cx+70*s} {cy-55*s}Z" fill="url(#m{uid})" stroke="#6b4a14" stroke-width="1"/>'
            f'<polygon points="{cx-62*s},{cy-170*s} {cx-30*s},{cy-215*s} {cx+30*s},{cy-215*s} {cx+62*s},{cy-170*s} {cx},{cy-95*s}" fill="url(#g{uid})" stroke="url(#m{uid})" stroke-width="{4*s}"/>'
            f'<polygon points="{cx-30*s},{cy-215*s} {cx},{cy-170*s} {cx+30*s},{cy-215*s}" fill="#fff" opacity=".35"/>'
            f'<line x1="{cx-62*s}" y1="{cy-170*s}" x2="{cx+62*s}" y2="{cy-170*s}" stroke="#fff" stroke-opacity=".4" stroke-width="{2*s}"/>'
            + "".join(gem(cx + dx * s, cy - 40 * s, 7 * s, uid, False) for dx in (-95, -115, 95, 115)) + "</g>")


def anklet(uid):
    out = [f'<g filter="url(#sh{uid})">']
    pts = [(120 + i * 14, 480 + math.sin(i / 4) * 40) for i in range(41)]
    out.append('<path d="M' + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + f'" fill="none" stroke="url(#m{uid})" stroke-width="8" stroke-dasharray="10 4"/>')
    for k, (x, y) in enumerate(pts[2::3]):
        out.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y+26:.1f}" stroke="url(#ms{uid})" stroke-width="2"/><circle cx="{x:.1f}" cy="{y+38:.1f}" r="12" fill="url(#m{uid})" stroke="#6b4a14" stroke-width=".8"/><line x1="{x-8:.1f}" y1="{y+42:.1f}" x2="{x+8:.1f}" y2="{y+42:.1f}" stroke="#4a3210" stroke-width="2"/>')
    out.append("</g>")
    return "".join(out)


def tikka(uid):
    return (f'<g filter="url(#sh{uid})"><path d="M400 120 L400 470" stroke="url(#ms{uid})" stroke-width="6" stroke-dasharray="10 5"/>'
            f'<circle cx="400" cy="110" r="18" fill="url(#m{uid})"/>{chandbali(400, 470, uid, 1.15)}</g>')


# ------------------------------------------------------------------ apparel primitives
def hanger(uid):
    return (f'<path d="M400 60 q30 0 30 28 q0 22 -30 34" fill="none" stroke="#8A6420" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M190 205 L400 118 L610 205" fill="none" stroke="#A97F35" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>')


def kurti(uid, long=True, sleeve="three-quarter"):
    hem = 900 if long else 760
    sl = {"sleeveless": 0, "short": 120, "three-quarter": 260, "full": 330}[sleeve]
    body = f'M330 190 Q400 235 470 190 L575 225 Q600 300 588 360 L560 {hem} L240 {hem} L212 360 Q200 300 225 225Z'
    sleeves = ""
    if sl:
        sleeves = (f'<path d="M575 225 Q640 250 660 300 L{640 + sl*0.12:.0f} {300+sl} L{585 + sl*0.08:.0f} {310+sl} L588 360Z" fill="url(#f{uid})" stroke="{shade("#000000", 0)}" stroke-opacity=".12"/>'
                   f'<path d="M225 225 Q160 250 140 300 L{160 - sl*0.12:.0f} {300+sl} L{215 - sl*0.08:.0f} {310+sl} L212 360Z" fill="url(#f{uid})" stroke="#000" stroke-opacity=".12"/>'
                   f'<path d="M{640 + sl*0.12:.0f} {300+sl} L{585 + sl*0.08:.0f} {310+sl}" stroke="url(#m{uid})" stroke-width="10"/>'
                   f'<path d="M{160 - sl*0.12:.0f} {300+sl} L{215 - sl*0.08:.0f} {310+sl}" stroke="url(#m{uid})" stroke-width="10"/>')
    return (f'<g filter="url(#sh{uid})">{hanger(uid)}{sleeves}<path d="{body}" fill="url(#f{uid})"/>'
            f'<path d="{body}" fill="url(#pt{uid})" opacity=".45"/>'
            f'<path d="M330 190 Q400 235 470 190 L470 205 Q400 255 330 205Z" fill="url(#m{uid})"/>'
            f'<path d="M400 230 L400 420" stroke="url(#ms{uid})" stroke-width="5"/>'
            + "".join(f'<circle cx="400" cy="{260+k*40}" r="6" fill="url(#m{uid})"/>' for k in range(4))
            + f'<path d="M300 210 Q400 330 500 210 L512 300 Q400 420 288 300Z" fill="url(#m{uid})" opacity=".35"/>'
            f'<rect x="240" y="{hem-60}" width="320" height="52" fill="url(#m{uid})" opacity=".85"/>'
            f'<rect x="240" y="{hem-60}" width="320" height="52" fill="url(#pt{uid})" opacity=".9"/>'
            f'<path d="M240 {hem} L262 {hem-300} M560 {hem} L538 {hem-300}" stroke="#000" stroke-opacity=".08" stroke-width="3"/></g>')


def anarkali(uid):
    skirt = "M300 380 Q400 400 500 380 L700 900 Q400 960 100 900Z"
    pleats = "".join(f'<path d="M{400 + (k-6)*16} 395 L{400 + (k-6)*50} 925" stroke="#000" stroke-opacity=".10" stroke-width="3"/>' for k in range(13))
    return (f'<g filter="url(#sh{uid})">{hanger(uid)}'
            f'<path d="M330 190 Q400 235 470 190 L560 220 Q585 290 560 340 L500 380 L300 380 L240 340 Q215 290 240 220Z" fill="url(#f{uid})"/>'
            f'<path d="M560 220 Q620 250 630 300 L600 560 L560 560 L560 340Z" fill="url(#f{uid})"/><path d="M240 220 Q180 250 170 300 L200 560 L240 560 L240 340Z" fill="url(#f{uid})"/>'
            f'<path d="M330 190 Q400 290 470 190" fill="none" stroke="url(#m{uid})" stroke-width="10"/>'
            f'<path d="M300 370 Q400 392 500 370 L500 392 Q400 414 300 392Z" fill="url(#m{uid})"/>'
            f'<path d="{skirt}" fill="url(#fv{uid})"/>{pleats}<path d="{skirt}" fill="url(#pd{uid})" opacity=".8"/>'
            f'<path d="M100 900 Q400 960 700 900 L688 868 Q400 926 112 868Z" fill="url(#m{uid})"/>'
            f'<path d="M112 868 Q400 926 688 868 L676 836 Q400 892 124 836Z" fill="url(#pt{uid})"/></g>')


def saree(uid):
    folds = []
    for k in range(5):
        y = 330 + k * 105
        folds.append(f'<path d="M150 {y} Q400 {y-40} 650 {y} L650 {y+92} Q400 {y+52} 150 {y+92}Z" fill="url(#f{uid})"/>'
                     f'<path d="M150 {y} Q400 {y-40} 650 {y} L650 {y+92} Q400 {y+52} 150 {y+92}Z" fill="url(#pd{uid})" opacity=".8"/>'
                     f'<path d="M150 {y+70} Q400 {y+30} 650 {y+70} L650 {y+92} Q400 {y+52} 150 {y+92}Z" fill="url(#m{uid})"/>'
                     f'<path d="M150 {y+70} Q400 {y+30} 650 {y+70} L650 {y+92} Q400 {y+52} 150 {y+92}Z" fill="url(#pt{uid})" opacity=".8"/>')
    pallu = (f'<path d="M520 180 Q610 160 690 220 L640 860 Q590 840 560 870Z" fill="url(#f{uid})" opacity=".95"/>'
             f'<path d="M520 180 Q610 160 690 220 L640 860 Q590 840 560 870Z" fill="url(#pt{uid})" opacity=".85"/>'
             f'<path d="M560 870 Q590 840 640 860 L646 830 Q594 812 562 838Z" fill="url(#m{uid})"/>')
    return f'<g filter="url(#sh{uid})">{"".join(folds)}{pallu}</g>'


def top(uid, peplum=False):
    hem = 640
    body = f'M330 210 Q400 250 470 210 L560 240 L548 520 Q560 {hem} 400 {hem+10} Q240 {hem} 252 520 L240 240Z'
    pep = f'<path d="M252 520 Q400 560 548 520 L600 {hem+40} Q400 {hem+90} 200 {hem+40}Z" fill="url(#fv{uid})"/>' if peplum else ""
    return (f'<g filter="url(#sh{uid})">{hanger(uid)}'
            f'<path d="M560 240 Q640 250 660 330 Q640 380 590 370 L555 300Z" fill="url(#f{uid})"/><path d="M240 240 Q160 250 140 330 Q160 380 210 370 L245 300Z" fill="url(#f{uid})"/>'
            f'<path d="{body}" fill="url(#f{uid})"/>{pep}<path d="M330 210 Q400 300 470 210" fill="none" stroke="#fff" stroke-opacity=".7" stroke-width="5"/>'
            f'<path d="M300 300 Q400 340 500 300" fill="none" stroke="#000" stroke-opacity=".08" stroke-width="3"/></g>')


def trousers(uid, wide=True):
    w = 120 if wide else 40
    return (f'<g filter="url(#sh{uid})"><rect x="250" y="170" width="300" height="60" rx="10" fill="url(#fv{uid})"/>'
            f'<path d="M250 230 L550 230 L{560+w*0.5:.0f} 900 L{420} 900 L400 420 L380 900 L{240-w*0.5:.0f} 900Z" fill="url(#f{uid})"/>'
            f'<path d="M330 240 L{310-w*0.3:.0f} 890 M470 240 L{490+w*0.3:.0f} 890" stroke="#000" stroke-opacity=".10" stroke-width="3"/>'
            f'<path d="M260 200 L540 200" stroke="#000" stroke-opacity=".15" stroke-width="2" stroke-dasharray="6 6"/>'
            f'<circle cx="400" cy="200" r="7" fill="url(#m{uid})"/></g>')


def lehenga(uid):
    skirt = "M260 420 Q400 440 540 420 L720 920 Q400 980 80 920Z"
    return (f'<g filter="url(#sh{uid})">{hanger(uid)}'
            f'<path d="M320 200 Q400 240 480 200 L560 230 L540 330 Q400 350 260 330 L240 230Z" fill="url(#f{uid})"/>'
            f'<path d="M260 330 Q400 350 540 330 L540 350 Q400 370 260 350Z" fill="url(#m{uid})"/>'
            f'<path d="{skirt}" fill="url(#fv{uid})"/><path d="{skirt}" fill="url(#pt{uid})" opacity=".55"/>'
            + "".join(f'<path d="M{400 + (k-5)*24} 432 L{400 + (k-5)*64} 940" stroke="#000" stroke-opacity=".08" stroke-width="3"/>' for k in range(11))
            + f'<path d="M80 920 Q400 980 720 920 L700 860 Q400 918 100 860Z" fill="url(#m{uid})"/><path d="M100 860 Q400 918 700 860 L690 836 Q400 890 110 836Z" fill="url(#pt{uid})"/>'
            f'<path d="M480 200 Q640 260 690 520 L650 900 Q620 880 600 900 L620 520 Q580 330 520 260Z" fill="url(#f{uid})" opacity=".55"/></g>')


def coord(uid):
    return (f'<g filter="url(#sh{uid})">'
            f'<path d="M300 120 Q400 150 500 120 L580 150 L570 380 L230 380 L220 150Z" fill="url(#f{uid})"/><path d="M300 120 Q400 150 500 120 L580 150 L570 380 L230 380 L220 150Z" fill="url(#pd{uid})"/>'
            f'<path d="M580 150 Q640 170 650 230 L600 260 L575 210Z" fill="url(#f{uid})"/><path d="M220 150 Q160 170 150 230 L200 260 L225 210Z" fill="url(#f{uid})"/>'
            f'<rect x="270" y="440" width="260" height="44" rx="8" fill="url(#fv{uid})"/>'
            f'<path d="M270 484 L530 484 L600 920 L420 920 L400 600 L380 920 L200 920Z" fill="url(#f{uid})"/><path d="M270 484 L530 484 L600 920 L420 920 L400 600 L380 920 L200 920Z" fill="url(#pd{uid})"/></g>')


RENDERERS = {
    "jhumka": lambda u, v: jhumka(270, 230, u, 1.05) + jhumka(530, 230, u, 1.05),
    "studs": lambda u, v: stud(270, 470, u, 1.6) + stud(530, 470, u, 1.6),
    "chandbali": lambda u, v: chandbali(260, 260, u, 1.05) + chandbali(540, 260, u, 1.05),
    "hoops": lambda u, v: hoop(280, 470, u, 1.1) + hoop(520, 470, u, 1.1),
    "choker": lambda u, v: necklace(u, "choker"),
    "kundan-set": lambda u, v: necklace(u, "kundan") + stud(140, 860, u, .55) + stud(660, 860, u, .55),
    "layered": lambda u, v: necklace(u, "layered"),
    "temple": lambda u, v: necklace(u, "temple"),
    "pendant": lambda u, v: pendant(u),
    "bangles": lambda u, v: bangles(u, 4),
    "kada": lambda u, v: bangles(u, 1, kada=True),
    "bracelet": lambda u, v: bracelet(u, True),
    "chain-bracelet": lambda u, v: bracelet(u, False),
    "ring": lambda u, v: ring(u),
    "ring-pair": lambda u, v: ring(u, 290, 600, .8) + ring(u, 520, 520, .8),
    "anklet": lambda u, v: anklet(u),
    "tikka": lambda u, v: tikka(u),
    "kurti": lambda u, v: kurti(u, True, "three-quarter"),
    "kurti-short": lambda u, v: kurti(u, False, "short"),
    "kurta-full": lambda u, v: kurti(u, True, "full"),
    "anarkali": lambda u, v: anarkali(u),
    "saree": lambda u, v: saree(u),
    "top": lambda u, v: top(u),
    "peplum": lambda u, v: top(u, True),
    "trousers": lambda u, v: trousers(u, False),
    "palazzo": lambda u, v: trousers(u, True),
    "lehenga": lambda u, v: lehenga(u),
    "coord": lambda u, v: coord(u),
}


FIT = {  # kind: (content centre y, scale) -> recentred around (400, 470)
    "jhumka": (330, 1.42), "studs": (470, 1.12), "chandbali": (345, 1.35), "hoops": (470, 1.2), "choker": (505, 1.06),
    "temple": (505, 1.06), "layered": (520, 1.0), "ring": (488, 1.45), "ring-pair": (480, 1.2), "bangles": (540, 1.15),
    "kada": (640, 1.35), "bracelet": (520, 1.25), "chain-bracelet": (500, 1.25),
}


def fitted(kind: str, uid: str, view: int = 0) -> str:
    body = RENDERERS[kind](uid, view)
    if kind in FIT:
        cy, k = FIT[kind]
        body = f'<g transform="translate(400 470) scale({k}) translate(-400 -{cy})">{body}</g>'
    return body


def render(kind: str, *, metal="gold", gem_="ruby", bg="ivory", fabric=None, fabric2=None, view=0, uid="a") -> str:
    d = defs(metal, gem_, bg, uid, fabric, fabric2)
    body = fitted(kind, uid, view)
    if view == 1:  # detail view: zoomed in & slightly rotated
        body = f'<g transform="translate(400 470) scale(1.45) rotate(-8) translate(-400 -470)">{body}</g>'
    elif view == 2:  # flat lay on a tray
        tray = (f'<rect x="70" y="120" width="660" height="760" rx="30" fill="#fff" opacity=".55"/>'
                f'<rect x="90" y="140" width="620" height="720" rx="22" fill="none" stroke="url(#m{uid})" stroke-width="2" stroke-dasharray="2 8"/>')
        body = tray + f'<g transform="translate(400 500) scale(.82) translate(-400 -470)">{body}</g>'
    return frame(body, d, uid, motif=view != 1)


def write(path: str, svg: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)


# ------------------------------------------------------------------ banners & tiles
def banner(name: str, kind: str, metal: str, gem_: str, bg: str, fabric: str | None = None, flip=False, uid="b") -> str:
    w, h = 1600, 800
    b = BGS[bg]
    d = defs(metal, gem_, bg, uid, fabric)
    rays = "".join(f'<line x1="{1150 if not flip else 450}" y1="400" x2="{(1150 if not flip else 450) + math.cos(a)*900:.0f}" y2="{400+math.sin(a)*900:.0f}" stroke="#C9A24D" stroke-opacity=".08" stroke-width="2"/>'
                   for a in [k * math.pi / 18 for k in range(36)])
    k = 0.78
    ox = (1150 if not flip else 450) - 400 * k
    prod = f'<g transform="translate({ox:.0f} {400 - 480 * k:.0f}) scale({k})">{fitted(kind, uid)}</g>'
    rings = f'<circle cx="{1150 if not flip else 450}" cy="400" r="330" fill="none" stroke="url(#m{uid})" stroke-width="2" opacity=".5"/><circle cx="{1150 if not flip else 450}" cy="400" r="300" fill="#fff" opacity=".35"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{d}'
            f'<linearGradient id="bb{uid}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{b[1]}"/><stop offset=".55" stop-color="{b[0]}"/><stop offset="1" stop-color="{b[1]}"/></linearGradient>'
            f'<rect width="{w}" height="{h}" fill="url(#bb{uid})"/>{rays}{rings}{prod}</svg>')


def tile(kind: str, metal: str, gem_: str, bg: str, fabric: str | None, uid: str) -> str:
    return render(kind, metal=metal, gem_=gem_, bg=bg, fabric=fabric, view=0, uid=uid)


def main() -> None:
    from scripts.seed_catalog import PRODUCTS, CATEGORY_ART, COLLECTION_ART, BANNER_ART

    n = 0
    for p in PRODUCTS:
        for vi, look in enumerate(p["looks"]):
            for view in range(3 if vi == 0 else 1):
                uid = f"{p['sku'].replace('-', '')}{vi}{view}"
                svg = render(p["art"], metal=look.get("metal", "gold"), gem_=look.get("gem", "ruby"), bg=look.get("bg", "ivory"),
                             fabric=look.get("fabric"), fabric2=look.get("fabric2"), view=view, uid=uid)
                write(os.path.join(OUT, "products", f"{p['slug']}-{vi}-{view}.svg"), svg)
                n += 1
    for slug, (kind, metal, gem_, bg, fabric) in {**CATEGORY_ART, **COLLECTION_ART}.items():
        write(os.path.join(OUT, "tiles", f"{slug}.svg"), tile(kind, metal, gem_, bg, fabric, "t" + slug.replace("-", "")[:10]))
        n += 1
    for i, (name, kind, metal, gem_, bg, fabric, flip) in enumerate(BANNER_ART):
        write(os.path.join(OUT, "banners", f"{name}.svg"), banner(name, kind, metal, gem_, bg, fabric, flip, uid=f"bn{i}"))
        n += 1
    print(f"Generated {n} images in {OUT}")


if __name__ == "__main__":
    main()
