"""Tutti i formati di contenuto. Ogni funzione genera i file in `out` e restituisce
dict(tipo="reel"|"carosello"|"immagine", file=[...], didascalia=str).
Ogni elemento ha il suo spazio riservato: il controllo `overlaps()` verifica che nessun
testo, mappa o illustrazione ne copra un altro (in caso contrario il file non viene salvato)."""
import os, re, random, subprocess, bisect
from PIL import Image, ImageDraw
from .base import *
from .base import extra, reg_geom, prov_geom, draw_area
from .city import city
from . import foto, musica, motivi

W, H = 1080, 1350            # post 4:5
VW, VH, FPS = 1080, 1920, 30  # reel 9:16
BOTTOM = H - 150              # limite inferiore dei contenuti nei post (sotto c'è il piè di pagina)
ease = lambda t: 1 - (1 - max(0, min(1, t))) ** 3
GENERICI = ["#comuniitaliani", "#borghiitaliani", "#geografia"]
def tag(x):
    t = re.sub(r"[^a-z0-9]", "", norm(x.split("/")[0])); return "#" + t if t else ""
def hashtags(*extra):
    """Instagram accetta al massimo 5 hashtag: il primo è sempre quello dell'account, poi i più specifici."""
    out = []
    for t in ["#italiaincomune", *extra, *GENERICI]:
        if t and t not in out: out.append(t)
    return " ".join(out[:5])
SEGUI = "Ogni giorno un comune diverso: seguite @italia_incomune."

class Sovrapposizione(Exception): pass
def verifica(where):
    ov = overlaps()
    if ov: raise Sovrapposizione(f"{where}: {ov}")

# ---------------------------------------------------------------- utilità comuni
def canvas(T, w=W, h=H): reset(); return Image.new("RGB", (w, h), T["bg"])
def footer(img, T, n=None, tot=None, fonte="Fonte: ISTAT, openpolis"):
    pill(img, HANDLE, (60, img.height - 110), font("b", 26), T["ink"], T["bg"], tag="firma")
    if fonte: txt(img, (img.width - 60, img.height - 84), fonte, font("m", 22), T["muted"], "ra", "fonte")
    if n: txt(img, (img.width - 60, 60), f"{n}/{tot}", font("b", 28), T["muted"], "ra", "pagina")
def save(img, out, name):
    verifica(name); os.makedirs(out, exist_ok=True); p = os.path.join(out, name + ".png"); img.convert("RGB").save(p); return p
def encode(path, frames, umore="pop"):
    """Codifica i fotogrammi (controllando le sovrapposizioni di ognuno) e aggiunge una musica originale."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True); muto, wav = path + ".muto.mp4", path + ".wav"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", muto], stdin=subprocess.PIPE)
    n = 0
    try:
        for i, f in enumerate(frames):
            verifica(f"{os.path.basename(os.path.dirname(path))} fotogramma {i}"); p.stdin.write(f.convert("RGB").tobytes()); n += 1
    finally:
        p.stdin.close(); p.wait()
    musica.genera(n / FPS, path, umore, wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", muto, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", path], check=True)
    os.remove(muto); os.remove(wav)
    return path
def vhandle(img, T): pill(img, HANDLE, (60, 150), font("b", 32), T["ink"], T["bg"], tag="firma")
def label(c): return f"{c['prov']} · {c['reg'].split('/')[0]}"
def nome(c): return c["nome"].split("/")[0]
def scena(c, T, w, h, margine=60, fs=20, soggetto=None):
    """Foto del comune (o di un soggetto, es. un monumento) da Wikimedia Commons in un riquadro arrotondato,
    con il credito sotto. None se non c'è."""
    r = foto.prendi_soggetto(soggetto) if soggetto else foto.prendi(c)
    if not r: return None
    im, cr = r; strip = fs + 18; pw, ph = w - 2 * margine, h - strip
    if ph < 200 or pw < 200: return None
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0)); q = foto.riquadro(im, pw, ph); out.paste(q, (margine, 0), q)
    d = ImageDraw.Draw(out); f = font("m", fs); t = foto.credito_breve(cr)
    while d.textlength(t, font=f) > pw - 24 and len(t) > 10: t = t[:-2].rstrip() + "…" if not t.endswith("…") else t[:-3].rstrip() + "…"
    tw = d.textlength(t, font=f)            # il credito sta in una piccola etichetta scura: si legge su qualsiasi colore
    d.rounded_rectangle((margine, ph + 4, margine + tw + 24, ph + 4 + fs + 12), (fs + 12) // 2, fill="#1A1446")
    d.text((margine + 12, ph + 8), t, font=f, fill="#FFFFFF"); foto.CREDITI.append(cr)
    return out
def city_in(img, c, T, top, bottom, maxh, seed="", con_foto=False):
    """Illustrazione (o foto, se con_foto) a tutta larghezza nello spazio libero tra top e bottom."""
    h = int(min(maxh, bottom - top))
    if h < 220: return
    if con_foto:
        s = scena(c, T, img.width, h)
        if s: paste(img, s, (0, bottom - h), "foto"); return
    ci = city(dict(c, nome=c["nome"] + seed), T, img.width, h); paste(img, ci, (0, bottom - h), "città")

# ---------------------------------------------------------------- classifiche
def _area(c):
    a = c["area"]; return f"{fmt(a)} km²" if a >= 10 else f"{a:.2f} km²".replace(".", ",")
METRICHE = {
    "area_max": dict(titolo="I 10 comuni più grandi d'Italia", sotto="per superficie", key=lambda c: -c["area"], val=_area,
                     gancio="Il 2° non è Milano", fonte="Fonte: ISTAT, openpolis"),
    "area_min": dict(titolo="I 10 comuni più piccoli d'Italia", sotto="per superficie", key=lambda c: c["area"], val=_area,
                     gancio="Il n.1 misura 0,1 km²", fonte="Fonte: ISTAT, openpolis"),
    "dens_max": dict(titolo="I 10 comuni più affollati d'Italia", sotto="abitanti per km²", key=lambda c: -(c["pop"] or 0) / c["area"],
                     val=lambda c: f"{fmt(c['pop'] / c['area'])} ab/km²", gancio="Napoli non è prima", fonte="Fonte: ISTAT 2011, openpolis"),
}
lettere = lambda c: len(re.sub(r"[^A-Za-zÀ-ÿ]", "", nome(c)))
METRICHE.update({
    "confinanti": dict(titolo="I 10 comuni con più vicini d'Italia", sotto="comuni confinanti", key=lambda c: (-c["confinanti"], c["nome"]),
                       val=lambda c: f"{c['confinanti']} confinanti", gancio="Il n.1 ha un vicinato enorme", fonte="Elaborazione su confini openpolis"),
    "pezzi": dict(titolo="I 10 comuni più spezzettati d'Italia", sotto="parti di territorio separate", key=lambda c: (-c["pezzi"], -c["area"]),
                  val=lambda c: f"{c['pezzi']} pezzi", gancio="Sparsi come un puzzle", fonte="Elaborazione su confini openpolis"),
    "nome_corto": dict(titolo="I nomi di comune più corti d'Italia", sotto="numero di lettere", key=lambda c: (lettere(c), c["nome"]),
                       val=lambda c: f"{lettere(c)} lettere", gancio="Due lettere bastano", fonte="Fonte: ISTAT"),
    "nome_lungo": dict(titolo="I nomi di comune più lunghi d'Italia", sotto="numero di lettere", key=lambda c: (-lettere(c), c["nome"]),
                       val=lambda c: f"{lettere(c)} lettere", gancio="Prova a dirlo d'un fiato", fonte="Fonte: ISTAT"),
})
def top10(metrica):
    comuni = extra(); return sorted(comuni, key=METRICHE[metrica]["key"])[:10]
def attacco(metrica, big):
    n1, n2 = big[0], big[1]; v = METRICHE[metrica]["val"]
    return {
        "area_max": f"{nome(n1)} era facile. Ma il secondo comune più grande d'Italia è {nome(n2)}, con {v(n2)}. Ve lo aspettavate?",
        "area_min": f"{nome(n1)} misura {v(n1)}. Ed è un comune a tutti gli effetti, con tanto di sindaco.",
        "dens_max": f"Il comune più affollato d'Italia è {nome(n1)}: {v(n1)} secondo il censimento 2011. Probabilmente non è quello a cui pensavate.",
        "confinanti": f"{nome(n1)} confina con {n1['confinanti']} comuni diversi. Pensate solo alle riunioni tra sindaci.",
        "pezzi": f"{nome(n1)} è diviso in {n1['pezzi']} pezzi di territorio separati. Un vero puzzle amministrativo.",
        "nome_corto": f"{lettere(n1)} lettere e basta: {nome(n1)}. In Italia ci sono comuni con nomi cortissimi.",
        "nome_lungo": f"{nome(n1)}: {lettere(n1)} lettere. Provate a dirlo tutto d'un fiato.",
    }[metrica]

def cta_slide(T, titolo, n=None, tot=None, extra=None, fonti=None):
    img = canvas(T)
    y = text_block(img, titolo, (60, 300), fit_font(img, titolo, "k", W - 120, 4, 88), T["ink"], W - 120, 1.04)
    b = pill(img, "Scrivilo nei commenti", (60, y + 50), font("k", 40), T["acc"], T["acc2"])
    y += 50 + 40 + 28
    if extra: y = text_block(img, extra, (60, y + 40), font("b", 32), T["ink"], W - 120)
    if fonti: text_block(img, "Fonti: " + "; ".join(fonti), (60, y + 50), font("m", 22), T["muted"], W - 120, 1.3, "fonti")
    footer(img, T, n, tot, ""); return img

def carosello_classifica(metrica, out):
    M = METRICHE[metrica]; big = top10(metrica); TOT = 12; files = []
    T = THEMES["giallo"]; img = canvas(T)
    pill(img, "CLASSIFICA", (60, 80), font("k", 30), T["acc"], "#FFFFFF")
    txt(img, (W - 60, 92), "scorri  →", font("k", 34), T["acc"], "ra")
    y = text_block(img, M["titolo"], (60, 180), fit_font(img, M["titolo"], "k", W - 120, 3, 88), T["ink"], W - 120, 1.02)
    pill(img, M["sotto"], (60, y + 24), font("x", 32), T["ink"], T["bg"]); y += 24 + 32 + 28
    hl = big[0]["geom"].union(big[1]["geom"])
    place(img, draw_map(T, highlight=hl, px=900), W // 2, y + 40, 760, BOTTOM - y - 40)
    footer(img, T, None, None, M["fonte"]); files.append(save(img, out, "01"))
    for i, c in enumerate(reversed(big)):
        T = THEMES[CYCLE[(i + 2) % 3]]; rank = 10 - i; img = canvas(T)
        txt(img, (60, 70), f"#{rank}", fit_font(img, f"#{rank}", "k", 560, 1, 180), T["acc"], "la", "numero")
        place(img, draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=500), 860, 110, 300, 250)
        y = text_block(img, nome(c), (60, 390), fit_font(img, nome(c), "k", W - 120, 2, 84), T["ink"], W - 120, 1.0)
        txt(img, (60, y + 14), label(c), font("b", 30), T["muted"])
        pill(img, M["val"](c), (60, y + 70), font("k", 48), T["ink"], T["bg"])
        city_in(img, c, T, y + 70 + 48 + 28 + 30, BOTTOM, 520, con_foto=True)
        footer(img, T, i + 2, TOT, M["fonte"]); files.append(save(img, out, f"{i + 2:02d}"))
    img = cta_slide(THEMES["rosa"], "E il tuo comune in che posizione è?", TOT, TOT, "ti mandiamo la sua scheda in DM")
    files.append(save(img, out, "12"))
    lista = "\n".join(f"{10 - i}. {nome(c)} ({c['prov']}) – {M['val'](c)}" for i, c in enumerate(reversed(big)))
    cap = (f"{attacco(metrica, big)}\n\n{M['titolo']} ({M['sotto']}):\n{lista}\n\nIl vostro comune dove si piazza? Scrivetelo qui sotto: "
           f"vi mandiamo la sua scheda in privato.\nSalvate il post, vi tornerà utile alla prossima discussione al bar.\n\n{M['fonte']}\n\n{hashtags('#classifiche')}")
    return dict(tipo="carosello", file=files, didascalia=cap)

def reel_countdown(metrica, out):
    M = METRICHE[metrica]; order = list(reversed(top10(metrica)))
    maps = [draw_map(THEMES[CYCLE[(i + 1) % 3]], highlight=c["geom"], point=c["geom"].centroid, px=320) for i, c in enumerate(order)]
    cities = [scena(c, THEMES[CYCLE[(i + 1) % 3]], 1080, 600, fs=24) or city(c, THEMES[CYCLE[(i + 1) % 3]], 1080, 600) for i, c in enumerate(order)]
    def frames():
        T = THEMES["indaco"]
        for f in range(int(1.4 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T)
            y = text_block(img, M["titolo"], (70, 520), fit_font(img, M["titolo"], "k", VW - 140, 4, 116), T["ink"], VW - 140, 1.0)
            pill(img, M["gancio"], (70, y + 50), fit_font(img, M["gancio"], "k", VW - 200, 1, 48), T["acc"], T["bg"])
            txt(img, (70, y + 170), f"({M['sotto']})", font("b", 40), T["muted"])
            yield img
        for i, c in enumerate(order):
            T = THEMES[CYCLE[(i + 1) % 3]]; rank = 10 - i; dur = 1.0 if rank > 3 else 1.6
            for f in range(int(dur * FPS)):
                t = f / FPS; e = ease(t / .45); img = canvas(T, VW, VH); vhandle(img, T)
                paste(img, maps[i], (VW - maps[i].width - 50, 250 + int(40 * (1 - e))), "mappa")
                rf = fit_font(img, f"#{rank}", "k", 560, 1, 220)
                txt(img, (70 - int(300 * (1 - e)), 260), f"#{rank}", rf, T["acc"], "la", "numero")
                y = text_block(img, nome(c), (70, 720), fit_font(img, nome(c), "k", VW - 140, 2, 96), T["ink"], VW - 140, 1.0)
                txt(img, (70, y + 14), label(c), font("b", 38), T["muted"])
                pill(img, M["val"](c), (70, y + 80), font("k", 54), T["ink"], T["bg"])
                rise = ease((t - .05) / .45); box = Image.new("RGBA", (1080, 600), (0, 0, 0, 0))
                box.paste(cities[i], (0, int(600 * (1 - rise))), cities[i]); paste(img, box, (0, max(y + 80 + 54 + 28 + 40, 1060)), "città")
                yield img
        T = THEMES["rosa"]
        for f in range(int(2.2 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T)
            y = text_block(img, "E il tuo comune in che posizione è?", (70, 560), font("k", 104), T["ink"], VW - 140, 1.0)
            if t > .3: pill(img, "Scrivilo nei commenti", (70, y + 60), font("k", 52), T["acc"], T["acc2"])
            if t > .6: txt(img, (70, y + 190), "ti mandiamo la sua scheda in DM", font("b", 40), T["ink"])
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "tensione")
    n1 = order[-1]
    cap = (f"{attacco(metrica, list(reversed(order)))}\n\nDal decimo al primo posto: il numero 1 arriva alla fine.\n\n"
           f"Mandatelo a chi pensa di sapere tutto dell'Italia. E il vostro comune? Scrivetelo nei commenti.\n{SEGUI}\n\n{M['fonte']}\n\n{hashtags('#classifiche')}")
    return dict(tipo="reel", file=[path], didascalia=cap)

# ---------------------------------------------------------------- mappe che si riempiono
SANTI = ("san ", "santa ", "santo ", "sant ", "santi ")
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
def _kw(*k):
    pat = re.compile(r"(^| )(" + "|".join(k) + ")")
    return lambda c: bool(pat.search(norm(c["nome"])))
for k, parola, domanda in [("castel", "«Castel»", "Quanti comuni hanno un castello nel nome?"), ("villa", "«Villa»", "Quanti comuni hanno «Villa» nel nome?"),
                           ("rocca", "«Rocca»", "Quanti comuni hanno «Rocca» nel nome?"), ("val", "«Val»", "Quanti comuni hanno «Val» nel nome?"),
                           ("terme|bagn", "«Terme» o «Bagni»", "Quanti comuni hanno le terme nel nome?"), ("torre", "«Torre»", "Quanti comuni hanno «Torre» nel nome?"),
                           ("ponte", "«Ponte»", "Quanti comuni hanno «Ponte» nel nome?"), ("borgo", "«Borgo»", "Quanti comuni hanno «Borgo» nel nome?"),
                           ("colle", "«Colle»", "Quanti comuni hanno «Colle» nel nome?"), ("porto", "«Porto»", "Quanti comuni hanno «Porto» nel nome?"),
                           ("poggio", "«Poggio»", "Quanti comuni hanno «Poggio» nel nome?"), ("pian", "«Piano» o «Pian»", "Quanti comuni hanno «Piano» nel nome?"),
                           ("sasso", "«Sasso»", "Quanti comuni hanno «Sasso» nel nome?"), ("fonte|font", "«Fonte»", "Quanti comuni hanno una fonte nel nome?"),
                           ("casal", "«Casal»", "Quanti comuni hanno «Casal» nel nome?"), ("serra", "«Serra»", "Quanti comuni hanno «Serra» nel nome?")]:
    MAPPE[k.split("|")[0]] = dict(f=_kw(*k.split("|")), testo=f"comuni hanno {parola} nel nome", domanda=domanda, cta="Il tuo è tra questi?", fonte="Fonte: ISTAT, openpolis")

def reel_mappa(chiave, out):
    M = MAPPE[chiave]; T = THEMES["indaco"]; comuni, _ = load()
    sel = [c for c in comuni if M["f"](c)]
    base = draw_map(T, px=820); full = draw_map(T, color_fn=lambda c: T["acc"] if M["f"](c) else None, px=820)
    base.thumbnail((820, 960)); full.thumbnail((820, 960))
    x0, y0, x1, y1 = map_bounds()
    ys = sorted((y1 - c["geom"].centroid.y) / (y1 - y0) * full.height for c in sel)
    mx, my = (VW - full.width) // 2, 700
    def frames():
        intro, sweep, hold = 1.0, 5.0, 2.5
        for f in range(int((intro + sweep + hold) * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); d = ImageDraw.Draw(img); vhandle(img, T)
            u = max(0, min(1, (t - intro) / sweep)); s = u * u * (3 - 2 * u)
            line = int(s * full.height); cnt = bisect.bisect_right(ys, line)
            if t < intro: text_block(img, M["domanda"], (70, 280), fit_font(img, M["domanda"], "k", VW - 140, 4, 80), T["ink"], VW - 140, 1.04)
            else:
                txt(img, (70, 250), fmt(cnt), font("k", 170), T["acc"], "la", "numero")
                y = text_block(img, M["testo"], (70, 470), fit_font(img, M["testo"], "b", VW - 140, 2, 44), T["ink"], VW - 140)
                if t > intro + sweep + .3: pill(img, M["cta"], (70, y + 20), fit_font(img, M["cta"], "k", VW - 200, 1, 50), T["acc2"], "#FFFFFF")
            img.paste(base, (mx, my), base)
            if line > 0:
                part = full.crop((0, 0, full.width, line)); img.paste(part, (mx, my), part)
                if s < .99: d.line((mx, my + line, mx + full.width, my + line), fill=T["acc2"], width=6)
            reg((mx, my, mx + full.width, my + full.height), "mappa")
            txt(img, (VW - 70, my + full.height + 40), M["fonte"], font("m", 28), T["muted"], "ra", "fonte")
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "pop")
    tot = len(comuni); ogni = max(2, round(tot / max(1, len(sel))))
    cap = (f"{fmt(len(sel))} {M['testo']}: più o meno uno ogni {ogni} in tutta Italia.\n\nGuardate la mappa fino alla fine, si accende da nord a sud. "
           f"{M['cta']} Scrivetelo nei commenti.\n{SEGUI}\n\n{M['fonte']}\n\n{hashtags('#mappe')}")
    return dict(tipo="reel", file=[path], didascalia=cap)

# ---------------------------------------------------------------- scheda del comune (DM e "comune del giorno")
def stats(c):
    comuni, _ = load(); reg_ = [x for x in comuni if x["reg"] == c["reg"]]; rk = 1 + sum(x["area"] > c["area"] for x in reg_)
    pos = "il più piccolo" if rk == len(reg_) else "il più grande" if rk == 1 else f"{rk}° su {len(reg_)}"
    return [(fmt(c["pop"]) if c["pop"] else "n.d.", "abitanti (censimento 2011)"), (_area(c), "di superficie"),
            (fmt(c["pop"] / c["area"]) if c["pop"] else "n.d.", "abitanti per km²"), (pos, f"per estensione in {c['reg'].split('/')[0]}")]
def scheda(c, path, T=None):
    T = T or THEMES["indaco"]; img = canvas(T)
    pill(img, "LA SCHEDA DEL TUO COMUNE", (60, 70), font("k", 26), T["acc2"], "#FFFFFF")
    place(img, draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=700), 870, 160, 300, 360)
    y = text_block(img, nome(c), (60, 160), fit_font(img, nome(c), "k", 600, 3, 96), T["acc"], 600, 1.0)
    txt(img, (60, y + 14), label(c), fit_font(img, label(c), "b", 600, 1, 32), T["muted"])
    yy = max(y + 90, 540)
    for v, k in stats(c):
        txt(img, (60, yy), v, fit_font(img, v, "k", 960, 1, 48), T["ink"]); txt(img, (60, yy + 60), k, font("m", 24), T["muted"]); yy += 108
    city_in(img, c, T, yy + 10, BOTTOM, 360)
    footer(img, T); verifica("scheda"); img.convert("RGB").save(path); return path

def reel_comune(c, out):
    T = THEMES[random.Random(c["nome"]).choice(CYCLE)]
    m = draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=420); m.thumbnail((360, 420)); rows = stats(c)
    tmp = canvas(T, VW, VH); nf = fit_font(tmp, nome(c), "k", 560, 3, 110)
    def layout(img, t):
        e = ease(t / .4)
        y = text_block(img, nome(c), (70 - int(40 * (1 - e)), 320), nf, T["acc"], 560, 1.0)
        txt(img, (70, y + 14), label(c), fit_font(img, label(c), "b", 560, 1, 40), T["muted"]); return y + 70
    y_name = layout(canvas(T, VW, VH), 1)
    ystats = max(y_name + 40, 320 + m.height + 40)
    ci_top = ystats + 4 * 140 + 10; ci_h = min(480, VH - 60 - ci_top)
    ci = (scena(c, T, 1080, ci_h, fs=24) or city(c, T, 1080, ci_h)) if ci_h >= 220 else None
    def frames():
        for f in range(int(8 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T)
            pill(img, "IL COMUNE DEL GIORNO" if t < 5.6 else "IL PROSSIMO PUÒ ESSERE IL TUO: SCRIVILO!", (70, 232), font("k", 26), T["acc2"], "#FFFFFF")
            layout(img, t)
            paste(img, m, (VW - m.width - 60, 320), "mappa")
            for i, (v, k) in enumerate(rows):
                if t > .6 + i * .8:
                    yy = ystats + i * 140; txt(img, (70, yy), v, fit_font(img, v, "k", 940, 1, 56), T["ink"]); txt(img, (70, yy + 70), k, font("m", 30), T["muted"])
            if ci:
                rise = ease(t / .9); box = Image.new("RGBA", (1080, ci_h), (0, 0, 0, 0))
                box.paste(ci, (0, int(ci_h * (1 - rise))), ci); paste(img, box, (0, ci_top), "città")
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), random.Random(c["nome"]).choice(["pop", "chill"]))
    v = dict((k, x) for x, k in rows)
    cap = (f"Oggi tocca a {nome(c)}, in provincia di {c['prov_nome']} ({c['reg'].split('/')[0]}).\n\n"
           f"{rows[1][0]} di territorio e {rows[0][0]} abitanti al censimento 2011. Per estensione è {rows[3][0]} della sua regione.\n\n"
           f"Ci siete mai passati? Taggate qualcuno che abita lì. E domani quale comune volete vedere? Scrivetelo nei commenti.\n\n"
           f"Fonte: ISTAT (censimento 2011), openpolis\n\n{hashtags(tag(c['nome']), tag(c['reg']))}")
    return dict(tipo="reel", file=[path], didascalia=cap)

# ---------------------------------------------------------------- sfida: chi è più grande?
def lat(c): return c["ll"].y
def coppia(seed, tipo="area"):
    """Due comuni abbastanza noti (oltre 20.000 abitanti nel 2011) con valori vicini: la risposta non è ovvia."""
    comuni, _ = load(); r = random.Random(seed); noti = [c for c in comuni if (c["pop"] or 0) >= 20000]
    for _ in range(2000):
        a, b = r.sample(noti, 2)
        if tipo == "area" and abs(a["area"] - b["area"]) > 2 and .8 < b["area"] / a["area"] < 1.25: return a, b
        if tipo == "nord" and a["reg"] != b["reg"] and .03 < abs(lat(a) - lat(b)) < .4: return a, b
    return noti[0], noti[1]
SFIDE = {"area": dict(domanda="Chi è più grande?", val=_area, vince=lambda a, b: a if a["area"] > b["area"] else b,
                      fonte="Elaborazione su confini openpolis"),
         "nord": dict(domanda="Chi sta più a nord?", val=lambda c: f"{lat(c):.2f}° N".replace(".", ","), vince=lambda a, b: a if lat(a) > lat(b) else b,
                      fonte="Elaborazione su confini openpolis")}
def reel_sfida(a, b, out, tipo="area"):
    S = SFIDE[tipo]; T = THEMES["giallo"]; TA, TB = THEMES["rosa"], THEMES["indaco"]
    ca = scena(a, TA, 540, 340, margine=30, fs=16) or city(a, TA, 540, 340)
    cb = scena(b, TB, 540, 340, margine=30, fs=16) or city(b, TB, 540, 340); win = S["vince"](a, b)
    tmp = canvas(T, VW, VH); fa, fb = (fit_font(tmp, nome(x), "k", 460, 3, 60) for x in (a, b))
    def frames():
        for f in range(int(8 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); d = ImageDraw.Draw(img); vhandle(img, T)
            text_block(img, S["domanda"], (70, 260), fit_font(img, S["domanda"], "k", VW - 140, 2, 92), T["ink"], VW - 140, 1.0)
            for i, (c, ci, TT, ff) in enumerate([(a, ca, TA, fa), (b, cb, TB, fb)]):
                x = i * 540; d.rectangle((x, 520, x + 540, 1420), fill=TT["bg"])
                y = text_block(img, nome(c), (x + 40, 560), ff, TT["ink"], 460, 1.0)
                txt(img, (x + 40, y + 16), f"{c['prov']} · {c['reg'].split('/')[0]}", fit_font(img, f"{c['prov']} · {c['reg'].split('/')[0]}", "b", 460, 1, 32), TT["muted"])
                if t > 5.2:
                    pill(img, S["val"](c), (x + 40, y + 70), fit_font(img, S["val"](c), "k", 400, 1, 42), TT["ink"], TT["bg"])
                    if c is win: pill(img, "VINCE!", (x + 40, y + 160), font("k", 38), T["bg"], T["ink"])
                paste(img, ci, (x, 1420 - 340), "città")
            txt(img, (VW // 2, 1450), "VS", font("k", 76), T["ink"], "ma")
            if 2.2 < t < 5.2: txt(img, (VW // 2, 1560), str(3 - int(t - 2.2)), font("k", 130), T["acc"], "ma")
            elif t <= 2.2: txt(img, (VW // 2, 1580), "Rispondi nei commenti prima del via!", font("b", 32), T["ink"], "ma")
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "tensione")
    q = "è più grande" if tipo == "area" else "sta più a nord"
    cap = (f"Senza cercare su Google: {q} {nome(a)} o {nome(b)}?\n\nScrivete la risposta nei commenti, poi guardate fino alla fine: la soluzione arriva dopo il conto alla rovescia. "
           f"Mandatelo a un amico e vedete se ci prende.\n{SEGUI}\n\n{S['fonte']}\n\n{hashtags('#quiz', tag(a['nome']), tag(b['nome']))}")
    return dict(tipo="reel", file=[path], didascalia=cap)

# ---------------------------------------------------------------- speciali a data fissa
def _mappa_sigle(T, sigle):
    from .base import prov_geom
    sig = set(sigle); pt = prov_geom(sigle[0]).centroid if len(sigle) == 1 else None
    return draw_map(T, color_fn=lambda c: T["ink"] if c["prov"] in sig else None, point=pt, px=700)
def mappa_regioni(T, item, fino=None, px=820):
    """Mappa d'Italia con le regioni colorate per gruppo (es. coalizione). fino = solo le prime n regioni da nord."""
    G, R = item["gruppi"], item["regioni"]; ordine = list(R)[:fino] if fino is not None else list(R)
    col = {r: G[g]["colore"] for r, g in R.items() if r in ordine}
    return draw_map(T, color_fn=lambda c: col.get(c["reg"].split("/")[0]), px=px)
def legenda(img, T, item, y, conta=None):
    """Pillole colorate una accanto all'altra (vanno a capo se serve). Restituisce la y sotto l'ultima riga."""
    x = 60; f = font("k", 30); d = ImageDraw.Draw(img)
    for k, g in item["gruppi"].items():
        t = f"{g['nome']} {conta[k]}" if conta else g["nome"]; w = d.textlength(t, font=f) + 52
        if x + w > W - 60: x, y = 60, y + 76
        pill(img, t, (x, y), f, g["colore"], "#1A1446", tag=f"legenda {k}"); x += w + 16
    return y + 30 + 28 + 18
def carosello_speciale(item, out):
    """Carosello libero per i temi del momento: copertina, slide di testo con numeri e mappa, chiusura con domanda."""
    os.makedirs(out, exist_ok=True); files = []; slides = item["slide"]; TOT = len(slides) + 2
    giro = [THEMES[item["tema"]]] if item.get("tema") else [THEMES[k] for k in CYCLE]
    T = THEMES[item.get("tema", "rosa")]; img = canvas(T)
    pill(img, item.get("etichetta", "SPECIALE"), (60, 80), font("k", 30), T["ink"], T["bg"])
    txt(img, (W - 60, 92), "scorri  →", font("k", 34), T["ink"], "ra")
    top = 190
    if item.get("evidenzia"): place(img, _mappa_sigle(T, item["evidenzia"]), W - 230, BOTTOM - 520, 340, 480); 
    y = text_block(img, item["titolo"], (60, top), fit_font(img, item["titolo"], "k", W - 120, 5, 104), T["ink"], W - 120, 1.02)
    if item.get("sotto"): y = text_block(img, item["sotto"], (60, y + 40), font("b", 40), T["acc"] if item.get("tema") else T["ink"], 560 if item.get("evidenzia") else W - 120, 1.25)
    if item.get("regioni"): place(img, mappa_regioni(T, item), W // 2, y + 50, 700, BOTTOM - y - 70)
    footer(img, T, None, None, ""); files.append(save(img, out, "01"))
    for i, sl in enumerate(slides):
        T = giro[i % len(giro)]; img = canvas(T); y = 150; tw = W - 120
        if sl.get("evidenzia"): place(img, _mappa_sigle(T, sl["evidenzia"]), W - 210, 130, 300, 360); tw = 560
        y = text_block(img, sl["titolo"], (60, y), fit_font(img, sl["titolo"], "k", tw, 3, 76), T["acc"], tw, 1.04)
        if sl.get("evidenzia"): y = max(y, 470)
        y = text_block(img, sl["testo"], (60, y + 36), font("m", 36), T["ink"], W - 120, 1.32)
        for v, k in sl.get("numeri", []):
            colore = item["gruppi"][v[1]]["colore"] if isinstance(v, list) else T["acc"]; v = v[0] if isinstance(v, list) else v
            yy = text_block(img, v, (60, y + 44), font("k", 92), colore, W - 120, 1.0)
            y = text_block(img, k, (60, yy + 8), font("b", 34), T["ink"], W - 120, 1.2)
        if sl.get("mappa_regioni"):
            y = legenda(img, T, item, y + 40, sl.get("conta"))
            place(img, mappa_regioni(T, item), W // 2, y + 10, 760, BOTTOM - y - 30)
        footer(img, T, i + 2, TOT, sl.get("fonte", "")); files.append(save(img, out, f"{i + 2:02d}"))
    img = cta_slide(THEMES["indaco" if item.get("tema") == "indaco" else "giallo"], item["domanda"], TOT, TOT, item.get("extra"), item.get("fonti"))
    files.append(save(img, out, f"{TOT:02d}"))
    cap = f"{item['didascalia']}\n\nFonti: {'; '.join(item.get('fonti', []))}\n\n{hashtags(*item.get('hashtag', []))}"
    return dict(tipo="carosello", file=files, didascalia=cap)

def reel_regioni(item, out):
    """Reel: le regioni si colorano una alla volta da nord a sud, con il conteggio che sale; poi il finale."""
    T = THEMES["indaco"]; R = item["regioni"]; n = len(R)
    maps = [mappa_regioni(T, item, fino=k, px=760) for k in range(n + 1)]
    for m in maps: m.thumbnail((760, 900))
    mx, my = (VW - maps[0].width) // 2, 660; piccola = maps[-1]
    passo, attesa, finale = .32, .9, 3.6
    def frames():
        tot = attesa + n * passo + finale
        for f in range(int(tot * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T)
            k = max(0, min(n, int((t - attesa) / passo) + 1)) if t >= attesa else 0
            y = text_block(img, item["titolo_reel"], (70, 250), fit_font(img, item["titolo_reel"], "k", VW - 140, 2, 92), T["ink"], VW - 140, 1.0)
            conta = {g: sum(1 for r in list(R)[:k] if R[r] == g) for g in item["gruppi"]}
            if t < attesa + n * passo + .4:
                legenda(img, T, item, y + 40, conta)
                m = maps[k]; img.paste(m, (mx, my), m); reg((mx, my, mx + m.width, my + m.height), "mappa")
                txt(img, (VW - 70, my + m.height + 30), item["fonte_reel"], font("m", 26), T["muted"], "ra", "fonte")
            else:
                yy = legenda(img, T, item, y + 40, conta) + 60
                for riga, colore in item["finale"]:
                    yy = text_block(img, riga, (70, yy), fit_font(img, riga, "k", VW - 140, 3, 64), item["gruppi"][colore]["colore"] if colore else T["ink"], VW - 140, 1.1) + 34
                yy += 10
                pill(img, item["cta_reel"], (70, yy), fit_font(img, item["cta_reel"], "k", VW - 200, 1, 44), T["acc2"], "#FFFFFF")
                fine = piccola; top = yy + 44 + 28 + 50
                if VH - 220 - top > 300:
                    f2 = fine.copy(); f2.thumbnail((VW - 140, VH - 220 - top)); place(img, f2, VW // 2, top, VW - 140, VH - 220 - top)
                txt(img, (VW - 70, VH - 160), item["fonte_finale"], font("m", 26), T["muted"], "ra", "fonte")
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "tensione")
    cap = f"{item['didascalia_reel']}\n\nFonti: {'; '.join(item.get('fonti', []))}\n\n{hashtags(*item.get('hashtag', []))}"
    return dict(tipo="reel", file=[path], didascalia=cap)

# ---------------------------------------------------------------- quiz: riconosci il comune dalla forma
def sagoma(geom, w, h, colore):
    """Il contorno del comune riempito di colore, centrato in un riquadro w×h."""
    x0, y0, x1, y1 = geom.bounds; k = min((w - 20) / (x1 - x0), (h - 20) / (y1 - y0))
    ox, oy = (w - (x1 - x0) * k) / 2, (h - (y1 - y0) * k) / 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for p in getattr(geom, "geoms", [geom]):
        pts = [(ox + (x - x0) * k, h - oy - (y - y0) * k) for x, y in p.exterior.coords]; d.polygon(pts, fill=colore)
        for hole in p.interiors: d.polygon([(ox + (x - x0) * k, h - oy - (y - y0) * k) for x, y in hole.coords], fill=(0, 0, 0, 0))
    return im
def tre_opzioni(giusto, altri, seed):
    r = random.Random(seed); ops = [giusto] + r.sample(altri, 2); r.shuffle(ops); return ops
def quiz_frames(T, titolo, centro, opzioni, giusta, rivela, dopo_txt, durata=9.0, rivela_a=5.6):
    """Impaginazione comune ai quiz: domanda, immagine centrale, tre risposte, conto alla rovescia, soluzione."""
    lettere_ = "ABC"; f_op = font("k", 46)
    for f in range(int(durata * FPS)):
        t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T); sol = t >= rivela_a
        text_block(img, titolo, (70, 250), fit_font(img, titolo, "k", VW - 140, 2, 84), T["ink"], VW - 140, 1.02)
        im = rivela if (sol and rivela is not None) else centro
        place(img, im, VW // 2, 470, 860, 640, "figura")
        for i, o in enumerate(opzioni):
            ok = sol and o == giusta; testo = f"{lettere_[i]}   {o}" + ("  · GIUSTA!" if ok else "")
            bg = T["acc"] if ok else ("#FFFFFF" if not sol else T["land"]); fg = "#1A1446" if not ok else "#FFFFFF"
            pill(img, testo, (70, 1150 + i * 120), fit_font(img, testo, "k", VW - 200, 1, 46), bg, fg, tag=f"opzione{i}")
        if not sol:
            n = 3 - int(max(0, t - (rivela_a - 3))) if t > rivela_a - 3 else None
            msg = str(n) if n else "Rispondi nei commenti: A, B o C"
            txt(img, (VW // 2, 1560), msg, font("k", 120 if n else 40), T["acc2"] if n else T["ink"], "ma", "conto")
        else:
            text_block(img, dopo_txt, (70, 1530), fit_font(img, dopo_txt, "b", VW - 140, 2, 40), T["ink"], VW - 140)
        yield img
def reel_forma(seed, out):
    comuni, _ = load(); r = random.Random(f"forma{seed}")
    noti = [c for c in comuni if (c["pop"] or 0) >= 40000 and len(getattr(c["geom"], "geoms", [1])) <= 3]
    c = r.choice(noti); simili = [x for x in comuni if x["reg"] == c["reg"] and (x["pop"] or 0) >= 15000 and x is not c] or [x for x in noti if x is not c]
    ops = tre_opzioni(nome(c), [nome(x) for x in simili], seed); T = THEMES[r.choice(CYCLE)]
    centro = sagoma(c["geom"], 860, 640, T["acc"])
    rivela = draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=700)
    giusta_lettera = "ABC"[ops.index(nome(c))]
    path = encode(os.path.join(out, "reel.mp4"), quiz_frames(T, "Riconosci il comune dalla forma?", centro, ops, nome(c), rivela,
                                                              f"È {nome(c)}, in provincia di {c['prov_nome']} ({c['reg'].split('/')[0]})."), "tensione")
    cap = (f"Solo la forma, niente nomi: che comune è? A, B o C?\n\nScrivete la risposta nei commenti prima del conto alla rovescia, poi guardate la soluzione. "
           f"(Era la {giusta_lettera}, ma non barate.)\n\nMandatelo a chi dice di conoscere bene la sua regione.\n{SEGUI}\n\n"
           f"Confini: openpolis\n\n{hashtags('#quiz', tag(c['nome']), tag(c['reg']))}")
    return dict(tipo="reel", file=[path], didascalia=cap, param=c["istat"])
def reel_dove(seed, out):
    comuni, _ = load(); r = random.Random(f"dove{seed}"); regs = sorted({x["reg"].split("/")[0] for x in comuni})
    cand = [c for c in comuni if 4000 <= (c["pop"] or 0) <= 60000 and not any(w in norm(c["nome"]) for w in map(norm, regs))]
    c = r.choice(cand); giusta = c["reg"].split("/")[0]
    ops = tre_opzioni(giusta, [x for x in regs if x != giusta], seed); T = THEMES[r.choice(CYCLE)]
    base = draw_map(T, px=700); rivela = draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=700)
    titolo = f"In che regione si trova {nome(c)}?"
    path = encode(os.path.join(out, "reel.mp4"), quiz_frames(T, titolo, base, ops, giusta, rivela,
                                                              f"{nome(c)} è in provincia di {c['prov_nome']}."), "tensione")
    cap = (f"{nome(c)}: in che regione si trova? A, B o C?\n\nSenza Google, scrivetelo nei commenti prima della soluzione. "
           f"Se ci abitate, valete doppio: taggate qualcuno di lì.\n{SEGUI}\n\nFonte: ISTAT, openpolis\n\n{hashtags('#quiz', tag(c['nome']), tag(giusta))}")
    return dict(tipo="reel", file=[path], didascalia=cap, param=c["istat"])

# ---------------------------------------------------------------- storie e piatti raccontati in un Reel
def reel_racconto(item, out, etichetta, cta, extra_tag=""):
    """Storia o piatto in un Reel: ogni passaggio ha testo, un'immagine (foto vera o illustrazione a tema) e un'animazione."""
    c = find(item["comune"], item.get("prov")); T0 = THEMES["indaco"]; VIS_Y, VIS_H = 900, 700
    slides = item["slide"]; intro, passo, fine = 2.8, 3.4, 2.8
    temi = [THEMES[CYCLE[(i + 1) % 3]] for i in range(len(slides))]
    # immagini: si alternano illustrazioni a tema e foto vere (del soggetto e del comune)
    foto_list = [scena(c, T0, VW, VIS_H, fs=24, soggetto=s_) for s_ in item.get("soggetti", [])]
    foto_list = [x for x in foto_list if x is not None]
    foto_comune = scena(c, T0, VW, VIS_H, fs=24)
    if foto_comune is not None: foto_list.append(foto_comune)
    def illustrazione(T, i):
        return motivi.disegna(item.get("motivo"), T, VW, VIS_H, i) or city(c, T, VW, VIS_H)
    copertina = foto_list[0] if foto_list else illustrazione(T0, 99)
    visuali = []
    for i, T in enumerate(temi):
        usa_foto = (i % 2 == 1) and foto_list
        visuali.append(("foto", foto_list[(i // 2) % len(foto_list)]) if usa_foto else ("disegno", illustrazione(T, i)))
    mappa = draw_map(THEMES["giallo"], highlight=c["geom"], point=c["geom"].centroid, px=700)
    def zoom(im, t):              # leggero zoom continuo sulle foto
        k = 1 + .06 * t; w2, h2 = int(im.width * k), int(im.height * k)
        big = im.resize((w2, h2), Image.LANCZOS); x, y = (w2 - im.width) // 2, (h2 - im.height) // 2
        return big.crop((x, y, x + im.width, y + im.height))
    def frames():
        tot = intro + passo * len(slides) + fine
        for f in range(int(tot * FPS)):
            t = f / FPS
            if t < intro:
                T = T0; img = canvas(T, VW, VH); vhandle(img, T)
                pill(img, etichetta, (70, 232), font("k", 28), T["acc2"], "#FFFFFF")
                y = text_block(img, item["titolo"], (70, 330), fit_font(img, item["titolo"], "k", VW - 140, 4, 96), T["ink"], VW - 140, 1.02)
                txt(img, (70, y + 24), f"{nome(c)} · {label(c)}", fit_font(img, f"{nome(c)} · {label(c)}", "b", VW - 140, 1, 40), T["acc"])
                paste(img, zoom(copertina, t / intro) if foto_list else copertina, (0, VIS_Y), "immagine")
            elif t < intro + passo * len(slides):
                i = int((t - intro) // passo); u = (t - intro - i * passo) / passo; sl = slides[i]; T = temi[i]
                img = canvas(T, VW, VH); vhandle(img, T)
                txt(img, (70, 250), nome(c).upper(), fit_font(img, nome(c).upper(), "b", VW - 300, 1, 34), T["muted"])
                pill(img, f"{i + 1}/{len(slides)}", (VW - 190, 236), font("k", 30), T["ink"], T["bg"], tag="passo")
                y = 330
                if sl.get("numero"): y = text_block(img, sl["numero"], (70, 320), fit_font(img, sl["numero"], "k", VW - 140, 1, 170), T["acc"], VW - 140) + 30
                text_block(img, sl["testo"], (70, y), fit_font(img, sl["testo"], "x", VW - 140, 6 if not sl.get("numero") else 4, 58), T["ink"], VW - 140, 1.22)
                kind, im = visuali[i]
                if kind == "foto": paste(img, zoom(im, u), (0, VIS_Y), "immagine")
                else:
                    rise = ease(min(1, u / .35)); box = Image.new("RGBA", (VW, VIS_H), (0, 0, 0, 0))
                    box.paste(im, (0, int(VIS_H * .25 * (1 - rise))), im); paste(img, box, (0, VIS_Y), "immagine")
                d = ImageDraw.Draw(img); d.rectangle((0, VH - 14, int(VW * (i + u) / len(slides)), VH), fill=T["acc"])
            else:
                T = THEMES["giallo"]; img = canvas(T, VW, VH); vhandle(img, T)
                y = text_block(img, f"{nome(c)} ({c['prov']})", (70, 250), fit_font(img, f"{nome(c)} ({c['prov']})", "k", VW - 140, 2, 84), T["ink"], VW - 140)
                y = place(img, mappa, VW // 2, y + 40, 760, 900)
                pill(img, cta, (70, y + 50), fit_font(img, cta, "k", VW - 200, 1, 44), T["acc"], "#FFFFFF")
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "chill")
    cap = (f"{item['didascalia']}\n\n{cta} Scrivetelo nei commenti, e mandatelo a chi deve conoscere questa storia.\n{SEGUI}\n\n"
           f"Fonti: {'; '.join(item.get('fonti', []))}\n\n{hashtags(tag(c['nome']), tag(c['reg']), *extra_tag.split())}")
    return dict(tipo="reel", file=[path], didascalia=cap)
def reel_storia(item, out): return reel_racconto(item, out, "STORIE DI COMUNI", "Conoscevate questa storia?", "#storiaitaliana")
def reel_cibo(item, out): return reel_racconto(item, out, "IL COMUNE E IL SUO PIATTO", "L'avete mai assaggiato?", "#cucinaitaliana")

# ---------------------------------------------------------------- post di presentazione
APP = dict(nome="Lethame", url="https://play.google.com/store/apps/details?id=com.lethame.drone")
def _punti(img, T, voci, y, colore):
    for titolo, testo in voci:
        y = text_block(img, titolo, (60, y), font("k", 44), colore, W - 120, 1.05)
        y = text_block(img, testo, (60, y + 12), font("m", 32), T["ink"], W - 120, 1.3) + 46
    return y
def carosello_intro(out):
    os.makedirs(out, exist_ok=True); comuni, _ = load(); files = []; TOT = 5; casa = dict(comuni[0], nome="italia in comune")
    T = THEMES["indaco"]; img = canvas(T)
    pill(img, "CHI SIAMO", (60, 80), font("k", 30), T["acc2"], "#FFFFFF")
    txt(img, (W - 60, 92), "scorri  →", font("k", 34), T["acc"], "ra")
    y = text_block(img, "Italia in comune", (60, 190), font("k", 120), T["ink"], W - 120, 1.0)
    y = text_block(img, "Quasi 8.000 comuni. Ognuno ha una storia, un numero strano, un piatto da difendere.", (60, y + 30), font("b", 40), T["acc"], W - 120, 1.2)
    city_in(img, casa, T, y + 50, BOTTOM - 20, 460); footer(img, T, None, None, ""); files.append(save(img, out, "01"))

    T = THEMES["giallo"]; img = canvas(T)
    y = text_block(img, "Cosa trovate qui", (60, 150), font("k", 84), T["ink"], W - 120, 1.0) + 50
    _punti(img, T, [("Storie vere", "Paesi sommersi, comuni enclave, borghi abbandonati e rinati. Ogni storia ha le sue fonti."),
                    ("Mappe e classifiche", "Il comune più grande, quello più piccolo, quello con più vicini. I numeri sono ISTAT e openpolis."),
                    ("Cibo", "I piatti che nascono in un comune preciso, e i derby del gusto da votare nei commenti."),
                    ("Sfide", "Due volte a settimana: chi è più grande, chi sta più a nord. Senza Google.")], y, T["acc"])
    footer(img, T, 2, TOT, ""); files.append(save(img, out, "02"))

    T = THEMES["rosa"]; img = canvas(T)
    y = text_block(img, "Un progetto spontaneo", (60, 180), font("k", 92), T["ink"], W - 120, 1.0)
    y = text_block(img, "Italia in comune è un piccolo collettivo. Nessuno sponsor, nessun ente dietro, nessun post pagato.", (60, y + 50), font("b", 44), T["ink"], W - 120, 1.25)
    y = text_block(img, "Lo facciamo perché pensiamo che l'Italia si capisca meglio un comune alla volta.", (60, y + 40), font("m", 40), T["ink"], W - 120, 1.3)
    footer(img, T, 3, TOT, ""); files.append(save(img, out, "03"))

    T = THEMES["indaco"]; img = canvas(T)
    y = text_block(img, "Come partecipare", (60, 150), font("k", 84), T["ink"], W - 120, 1.0) + 50
    _punti(img, T, [("Scrivete il vostro comune", "Sotto qualsiasi post: vi mandiamo in privato la sua scheda."),
                    ("Votate i derby", "Arancina o arancino? Un voto a testa, poi la mappa dei risultati."),
                    ("Rispondete alle sfide", "Prima del conto alla rovescia, senza barare."),
                    ("Proponete", "Una storia, un piatto, un comune che meriterebbe un post.")], y, T["acc"])
    footer(img, T, 4, TOT, ""); files.append(save(img, out, "04"))

    T = THEMES["giallo"]; img = canvas(T)
    pill(img, "SE VI VA DI SOSTENERCI", (60, 80), font("k", 30), T["acc"], "#FFFFFF")
    y = text_block(img, f"Giocate a {APP['nome']}", (60, 190), font("k", 104), T["ink"], W - 120, 1.0)
    y = text_block(img, "Per tenere in piedi il progetto da soli abbiamo creato un gioco per Android: si pilota un drone e si raccolgono monete.", (60, y + 40), font("b", 42), T["ink"], W - 120, 1.25)
    y = text_block(img, "Scaricarlo e giocarci è il modo più semplice per darci una mano.", (60, y + 36), font("m", 38), T["ink"], W - 120, 1.3)
    pill(img, "Link in bio", (60, y + 50), font("k", 48), T["acc"], "#FFFFFF")
    city_in(img, dict(casa, nome="sostegno"), T, y + 50 + 48 + 120, BOTTOM - 20, 380); footer(img, T, 5, TOT, ""); files.append(save(img, out, "05"))

    cap = ("Ciao, siamo Italia in comune.\n\nRaccontiamo l'Italia un comune alla volta: storie vere, mappe, classifiche, cibo e sfide. "
           "I dati vengono da ISTAT e openpolis, le storie hanno sempre le loro fonti.\n\n"
           "È un progetto spontaneo: nessuno sponsor, nessun ente, nessuna sponsorizzata. "
           f"Se vi va di sostenerci, scaricate {APP['nome']}, il gioco che abbiamo creato per autofinanziarci: il link è in bio.\n\n"
           "Intanto scrivete qui sotto il vostro comune: vi mandiamo la sua scheda in privato.\n\n"
           + hashtags("#chisiamo"))
    return dict(tipo="carosello", file=files, didascalia=cap)

# ---------------------------------------------------------------- caroselli narrativi: storie e cibo
def carosello_racconto(item, out, etichetta, cta, extra_tag=""):
    c = find(item["comune"], item.get("prov")); files = []; fb = item.get("fonte_breve", "")
    slides = item["slide"]; TOT = len(slides) + 3
    T = THEMES["indaco"]; img = canvas(T)
    pill(img, etichetta, (60, 80), font("k", 26), T["acc2"], "#FFFFFF")
    txt(img, (W - 60, 88), "scorri  →", font("k", 30), T["acc"], "ra")
    y = text_block(img, item["titolo"], (60, 180), fit_font(img, item["titolo"], "k", W - 120, 4, 84), T["ink"], W - 120, 1.04)
    txt(img, (60, y + 20), f"{nome(c)} · {label(c)}", fit_font(img, f"{nome(c)} · {label(c)}", "b", W - 120, 1, 34), T["acc"])
    city_in(img, c, T, y + 90, BOTTOM, 560, con_foto=True)
    footer(img, T, None, None, fb); files.append(save(img, out, "01"))
    for i, s in enumerate(slides):
        T = THEMES[CYCLE[(i + 1) % 3]]; img = canvas(T)
        txt(img, (60, 70), nome(c).upper(), font("b", 26), T["muted"])
        y0 = 170
        if s.get("numero"): y0 = text_block(img, s["numero"], (60, 150), fit_font(img, s["numero"], "k", W - 120, 1, 170), T["acc"], W - 120) + 30
        y = text_block(img, s["testo"], (60, y0), fit_font(img, s["testo"], "x", W - 120, 7 if not s.get("numero") else 5, 62), T["ink"], W - 120, 1.25)
        hh = int(min(320, BOTTOM - y - 40))
        mot = motivi.disegna(item.get("motivo"), T, W, hh, i) if hh >= 220 else None
        if mot: paste(img, mot, (0, BOTTOM - hh), "illustrazione")
        else: city_in(img, c, T, y + 40, BOTTOM, 300, seed=str(i))
        footer(img, T, i + 2, TOT, fb); files.append(save(img, out, f"{i + 2:02d}"))
    T = THEMES["giallo"]; img = canvas(T)
    pill(img, "DOVE SI TROVA", (60, 80), font("k", 28), T["acc"], "#FFFFFF")
    y = text_block(img, f"{nome(c)} ({c['prov']})", (60, 180), fit_font(img, f"{nome(c)} ({c['prov']})", "k", W - 120, 2, 80), T["ink"], W - 120)
    place(img, draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=900), W // 2, y + 40, 760, BOTTOM - y - 40)
    footer(img, T, TOT - 1, TOT, fb); files.append(save(img, out, f"{TOT - 1:02d}"))
    img = cta_slide(THEMES["rosa"], cta, TOT, TOT, None, item.get("fonti")); files.append(save(img, out, f"{TOT:02d}"))
    cap = (f"{item['didascalia']}\n\n{cta} Scrivetelo nei commenti.\nTaggate qualcuno che dovrebbe conoscere questa storia.\n\n"
           f"Fonti: {'; '.join(item.get('fonti', []))}\n\n{hashtags(tag(c['nome']), tag(c['reg']), *extra_tag.split())}")
    return dict(tipo="carosello", file=files, didascalia=cap)
def carosello_storia(item, out):
    return carosello_racconto(item, out, "STORIE DI COMUNI", "Conoscete un comune con una storia così?", "#storiaitaliana")
def carosello_cibo(item, out):
    return carosello_racconto(item, out, "IL COMUNE E IL SUO PIATTO", "Qual è il piatto simbolo del vostro comune?", "#cucinaitaliana")

# ---------------------------------------------------------------- la tua provincia in numeri
def slide_comune(T, etichetta, c, valore, n, tot, fonte):
    img = canvas(T)
    pill(img, etichetta, (60, 80), font("k", 28), T["acc"], T["bg"] if T["acc"] != T["bg"] else T["ink"])
    place(img, draw_map(T, highlight=c["geom"], point=c["geom"].centroid, px=500), 860, 160, 300, 250)
    y = text_block(img, nome(c), (60, 190), fit_font(img, nome(c), "k", 600, 3, 84), T["ink"], 600, 1.0)
    y = max(y, 430)
    txt(img, (60, y + 14), label(c), font("b", 30), T["muted"])
    pill(img, valore, (60, y + 70), fit_font(img, valore, "k", 900, 1, 48), T["ink"], T["bg"])
    city_in(img, c, T, y + 70 + 48 + 28 + 30, BOTTOM, 520, con_foto=True)
    footer(img, T, n, tot, fonte); return img

ENTE = {"Città metropolitana": "Città metropolitana di {}", "Provincia autonoma": "Provincia autonoma di {}",
        "Libero consorzio di comuni": "Libero consorzio comunale di {}", "Provincia": "Provincia di {}"}
def province():
    """Province, città metropolitane e liberi consorzi. Esclusi: Sardegna (i confini disponibili usano ancora il vecchio
    assetto provinciale), Friuli-Venezia Giulia (le province non esistono più) e Valle d'Aosta (non ha province)."""
    comuni, _ = load()
    return sorted({c["prov"] for c in comuni if c["prov_tipo"] in ENTE and not c["reg"].startswith(("Sardegna", "Valle d'Aosta"))})
def carosello_provincia(sigla, out):
    comuni = extra(); sub = [c for c in comuni if c["prov"] == sigla]; pn = sub[0]["prov_nome"]; files = []; TOT = 7
    ente = ENTE[sub[0]["prov_tipo"]].format(pn)
    fonte = "Fonte: ISTAT (2011), openpolis"
    T = THEMES["indaco"]; img = canvas(T)
    pill(img, "IL TUO TERRITORIO IN NUMERI", (60, 80), font("k", 24), T["acc2"], "#FFFFFF")
    txt(img, (W - 60, 86), "scorri  →", font("k", 28), T["acc"], "ra")
    y = text_block(img, ente, (60, 180), fit_font(img, ente, "k", W - 120, 3, 88), T["ink"], W - 120, 1.02)
    r = random.Random(sigla); pal = ["#FF3E7F", "#FFD23F", "#2EC4F1", "#7B61FF", "#FF8C42", "#3DDC97"]
    place(img, draw_area(T, sub, color_fn=lambda c: r.choice(pal), px=900), W // 2, y + 50, 900, BOTTOM - y - 50)
    footer(img, T, None, None, fonte); files.append(save(img, out, "01"))
    T = THEMES["giallo"]; img = canvas(T)
    txt(img, (60, 70), ente.upper(), fit_font(img, ente.upper(), "b", 820, 1, 26), T["muted"])
    y = text_block(img, str(len(sub)), (60, 150), font("k", 220), T["acc"], W - 120)
    y = text_block(img, "comuni in tutto il territorio", (60, y + 10), font("x", 52), T["ink"], 620, 1.15)
    place(img, draw_map(T, highlight=prov_geom(sigla), px=700), 870, 160, 300, 380)
    text_block(img, f"Regione: {sub[0]['reg'].split('/')[0]}", (60, y + 50), font("m", 34), T["ink"], 620)
    footer(img, T, 2, TOT, fonte); files.append(save(img, out, "02"))
    big = max(sub, key=lambda c: c["area"]); small = min(sub, key=lambda c: c["area"])
    lung = max(sub, key=lambda c: (lettere(c), c["nome"])); popo = max(sub, key=lambda c: c["pop"] or 0)
    for i, (et, c, v) in enumerate([("IL PIÙ GRANDE", big, _area(big)), ("IL PIÙ PICCOLO", small, _area(small)),
                                    ("IL NOME PIÙ LUNGO", lung, f"{lettere(lung)} lettere"), ("IL PIÙ POPOLOSO", popo, f"{fmt(popo['pop'])} abitanti (2011)")]):
        files.append(save(slide_comune(THEMES[CYCLE[(i + 2) % 3]], et, c, v, i + 3, TOT, fonte), out, f"{i + 3:02d}"))
    img = cta_slide(THEMES["rosa"], f"Di quale comune sei? {ente} ne ha {len(sub)}", TOT, TOT, "ti mandiamo la sua scheda in DM")
    files.append(save(img, out, f"{TOT:02d}"))
    cap = (f"{ente} in pillole.\n\n{len(sub)} comuni. Il più grande è {nome(big)} ({_area(big)}), il più piccolo {nome(small)} ({_area(small)}). "
           f"Il nome più lungo? {nome(lung)}, {lettere(lung)} lettere.\n\nDi quale comune siete? Scrivetelo nei commenti: vi mandiamo la sua scheda in privato.\n\n"
           f"{fonte}\n\n{hashtags(tag(pn), tag(sub[0]['reg']))}")
    return dict(tipo="carosello", file=files, didascalia=cap)

# ---------------------------------------------------------------- derby del gusto
def reel_derby(dz, out):
    T = THEMES["rosa"]; TA, TB = THEMES["giallo"], THEMES["indaco"]
    ma = draw_map(TA, highlight=reg_geom(next(r for r in _regioni() if r.startswith(dz["reg_a"]))), px=300)
    mb = draw_map(TB, highlight=reg_geom(next(r for r in _regioni() if r.startswith(dz["reg_b"]))), px=300)
    tmp = canvas(T, VW, VH); fa, fb = (fit_font(tmp, x, "k", 440, 3, 70) for x in (dz["a"], dz["b"]))
    def frames():
        for f in range(int(8 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); d = ImageDraw.Draw(img); vhandle(img, T); e = ease(.5 + t / .5)
            pill(img, "DERBY DEL GUSTO", (70, 232), font("k", 30), T["acc"], T["acc2"])
            y = text_block(img, dz["domanda"], (70, 330), fit_font(img, dz["domanda"], "k", VW - 140, 2, 76), T["ink"], VW - 140, 1.02)
            top = y + 50
            for i, (nm, rg, M, TT, ff) in enumerate([(dz["a"], dz["reg_a"], ma, TA, fa), (dz["b"], dz["reg_b"], mb, TB, fb)]):
                dx = int((1 - e) * (-600 if i == 0 else 600)); x = i * 540 + dx
                d.rectangle((x + 20, top, x + 520, top + 900), fill=TT["bg"])
                txt(img, (x + 50, top + 30), str(i + 1), font("k", 150), TT["acc"], "la", f"num{i}")
                yy = text_block(img, nm, (x + 50, top + 220), ff, TT["ink"], 440, 1.0, f"piatto{i}")
                txt(img, (x + 50, yy + 14), rg, font("b", 32), TT["muted"], "la", f"reg{i}")
                M2 = M.copy(); M2.thumbnail((300, 340)); paste(img, M2, (x + 270 - M2.width // 2, top + 880 - M2.height), f"mappa{i}")
            if t > .8:
                pill(img, "Vota nei commenti: scrivi 1 o 2", (70, top + 940), fit_font(img, "Vota nei commenti: scrivi 1 o 2", "k", VW - 200, 1, 44), T["ink"], T["bg"])
                text_block(img, "Aggiungi il tuo comune: faremo la mappa dei voti!", (70, top + 1040), font("b", 34), T["ink"], VW - 140)
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "pop")
    cap = (f"{dz['domanda']}\n\nScrivete 1 per {dz['a']} o 2 per {dz['b']}. Se aggiungete il vostro comune, nei risultati facciamo la mappa d'Italia dei voti, regione per regione.\n\n"
           f"Un voto a testa, risultati tra tre giorni. Che vinca il migliore (cioè il vostro).\n\n{hashtags('#cucinaitaliana', tag(dz['a']), tag(dz['b']))}")
    return dict(tipo="reel", file=[path], didascalia=cap)

def _regioni():
    comuni, _ = load(); return sorted({c["reg"] for c in comuni})
def carosello_risultati(dz, voti, out):
    """voti: {utente: {"v": 1|2, "reg": regione o None}}"""
    files = []; TOT = 3; tot = len(voti); a = sum(1 for v in voti.values() if v["v"] == 1); b = tot - a
    pa = round(100 * a / tot) if tot else 0; pb = 100 - pa if tot else 0
    win = dz["a"] if a > b else dz["b"] if b > a else None
    T = THEMES["indaco"]; img = canvas(T)
    pill(img, "DERBY DEL GUSTO · RISULTATI", (60, 80), font("k", 24), T["acc2"], "#FFFFFF")
    titolo = f"Ha vinto {win}!" if win else "Pareggio perfetto!"
    y = text_block(img, titolo, (60, 180), fit_font(img, titolo, "k", W - 120, 3, 96), T["acc"], W - 120, 1.02)
    y += 60
    for nm, p, n, col in [(dz["a"], pa, a, "#FFD23F"), (dz["b"], pb, b, "#FF3E7F")]:
        txt(img, (60, y), nm, fit_font(img, nm, "x", 700, 1, 44), T["ink"]); txt(img, (W - 60, y), f"{p}%", font("k", 44), col, "ra", "perc")
        ImageDraw.Draw(img).rounded_rectangle((60, y + 70, 60 + max(24, int(960 * p / 100)), y + 110), 20, fill=col); reg((60, y + 70, 1020, y + 110), "barra")
        txt(img, (60, y + 126), f"{n} voti", font("m", 28), T["muted"]); y += 230
    text_block(img, f"Avete votato in {tot}. Grazie!", (60, y + 20), font("b", 36), T["ink"], W - 120)
    footer(img, T, 1, TOT, "Fonte: i vostri commenti"); files.append(save(img, out, "01"))
    T = THEMES["giallo"]; img = canvas(T)
    pill(img, "LA MAPPA DEI VOTI", (60, 80), font("k", 28), T["acc"], "#FFFFFF")
    per = {}
    for v in voti.values():
        if v.get("reg"): per.setdefault(v["reg"], [0, 0])[v["v"] - 1] += 1
    colore = {r: ("#E0A800" if x[0] > x[1] else "#FF3E7F" if x[1] > x[0] else "#7B61FF") for r, x in per.items()}
    x = pill(img, f"1 · {dz['a']}", (60, 180), fit_font(img, f"1 · {dz['a']}", "k", 360, 1, 32), "#E0A800", "#1A1446")
    pill(img, f"2 · {dz['b']}", (60, 260), fit_font(img, f"2 · {dz['b']}", "k", 360, 1, 32), "#FF3E7F", "#FFFFFF")
    pill(img, "pari", (60, 340), font("k", 32), "#7B61FF", "#FFFFFF")
    nota = f"Regioni con almeno un voto: {len(per)} su 20." if per else "Nessuno ha indicato il proprio comune: la prossima volta scrivetelo!"
    text_block(img, nota, (60, 440), font("m", 30), T["ink"], 400, 1.3)
    place(img, draw_map(T, color_fn=lambda c: colore.get(c["reg"]), px=900), 775, 170, 470, BOTTOM - 190)
    footer(img, T, 2, TOT, "Fonte: i vostri commenti"); files.append(save(img, out, "02"))
    img = cta_slide(THEMES["rosa"], "Quale sfida volete per il prossimo derby?", TOT, TOT, "proponi due piatti rivali")
    files.append(save(img, out, "03"))
    cap = (f"{'Ha vinto ' + win + '.' if win else 'Pareggio perfetto.'} {dz['a']} {pa}%, {dz['b']} {pb}%, su {tot} voti.\n\n"
           f"Nella seconda slide la mappa dei voti regione per regione: c'è la vostra?\n\nQuale sfida volete per il prossimo derby? Proponetela nei commenti.\n\n"
           f"{hashtags('#cucinaitaliana', tag(dz['a']), tag(dz['b']))}")
    return dict(tipo="carosello", file=files, didascalia=cap)
