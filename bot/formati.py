"""Tutti i formati di contenuto. Ogni funzione genera i file in `out` e restituisce
dict(tipo="reel"|"carosello"|"immagine", file=[...], didascalia=str)."""
import os, random, subprocess, bisect
from PIL import Image, ImageDraw
from .base import *
from .city import city

W, H = 1080, 1350            # post 4:5
VW, VH, FPS = 1080, 1920, 30  # reel 9:16
ease = lambda t: 1 - (1 - max(0, min(1, t))) ** 3
HASHTAG = "#italiaincomune #comuniitaliani #borghiitaliani #italia #curiosità #geografia"

# ---------------------------------------------------------------- utilità comuni
def canvas(T, w=W, h=H): return Image.new("RGB", (w, h), T["bg"])
def footer(img, T, n=None, tot=None, fonte="Fonte: ISTAT, openpolis"):
    d = ImageDraw.Draw(img)
    pill(img, HANDLE, (60, img.height - 110), font("b", 28), T["ink"], T["bg"])
    d.text((img.width - 60, img.height - 84), fonte, font=font("m", 22), fill=T["muted"], anchor="ra")
    if n: d.text((img.width - 60, 60), f"{n}/{tot}", font=font("b", 28), fill=T["muted"], anchor="ra")
def save(img, out, name):
    p = os.path.join(out, name + ".png"); img.convert("RGB").save(p); return p
def encode(path, frames):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}", "-r", str(FPS), "-i", "-",
                          "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                          "-movflags", "+faststart", path], stdin=subprocess.PIPE)
    for f in frames: p.stdin.write(f.convert("RGB").tobytes())
    p.stdin.close(); p.wait(); return path
def vhandle(img, T): pill(img, HANDLE, (60, 150), font("b", 34), T["ink"], T["bg"])
def label(c): return f"{c['prov']} · {c['reg'].split('/')[0]}"
def nome(c): return c["nome"].split("/")[0]

# ---------------------------------------------------------------- classifiche
def _area(c):
    a = c["area"]; return f"{fmt(a)} km²" if a >= 10 else f"{a:.2f} km²".replace(".", ",")
METRICHE = {
    "area_max": dict(titolo="I 10 comuni più grandi d'Italia", sotto="per superficie", key=lambda c: -c["area"], val=_area,
                     gancio="Il 2° non è Milano", fonte="Fonte: ISTAT, openpolis"),
    "area_min": dict(titolo="I 10 comuni più piccoli d'Italia", sotto="per superficie", key=lambda c: c["area"], val=_area,
                     gancio="Il n.1 sta in un chilometro quadrato?", fonte="Fonte: ISTAT, openpolis"),
    "dens_max": dict(titolo="I 10 comuni più affollati d'Italia", sotto="abitanti per km²", key=lambda c: -(c["pop"] or 0) / c["area"],
                     val=lambda c: f"{fmt(c['pop'] / c['area'])} ab/km²", gancio="Napoli non è prima", fonte="Fonte: ISTAT 2011, openpolis"),
}
def top10(metrica):
    comuni, _ = load(); return sorted(comuni, key=METRICHE[metrica]["key"])[:10]

def carosello_classifica(metrica, out):
    M = METRICHE[metrica]; big = top10(metrica); TOT = 12; files = []
    T = THEMES["giallo"]; img = canvas(T); d = ImageDraw.Draw(img)
    pill(img, "CLASSIFICA", (60, 80), font("k", 30), T["acc"], "#FFFFFF")
    y = text_block(img, M["titolo"], (60, 170), fit_font(img, M["titolo"], "k", W - 120, 3, 92), T["ink"], W - 120, 1.02)
    pill(img, M["sotto"], (60, y + 20), font("x", 34), T["ink"], T["bg"])
    hl = big[0]["geom"].union(big[1]["geom"])
    place(img, draw_map(T, highlight=hl, px=900), W // 2 + 120, y + 110, 700, H - y - 260)
    d.text((W - 60, H - 170), "scorri  →", font=font("k", 40), fill=T["acc"], anchor="ra")
    footer(img, T, 1, TOT, M["fonte"]); files.append(save(img, out, "01"))
    for i, c in enumerate(reversed(big)):
        T = THEMES[CYCLE[(i + 2) % 3]]; rank = 10 - i
        img = canvas(T); d = ImageDraw.Draw(img)
        d.text((60, 70), f"#{rank}", font=font("k", 200), fill=T["acc"])
        place(img, draw_map(T, highlight=c["geom"], point=c["ll_m"] if "ll_m" in c else c["geom"].centroid, px=500), 870, 60, 300, 330)
        y = text_block(img, nome(c), (60, 330), fit_font(img, nome(c), "k", W - 120, 2, 84), T["ink"], W - 120, 1.0)
        d.text((60, y + 8), label(c), font=font("b", 30), fill=T["muted"])
        pill(img, M["val"](c), (60, y + 70), font("k", 50), T["ink"], T["bg"])
        ci = city(c, T, 1080, 540); img.paste(ci, (0, H - 150 - 540), ci)
        footer(img, T, i + 2, TOT, M["fonte"]); files.append(save(img, out, f"{i + 2:02d}"))
    T = THEMES["rosa"]; img = canvas(T); d = ImageDraw.Draw(img)
    y = text_block(img, "E il tuo comune in che posizione è?", (60, 330), font("k", 92), T["ink"], W - 120, 1.02)
    pill(img, "Scrivilo nei commenti", (60, y + 50), font("k", 44), T["acc"], T["acc2"])
    d.text((60, y + 160), "ti mandiamo la sua scheda in DM", font=font("b", 36), fill=T["ink"])
    footer(img, T, TOT, TOT, M["fonte"]); files.append(save(img, out, "12"))
    lista = "\n".join(f"{10 - i}. {nome(c)} ({c['prov']}) – {M['val'](c)}" for i, c in enumerate(reversed(big)))
    cap = (f"{M['titolo']} ({M['sotto']}) 🇮🇹\n\n{lista}\n\nScrivi il nome del tuo comune nei commenti: "
           f"ti mandiamo in DM la sua scheda 📩\n\n{M['fonte']}\n\n{HASHTAG}")
    return dict(tipo="carosello", file=files, didascalia=cap)

def reel_countdown(metrica, out):
    M = METRICHE[metrica]; order = list(reversed(top10(metrica)))
    maps = [draw_map(THEMES[CYCLE[(i + 1) % 3]], highlight=c["geom"], point=c["geom"].centroid, px=380) for i, c in enumerate(order)]
    cities = [city(c, THEMES[CYCLE[(i + 1) % 3]], 1080, 640) for i, c in enumerate(order)]
    def frames():
        T = THEMES["indaco"]
        for f in range(int(2.2 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T)
            y = text_block(img, M["titolo"], (70, 520 + int(80 * (1 - ease(t / .5)))), fit_font(img, M["titolo"], "k", VW - 140, 4, 120), T["ink"], VW - 140, 1.0)
            if t > .8: pill(img, M["gancio"], (70, y + 50), font("k", 50), T["acc"], T["bg"])
            if t > 1.4: ImageDraw.Draw(img).text((70, y + 180), f"({M['sotto']})", font=font("b", 42), fill=T["muted"])
            yield img
        for i, c in enumerate(order):
            T = THEMES[CYCLE[(i + 1) % 3]]; rank = 10 - i; dur = 1.4 if rank > 3 else 2.0
            for f in range(int(dur * FPS)):
                t = f / FPS; e = ease(t / .45); img = canvas(T, VW, VH); d = ImageDraw.Draw(img); vhandle(img, T)
                img.paste(maps[i], (VW - maps[i].width - 40, 250 - int(40 * (1 - e))), maps[i])
                rise = ease((t - .15) / .6); box = Image.new("RGBA", (1080, 640), (0, 0, 0, 0))
                box.paste(cities[i], (0, int(640 * (1 - rise))), cities[i]); img.paste(box, (0, 1000), box)
                d.text((70 - int(300 * (1 - e)), 260), f"#{rank}", font=font("k", 240), fill=T["acc"])
                y = text_block(img, nome(c), (70, 560), fit_font(img, nome(c), "k", VW - 140, 2, 100), T["ink"], VW - 140, 1.0)
                d.text((70, y + 10), label(c), font=font("b", 40), fill=T["muted"])
                pill(img, M["val"](c), (70, y + 80), font("k", 58), T["ink"], T["bg"])
                yield img
        T = THEMES["rosa"]
        for f in range(int(3 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T)
            y = text_block(img, "E il tuo comune in che posizione è?", (70, 560), font("k", 108), T["ink"], VW - 140, 1.0)
            if t > .5: pill(img, "Scrivilo nei commenti", (70, y + 60), font("k", 56), T["acc"], T["acc2"])
            if t > 1: ImageDraw.Draw(img).text((70, y + 190), "ti mandiamo la sua scheda in DM", font=font("b", 42), fill=T["ink"])
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames())
    n1 = order[-1]
    cap = (f"{M['titolo']} ({M['sotto']}) — al primo posto {nome(n1)} ({n1['prov']}) con {M['val'](n1)}. Te lo aspettavi?\n\n"
           f"Scrivi il tuo comune nei commenti: ti mandiamo la sua scheda in DM 📩\n\n{M['fonte']}\n\n{HASHTAG}")
    return dict(tipo="reel", file=[path], didascalia=cap)

# ---------------------------------------------------------------- mappe che si riempiono
SANTI = ("san ", "santa ", "santo ", "sant ", "santi ", "santo stefano")
MAPPE = {
    "sotto1000": dict(f=lambda c: c["pop"] is not None and c["pop"] < 1000, testo="comuni hanno meno di 1.000 abitanti",
                      domanda="Quanti comuni hanno meno di 1.000 abitanti?", cta="Il tuo è tra questi?", fonte="Fonte: ISTAT, censimento 2011"),
    "mare": dict(f=lambda c: c.get("coast"), testo="comuni si affacciano sul mare", domanda="Quanti comuni italiani hanno il mare?",
                 cta="Il tuo ha il mare?", fonte="Elaborazione su confini openpolis"),
    "santi": dict(f=lambda c: norm(c["nome"]).startswith(SANTI), testo="comuni portano il nome di un santo",
                  domanda="Quanti comuni portano il nome di un santo?", cta="Qual è il santo del tuo comune?", fonte="Fonte: ISTAT, openpolis"),
    "monte": dict(f=lambda c: norm(c["nome"]).startswith("monte") or " monte" in " " + norm(c["nome"]), testo="comuni hanno «Monte» nel nome",
                  domanda="Quanti comuni hanno «Monte» nel nome?", cta="Il tuo è tra questi?", fonte="Fonte: ISTAT, openpolis"),
}
def reel_mappa(chiave, out):
    M = MAPPE[chiave]; T = THEMES["indaco"]; px = 980; comuni, _ = load()
    sel = [c for c in comuni if M["f"](c)]
    base = draw_map(T, px=px); full = draw_map(T, color_fn=lambda c: T["acc"] if M["f"](c) else None, px=px)
    x0, y0, x1, y1 = map_bounds()
    ys = sorted((y1 - c["geom"].centroid.y) / (y1 - y0) * full.height for c in sel)
    mx, my = (VW - px) // 2 + 30, 640
    def frames():
        intro, sweep, hold = 1.8, 6.0, 3.2
        for f in range(int((intro + sweep + hold) * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); d = ImageDraw.Draw(img); vhandle(img, T)
            u = max(0, min(1, (t - intro) / sweep)); s = u * u * (3 - 2 * u)
            line = int(s * full.height); cnt = bisect.bisect_right(ys, line)
            if t < intro: text_block(img, M["domanda"], (70, 300), font("k", 80), T["ink"], VW - 140, 1.04)
            else:
                d.text((70, 260), fmt(cnt), font=font("k", 190), fill=T["acc"])
                text_block(img, M["testo"], (70, 500), font("b", 44), T["ink"], VW - 140)
            img.paste(base, (mx, my), base)
            if line > 0:
                part = full.crop((0, 0, full.width, line)); img.paste(part, (mx, my), part)
                if s < .99: d.line((mx, my + line, mx + full.width, my + line), fill=T["acc2"], width=6)
            if t > intro + sweep + .3: pill(img, M["cta"], (70, VH - 430), font("k", 56), T["acc2"], "#FFFFFF")
            d.text((VW - 70, VH - 140), M["fonte"], font=font("m", 28), fill=T["muted"], anchor="ra")
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames())
    cap = (f"{fmt(len(sel))} {M['testo']} 🇮🇹 {M['cta']}\n\nScrivi il tuo comune nei commenti: ti mandiamo la sua scheda in DM 📩\n\n"
           f"{M['fonte']}\n\n{HASHTAG}")
    return dict(tipo="reel", file=[path], didascalia=cap)

# ---------------------------------------------------------------- scheda del comune (DM e "comune del giorno")
def stats(c):
    comuni, _ = load(); reg = [x for x in comuni if x["reg"] == c["reg"]]; rk = 1 + sum(x["area"] > c["area"] for x in reg)
    pos = "il più piccolo" if rk == len(reg) else "il più grande" if rk == 1 else f"{rk}° su {len(reg)}"
    rows = [(fmt(c["pop"]) if c["pop"] else "n.d.", "abitanti (censimento 2011)"), (_area(c), "di superficie"),
            (fmt(c["pop"] / c["area"]) if c["pop"] else "n.d.", "abitanti per km²"), (pos, f"per estensione in {c['reg'].split('/')[0]}")]
    return rows
def scheda(c, path, T=None):
    T = T or THEMES["indaco"]; img = canvas(T); d = ImageDraw.Draw(img)
    pill(img, "LA SCHEDA DEL TUO COMUNE", (60, 70), font("k", 28), T["acc2"], "#FFFFFF")
    y = text_block(img, nome(c), (60, 150), fit_font(img, nome(c), "k", 700, 2, 104), T["acc"], 700, 1.0)
    d.text((60, y + 10), label(c), font=font("b", 34), fill=T["muted"])
    place(img, draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=800), 840, y + 80, 360, 420)
    yy = y + 100
    for v, k in stats(c):
        d.text((60, yy), v, font=font("k", 50), fill=T["ink"]); d.text((60, yy + 62), k, font=font("m", 24), fill=T["muted"]); yy += 116
    ci = city(c, T, 1080, 380); img.paste(ci, (0, H - 140 - 380), ci)
    footer(img, T); img.convert("RGB").save(path); return path

def reel_comune(c, out):
    T = THEMES[random.Random(c["nome"]).choice(CYCLE)]
    ci = city(c, T, 1080, 480); m = draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=420); rows = stats(c)
    def frames():
        for f in range(int(9 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); d = ImageDraw.Draw(img); vhandle(img, T)
            pill(img, "IL COMUNE DEL GIORNO" if t < 6.2 else "IL PROSSIMO PUÒ ESSERE IL TUO: SCRIVILO!", (70, 260), font("k", 30), T["acc2"], "#FFFFFF")
            e = ease(t / .6); y = text_block(img, nome(c), (70 - int(200 * (1 - e)), 360), fit_font(img, nome(c), "k", VW - 140, 2, 120), T["acc"], VW - 140, 1.0)
            d.text((70, y + 10), label(c), font=font("b", 42), fill=T["muted"])
            img.paste(m, (VW - m.width - 40, y + 90), m)
            for i, (v, k) in enumerate(rows):
                if t > 1.2 + i * .9:
                    yy = y + 110 + i * 140; d.text((70, yy), v, font=font("k", 56), fill=T["ink"]); d.text((70, yy + 72), k, font=font("m", 30), fill=T["muted"])
            rise = ease((t - .3) / 1.2); box = Image.new("RGBA", (1080, 480), (0, 0, 0, 0))
            box.paste(ci, (0, int(480 * (1 - rise))), ci); img.paste(box, (0, VH - 480 - 60), box)
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames())
    cap = (f"Il comune del giorno è {nome(c)} ({c['prov']}, {c['reg'].split('/')[0]}) 📍\n\n" +
           "\n".join(f"• {v} {k}" for v, k in rows) +
           f"\n\nQuale comune vuoi vedere domani? Scrivilo nei commenti 👇\n\nFonte: ISTAT (censimento 2011), openpolis\n\n{HASHTAG}")
    return dict(tipo="reel", file=[path], didascalia=cap)

# ---------------------------------------------------------------- sfida: chi è più grande?
def coppia(seed):
    comuni, _ = load(); r = random.Random(seed)
    for _ in range(500):
        a = r.choice(comuni); cand = [b for b in comuni if b["reg"] == a["reg"] and b is not a and .7 < b["area"] / a["area"] < 1.4 and abs(b["area"] - a["area"]) > .5]
        if cand: return a, r.choice(cand)
    return comuni[0], comuni[1]
def reel_sfida(a, b, out):
    T = THEMES["giallo"]; ca, cb = city(a, THEMES["rosa"], 540, 420), city(b, THEMES["indaco"], 540, 420)
    win = a if a["area"] > b["area"] else b
    def frames():
        for f in range(int(10 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); d = ImageDraw.Draw(img); vhandle(img, T)
            text_block(img, "Chi è più grande?", (70, 260), font("k", 96), T["ink"], VW - 140, 1.0)
            for i, (c, ci, TT) in enumerate([(a, ca, THEMES["rosa"]), (b, cb, THEMES["indaco"])]):
                x = i * 540; d.rectangle((x, 520, x + 540, 1420), fill=TT["bg"])
                img.paste(ci, (x, 1000), ci)
                text_block(img, nome(c), (x + 40, 560), fit_font(img, nome(c), "k", 460, 3, 64), TT["ink"], 460, 1.0)
                d.text((x + 40, 800), c["prov"], font=font("b", 36), fill=TT["muted"])
                if t > 6:
                    pill(img, _area(c), (x + 40, 870), font("k", 44), TT["ink"], TT["bg"])
                    if c is win: pill(img, "VINCE!", (x + 40, 960), font("k", 40), T["bg"], T["ink"])
            d.text((VW // 2, 1440), "VS", font=font("k", 80), fill=T["ink"], anchor="ma")
            if 2.5 < t < 5.5: d.text((VW // 2, 1560), str(3 - int(t - 2.5)), font=font("k", 140), fill=T["acc"], anchor="ma")
            elif t <= 2.5: d.text((VW // 2, 1580), "Scrivi la tua risposta prima del via!", font=font("b", 34), fill=T["ink"], anchor="ma")
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames())
    cap = (f"Sfida: chi è più grande tra {nome(a)} e {nome(b)} ({a['reg'].split('/')[0]})? 🤔\n\nHai indovinato? Vince {nome(win)} con {_area(win)}.\n\n"
           f"Proponi la prossima sfida tra due comuni nei commenti 👇\n\nFonte: elaborazione su confini openpolis\n\n{HASHTAG}")
    return dict(tipo="reel", file=[path], didascalia=cap)

# ---------------------------------------------------------------- caroselli narrativi: storie e cibo
def carosello_racconto(item, out, etichetta, cta, extra_tag=""):
    c = find(item["comune"], item.get("prov")); files = []
    slides = item["slide"]; TOT = len(slides) + 3
    T = THEMES["indaco"]; img = canvas(T); d = ImageDraw.Draw(img)
    pill(img, etichetta, (60, 80), font("k", 28), T["acc2"], "#FFFFFF")
    y = text_block(img, item["titolo"], (60, 170), fit_font(img, item["titolo"], "k", W - 120, 4, 84), T["ink"], W - 120, 1.04)
    d.text((60, y + 20), f"{nome(c)} · {label(c)}", font=font("b", 34), fill=T["acc"])
    ci = city(c, T, 1080, 560); img.paste(ci, (0, H - 150 - 560), ci)
    d.text((W - 60, H - 175), "scorri  →", font=font("k", 34), fill=T["acc"], anchor="ra")
    footer(img, T, 1, TOT, item.get("fonte_breve", "")); files.append(save(img, out, "01"))
    for i, s in enumerate(slides):
        T = THEMES[CYCLE[(i + 1) % 3]]; img = canvas(T); d = ImageDraw.Draw(img)
        d.text((60, 70), nome(c).upper(), font=font("b", 28), fill=T["muted"])
        if s.get("numero"): d.text((60, 170), s["numero"], font=font("k", 170), fill=T["acc"]); y0 = 400
        else: y0 = 220
        text_block(img, s["testo"], (60, y0), fit_font(img, s["testo"], "x", W - 120, 7 if not s.get("numero") else 5, 64), T["ink"], W - 120, 1.25)
        strip = city(dict(c, nome=c["nome"] + str(i)), T, 1080, 300); img.paste(strip, (0, H - 140 - 300), strip)
        footer(img, T, i + 2, TOT, item.get("fonte_breve", "")); files.append(save(img, out, f"{i + 2:02d}"))
    T = THEMES["giallo"]; img = canvas(T); d = ImageDraw.Draw(img)
    pill(img, "DOVE SI TROVA", (60, 80), font("k", 30), T["acc"], "#FFFFFF")
    text_block(img, f"{nome(c)} ({c['prov']})", (60, 170), fit_font(img, f"{nome(c)} ({c['prov']})", "k", W - 120, 2, 80), T["ink"], W - 120)
    place(img, draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=900), W // 2, 360, 760, 820)
    footer(img, T, TOT - 1, TOT, item.get("fonte_breve", "")); files.append(save(img, out, f"{TOT - 1:02d}"))
    T = THEMES["rosa"]; img = canvas(T); d = ImageDraw.Draw(img)
    y = text_block(img, cta, (60, 300), font("k", 84), T["ink"], W - 120, 1.04)
    pill(img, "Scrivilo nei commenti", (60, y + 50), font("k", 44), T["acc"], T["acc2"])
    if item.get("fonti"): text_block(img, "Fonti: " + "; ".join(item["fonti"]), (60, y + 200), font("m", 24), T["muted"], W - 120, 1.3)
    footer(img, T, TOT, TOT, ""); files.append(save(img, out, f"{TOT:02d}"))
    cap = f"{item['didascalia']}\n\n{cta} Scrivilo nei commenti 👇\n\nFonti: {'; '.join(item.get('fonti', []))}\n\n{HASHTAG} {extra_tag}".strip()
    return dict(tipo="carosello", file=files, didascalia=cap)
def carosello_storia(item, out):
    return carosello_racconto(item, out, "STORIE DI COMUNI", "Conosci un comune con una storia così?")
def carosello_cibo(item, out):
    return carosello_racconto(item, out, "IL COMUNE E IL SUO PIATTO", "Qual è il piatto simbolo del tuo comune?", "#cucinaitaliana #ciboitaliano")
