"""I giochi di @italia_incomune.

- Il comune misterioso: ogni mattina un comune da indovinare (forma, regione, iniziale); punti a chi indovina, classifica la domenica.
- Il Torneo d'Italia: candidature nei commenti, poi 31 sfide a eliminazione diretta votate nei commenti, una al giorno.
- Accendiamo l'Italia: ogni comune scritto nei commenti si accende sulla mappa; ogni domenica il Reel con la mappa.
- La gara dello gnomo di Natale: ogni settimana il comune più scritto nei commenti vince uno gnomo spedito al municipio (fino al 20 dicembre).

I commenti li raccoglie il run dei commenti (stato/commenti.json); i Reel e i caroselli li genera il run di pubblicazione.
"""
import datetime, math, os, random
from PIL import Image, ImageDraw
from .base import load, extra, norm, fmt, THEMES, CYCLE, font, find, draw_map
from . import formati as F
from .formati import (canvas, vhandle, txt, text_block, fit_font, pill, paste, place, encode, save, footer, cta_slide,
                      nome, label, scena, city, sagoma, hashtags, tag, SEGUI, VW, VH, W, H, BOTTOM, FPS)
from . import motivi

D = datetime.date
INIZIO_GIOCHI = D(2026, 11, 18)
CANDIDATURE = [D(2026, 11, 18), D(2026, 11, 19), D(2026, 11, 20)]
INIZIO_SFIDE = D(2026, 11, 21)          # 31 sfide: dal 21 novembre al 21 dicembre, il campione il 22
GNOMO = [(D(2026, 11, 18), D(2026, 11, 22)), (D(2026, 11, 23), D(2026, 11, 29)), (D(2026, 11, 30), D(2026, 12, 6)),
         (D(2026, 12, 7), D(2026, 12, 13)), (D(2026, 12, 14), D(2026, 12, 20))]
DISCLAIMER = ("Regolamento: vince il comune scritto nei commenti dal maggior numero di persone diverse nella settimana (un comune a persona, "
              "conta il primo). Il premio, uno gnomo di Natale in una scatola regalo, è spedito al municipio del comune vincitore, non a privati. "
              "Partecipare è gratis; seguire l'account non è obbligatorio. Iniziativa non sponsorizzata, gestita o associata a Instagram o Meta.")
TURNI = [("Sedicesimi", 0, 16), ("Ottavi", 16, 8), ("Quarti", 24, 4), ("Semifinali", 28, 2), ("Finale", 30, 1)]
ORDINE_TABELLONE = [0, 15, 7, 8, 3, 12, 4, 11, 1, 14, 6, 9, 2, 13, 5, 10]

def oggi(): return datetime.date.today()
def pill_y(img, text, xy, f, bg, fg, tag="etichetta"):
    """Come pill, ma restituisce il bordo inferiore (per impilare le etichette)."""
    pill(img, text, xy, f, bg, fg, tag=tag); return xy[1] + f.size + 28
def comuni_per_istat():
    comuni, _ = load(); return {c["istat"]: c for c in comuni}

# ------------------------------------------------------------------ calendario dei giochi
def override(data, slot):
    """Il gioco previsto per quella data e quello slot, oppure None (vale il calendario normale)."""
    if data < INIZIO_GIOCHI: return None
    wd = data.weekday()  # lunedì = 0
    if slot == "mattina": return ("reel_misterioso", data.isoformat())
    if slot == "reel":
        if data in CANDIDATURE: return ("reel_torneo_candidature", str(CANDIDATURE.index(data) + 1))
        m = (data - INIZIO_SFIDE).days
        if 0 <= m <= 30: return ("reel_torneo_sfida", str(m))
        if m == 31: return ("reel_torneo_campione", "0")
    if slot == "carosello":
        if data == GNOMO[0][0]: return ("carosello_gnomo", "0")
        for i, (a, b) in enumerate(GNOMO[1:], 1):
            if data == a: return ("carosello_gnomo", str(i))
        if data == GNOMO[-1][1] + datetime.timedelta(days=1): return ("carosello_gnomo", str(len(GNOMO)))
        if wd == 6 and data >= D(2026, 11, 22): return ("carosello_classifica_giocatori", data.isoformat())
        if wd == 5 and D(2026, 11, 28) <= data <= D(2026, 12, 19): return ("carosello_tabellone", data.isoformat())
    if slot == "sera" and wd == 6 and data >= D(2026, 11, 22): return ("reel_accendiamo", data.isoformat())
    return None

# ------------------------------------------------------------------ raccolta dai commenti
def turno_gnomo(d):
    for i, (a, b) in enumerate(GNOMO):
        if a <= d <= b: return i
    return None

def registra(cs, post, cm_user, testo, c, quando, voto_fn):
    """Aggiorna i giochi con un commento. post = voce di 'pubblicati' (o None). Restituisce True se era una risposta di gioco."""
    g = cs.setdefault("giochi", {}); d = quando.date(); ts = quando.isoformat()
    gioco = False
    if c:
        g.setdefault("accesi", {}).setdefault(c["istat"], [cm_user, ts])
        t = turno_gnomo(d)
        if t is not None: g.setdefault("gnomo", {}).setdefault(str(t), {}).setdefault(cm_user, [c["istat"], ts])
    if post:
        f, p = post.get("formato"), str(post.get("param"))
        if f == "reel_misterioso" and c:
            g.setdefault("misterioso", {}).setdefault(post["data"], {}).setdefault(cm_user, [c["istat"], ts]); gioco = True
        elif f == "reel_torneo_candidature" and c:
            lst = g.setdefault("candidature", {}).setdefault(c["istat"], [])
            if cm_user not in lst: lst.append(cm_user)
        elif f == "reel_torneo_sfida":
            m, coppia = p.split(":") if ":" in p else (p, "")
            a, b = (coppia.split("-") + ["", ""])[:2]
            v = voto_fn(testo, a, b, c)
            if v: g.setdefault("torneo_voti", {}).setdefault(m, {})[cm_user] = v; gioco = True
    return gioco

def voto_sfida(testo, a, b, c):
    w = norm(testo).split()
    if c and c["istat"] == a: return 1
    if c and c["istat"] == b: return 2
    uno, due = "1" in w, "2" in w
    return 1 if uno and not due else 2 if due and not uno else None

# ------------------------------------------------------------------ il comune misterioso
def soluzione(s, data):
    return next((p["param"] for p in s["pubblicati"] if p.get("formato") == "reel_misterioso" and p.get("data") == data), None)

def punti(ts, data):
    t = datetime.datetime.fromisoformat(ts); g = D.fromisoformat(data)
    if t.date() == g and t.hour < 12: return 3
    if t.date() == g and t.hour < 18: return 2
    return 1

def esito_misterioso(s, cs, data):
    sol = soluzione(s, data); risposte = cs.get("giochi", {}).get("misterioso", {}).get(data, {})
    giusti = sorted([(ts, u) for u, (ist, ts) in risposte.items() if ist == sol], key=lambda x: x[0])
    return sol, giusti

def classifica_giocatori(s, cs, dal, al):
    tot = {}
    for data in cs.get("giochi", {}).get("misterioso", {}):
        if not (dal.isoformat() <= data <= al.isoformat()): continue
        sol, giusti = esito_misterioso(s, cs, data)
        for ts, u in giusti: tot[u] = tot.get(u, 0) + punti(ts, data)
    return sorted(tot.items(), key=lambda x: (-x[1], x[0]))

def scegli_misterioso(s, data):
    comuni, _ = load(); usati = {p.get("param") for p in s["pubblicati"] if p.get("formato") == "reel_misterioso"}
    cand = [c for c in comuni if 8000 <= (c["pop"] or 0) <= 150000 and c["istat"] not in usati and len(getattr(c["geom"], "geoms", [1])) <= 2]
    return random.Random(f"misterioso{data}").choice(cand)

def reel_misterioso(data, out, s, cs):
    c = scegli_misterioso(s, data); n = 1 + (D.fromisoformat(data) - INIZIO_GIOCHI).days
    ieri = (D.fromisoformat(data) - datetime.timedelta(days=1)).isoformat(); sol, giusti = esito_misterioso(s, cs, ieri)
    cid = comuni_per_istat(); cieri = cid.get(sol) if sol else None
    T = THEMES["indaco"]; TI = THEMES["giallo"]; sag = sagoma(c["geom"], 860, 600, T["acc"])
    lett = sum(ch.isalpha() for ch in c["nome"].split("/")[0])
    indizi = [("Indizio 1", "la forma"), ("Indizio 2", f"si trova in {c['reg'].split('/')[0]}"),
              ("Indizio 3", f"il nome ha {lett} lettere e inizia per «{c['nome'][0].upper()}»")]
    mappa_ieri = draw_map(TI, highlight=cieri["geom"], point=cieri["geom"].centroid, px=600) if cieri else None
    pre = 2.8 if cieri else 0.0
    def frames():
        for f in range(int((pre + 10.5) * FPS)):
            t = f / FPS
            if t < pre:
                img = canvas(TI, VW, VH); vhandle(img, TI)
                pill(img, "LA SOLUZIONE DI IERI", (70, 232), font("k", 28), TI["acc2"], "#FFFFFF")
                y = text_block(img, nome(cieri), (70, 320), fit_font(img, nome(cieri), "k", VW - 140, 2, 110), TI["ink"], VW - 140, 1.0)
                riga = (f"Indovinato da {len(giusti)} {'persona' if len(giusti) == 1 else 'persone'}. Il più veloce: @{giusti[0][1]}" if giusti
                        else "Nessuno l'ha indovinato. Oggi si rifà!")
                y = text_block(img, riga, (70, y + 30), fit_font(img, riga, "b", VW - 140, 2, 44), TI["ink"], VW - 140)
                place(img, mappa_ieri, VW // 2, y + 50, 760, VH - 220 - y - 50, "mappa")
            else:
                u = t - pre; img = canvas(T, VW, VH); vhandle(img, T)
                pill(img, f"IL COMUNE MISTERIOSO #{n}", (70, 232), font("k", 28), T["acc2"], "#FFFFFF")
                text_block(img, "Che comune è?", (70, 300), font("k", 96), T["ink"], VW - 140, 1.0)
                place(img, sag, VW // 2, 440, 860, 600, "forma")
                y = 1080
                for i, (a, b) in enumerate(indizi):
                    if u >= 1.2 + i * 2.4:
                        y = pill_y(img, f"{a}: {b}", (70, y), fit_font(img, f"{a}: {b}", "k", VW - 200, 1, 40), T["acc"] if i == len(indizi) - 1 else "#FFFFFF", "#1A1446", tag=f"indizio{i}") + 22
                if u >= 8.4:
                    msg = "Rispondi nei commenti: entro le 12 = 3 punti, entro le 18 = 2, dopo = 1. Soluzione domani alle 8:23."
                    text_block(img, msg, (70, 1500), fit_font(img, msg, "b", VW - 140, 3, 36), T["ink"], VW - 140, 1.2)
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "tensione")
    testa = f"Ieri era {nome(cieri)}: " + (f"indovinato da {len(giusti)}, il più veloce è stato @{giusti[0][1]}. " if giusti else "nessuno l'ha indovinato. ") if cieri else ""
    cap = (f"{testa}Il comune misterioso #{n}: che comune è?\n\nTre indizi nel video. Scrivete il nome nei commenti: conta la prima risposta. "
           f"Entro le 12 valete 3 punti, entro le 18 due, dopo uno. La soluzione domani alle 8:23, la classifica dei giocatori ogni domenica.\n\n"
           f"Seguite @italia_incomune per non perdere il prossimo indizio.\n\nConfini: openpolis\n\n{hashtags('#quiz', '#giochi', tag(c['reg']))}")
    return dict(tipo="reel", file=[path], didascalia=cap, param=c["istat"])

def carosello_classifica_giocatori(data, out, s, cs):
    al = D.fromisoformat(data); dal = al - datetime.timedelta(days=6)
    sett = classifica_giocatori(s, cs, dal, al)[:10]; tot = classifica_giocatori(s, cs, INIZIO_GIOCHI, al)[:5]; files = []; TOT = 3
    T = THEMES["giallo"]; img = canvas(T)
    pill(img, "IL COMUNE MISTERIOSO", (60, 80), font("k", 30), T["acc2"], "#FFFFFF")
    y = text_block(img, "La classifica della settimana", (60, 180), font("k", 84), T["ink"], W - 120, 1.02) + 40
    if not sett: y = text_block(img, "Nessuno ha indovinato questa settimana. Il podio è libero: si gioca ogni mattina alle 8:23.", (60, y), font("b", 40), T["ink"], W - 120, 1.25)
    for i, (u, p) in enumerate(sett):
        f = font("k" if i < 3 else "b", 40 if i < 3 else 34)
        txt(img, (60, y), f"{i + 1}. @{u}", fit_font(img, f"{i + 1}. @{u}", "k" if i < 3 else "b", 700, 1, 40 if i < 3 else 34), T["ink"])
        txt(img, (W - 60, y), f"{p} punti", f, T["acc"], "ra"); y += 70 if i < 3 else 58
    footer(img, T, 1, TOT, ""); files.append(save(img, out, "01"))
    T = THEMES["indaco"]; img = canvas(T)
    y = text_block(img, "Dall'inizio del gioco", (60, 180), font("k", 72), T["ink"], W - 120, 1.02) + 40
    if not tot: y = text_block(img, "La classifica generale è ancora vuota.", (60, y), font("b", 40), T["ink"], W - 120)
    for i, (u, p) in enumerate(tot):
        txt(img, (60, y), f"{i + 1}. @{u}", fit_font(img, f"{i + 1}. @{u}", "k", 700, 1, 42), T["ink"]); txt(img, (W - 60, y), f"{p}", font("k", 42), T["acc"], "ra"); y += 76
    y = text_block(img, "Chi è primo a fine dicembre diventa «Esploratore d'Italia» con un post tutto suo.", (60, y + 40), font("b", 36), T["acc"], W - 120, 1.25)
    footer(img, T, 2, TOT, ""); files.append(save(img, out, "02"))
    img = cta_slide(THEMES["rosa"], "Domani alle 8:23 un nuovo comune misterioso", TOT, TOT, "seguite per non perdere gli indizi"); files.append(save(img, out, "03"))
    primo = f"In testa questa settimana: @{sett[0][0]} con {sett[0][1]} punti. " if sett else ""
    cap = (f"La classifica del comune misterioso. {primo}Ogni mattina alle 8:23 un comune da indovinare: entro le 12 valete 3 punti, entro le 18 due, dopo uno.\n\n"
           f"Chi c'è in classifica? Taggate i vostri avversari.\n\n{hashtags('#quiz', '#giochi', '#classifica')}")
    return dict(tipo="carosello", file=files, didascalia=cap)

# ------------------------------------------------------------------ il Torneo d'Italia
def seeds(s, cs):
    """I 32 comuni del torneo: i più candidati nei commenti, completati dai comuni più popolosi. Fissati alla prima sfida."""
    t = s.setdefault("torneo", {})
    if t.get("seeds"): return t["seeds"]
    cid = comuni_per_istat(); cand = cs.get("giochi", {}).get("candidature", {})
    ordine = sorted(cand, key=lambda i: (-len(cand[i]), -(cid[i]["pop"] or 0) if i in cid else 0))
    sel = [i for i in ordine if i in cid][:32]
    for c in sorted(cid.values(), key=lambda c: -(c["pop"] or 0)):
        if len(sel) >= 32: break
        if c["istat"] not in sel: sel.append(c["istat"])
    t["seeds"] = sel; t["candidati"] = {i: len(cand.get(i, [])) for i in sel}; return sel

def partecipanti(m, s, cs):
    if m < 16:
        k = ORDINE_TABELLONE[m]; sd = seeds(s, cs); return sd[k], sd[31 - k]
    for nome_, ini, n in TURNI[1:]:
        if ini <= m < ini + n:
            prev = [x for x in TURNI if x[1] + x[2] == ini][0]; j = m - ini
            return vincitore(prev[1] + 2 * j, s, cs), vincitore(prev[1] + 2 * j + 1, s, cs)

def vincitore(m, s, cs):
    t = s.setdefault("torneo", {}).setdefault("risultati", {})
    if str(m) in t: return t[str(m)]["v"]
    a, b = partecipanti(m, s, cs); voti = cs.get("giochi", {}).get("torneo_voti", {}).get(str(m), {})
    va, vb = sum(1 for v in voti.values() if v == 1), sum(1 for v in voti.values() if v == 2)
    cand = s["torneo"].get("candidati", {})
    if va != vb: w = a if va > vb else b
    elif cand.get(a, 0) != cand.get(b, 0): w = a if cand.get(a, 0) > cand.get(b, 0) else b
    else: w = random.Random(f"spareggio{m}").choice([a, b])
    if m < (oggi() - INIZIO_SFIDE).days:        # il risultato si fissa solo a votazione chiusa
        t[str(m)] = dict(a=a, b=b, va=va, vb=vb, v=w)
    return w

def turno_di(m):
    for nome_, ini, n in TURNI:
        if ini <= m < ini + n: return nome_, m - ini + 1, n

def reel_torneo_candidature(k, out, s, cs):
    cid = comuni_per_istat(); cand = cs.get("giochi", {}).get("candidature", {})
    top = sorted(((len(v), i) for i, v in cand.items() if i in cid), reverse=True)[:5]
    T = THEMES["rosa"]; k = int(k); giorni = {1: "Ultimi 3 giorni", 2: "Ultimi 2 giorni", 3: "Ultimo giorno"}[k]
    regole = ["Scrivete il vostro comune nei commenti", "I 32 più nominati entrano nel tabellone", "Dal 21 novembre una sfida al giorno: votate voi",
              "Il 22 dicembre il Comune campione d'Italia"]
    def frames():
        for f in range(int(10 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T)
            pill(img, f"CANDIDATURE · {giorni.upper()}", (70, 232), font("k", 28), T["acc2"], "#FFFFFF")
            y = text_block(img, "Il Torneo d'Italia", (70, 310), font("k", 120), T["ink"], VW - 140, 1.0)
            y = text_block(img, "32 comuni, una sola vincitrice. Il vostro paese ce la può fare?", (70, y + 20), font("b", 44), T["acc"], VW - 140, 1.2) + 40
            for i, r_ in enumerate(regole):
                if t >= .4 + i * .7: y = pill_y(img, f"{i + 1}  {r_}", (70, y), fit_font(img, f"{i + 1}  {r_}", "k", VW - 200, 1, 36), "#FFFFFF", "#1A1446", tag=f"regola{i}") + 20
            if t >= 3.6:
                y += 30
                if top:
                    txt(img, (70, y), "Per ora in testa:", font("k", 44), T["ink"], tag="testa"); y += 70
                    for i, (n_, ist) in enumerate(top):
                        riga = f"{nome(cid[ist])} · {n_} {'voto' if n_ == 1 else 'voti'}"
                        txt(img, (70, y), riga, fit_font(img, riga, "b", VW - 140, 1, 38), T["ink"], tag=f"top{i}"); y += 56
                else:
                    text_block(img, "Il tabellone è vuoto: il primo comune lo scrivete voi.", (70, y), font("k", 50), T["ink"], VW - 140, 1.15)
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "pop")
    testa = ("In testa per ora: " + ", ".join(f"{nome(cid[i])} ({n_})" for n_, i in top[:3]) + ".\n\n") if top else ""
    cap = (f"Parte il Torneo d'Italia: 32 comuni, una sfida al giorno, il campione il 22 dicembre.\n\n{testa}"
           f"Per candidare il vostro comune scrivetelo qui sotto. Entrano i 32 più nominati, poi votate voi le sfide. "
           f"Chiamate amici e parenti: ogni persona conta.\n\nSeguite @italia_incomune per non perdere le sfide del vostro comune.\n\n{hashtags('#torneo', '#giochi', '#comuniitaliani')}")
    return dict(tipo="reel", file=[path], didascalia=cap)

def reel_torneo_sfida(m, out, s, cs):
    m = int(m); cid = comuni_per_istat(); a, b = (cid[x] for x in partecipanti(m, s, cs)); turno, k, n = turno_di(m)
    prima = s["torneo"].get("risultati", {}).get(str(m - 1)) if m > 0 else None
    if m > 0 and not prima: vincitore(m - 1, s, cs); prima = s["torneo"].get("risultati", {}).get(str(m - 1))
    T = THEMES["indaco"]; TA, TB = THEMES["rosa"], THEMES["giallo"]
    ia = scena(a, TA, 540, 360, margine=24, fs=15) or city(a, TA, 540, 360); ib = scena(b, TB, 540, 360, margine=24, fs=15) or city(b, TB, 540, 360)
    pre = 2.6 if prima else 0.0
    def frames():
        for f in range(int((pre + 9) * FPS)):
            t = f / FPS
            if t < pre:
                TI = THEMES["giallo"]; img = canvas(TI, VW, VH); vhandle(img, TI); w = cid[prima["v"]]; l = cid[prima["b"] if prima["v"] == prima["a"] else prima["a"]]
                vw, vl = (prima["va"], prima["vb"]) if prima["v"] == prima["a"] else (prima["vb"], prima["va"])
                pill(img, "RISULTATO DI IERI", (70, 232), font("k", 28), TI["acc2"], "#FFFFFF")
                y = text_block(img, f"{nome(w)} passa il turno!", (70, 330), fit_font(img, f"{nome(w)} passa il turno!", "k", VW - 140, 3, 100), TI["ink"], VW - 140, 1.0)
                riga = f"{vw} voti contro {vl} per {nome(l)}"
                text_block(img, riga, (70, y + 30), fit_font(img, riga, "b", VW - 140, 2, 46), TI["acc"], VW - 140)
                paste(img, city(w, TI, VW, 520), (0, VH - 220 - 520), "città")
            else:
                u = t - pre; img = canvas(T, VW, VH); d = ImageDraw.Draw(img); vhandle(img, T)
                pill(img, f"IL TORNEO D'ITALIA · {turno.upper()} {k}/{n}", (70, 232), fit_font(img, f"IL TORNEO D'ITALIA · {turno.upper()} {k}/{n}", "k", VW - 140, 1, 28), T["acc2"], "#FFFFFF")
                text_block(img, "Chi passa il turno?", (70, 300), fit_font(img, "Chi passa il turno?", "k", VW - 140, 1, 88), T["ink"], VW - 140, 1.0)
                for i, (c, im, TT) in enumerate([(a, ia, TA), (b, ib, TB)]):
                    x = i * 540; d.rectangle((x, 440, x + 540, 1400), fill=TT["bg"])
                    pill(img, str(i + 1), (x + 30, 470), font("k", 64), TT["ink"], TT["bg"], tag=f"numero{i}")
                    y = text_block(img, nome(c), (x + 30, 590), fit_font(img, nome(c), "k", 480, 3, 58), TT["ink"], 480, 1.0)
                    txt(img, (x + 30, y + 14), label(c), fit_font(img, label(c), "b", 480, 1, 30), TT["muted"])
                    paste(img, im, (x, 1400 - 360), "foto")
                txt(img, (VW // 2, 1430), "VS", font("k", 76), T["ink"], "ma")
                msg = "Vota 1 o 2 nei commenti · si chiude domani alle 18:23"
                text_block(img, msg, (70, 1560), fit_font(img, msg, "k", VW - 140, 2, 40), T["acc"], VW - 140, 1.15)
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "tensione")
    ieri = ""
    if prima:
        w = cid[prima["v"]]; ieri = f"Ieri {nome(w)} ha passato il turno ({max(prima['va'], prima['vb'])} a {min(prima['va'], prima['vb'])}).\n\n"
    cap = (f"{ieri}Il Torneo d'Italia, {turno.lower()} {k} di {n}: {nome(a)} o {nome(b)}?\n\nScrivete 1 per {nome(a)} o 2 per {nome(b)} nei commenti, "
           f"oppure il nome del comune. Un voto a persona, si chiude domani alle 18:23. Chiamate a raccolta il vostro paese!\n\n"
           f"Seguite @italia_incomune per vedere chi passa.\n\n{hashtags('#torneo', tag(a['nome']), tag(b['nome']))}")
    return dict(tipo="reel", file=[path], didascalia=cap, param=f"{m}:{a['istat']}-{b['istat']}")

def reel_torneo_campione(out, s, cs):
    cid = comuni_per_istat(); w = cid[vincitore(30, s, cs)]; fin = s["torneo"]["risultati"].get("30", {})
    T = THEMES["giallo"]; ill = city(w, T, VW, 640); rr = random.Random(7)
    coriandoli = [(rr.uniform(0, VW), rr.uniform(-VH, 0), rr.choice(["#FF3E7F", "#1A1446", "#FFFFFF", "#3DDC97"]), rr.uniform(260, 520)) for _ in range(90)]
    def frames():
        for f in range(int(9 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T); d = ImageDraw.Draw(img)
            pill(img, "IL TORNEO D'ITALIA · FINALE", (70, 232), font("k", 28), T["acc2"], "#FFFFFF")
            y = text_block(img, "Il Comune campione d'Italia è", (70, 320), font("k", 64), T["ink"], VW - 140, 1.05)
            y = text_block(img, nome(w), (70, y + 30), fit_font(img, nome(w), "k", VW - 140, 2, 140), T["acc"], VW - 140, 1.0)
            if fin: y = text_block(img, f"{fin.get('va', 0) + fin.get('vb', 0)} voti in finale. Grazie a tutti i paesi in gara!", (70, y + 30), font("b", 40), T["ink"], VW - 140)
            alto, basso = y + 40, VH - 220 - 640 - 20          # i coriandoli cadono solo nello spazio libero
            for (x, y0, col, v) in coriandoli:
                yy = alto + ((y0 + v * t) % max(1, basso - alto - 20))
                d.rectangle((x, yy, x + 12, yy + 20), fill=col)
            paste(img, ill, (0, VH - 220 - 640), "città")
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "pop")
    cap = (f"{nome(w)} è il Comune campione d'Italia! Un mese di sfide, 31 partite, e alla fine ha vinto il paese che si è fatto sentire di più.\n\n"
           f"Grazie a chi ha votato. A gennaio la prossima edizione: quale torneo volete? Scrivetelo nei commenti.\n\n{hashtags('#torneo', tag(w['nome']), tag(w['reg']))}")
    return dict(tipo="reel", file=[path], didascalia=cap)

def carosello_tabellone(data, out, s, cs):
    cid = comuni_per_istat(); m_oggi = (D.fromisoformat(data) - INIZIO_SFIDE).days; files = []
    pagine = []
    for nome_, ini, n in TURNI:
        righe = []
        for m in range(ini, ini + n):
            if m > m_oggi: break
            ab = partecipanti(m, s, cs)
            if None in ab: break
            r = s["torneo"].get("risultati", {}).get(str(m)) if m < m_oggi else None
            a, b = cid[ab[0]], cid[ab[1]]
            if r: righe.append((f"{nome(a)} {r['va']} – {r['vb']} {nome(b)}", r["v"]))
            else: righe.append((f"{nome(a)} – {nome(b)}", None))
        if righe: pagine.append((nome_, righe))
    TOT = len(pagine) + 2; T = THEMES["indaco"]; img = canvas(T)
    pill(img, "IL TORNEO D'ITALIA", (60, 80), font("k", 30), T["acc2"], "#FFFFFF")
    text_block(img, "Il tabellone aggiornato", (60, 180), font("k", 96), T["ink"], W - 120, 1.02)
    paste(img, city(cid[seeds(s, cs)[0]], T, W, 520), (0, BOTTOM - 520), "città")
    footer(img, T, None, None, ""); files.append(save(img, out, "01"))
    for i, (nome_, righe) in enumerate(pagine):
        T = THEMES[CYCLE[(i + 1) % 3]]; img = canvas(T)
        y = text_block(img, nome_, (60, 160), font("k", 80), T["ink"], W - 120) + 30
        size = 30 if len(righe) > 8 else 38
        for testo, v in righe:
            y = text_block(img, testo, (60, y), fit_font(img, testo, "b", W - 120, 1, size), T["ink"], W - 120) + (14 if size == 30 else 22)
        footer(img, T, i + 2, TOT, "Voti dai commenti"); files.append(save(img, out, f"{i + 2:02d}"))
    img = cta_slide(THEMES["giallo"], "Stasera alle 18:23 la prossima sfida", TOT, TOT, "votate il vostro comune nei commenti"); files.append(save(img, out, f"{TOT:02d}"))
    cap = (f"Il tabellone del Torneo d'Italia, aggiornato. Chi ci arriva fino al 22 dicembre?\n\nOgni sera alle 18:23 una sfida: si vota nei commenti con 1 o 2.\n\n"
           f"{hashtags('#torneo', '#giochi', '#comuniitaliani')}")
    return dict(tipo="carosello", file=files, didascalia=cap)

# ------------------------------------------------------------------ Accendiamo l'Italia
def reel_accendiamo(data, out, s, cs):
    cid = comuni_per_istat(); accesi = {i: v for i, v in cs.get("giochi", {}).get("accesi", {}).items() if i in cid}
    ordine = sorted(accesi, key=lambda i: accesi[i][1]); n = len(ordine); tot = len(cid)
    settimana = (D.fromisoformat(data) - datetime.timedelta(days=6)).isoformat(); nuovi = sum(1 for i in ordine if accesi[i][1][:10] >= settimana)
    per_reg = {}
    for c in cid.values(): per_reg.setdefault(c["reg"].split("/")[0], [0, 0])[1] += 1
    for i in ordine: per_reg[cid[i]["reg"].split("/")[0]][0] += 1
    best = max(per_reg.items(), key=lambda x: (x[1][0] / x[1][1], x[1][0])) if n else None
    T = THEMES["indaco"]; passi = 6; mappe = []
    for k in range(passi + 1):
        acc = set(ordine[: math.ceil(n * k / passi)])
        mappe.append(draw_map(T, color_fn=lambda c, acc=acc: "#FFD23F" if c["istat"] in acc else None, px=760))
    def frames():
        for f in range(int(10 * FPS)):
            t = f / FPS; img = canvas(T, VW, VH); vhandle(img, T)
            pill(img, "ACCENDIAMO L'ITALIA", (70, 232), font("k", 28), T["acc2"], "#FFFFFF")
            k = min(passi, int(t / .9)); cont = math.ceil(n * k / passi)
            y = text_block(img, f"{fmt(cont)} comuni accesi", (70, 300), fit_font(img, f"{fmt(cont)} comuni accesi", "k", VW - 140, 1, 96), T["acc"], VW - 140)
            txt(img, (70, y + 16), f"su {fmt(tot)} · {100 * n / tot:.1f}% dell'Italia".replace(".", ","), font("b", 40), T["ink"], tag="perc")
            place(img, mappe[k], VW // 2, y + 90, 820, 900, "mappa")
            if t >= 6.2:
                righe = [f"+{nuovi} questa settimana"] + ([f"Regione più accesa: {best[0]}"] if best else []) + ["Scrivi il tuo comune per accenderlo"]
                yy = 1450
                for i, r_ in enumerate(righe):
                    yy = pill_y(img, r_, (70, yy), fit_font(img, r_, "k", VW - 200, 1, 34), T["acc"] if i == len(righe) - 1 else "#FFFFFF", "#1A1446", tag=f"riga{i}") + 16
            yield img
    path = encode(os.path.join(out, "reel.mp4"), frames(), "pop")
    cap = (f"Accendiamo l'Italia: ogni comune che scrivete nei commenti si accende sulla mappa. Siamo a {fmt(n)} comuni su {fmt(tot)}"
           f"{f', {nuovi} nuovi questa settimana' if nuovi else ''}.\n\n{('La regione più accesa è ' + best[0] + '. ') if best else ''}"
           f"Il vostro comune è ancora spento? Scrivetelo qui sotto e taggate chi abita in un paese che manca.\n\n"
           f"Ogni domenica la mappa aggiornata: seguite @italia_incomune per vederla crescere.\n\n{hashtags('#mappe', '#giochi', '#comuniitaliani')}")
    return dict(tipo="reel", file=[path], didascalia=cap)

# ------------------------------------------------------------------ la gara dello gnomo di Natale
def classifica_gnomo(cs, t):
    voti = cs.get("giochi", {}).get("gnomo", {}).get(str(t), {}); cont = {}
    for u, (ist, ts) in voti.items(): cont.setdefault(ist, []).append(ts)
    return sorted(((len(v), sorted(v)[-1], ist) for ist, v in cont.items()), key=lambda x: (-x[0], x[1]))

def vincitore_gnomo(cs, t):
    cl = classifica_gnomo(cs, t); return (cl[0][2], cl[0][0]) if cl else (None, 0)

def carosello_gnomo(k, out, s, cs):
    """k = 0: lancio; 1..4: vincitore della settimana precedente e nuova settimana; 5: vincitore finale."""
    k = int(k); cid = comuni_per_istat(); files = []; finale = k == len(GNOMO)
    win, nv = vincitore_gnomo(cs, k - 1) if k > 0 else (None, 0)
    if win:
        s.setdefault("gnomo_vincitori", {})[str(k - 1)] = dict(istat=win, nome=cid[win]["nome"], prov=cid[win]["prov"], voti=nv)
    slides = []
    T = THEMES["rosa"]; img = canvas(T)
    pill(img, "LA GARA DELLO GNOMO DI NATALE", (60, 80), font("k", 28), T["acc2"], "#FFFFFF")
    if win:
        y = text_block(img, f"Lo gnomo va a {nome(cid[win])}!", (60, 170), fit_font(img, f"Lo gnomo va a {nome(cid[win])}!", "k", W - 120, 3, 96), T["ink"], W - 120, 1.02)
        y = text_block(img, f"{nv} persone hanno scritto {nome(cid[win])} nei commenti. Lo spediamo al municipio.", (60, y + 24), font("b", 38), T["acc"], W - 120, 1.25)
    else:
        y = text_block(img, "Vinci uno gnomo di Natale per il tuo comune", (60, 170), font("k", 86), T["ink"], W - 120, 1.02)
        y = text_block(img, "Ogni settimana fino al 20 dicembre", (60, y + 24), font("b", 42), T["acc"], W - 120)
    paste(img, motivi.disegna("gnomo", T, W, 560, k), (0, BOTTOM - 560), "gnomo")
    footer(img, T, None, None, ""); slides.append(img)
    T = THEMES["giallo"]; img = canvas(T)
    titolo = "Come si gioca" if not finale else "Com'è andata"
    y = text_block(img, titolo, (60, 160), font("k", 84), T["ink"], W - 120) + 40
    passi = ([("1", "Scrivete il nome del vostro comune nei commenti di qualsiasi nostro post."),
              ("2", "Conta una persona, un comune: chiamate amici, parenti e vicini di casa."),
              ("3", "La domenica sera si chiude: il comune con più persone vince."),
              ("4", "Lo gnomo, in una scatola regalo, parte per il municipio del comune vincitore.")] if not finale else
             [("5", "settimane di gara, dal 18 novembre al 20 dicembre."),
              (str(len(s.get("gnomo_vincitori", {}))), "gnomi in viaggio verso altrettanti municipi."),
              (str(len({u for t_ in cs.get("giochi", {}).get("gnomo", {}).values() for u in t_})), "persone hanno scritto il loro comune. Grazie!")])
    larg = max(ImageDraw.Draw(img).textlength(n_, font=font("k", 72)) for n_, _ in passi) + 40
    for j, (n_, t_) in enumerate(passi):
        txt(img, (60, y), n_, font("k", 72), T["acc"], tag=f"n{j}")
        y = max(y + 90, text_block(img, t_, (60 + larg, y + 6), font("b", 38), T["ink"], W - 120 - larg, 1.25) + 34)
    footer(img, T, 2, 4, ""); slides.append(img)
    T = THEMES["indaco"]; img = canvas(T)
    if win and not finale:
        albo = s.get("gnomo_vincitori", {})
        y = text_block(img, "Albo d'oro", (60, 160), font("k", 84), T["ink"], W - 120) + 40
        for t_, v in sorted(albo.items(), key=lambda x: int(x[0])):
            riga = f"Settimana {int(t_) + 1}: {nome(cid[v['istat']])} ({v['voti']})"
            y = text_block(img, riga, (60, y), fit_font(img, riga, "k", W - 120, 1, 44), T["ink"], W - 120) + 26
        y = text_block(img, f"Settimana {k + 1} di {len(GNOMO)}: si riparte da zero, ogni comune può vincere.", (60, y + 30), font("b", 38), T["acc"], W - 120, 1.25)
    else:
        y = text_block(img, "Il premio" if not finale else "Grazie!", (60, 160), font("k", 84), T["ink"], W - 120) + 40
        y = text_block(img, ("Uno gnomo di Natale in una scatola regalo, spedito al municipio con una lettera di auguri da @italia_incomune." if not finale
                             else "Gli gnomi stanno partendo. Se siete del comune vincitore, fateci vedere dove li mette il vostro sindaco!"), (60, y), font("b", 40), T["ink"], W - 120, 1.3)
    footer(img, T, 3, 4, ""); slides.append(img)
    T = THEMES["rosa"]; img = canvas(T)
    y = text_block(img, "Regolamento", (60, 160), font("k", 72), T["ink"], W - 120) + 30
    text_block(img, DISCLAIMER, (60, y), fit_font(img, DISCLAIMER, "m", W - 120, 18, 30), T["ink"], W - 120, 1.32)
    footer(img, T, 4, 4, ""); slides.append(img)
    for i, im in enumerate(slides): files.append(save(im, out, f"{i + 1:02d}"))
    if finale:
        testa = f"Ultima settimana: lo gnomo va a {nome(cid[win])}, con {nv} persone! " if win else "Ultima settimana chiusa. "
        corpo = "La gara dello gnomo è finita: grazie a tutti i paesi che hanno partecipato."
    elif win:
        testa = f"Lo gnomo di Natale della settimana va a {nome(cid[win])} ({cid[win]['prov']}): {nv} persone hanno scritto il loro comune! "
        corpo = f"Si riparte da zero: settimana {k + 1} di {len(GNOMO)}, si chiude domenica sera."
    else:
        testa = "Parte la gara dello gnomo di Natale! "
        corpo = "Ogni settimana, fino al 20 dicembre, il comune scritto da più persone nei commenti vince uno gnomo di Natale spedito al suo municipio."
    cap = (f"{testa}{corpo}\n\nCome si gioca: scrivete il vostro comune nei commenti di qualsiasi nostro post e chiamate a raccolta il paese. "
           f"Una persona, un comune.\n\nSe vi va, seguite @italia_incomune per sapere chi vince.\n\n{DISCLAIMER}\n\n{hashtags('#natale', '#giochi', '#comuniitaliani')}")
    return dict(tipo="carosello", file=files, didascalia=cap)

# ------------------------------------------------------------------ dispatcher
def genera(formato, par, out, s, cs):
    os.makedirs(out, exist_ok=True)
    if formato == "reel_misterioso": return reel_misterioso(par, out, s, cs)
    if formato == "reel_torneo_candidature": return reel_torneo_candidature(par, out, s, cs)
    if formato == "reel_torneo_sfida": return reel_torneo_sfida(par, out, s, cs)
    if formato == "reel_torneo_campione": return reel_torneo_campione(out, s, cs)
    if formato == "carosello_tabellone": return carosello_tabellone(par, out, s, cs)
    if formato == "carosello_classifica_giocatori": return carosello_classifica_giocatori(par, out, s, cs)
    if formato == "reel_accendiamo": return reel_accendiamo(par, out, s, cs)
    if formato == "carosello_gnomo": return carosello_gnomo(par, out, s, cs)
    raise ValueError(formato)
