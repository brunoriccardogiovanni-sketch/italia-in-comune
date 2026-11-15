"""Città stilizzate generate dal codice: ogni comune ha la sua (seme = nome).
Dimensione dell'abitato dalla popolazione; mare se costiero; montagne se alpino."""
import math, random, hashlib
from PIL import Image, ImageDraw

VIVID = ["#FF3E7F", "#FFD23F", "#2EC4F1", "#7B61FF", "#FF8C42", "#FFFFFF", "#3DDC97"]
ROOF = ["#C8553D", "#A23E48", "#E07A5F"]
ALPINE = {"AO", "BZ", "TN", "BL", "SO", "VB"}
LANDLOCKED = {"Valle d'Aosta/Vallée d'Aoste", "Piemonte", "Lombardia", "Trentino-Alto Adige/Südtirol", "Umbria"}

def tag_comuni(comuni, regioni):
    import shapely
    italy = shapely.union_all(regioni).buffer(0); edge = italy.boundary
    udine = next((c for c in comuni if c["nome"] == "Udine"), None)
    for c in comuni:
        coast = c["reg"] not in LANDLOCKED and c["prov"] not in {"BL", "BZ", "TN", "SO", "VB", "AO"} and c["geom"].distance(edge) < 300
        if coast and c["prov"] == "UD" and udine and c["geom"].centroid.y > udine["geom"].centroid.y: coast = False
        c["coast"] = coast; c["alpine"] = c["prov"] in ALPINE

def _hex(h, a=255): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)

def city(c, T, w=1000, h=620):
    S = 2; W, H = w * S, h * S
    rnd = random.Random(int(hashlib.md5(c["nome"].encode()).hexdigest(), 16))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    pal = [x for x in VIVID if x.lower() != T["bg"].lower() and x.lower() != T["acc"].lower()]
    ground = H - (int(H * 0.2) if c.get("coast") else int(H * 0.08))
    # sole
    r = int(H * 0.11); sx = rnd.randint(int(W * .55), int(W * .85)); sy = int(H * rnd.uniform(.12, .25))
    d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=_hex(T["acc"]))
    # montagne o colline
    if c.get("alpine"):
        x = -100
        while x < W:
            mw = rnd.randint(int(W * .25), int(W * .45)); mh = rnd.randint(int(H * .35), int(H * .6))
            d.polygon([(x, ground), (x + mw // 2, ground - mh), (x + mw, ground)], fill=_hex(T["land"]))
            d.polygon([(x + mw // 2, ground - mh), (x + mw // 2 - mw // 9, ground - mh + mh // 4), (x + mw // 2 + mw // 9, ground - mh + mh // 4)], fill=(255, 255, 255, 255))
            x += int(mw * .6)
    else:
        for k in range(2):
            pts = [(0, H)]; base = ground - int(H * (.18 + .1 * k))
            for i in range(0, W + 40, 40): pts.append((i, base + int(math.sin(i / W * math.pi * rnd.uniform(1.5, 3) + rnd.random() * 6) * H * .05)))
            pts.append((W, H)); d.polygon(pts, fill=_hex(T["land"], 255 if k else 150))
    # edifici: quanti dipende dagli abitanti
    pop = c.get("pop") or 2000
    n = max(5, min(22, int(3 * math.log10(pop + 10))))
    spots = sorted(rnd.uniform(0.04, 0.9) for _ in range(n))
    specials = rnd.sample(range(n), k=min(n, 2 if pop < 20000 else 3))
    for i, fx in enumerate(spots):
        x = int(fx * W); bw = rnd.randint(int(W * .07), int(W * .12)); bh = rnd.randint(int(H * .15), int(H * (.3 + .25 * math.log10(pop + 10) / 6)))
        col = _hex(rnd.choice(pal)); win = _hex(T["bg"])
        kind = ("campanile" if i == specials[0] else "cupola" if len(specials) > 1 and i == specials[1] else "torre" if len(specials) > 2 and i == specials[2] else "casa")
        if kind == "campanile":
            tw = int(bw * .55); th = int(H * .55)
            d.rectangle((x, ground - th, x + tw, ground), fill=col)
            d.rectangle((x + tw // 4, ground - th + tw // 2, x + tw * 3 // 4, ground - th + tw * 3 // 2), fill=win)
            d.polygon([(x - 6, ground - th), (x + tw // 2, ground - th - tw), (x + tw + 6, ground - th)], fill=_hex(rnd.choice(ROOF)))
        elif kind == "cupola":
            cw = int(bw * 1.4); ch = int(H * .28)
            d.rectangle((x, ground - ch, x + cw, ground), fill=col)
            d.pieslice((x, ground - ch - cw // 2, x + cw, ground - ch + cw // 2), 180, 360, fill=_hex(rnd.choice(ROOF)))
            d.rectangle((x + cw // 2 - 8, ground - ch - cw // 2 - 40, x + cw // 2 + 8, ground - ch - cw // 2), fill=col)
            for k in range(3): d.rounded_rectangle((x + cw * (k + 1) // 4 - 12, ground - ch * .7, x + cw * (k + 1) // 4 + 12, ground - ch * .3), 12, fill=win)
        elif kind == "torre":
            tw = int(bw * .7); th = int(H * .5)
            d.rectangle((x, ground - th, x + tw, ground), fill=col)
            for k in range(4): d.rectangle((x + k * tw // 4, ground - th - 26, x + k * tw // 4 + tw // 8, ground - th), fill=col)
        else:
            d.rectangle((x, ground - bh, x + bw, ground), fill=col)
            d.polygon([(x - 8, ground - bh), (x + bw // 2, ground - bh - int(bw * .35)), (x + bw + 8, ground - bh)], fill=_hex(rnd.choice(ROOF)))
            ww = max(10, bw // 6)
            for yy in range(ground - bh + ww * 2, ground - ww * 2, ww * 3):
                for xx in (x + bw // 4 - ww // 2, x + 3 * bw // 4 - ww // 2):
                    d.rectangle((xx, yy, xx + ww, yy + int(ww * 1.5)), fill=win)
            d.rounded_rectangle((x + bw // 2 - ww, ground - ww * 3, x + bw // 2 + ww, ground), ww, fill=win)
    # cipressi o abeti
    for _ in range(rnd.randint(2, 5)):
        x = rnd.randint(0, W); th = rnd.randint(int(H * .12), int(H * .22)); tw = th // 4
        green = (31, 92, 70, 255)
        if c.get("alpine"): d.polygon([(x - tw, ground), (x, ground - th), (x + tw, ground)], fill=green)
        else: d.ellipse((x - tw // 2, ground - th, x + tw // 2, ground + 10), fill=green)
    # terreno e mare
    d.rectangle((0, ground, W, ground + 12), fill=_hex(T["ink"]))
    if c.get("coast"):
        sea = _hex("#2EC4F1" if T["bg"].lower() != "#2ec4f1" else "#1A1446")
        d.rectangle((0, ground + 12, W, H), fill=sea)
        for k in range(3):
            y = ground + 50 + k * 60
            for x0 in range(rnd.randint(0, 80), W, 160): d.arc((x0, y, x0 + 80, y + 30), 200, 340, fill=(255, 255, 255, 200), width=6)
        bx = rnd.randint(int(W * .1), int(W * .7)); by = ground + 40
        d.polygon([(bx, by), (bx + 120, by), (bx + 95, by + 34), (bx + 25, by + 34)], fill=_hex("#FFFFFF"))
        d.polygon([(bx + 55, by - 90), (bx + 55, by - 4), (bx + 110, by - 4)], fill=_hex(T["acc2"] if T["acc2"].lower() != T["bg"].lower() else "#FF3E7F"))
    return img.resize((w, h), Image.LANCZOS)
