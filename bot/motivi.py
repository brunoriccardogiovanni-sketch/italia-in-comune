"""Illustrazioni stilizzate a tema (fortezze, trulli, alberi di luci, piatti...) per storie e piatti.

Stesso stile delle città: forme piatte, colori vivaci del profilo, nessun elemento sopra un altro
se non dove è voluto (una finestra su un muro). Ogni funzione disegna su una tela w×h trasparente.
"""
import math, random
from PIL import Image, ImageDraw, ImageFont
from .city import VIVID, _hex

S = 2  # disegno al doppio e poi riduco: bordi più puliti

def _tela(w, h): im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); return im, ImageDraw.Draw(im)
def _fine(im, w, h): return im.resize((w, h), Image.LANCZOS)
def _pal(T): return [x for x in VIVID if x.lower() not in (T["bg"].lower(),)]
def _font(size):
    from .base import font
    return font("k", size)

def fortezza(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; p = _pal(T)
    d.ellipse((W * .08, H * .06, W * .08 + H * .16, H * .22), fill=_hex(T["acc"]))
    cresta = [(0, H), (0, H * .88), (W, H * .42), (W, H)]
    d.polygon(cresta, fill=_hex(T["land"]))
    pts = [(x, H * .88 - (H * .46) * x / W) for x in [W * i / 60 for i in range(61)]]
    muro = H * .07
    for i in range(60):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        d.polygon([(x0, y0), (x1, y1), (x1, y1 - muro), (x0, y0 - muro)], fill=_hex("#C9B28A"))
        if i % 2 == 0: d.rectangle((x0, y0 - muro - H * .02, x0 + (x1 - x0) * .5, y0 - muro), fill=_hex("#C9B28A"))
    for k, t in enumerate([.12, .38, .64, .9]):
        x, y = pts[int(t * 60)]; tw, th = H * .13, H * .22
        d.rectangle((x - tw / 2, y - muro - th, x + tw / 2, y - muro + 4), fill=_hex("#B39A70"))
        for j in range(3): d.rectangle((x - tw / 2 + j * tw / 2.5, y - muro - th - H * .03, x - tw / 2 + j * tw / 2.5 + tw / 5, y - muro - th), fill=_hex("#B39A70"))
        d.rectangle((x - tw * .13, y - muro - th * .65, x + tw * .13, y - muro - th * .35), fill=_hex(T["bg"]))
        if k == 3:
            d.line((x, y - muro - th - H * .03, x, y - muro - th - H * .14), fill=_hex(T["ink"]), width=4 * S)
            d.polygon([(x, y - muro - th - H * .14), (x + tw * .7, y - muro - th - H * .115), (x, y - muro - th - H * .09)], fill=_hex(p[0]))
    for i in range(4, 56, 3):          # la scala coperta: gradini lungo la cresta
        x, y = pts[i]; d.rectangle((x, y - muro * .6, x + W * .008, y - muro * .4), fill=_hex(T["acc2"]))
    return _fine(im, w, h)

def fabbrica(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; p = _pal(T)
    d.rectangle((0, H * .82, W, H), fill=_hex(T["land"]))
    x0, x1, y0 = W * .06, W * .64, H * .3
    d.rectangle((x0, y0, x1, H * .82), fill=_hex("#E8E6F5"))
    for i in range(10):
        for j in range(4):
            cx = x0 + 16 * S + i * (x1 - x0 - 24 * S) / 10; cy = y0 + 18 * S + j * (H * .52 - 30 * S) / 4
            d.rectangle((cx, cy, cx + (x1 - x0) / 10 - 12 * S, cy + (H * .52) / 4 - 22 * S), fill=_hex("#7FB7E6"))
    d.rectangle((x0, y0 - 16 * S, x1, y0), fill=_hex(p[0]))
    tx, ty, tw = W * .7, H * .5, W * .26           # macchina da scrivere
    d.rounded_rectangle((tx, ty, tx + tw, ty + H * .3), 18 * S, fill=_hex(p[1]))
    d.rectangle((tx + tw * .1, ty - H * .12, tx + tw * .9, ty), fill=_hex("#FFFFFF"))
    for row in range(3):
        for k in range(6):
            cx = tx + tw * (.12 + k * .15); cy = ty + H * (.07 + row * .075)
            d.ellipse((cx, cy, cx + 18 * S, cy + 18 * S), fill=_hex(T["bg"]))
    return _fine(im, w, h)

def albero_luci(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S
    d.polygon([(0, H), (W * .5, H * .08), (W, H)], fill=_hex(T["land"]))
    top, base = (W * .5, H * .18), H * .8
    for t in [i / 22 for i in range(23)]:
        for sgn in (-1, 1):
            x = top[0] + sgn * t * W * .26; y = top[1] + t * (base - top[1])
            d.ellipse((x - 7 * S, y - 7 * S, x + 7 * S, y + 7 * S), fill=_hex("#FFF3B0"))
    for x in [W * .24 + i * W * .52 / 16 for i in range(17)]: d.ellipse((x - 6 * S, base - 6 * S, x + 6 * S, base + 6 * S), fill=_hex("#FFF3B0"))
    rr = random.Random(r)
    for _ in range(40):
        t = rr.random() * .9 + .05; xs = top[0] + (rr.random() * 2 - 1) * t * W * .2; ys = top[1] + t * (base - top[1])
        d.ellipse((xs - 5 * S, ys - 5 * S, xs + 5 * S, ys + 5 * S), fill=_hex(rr.choice(VIVID)))
    cx, cy, R = top[0], top[1] - 40 * S, 34 * S
    d.polygon([(cx + R * math.cos(math.pi / 2 + k * math.pi / 5) * (1 if k % 2 == 0 else .45), cy - R * math.sin(math.pi / 2 + k * math.pi / 5) * (1 if k % 2 == 0 else .45)) for k in range(10)], fill=_hex(T["acc"]))
    d.rectangle((0, H * .9, W, H), fill=_hex("#C9B28A"))
    for x in range(0, W, 40 * S): d.rectangle((x, H * .87, x + 22 * S, H * .9), fill=_hex("#C9B28A"))
    return _fine(im, w, h)

def presepe(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; p = _pal(T)
    d.rectangle((0, H * .85, W, H), fill=_hex(T["land"]))
    d.pieslice((W * .2, H * .25, W * .8, H * 1.45), 180, 360, fill=_hex("#8C6A4F"))
    d.pieslice((W * .28, H * .37, W * .72, H * 1.33), 180, 360, fill=_hex(T["bg"]))
    d.rectangle((W * .42, H * .7, W * .58, H * .8), fill=_hex("#C9A46A"))
    d.ellipse((W * .465, H * .63, W * .535, H * .7), fill=_hex("#FFE0B8"))
    for cx, col in ((W * .34, p[0]), (W * .66, p[2])):
        d.polygon([(cx - 34 * S, H * .85), (cx + 34 * S, H * .85), (cx, H * .58)], fill=_hex(col))
        d.ellipse((cx - 20 * S, H * .5, cx + 20 * S, H * .58), fill=_hex("#FFE0B8"))
    cx, cy, R = W * .82, H * .14, 34 * S
    d.polygon([(cx + R * math.cos(math.pi / 2 + k * math.pi / 5) * (1 if k % 2 == 0 else .45), cy - R * math.sin(math.pi / 2 + k * math.pi / 5) * (1 if k % 2 == 0 else .45)) for k in range(10)], fill=_hex(T["acc"]))
    d.polygon([(cx - 10 * S, cy + 10 * S), (cx - 140 * S, cy + 120 * S), (cx - 4 * S, cy + 22 * S)], fill=_hex(T["acc"]))
    return _fine(im, w, h)

def sassi(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; rr = random.Random(r)
    d.polygon([(0, H), (0, H * .3), (W, H * .55), (W, H)], fill=_hex("#C9A46A"))
    for row in range(5):
        y = H * (.36 + row * .13); n = 7 - row // 2
        for k in range(n):
            x = W * (.04 + k * .14) + (row % 2) * W * .06; bw, bh = W * .1, H * .1
            if y + bh > H: continue
            d.rectangle((x, y + (x / W) * H * .2, x + bw, y + bh + (x / W) * H * .2), fill=_hex(rr.choice(["#E9D3A6", "#DCC08D", "#F2E2C0"])))
            dx, dy = x + bw * .35, y + bh * .45 + (x / W) * H * .2
            d.pieslice((dx, dy, dx + bw * .3, dy + bh * .5), 180, 360, fill=_hex("#5A4632")); d.rectangle((dx, dy + bh * .25, dx + bw * .3, dy + bh * .5), fill=_hex("#5A4632"))
    d.rectangle((W * .78, H * .12, W * .8, H * .32), fill=_hex("#DCC08D"))
    d.polygon([(W * .76, H * .12), (W * .79, H * .05), (W * .82, H * .12)], fill=_hex("#C8553D"))
    return _fine(im, w, h)

def trulli(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; rr = random.Random(r); p = _pal(T)
    d.rectangle((0, H * .86, W, H), fill=_hex(T["land"]))
    n = 4
    for k in range(n):
        bw = W / n * .7; x = W * .04 + k * W / n; base = H * .86; sh = H * rr.uniform(.18, .26)
        d.rectangle((x, base - sh, x + bw, base), fill=_hex("#FFFFFF"))
        ch = H * rr.uniform(.34, .44)
        d.polygon([(x - 8 * S, base - sh), (x + bw + 8 * S, base - sh), (x + bw / 2, base - sh - ch)], fill=_hex("#8E8C99"))
        d.ellipse((x + bw / 2 - 14 * S, base - sh - ch - 22 * S, x + bw / 2 + 14 * S, base - sh - ch + 6 * S), fill=_hex("#FFFFFF"))
        cy = base - sh - ch * .45; cx = x + bw / 2
        if k % 2: d.ellipse((cx - 16 * S, cy - 16 * S, cx + 16 * S, cy + 16 * S), outline=_hex("#FFFFFF"), width=5 * S)
        else: d.line((cx, cy - 18 * S, cx, cy + 18 * S), fill=_hex("#FFFFFF"), width=5 * S); d.line((cx - 14 * S, cy - 4 * S, cx + 14 * S, cy - 4 * S), fill=_hex("#FFFFFF"), width=5 * S)
        d.rectangle((x + bw * .38, base - sh * .6, x + bw * .62, base), fill=_hex(p[k % len(p)]))
    return _fine(im, w, h)

def mare_bronzi(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; rr = random.Random(r)
    d.rectangle((0, H * .12, W, H), fill=_hex("#2E86C1"))
    for k in range(5):
        y = H * (.12 + k * .17)
        for x in range(0, W, 120 * S): d.arc((x, y - 20 * S, x + 120 * S, y + 20 * S), 0, 180, fill=_hex("#7FC8F8"), width=5 * S)
    d.rectangle((0, H * .88, W, H), fill=_hex("#E9D3A6"))
    u = H / 100
    for cx in (W * .36, W * .62):
        col = _hex("#8C6A3F"); top = H * .2
        d.ellipse((cx - 4 * u, top, cx + 4 * u, top + 9 * u), fill=col)
        d.rounded_rectangle((cx - 7 * u, top + 10 * u, cx + 7 * u, top + 40 * u), 3 * u, fill=col)
        d.rectangle((cx - 6 * u, top + 40 * u, cx - 2 * u, H * .88), fill=col); d.rectangle((cx + 2 * u, top + 40 * u, cx + 6 * u, H * .88), fill=col)
        d.line((cx + 7 * u, top + 13 * u, cx + 14 * u, top + 2 * u), fill=col, width=int(3 * u))
    for _ in range(14):
        x, y, s = rr.uniform(W * .7, W * .95), rr.uniform(H * .2, H * .8), rr.uniform(6, 16) * S
        d.ellipse((x, y, x + s, y + s), outline=_hex("#FFFFFF"), width=3 * S)
    return _fine(im, w, h)

def neve(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; rr = random.Random(r); p = _pal(T)
    for (a, b, c, col) in [(0, .45, .55, "#B9C6E6"), (.35, .2, 1.0, "#D6DEF2")]:
        d.polygon([(W * a, H * .88), (W * (a + b), H * c * .3), (W * min(1, a + 2 * b + .2), H * .88)], fill=_hex(col))
    d.rectangle((0, H * .86, W, H), fill=_hex("#FFFFFF"))
    x = W * .12; d.rectangle((x, H * .66, x + W * .2, H * .86), fill=_hex("#8C6A4F"))
    d.polygon([(x - 20 * S, H * .66), (x + W * .1, H * .52), (x + W * .2 + 20 * S, H * .66)], fill=_hex("#FFFFFF"))
    d.rectangle((x + W * .08, H * .74, x + W * .12, H * .86), fill=_hex(p[0]))
    tx, ty = W * .6, H * .58
    d.polygon([(tx, ty), (tx + W * .3, ty), (tx + W * .3, ty + H * .2), (tx, ty + H * .2), (tx - W * .05, ty + H * .1)], fill=_hex(T["acc"]))
    d.ellipse((tx + 6 * S, ty + H * .09, tx + 18 * S, ty + H * .11), fill=_hex(T["bg"]))
    d.text((tx + W * .15, ty + H * .1), "0% IVA", font=_font(int(H * .08)), fill=_hex(T["bg"]), anchor="mm")
    for _ in range(26):
        sx, sy = rr.uniform(0, W), rr.uniform(0, H * .5); s = rr.uniform(4, 9) * S
        d.ellipse((sx, sy, sx + s, sy + s), fill=_hex("#FFFFFF"))
    return _fine(im, w, h)

def zipline(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; p = _pal(T)
    d.polygon([(0, H), (W * .06, H * .3), (W * .18, H * .22), (W * .3, H * .4), (W * .36, H)], fill=_hex("#9A8F86"))
    d.polygon([(W * .64, H), (W * .72, H * .45), (W * .84, H * .36), (W * .96, H * .5), (W, H)], fill=_hex("#9A8F86"))
    for (x0, y0) in ((W * .08, H * .22), (W * .74, H * .36)):
        for k in range(3):
            d.rectangle((x0 + k * 34 * S, y0 - 40 * S, x0 + k * 34 * S + 26 * S, y0), fill=_hex(VIVID[k]))
    a, b = (W * .2, H * .2), (W * .8, H * .34)
    d.line((a, b), fill=_hex(T["ink"]), width=3 * S)
    t = .45; px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
    d.line((px, py, px, py + 40 * S), fill=_hex(T["ink"]), width=3 * S)
    d.rounded_rectangle((px - 50 * S, py + 40 * S, px + 50 * S, py + 66 * S), 12 * S, fill=_hex(p[0]))
    d.ellipse((px + 46 * S, py + 36 * S, px + 74 * S, py + 64 * S), fill=_hex("#FFE0B8"))
    d.rectangle((0, H * .9, W, H), fill=_hex(T["land"]))
    return _fine(im, w, h)

def casa_euro(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; p = _pal(T)
    d.rectangle((0, H * .88, W, H), fill=_hex(T["land"]))
    x0, x1 = W * .14, W * .58
    d.rectangle((x0, H * .38, x1, H * .88), fill=_hex("#E9D3A6"))
    d.polygon([(x0 - 20 * S, H * .38), ((x0 + x1) / 2, H * .14), (x1 + 20 * S, H * .38)], fill=_hex("#C8553D"))
    for k in range(2):
        d.rectangle((x0 + W * (.05 + k * .24), H * .48, x0 + W * (.12 + k * .24), H * .6), fill=_hex("#7A5C46"))
    d.rectangle(((x0 + x1) / 2 - W * .04, H * .66, (x0 + x1) / 2 + W * .04, H * .88), fill=_hex("#7A5C46"))
    tx, ty = W * .66, H * .32
    d.line((x1 - 10 * S, H * .44, tx + W * .02, ty + H * .1), fill=_hex(T["ink"]), width=3 * S)
    d.polygon([(tx, ty + H * .1), (tx + W * .07, ty), (tx + W * .3, ty), (tx + W * .3, ty + H * .2), (tx + W * .07, ty + H * .2)], fill=_hex(T["acc"]))
    d.text((tx + W * .185, ty + H * .1), "1 €", font=_font(int(H * .11)), fill=_hex(T["bg"]), anchor="mm")
    return _fine(im, w, h)

def cioccolatini(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S
    for k in range(5):
        x = W * (.06 + k * .18); y = H * (.4 if k % 2 else .5); bw, bh = W * .14, H * .3
        d.polygon([(x, y + bh), (x + bw, y + bh), (x + bw * .8, y), (x + bw * .2, y)], fill=_hex("#E2B34B" if k % 2 else "#C9C9D6"))
        d.line((x + bw * .5, y, x + bw * .5, y + bh), fill=_hex("#B88A2A" if k % 2 else "#9A9AAE"), width=3 * S)
    return _fine(im, w, h)

def salsiccia(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S
    d.rounded_rectangle((W * .1, H * .6, W * .9, H * .9), 30 * S, fill=_hex("#C9A46A"))
    cx, cy = W * .5, H * .42
    for k in range(90):
        t = k / 90 * 4 * math.pi; rad = H * (.06 + .055 * t / math.pi)
        x, y = cx + rad * math.cos(t), cy + rad * math.sin(t) * .6
        d.ellipse((x - 22 * S, y - 22 * S, x + 22 * S, y + 22 * S), fill=_hex("#E36F6F"))
    return _fine(im, w, h)

def tartufo(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; rr = random.Random(r)
    d.ellipse((W * .2, H * .78, W * .8, H * .95), fill=_hex(T["land"]))
    cx, cy = W * .5, H * .55
    for _ in range(30):
        a = rr.uniform(0, 2 * math.pi); rad = rr.uniform(0, H * .16); s = rr.uniform(40, 70) * S
        x, y = cx + rad * math.cos(a) * 1.3, cy + rad * math.sin(a)
        d.ellipse((x - s / 2, y - s / 2, x + s / 2, y + s / 2), fill=_hex(rr.choice(["#C9B48A", "#BFA77A", "#D6C399"])))
    for k in range(4):
        x = W * (.12 + k * .25); d.polygon([(x, H * .3), (x + 30 * S, H * .1), (x + 60 * S, H * .3)], fill=_hex("#3DDC97"))
    return _fine(im, w, h)

def alici(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S
    for row in range(3):
        for k in range(4):
            x, y = W * (.04 + k * .14), H * (.25 + row * .2)
            d.ellipse((x, y, x + W * .11, y + H * .07), fill=_hex("#A9B8C9"))
            d.polygon([(x, y + H * .035), (x - W * .03, y), (x - W * .03, y + H * .07)], fill=_hex("#A9B8C9"))
            d.ellipse((x + W * .085, y + H * .02, x + W * .095, y + H * .035), fill=_hex(T["bg"]))
    bx = W * .72
    d.rectangle((bx + W * .07, H * .12, bx + W * .11, H * .25), fill=_hex("#8C6A4F"))
    d.rounded_rectangle((bx, H * .25, bx + W * .18, H * .9), 24 * S, fill=_hex("#C77D1A"))
    d.rectangle((bx + W * .02, H * .45, bx + W * .16, H * .65), fill=_hex("#FFFFFF"))
    return _fine(im, w, h)

def pomodori(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; rr = random.Random(r)
    d.line((W * .1, H * .15, W * .9, H * .15), fill=_hex("#3DDC97"), width=8 * S)
    for k in range(9):
        x = W * (.12 + k * .09); y = H * (.3 + (k % 3) * .17); R = H * .1
        d.line((x, H * .15, x, y - R), fill=_hex("#3DDC97"), width=5 * S)
        d.ellipse((x - R, y - R, x + R, y + R), fill=_hex("#E8423F"))
        d.ellipse((x - R * .5, y - R * .6, x - R * .1, y - R * .3), fill=_hex("#FF8A80"))
    return _fine(im, w, h)

def confetti(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; rr = random.Random(r)
    cols = ["#FFFFFF", "#FFC2D6", "#C9E7FF", "#FFF1A8", "#D9F7E6"]
    for k in range(5):                       # un fiore di confetti
        a = k * 2 * math.pi / 5; cx, cy = W * .3 + math.cos(a) * W * .1, H * .45 + math.sin(a) * H * .18
        d.ellipse((cx - W * .055, cy - H * .07, cx + W * .055, cy + H * .07), fill=_hex(cols[k]))
    d.ellipse((W * .27, H * .41, W * .33, H * .49), fill=_hex(T["acc"]))
    d.line((W * .3, H * .63, W * .3, H * .95), fill=_hex("#3DDC97"), width=8 * S)
    for k in range(10):
        x, y = W * (.55 + (k % 5) * .085), H * (.3 + (k // 5) * .3)
        d.ellipse((x, y, x + W * .07, y + H * .14), fill=_hex(cols[k % 5]))
    return _fine(im, w, h)

def botti(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S
    d.rectangle((0, H * .86, W, H), fill=_hex(T["land"]))
    x = W * .04
    for k in range(5):
        s = 1 - k * .14; bw, bh = W * .22 * s, H * .55 * s
        d.ellipse((x, H * .86 - bh, x + bw, H * .86), fill=_hex("#9C6B3F"))
        for f in (.25, .75): d.line((x + bw * f, H * .86 - bh * .95, x + bw * f, H * .86 - bh * .05), fill=_hex("#5A4632"), width=5 * S)
        x += bw + W * .02
    return _fine(im, w, h)

def prosciutti(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S
    d.line((0, H * .08, W, H * .08), fill=_hex("#8C6A4F"), width=10 * S)
    for k in range(4):
        x = W * (.08 + k * .23)
        d.line((x + W * .07, H * .08, x + W * .07, H * .2), fill=_hex(T["ink"]), width=3 * S)
        d.polygon([(x + W * .05, H * .2), (x + W * .09, H * .2), (x + W * .16, H * .7), (x + W * .07, H * .9), (x - W * .02, H * .7)], fill=_hex("#E9A08E"))
        d.polygon([(x + W * .09, H * .2), (x + W * .16, H * .7), (x + W * .13, H * .78), (x + W * .1, H * .3)], fill=_hex("#FFFFFF"))
    return _fine(im, w, h)

def gnomo(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; rr = random.Random(r)
    d.rectangle((0, H * .88, W, H), fill=_hex("#FFFFFF"))
    bx = W * .62                               # la scatola regalo
    d.rectangle((bx, H * .52, bx + W * .3, H * .88), fill=_hex(T["acc2"] if T["acc2"] != T["bg"] else "#3DDC97"))
    d.rectangle((bx + W * .135, H * .52, bx + W * .165, H * .88), fill=_hex("#FFD23F"))
    d.rectangle((bx - W * .01, H * .46, bx + W * .31, H * .53), fill=_hex(T["acc2"] if T["acc2"] != T["bg"] else "#3DDC97"))
    d.ellipse((bx + W * .1, H * .38, bx + W * .15, H * .47), outline=_hex("#FFD23F"), width=6 * S)
    d.ellipse((bx + W * .15, H * .38, bx + W * .2, H * .47), outline=_hex("#FFD23F"), width=6 * S)
    gx = W * .3                                # lo gnomo
    d.rounded_rectangle((gx - W * .1, H * .55, gx + W * .1, H * .86), 30 * S, fill=_hex("#2E86C1"))
    d.ellipse((gx - W * .12, H * .83, gx - W * .02, H * .9), fill=_hex("#5A4632")); d.ellipse((gx + W * .02, H * .83, gx + W * .12, H * .9), fill=_hex("#5A4632"))
    d.polygon([(gx - W * .11, H * .5), (gx + W * .11, H * .5), (gx, H * .62)], fill=_hex("#FFFFFF"))
    d.polygon([(gx - W * .09, H * .5), (gx + W * .09, H * .5), (gx, H * .8)], fill=_hex("#FFFFFF"))
    d.polygon([(gx - W * .11, H * .44), (gx + W * .11, H * .44), (gx + W * .02, H * .05)], fill=_hex("#C1121F"))
    d.ellipse((gx - W * .03, H * .41, gx + W * .03, H * .5), fill=_hex("#FFB4A2"))
    d.ellipse((gx - 14 * S + W * .02 - 14 * S, H * .03, gx + W * .02 + 14 * S, H * .03 + 28 * S), fill=_hex("#FFFFFF"))
    for _ in range(30):
        x, y, s_ = rr.uniform(0, W), rr.uniform(0, H * .4), rr.uniform(4, 9) * S
        if abs(x - gx) > W * .13 and not (bx - 10 < x < bx + W * .32 and y > H * .36): d.ellipse((x, y, x + s_, y + s_), fill=_hex("#FFFFFF"))
    return _fine(im, w, h)

def ponte_barche(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S
    d.rectangle((0, H * .62, W, H), fill=_hex("#2E86C1"))
    for k in range(4): d.line((0, H * (.7 + k * .08), W, H * (.7 + k * .08)), fill=_hex("#7FC8F8"), width=3 * S)
    x0 = W * .58; d.rectangle((x0, H * .3, x0 + W * .36, H * .62), fill=_hex("#F2E2C0"))       # la basilica
    d.ellipse((x0 + W * .08, H * .08, x0 + W * .28, H * .42), fill=_hex("#E9D3A6"))
    d.rectangle((x0 + W * .08, H * .25, x0 + W * .28, H * .32), fill=_hex("#F2E2C0"))
    for k in range(4): d.rectangle((x0 + W * (.04 + k * .085), H * .4, x0 + W * (.06 + k * .085), H * .62), fill=_hex("#D6C399"))
    for k in range(7):                                                                    # il ponte di barche
        bx = W * (.02 + k * .08); d.ellipse((bx, H * .6, bx + W * .075, H * .68), fill=_hex("#8C6A4F"))
    d.rectangle((0, H * .57, W * .58, H * .61), fill=_hex("#C9A46A"))
    for k in range(8):
        px = W * (.04 + k * .07); d.ellipse((px, H * .47, px + 16 * S, H * .47 + 16 * S), fill=_hex(VIVID[k % 5])); d.rectangle((px, H * .47 + 16 * S, px + 16 * S, H * .57), fill=_hex(VIVID[k % 5]))
    return _fine(im, w, h)

def casa_volante(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S; rr = random.Random(r)
    for _ in range(9):                                                                    # fuochi della Venuta
        cx, cy, R = rr.uniform(W * .05, W * .95), rr.uniform(H * .08, H * .35), rr.uniform(30, 55) * S
        if W * .3 < cx < W * .7 and cy > H * .2: continue
        col = rr.choice(VIVID)
        for k in range(12):
            a = k * math.pi / 6; d.line((cx + math.cos(a) * R * .3, cy + math.sin(a) * R * .3, cx + math.cos(a) * R, cy + math.sin(a) * R), fill=_hex(col), width=3 * S)
    x0, x1 = W * .36, W * .64
    d.rectangle((x0, H * .45, x1, H * .72), fill=_hex("#E9D3A6")); d.polygon([(x0 - 10 * S, H * .45), (W * .5, H * .3), (x1 + 10 * S, H * .45)], fill=_hex("#C8553D"))
    d.rectangle((W * .47, H * .58, W * .53, H * .72), fill=_hex("#7A5C46"))
    for k, sx in enumerate((x0 - W * .12, x1 + W * .02)):                                 # le ali
        d.polygon([(sx, H * .5), (sx + W * .1, H * .46), (sx + W * .1, H * .56)] if k else [(sx + W * .1, H * .5), (sx, H * .46), (sx, H * .56)], fill=_hex("#FFFFFF"))
    for k in range(3):
        fx = W * (.25 + k * .25); d.polygon([(fx, H), (fx + W * .04, H * .8), (fx + W * .08, H)], fill=_hex("#FF8C42")); d.polygon([(fx + W * .02, H), (fx + W * .04, H * .87), (fx + W * .06, H)], fill=_hex("#FFD23F"))
    return _fine(im, w, h)

def candele(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S
    for k in range(7):
        x = W * (.08 + k * .125); top = H * (.35 + (k % 3) * .08)
        d.rectangle((x, top, x + W * .06, H * .9), fill=_hex("#FFFFFF"))
        d.ellipse((x + W * .012, top - H * .12, x + W * .048, top - H * .01), fill=_hex("#FFD23F"))
        d.ellipse((x + W * .022, top - H * .07, x + W * .038, top - H * .02), fill=_hex("#FF8C42"))
    d.rectangle((0, H * .9, W, H), fill=_hex(T["land"]))
    return _fine(im, w, h)

def stretto(T, w, h, r):
    im, d = _tela(w, h); W, H = w * S, h * S
    d.polygon([(0, H * .35), (W * .32, H * .45), (W * .3, H), (0, H)], fill=_hex(T["land"]))
    d.polygon([(W, H * .3), (W * .7, H * .42), (W * .72, H), (W, H)], fill=_hex(T["land"]))
    d.rectangle((W * .3, H * .5, W * .72, H), fill=_hex("#2E86C1"))
    for k in range(5):
        y = H * (.55 + k * .09)
        for x in range(int(W * .3), int(W * .7), 90 * S): d.arc((x, y - 14 * S, x + 90 * S, y + 14 * S), 0, 180, fill=_hex("#7FC8F8"), width=4 * S)
    for k in range(5):
        x = W * (.03 + k * .05); d.rectangle((x, H * .27 + k * H * .015, x + W * .035, H * .4 + k * H * .015), fill=_hex(VIVID[k]))
        x2 = W * (.75 + k * .045); d.rectangle((x2, H * .2 + k * H * .015, x2 + W * .03, H * .33 + k * H * .015), fill=_hex(VIVID[(k + 2) % 7]))
    d.line((W * .08, H * .55, W * .14, H * .66, W * .1, H * .78, W * .17, H * .92), fill=_hex(T["bg"]), width=5 * S)
    return _fine(im, w, h)

MOTIVI = dict(ponte_barche=ponte_barche, casa_volante=casa_volante, candele=candele, stretto=stretto, gnomo=gnomo, fortezza=fortezza, fabbrica=fabbrica, albero_luci=albero_luci, presepe=presepe, sassi=sassi, trulli=trulli,
              mare_bronzi=mare_bronzi, neve=neve, zipline=zipline, casa_euro=casa_euro, cioccolatini=cioccolatini,
              salsiccia=salsiccia, tartufo=tartufo, alici=alici, pomodori=pomodori, confetti=confetti, botti=botti, prosciutti=prosciutti)

def disegna(motivo, T, w, h, seme=0):
    f = MOTIVI.get(motivo)
    return f(T, w, h, seme) if f else None
