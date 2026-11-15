"""Città stilizzate generate dal codice: ogni comune ha la sua (seme = nome).
Regola fissa: nessun elemento si sovrappone a un altro. Edifici e alberi stanno in fila
con uno spazio tra l'uno e l'altro; il sole sta nel cielo libero sopra lo skyline;
la barca sta sul mare. Colline e montagne sono solo lo sfondo basso, sotto la linea dei tetti."""
import math, random, hashlib
from PIL import Image, ImageDraw

VIVID = ["#FF3E7F", "#FFD23F", "#2EC4F1", "#7B61FF", "#FF8C42", "#FFFFFF", "#3DDC97"]
ROOF = ["#C8553D", "#A23E48", "#E07A5F"]
ALPINE = {"AO", "BZ", "TN", "BL", "SO", "VB"}
LANDLOCKED = {"Valle d'Aosta/Vallée d'Aoste", "Piemonte", "Lombardia", "Trentino-Alto Adige/Südtirol", "Umbria"}
GREEN = (31, 92, 70, 255)

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
    pal = [x for x in VIVID if x.lower() not in (T["bg"].lower(), T["acc"].lower())]
    coast = bool(c.get("coast")); alpine = bool(c.get("alpine"))
    ground = H - (int(H * .2) if coast else int(H * .06))
    pop = c.get("pop") or 2000
    sky_top = int(H * .30)                      # i tetti non salgono oltre: sopra resta il cielo per il sole
    maxb = ground - sky_top

    # ---- elementi in fila: edifici e alberi, ognuno nel suo spazio
    n = max(4, min(12, int(2.2 * math.log10(pop + 10))))
    kinds = ["casa"] * n
    for k, kind in zip(rnd.sample(range(n), min(n, 3 if pop >= 20000 else 2)), ["campanile", "cupola", "torre"]): kinds[k] = kind
    items = []
    for kind in kinds:
        items.append(kind)
        if rnd.random() < .35: items.append("albero")
    widths = {"casa": (.075, .11), "campanile": (.045, .06), "cupola": (.13, .16), "torre": (.06, .08), "albero": (.03, .04)}
    ws = [rnd.uniform(*widths[k]) * W for k in items]
    gap = W * .018; margin = W * .03
    scale = min(1.0, (W - 2 * margin - gap * (len(items) - 1)) / sum(ws))
    ws = [x * scale for x in ws]
    used = sum(ws) + gap * (len(items) - 1); x = (W - used) / 2
    slots = []
    for k, bw in zip(items, ws):
        if k == "campanile": bh = maxb * rnd.uniform(.85, 1.0)
        elif k == "torre": bh = maxb * rnd.uniform(.7, .85)
        elif k == "cupola": bh = maxb * rnd.uniform(.75, .9)       # comprende la cupola
        elif k == "albero": bh = maxb * rnd.uniform(.3, .45)
        else: bh = maxb * rnd.uniform(.35, .3 + .4 * min(1, math.log10(pop + 10) / 6))
        slots.append((k, int(x), int(bw), int(bh))); x += bw + gap

    # ---- sfondo basso: colline o montagne, sempre sotto il tetto più basso degli edifici
    lowest = min(bh for k, _, _, bh in slots if k != "albero")
    bg_top = ground - int(lowest * .55)
    if alpine:
        xx = -int(W * .05)
        while xx < W:
            mw = rnd.randint(int(W * .22), int(W * .34)); mh = ground - bg_top
            d.polygon([(xx, ground), (xx + mw // 2, ground - mh), (xx + mw, ground)], fill=_hex(T["land"]))
            d.polygon([(xx + mw // 2, ground - mh), (xx + mw // 2 - mw // 10, ground - mh + mh // 4), (xx + mw // 2 + mw // 10, ground - mh + mh // 4)], fill=(255, 255, 255, 255))
            xx += mw
    else:
        pts = [(0, ground)]; ph = rnd.random() * 6; fq = rnd.uniform(1.5, 3)
        for i in range(0, W + 40, 40):
            pts.append((i, bg_top + int((math.sin(i / W * math.pi * fq + ph) + 1) / 2 * (ground - bg_top) * .5)))
        pts.append((W, ground)); d.polygon(pts, fill=_hex(T["land"]))

    # ---- edifici e alberi
    win = _hex(T["bg"])
    for k, x, bw, bh in slots:
        col = _hex(rnd.choice(pal)); roof = _hex(rnd.choice(ROOF)); top = ground - bh
        if k == "albero":
            if alpine: d.polygon([(x, ground), (x + bw // 2, top), (x + bw, ground)], fill=GREEN)
            else: d.ellipse((x, top, x + bw, ground + 4), fill=GREEN)
        elif k == "campanile":
            rh = int(bw * .9); body = top + rh
            d.rectangle((x, body, x + bw, ground), fill=col)
            d.polygon([(x, body), (x + bw // 2, top), (x + bw, body)], fill=roof)
            d.rectangle((x + bw // 4, body + bw // 3, x + 3 * bw // 4, body + bw), fill=win)
        elif k == "cupola":
            dome = bw // 2; lantern = int(bw * .18); body = top + lantern + dome
            d.rectangle((x, body, x + bw, ground), fill=col)
            d.pieslice((x, body - dome, x + bw, body + dome), 180, 360, fill=roof)
            d.rectangle((x + bw // 2 - bw // 20, top, x + bw // 2 + bw // 20, body - dome), fill=col)
            for j in range(3):
                cx = x + bw * (j + 1) // 4; d.rounded_rectangle((cx - bw // 16, body + (ground - body) * .25, cx + bw // 16, body + (ground - body) * .65), bw // 16, fill=win)
        elif k == "torre":
            mer = int(bw * .22); body = top + mer
            d.rectangle((x, body, x + bw, ground), fill=col)
            for j in range(4): d.rectangle((x + j * bw // 4 + bw // 32, top, x + j * bw // 4 + bw // 8 + bw // 32, body), fill=col)
            d.rectangle((x + bw // 3, body + mer * 2, x + 2 * bw // 3, body + mer * 4), fill=win)
        else:
            rh = int(bw * .3); body = top + rh
            d.rectangle((x, body, x + bw, ground), fill=col)
            d.polygon([(x, body), (x + bw // 2, top), (x + bw, body)], fill=roof)
            ww = max(8, bw // 6)
            for yy in range(body + ww * 2, ground - ww * 3, ww * 3):
                for xx in (x + bw // 4 - ww // 2, x + 3 * bw // 4 - ww // 2): d.rectangle((xx, yy, xx + ww, yy + int(ww * 1.5)), fill=win)
            d.rectangle((x + bw // 2 - ww, ground - ww * 3, x + bw // 2 + ww, ground), fill=win)

    # ---- sole: nel cielo, lontano da qualunque tetto
    r = int(H * .09); placed = False
    for _ in range(60):
        sx = rnd.randint(r + int(W * .05), W - r - int(W * .05)); sy = rnd.randint(r + 10, max(r + 11, sky_top - r - 10))
        under = [ground - bh for k, x, bw, bh in slots if x < sx + r + 20 and x + bw > sx - r - 20]
        roofline = min(under + [bg_top])
        if sy + r + 20 < roofline: placed = True; break
    if placed: d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=_hex(T["acc"]))

    # ---- terreno e mare
    d.rectangle((0, ground, W, ground + 12), fill=_hex(T["ink"]))
    if coast:
        sea = _hex("#2EC4F1" if T["bg"].lower() != "#2ec4f1" else "#1A1446")
        d.rectangle((0, ground + 12, W, H), fill=sea)
        bx = rnd.randint(int(W * .55), int(W * .8)); by = ground + 80
        for k in range(3):
            y = ground + 40 + k * 55
            for x0 in range(rnd.randint(0, 60), int(W * .48), 150): d.arc((x0, y, x0 + 70, y + 26), 200, 340, fill=(255, 255, 255, 200), width=6)
        d.polygon([(bx, by), (bx + 120, by), (bx + 95, by + 34), (bx + 25, by + 34)], fill=_hex("#FFFFFF"))
        d.polygon([(bx + 55, by - 50), (bx + 55, by - 4), (bx + 105, by - 4)], fill=_hex(T["acc2"] if T["acc2"].lower() != T["bg"].lower() else "#FF3E7F"))
    return img.resize((w, h), Image.LANCZOS)
