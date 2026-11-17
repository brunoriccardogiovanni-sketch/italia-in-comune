"""Regia di Italia in comune.
python -m bot.main verifica            -> controlla token e account (non pubblica nulla)
python -m bot.main anteprima           -> genera in anteprima/ i contenuti dei prossimi GIORNI (default 7), senza pubblicare
python -m bot.main calendario          -> stampa il piano dei prossimi 60 giorni
python -m bot.main lancio              -> primo avvio: pubblica i primi 3 giorni (6 contenuti)
python -m bot.main pubblica carosello  -> pubblica il carosello di oggi (12:23)
python -m bot.main pubblica reel       -> pubblica il Reel di oggi (18:23); anche "mattina" (08:23) e "sera" (21:23)
python -m bot.main recupero            -> pubblica subito ciò che oggi doveva già uscire e gli extra in sospeso
python -m bot.main commenti            -> schede in DM a chi scrive un comune, conteggio voti dei derby
"""
import os, sys, json, datetime, subprocess, shutil, time, difflib, re, random
import requests
from . import formati as F, giochi as G
from .base import load, norm, ROOT
from .instagram import IG, rileva, APIError

STATO = ROOT / "stato" / "stato.json"
OGGI = datetime.date.fromisoformat(os.environ["DATA"]) if os.environ.get("DATA") else datetime.date.today()
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
MIN_VOTI = 5
J = lambda n: json.load(open(ROOT / "contenuti" / n))

def stato():
    s = json.loads(STATO.read_text() or "{}")
    for k, v in dict(pubblicati=[], commenti_gestiti=[], voti={}).items(): s.setdefault(k, v)
    return s
def salva(s): STATO.write_text(json.dumps(s, ensure_ascii=False, indent=1))

# Commenti e voti hanno un file a parte: così i run dei commenti e quelli di pubblicazione,
# che possono partire quasi insieme, non modificano mai lo stesso file.
STATO_C = ROOT / "stato" / "commenti.json"
def stato_commenti():
    if STATO_C.exists(): c = json.loads(STATO_C.read_text() or "{}")
    else:
        vecchio = json.loads(STATO.read_text() or "{}") if STATO.exists() else {}
        c = dict(commenti_gestiti=vecchio.get("commenti_gestiti", []), voti=vecchio.get("voti", {}))
    c.setdefault("commenti_gestiti", []); c.setdefault("voti", {}); return c
def salva_commenti(c): STATO_C.write_text(json.dumps(c, ensure_ascii=False, indent=1))

def git_push(msg):
    if not REPO: return
    subprocess.run(["git", "add", "-A", "media", "stato"], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0: return
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
    for _ in range(3):
        if subprocess.run(["git", "push"], cwd=ROOT).returncode == 0: return
        subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=ROOT)
    raise RuntimeError("git push non riuscito")

def url_pubblico(path):
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{rel}"
def attendi_url(url):
    for _ in range(20):
        try:
            if requests.head(url, timeout=20).status_code == 200: return
        except Exception: pass
        time.sleep(6)
    raise RuntimeError(f"Il file non è raggiungibile: {url}. Il repository è pubblico?")

# ------------------------------------------------------------ calendario (giorno 1 = primo giorno di pubblicazione)
REEL_SETT = ["sfida", "mappa", "derby", "comune", "countdown", "sfida", "mappa"]
CAR_SETT = ["storia", "provincia", "cibo", "classifica", "provincia", "risultati", "alterna"]
REEL_MATTINA = ["dove", "forma", "dove", "forma", "dove", "forma", "dove"]          # 08:23, quiz veloci
REEL_SERA = ["storia", "cibo", "forma", "storia", "cibo", "dove", "storia"]          # 21:23, racconti
SLOT_ORE = [("mattina", (8, 23)), ("carosello", (12, 23)), ("reel", (18, 23)), ("sera", (21, 23))]
SLOT = [s for s, _ in SLOT_ORE]
ORD_COUNTDOWN = ["area_max", "confinanti", "area_min", "nome_corto", "pezzi", "dens_max", "nome_lungo"]
ORD_CLASSIFICA = ["dens_max", "nome_lungo", "pezzi", "area_max", "nome_corto", "area_min", "confinanti"]

def piano(giorno):
    """Restituisce {"carosello": (formato, parametro), "reel": (formato, parametro)} per il giorno n (da 1)."""
    storie, cibo, derby, mappe = J("storie.json"), J("cibo.json"), J("derby.json"), list(F.MAPPE)
    datate = {x.get("comune") for x in tutti_speciali() if x.get("tipo") == "reel_storia"}
    storie = [x for x in storie if x["comune"] not in datate]          # Gubbio, Greccio...: escono solo nel loro giorno
    prov = F.province(); random.Random(7).shuffle(prov)
    if "TO" in prov: prov.remove("TO"); prov.insert(0, "TO")        # la Città metropolitana di Torino apre la serie
    n = dict(storia=0, cibo=0, provincia=0, classifica=0, countdown=0, mappa=0, derby=0, rstoria=0, rcibo=0)
    storie_r, cibo_r = storie[::-1], cibo[::-1]             # nei Reel le storie partono dal fondo: mai la stessa del carosello
    out = None; usati = {}                                   # comune -> ultimo giorno in cui è uscito
    def pesca(lista, chiave, g):
        """Il prossimo elemento della lista non uscito negli ultimi 10 giorni (in nessun formato)."""
        for _ in range(len(lista)):
            x = lista[n[chiave] % len(lista)]; n[chiave] += 1
            if g - usati.get(x["comune"], -99) > 10: break
        usati[x["comune"]] = g; return x["comune"]
    for g in range(1, giorno + 1):
        k = (g - 1) % 7; sett = (g - 1) // 7
        # reel
        tipo = REEL_SETT[k]
        if tipo == "mappa" and n["mappa"] < len(mappe): r = ("reel_mappa", mappe[n["mappa"]]); n["mappa"] += 1
        elif tipo == "countdown" and n["countdown"] < len(ORD_COUNTDOWN): r = ("reel_countdown", ORD_COUNTDOWN[n["countdown"]]); n["countdown"] += 1
        elif tipo == "derby" and n["derby"] < len(derby): r = ("reel_derby", derby[n["derby"]]["id"]); n["derby"] += 1
        elif tipo == "sfida": r = ("reel_sfida", f"{'area' if k == 0 else 'nord'}:s{g}")
        else: r = ("reel_comune", f"c{g}")
        # carosello
        tipo = CAR_SETT[k]
        if tipo == "alterna": tipo = "storia" if sett % 2 == 0 else "cibo"
        if tipo == "storia": c = ("carosello_storia", pesca(storie, "storia", g))
        elif tipo == "cibo": c = ("carosello_cibo", pesca(cibo, "cibo", g))
        elif tipo == "classifica" and n["classifica"] < len(ORD_CLASSIFICA): c = ("carosello_classifica", ORD_CLASSIFICA[n["classifica"]]); n["classifica"] += 1
        elif tipo == "risultati" and sett < len(derby): c = ("carosello_risultati", derby[sett]["id"])
        else: c = ("carosello_provincia", prov[n["provincia"] % len(prov)]); n["provincia"] += 1
        # Reel del mattino e della sera
        tipo = REEL_MATTINA[k]; mt = (f"reel_{tipo}", f"m{g}")
        tipo = REEL_SERA[k]
        if tipo == "storia": se = ("reel_storia", pesca(storie_r, "rstoria", g))
        elif tipo == "cibo": se = ("reel_cibo", pesca(cibo_r, "rcibo", g))
        else: se = (f"reel_{tipo}", f"s{g}")
        out = {"carosello": c, "reel": r, "mattina": mt, "sera": se}
    return out

# ------------------------------------------------------------ speciali a data fissa (contenuti/speciali.json)
def tutti_speciali():
    p = ROOT / "contenuti" / "speciali.json"
    return json.loads(p.read_text()) if p.exists() else []
def speciali():
    """Speciali che prendono il posto del contenuto del giorno (gli "extra" invece si aggiungono)."""
    return [x for x in tutti_speciali() if not x.get("in_piu")]
def data_di(s, giorno): return datetime.date.fromisoformat(s["inizio"]) + datetime.timedelta(days=giorno - 1)
def speciale(s, giorno, slot):
    d = data_di(s, giorno).isoformat()
    return next((x for x in speciali() if x["data"] == d and x.get("slot", "carosello") == slot), None)
def giorno_piano(s, giorno, slot):
    """Il contenuto saltato per uno speciale non si perde: il calendario normale slitta di un giorno."""
    ini, d = s["inizio"], data_di(s, giorno).isoformat()
    return giorno - sum(1 for x in speciali() if x.get("slot", "carosello") == slot and ini <= x["data"] < d)

def con_crediti(res):
    """Aggiunge alla didascalia, prima degli hashtag, autore e licenza di ogni foto usata."""
    visti, righe = set(), []
    for cr in F.foto.CREDITI:
        if cr["file"] in visti: continue
        visti.add(cr["file"]); righe.append(f"{cr['comune']}: {cr['autore']}, {cr['licenza']} (Wikimedia Commons, {cr['file']})")
    if righe:
        testo, tags = res["didascalia"].rsplit("\n\n", 1)
        for forma in (righe, [r.split(" (Wikimedia")[0] for r in righe]):      # Instagram accetta al massimo 2.200 caratteri
            cap = f"{testo}\n\nFoto da Wikimedia Commons. " + "; ".join(forma) + f"\n\n{tags}"
            if len(cap) <= 2150: break
        res["didascalia"] = cap if len(cap) <= 2150 else f"{testo}\n\nFoto: Wikimedia Commons, autori e licenze nelle slide.\n\n{tags}"
    return res

def genera(giorno, slot, s, out):
    F.foto.CREDITI.clear(); return con_crediti(_genera(giorno, slot, s, out))

def genera_speciale(sp, out):
    os.makedirs(out, exist_ok=True); tipo = sp.get("tipo", "carosello")
    if tipo == "carosello": res = F.carosello_speciale(sp, out)
    elif tipo == "regioni": res = F.reel_regioni(sp, out)
    elif tipo in ("storia", "cibo"): res = getattr(F, f"carosello_{tipo}")(sp, out)
    elif tipo == "sfida": a, b = F.find(sp["a"]), F.find(sp["b"]); res = F.reel_sfida(a, b, out, sp.get("domanda", "area"))
    elif tipo == "mappa": res = F.reel_mappa(sp["mappa"], out)
    elif tipo == "reel_storia":           # «Accadde oggi»: una storia legata alla data esatta
        item = sp if sp.get("slide") else next(x for x in J("storie.json") if x["comune"] == sp["comune"])
        item = dict(item, **{k: v for k, v in sp.items() if k in ("didascalia", "titolo")})
        d = datetime.date.fromisoformat(sp["data"]); mesi = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
        res = F.reel_racconto(item, out, sp.get("etichetta") or f"ACCADDE OGGI · {d.day} {mesi[d.month - 1].upper()}", "Lo sapevate?", "#accaddeoggi")
    else: raise ValueError(f"Tipo di speciale sconosciuto: {tipo}")
    res["formato"], res["param"] = f"speciale_{tipo}", sp["data"]
    return res

def _genera(giorno, slot, s, out):
    os.makedirs(out, exist_ok=True); comuni, _ = load()
    sp = speciale(s, giorno, slot)
    if sp: return genera_speciale(sp, out)
    ov = G.override(data_di(s, giorno), slot)          # i giochi hanno la precedenza sul calendario normale
    if ov:
        formato, par = ov; res = G.genera(formato, par, out, s, stato_commenti())
        res["formato"] = formato; res.setdefault("param", par); return res
    formato, par = piano(giorno_piano(s, giorno, slot))[slot]
    if formato == "reel_comune":
        fatti = {p.get("param") for p in s["pubblicati"]}
        cand = [c for c in comuni if c["istat"] not in fatti and c["pop"]]
        c = random.Random(par).choice(cand); res = F.reel_comune(c, out); par = c["istat"]
    elif formato == "reel_sfida":
        tipo, seme = par.split(":"); a, b = F.coppia(seme, tipo); res = F.reel_sfida(a, b, out, tipo); par = f"{tipo}:{a['istat']}-{b['istat']}"
    elif formato in ("carosello_storia", "carosello_cibo", "reel_storia", "reel_cibo"):
        item = next(x for x in J("storie.json" if formato.endswith("storia") else "cibo.json") if x["comune"] == par)
        res = getattr(F, formato)(item, out)
    elif formato in ("reel_forma", "reel_dove"):
        res = getattr(F, formato)(par, out); par = res.get("param", par)
    elif formato == "reel_derby":
        res = F.reel_derby(next(d for d in J("derby.json") if d["id"] == par), out)
    elif formato == "carosello_risultati":
        voti = stato_commenti()["voti"].get(par, {})
        if len(voti) < MIN_VOTI:            # troppo pochi voti: al loro posto una provincia (diversa dal piano)
            prov = F.province(); random.Random(99).shuffle(prov)
            formato, par = "carosello_provincia", prov[giorno % len(prov)]; res = F.carosello_provincia(par, out)
        else:
            res = F.carosello_risultati(next(d for d in J("derby.json") if d["id"] == par), voti, out)
    else:
        res = getattr(F, formato)(par, out)
    res["formato"], res["param"] = formato, par
    return res

def giorno_di(s, data=None):
    data = data or OGGI
    if not s.get("inizio"): return None
    return (data - datetime.date.fromisoformat(s["inizio"])).days + 1

# ------------------------------------------------------------ comandi
def senza_token():
    if os.environ.get("IG_TOKEN"): return False
    print("Il token non è ancora configurato: non faccio nulla."); return True

def client(s):
    tok = os.environ["IG_TOKEN"]
    if not s.get("host"):
        host, ig, user, log = rileva(tok, os.environ.get("GRAPH_HOST") or None, os.environ.get("IG_USER_ID") or None)
        if not ig: print("\n".join(log)); sys.exit("Non riesco a trovare l'account Instagram con questo token.")
        s.update(host=host, ig_id=ig, username=user); salva(s)
    return IG(tok, s["host"], s["ig_id"])

def cmd_verifica():
    if senza_token(): sys.exit(1)
    host, ig, user, log = rileva(os.environ["IG_TOKEN"], os.environ.get("GRAPH_HOST") or None, os.environ.get("IG_USER_ID") or None)
    print("Prove effettuate:\n  " + "\n  ".join(log))
    if not ig: sys.exit("\n❌ Token non valido o account non trovato.")
    print(f"\n✅ Collegato a @{user} (id {ig}) tramite {host}")
    s = stato(); s.update(host=host, ig_id=ig, username=user); salva(s); git_push("verifica collegamento")

def cmd_calendario():
    s = stato(); s.setdefault("inizio", OGGI.isoformat())
    for g in range(1, int(os.environ.get("GIORNI", "60")) + 1):
        riga = [f"giorno {g:2d} ({data_di(s, g):%d/%m})"]
        for slot in SLOT:
            sp = speciale(s, g, slot); ov = G.override(data_di(s, g), slot)
            f, p = (f"SPECIALE {sp.get('tipo', 'carosello')}", sp.get("titolo", "")[:30]) if sp else (ov or piano(giorno_piano(s, g, slot))[slot])
            riga.append(f"{slot}: {f} {p}")
        print("  ".join(riga))

def cmd_anteprima():
    s = stato(); s.setdefault("inizio", OGGI.isoformat()); out = ROOT / "anteprima"; shutil.rmtree(out, ignore_errors=True)
    g0 = giorno_di(s); d = out / "00_presentazione"; res = F.carosello_intro(str(d)); (d / "didascalia.txt").write_text(res["didascalia"])
    for i, sp in enumerate(x for x in tutti_speciali() if x.get("in_piu") and x["data"] >= OGGI.isoformat()):
        d = out / f"00_extra_{sp['data']}_{sp.get('slot', 'carosello')}"; F.foto.CREDITI.clear()
        res = con_crediti(genera_speciale(sp, str(d))); (d / "didascalia.txt").write_text(res["didascalia"])
    for k in range(int(os.environ.get("GIORNI", "7"))):
        for slot in SLOT:
            g = g0 + k; d = out / f"giorno{g:02d}_{slot}"
            res = genera(g, slot, s, str(d)); (d / "didascalia.txt").write_text(res["didascalia"])
            s["pubblicati"].append(dict(giorno=g, slot=slot, formato=res["formato"], param=str(res["param"])))
            print("ok", g, slot, res["formato"], res["param"] if isinstance(res["param"], str) else "")

def pubblica(s, ig, giorno, slot):
    if any(p.get("giorno") == giorno and p.get("slot") == slot for p in s["pubblicati"]): return print(f"Giorno {giorno} {slot}: già pubblicato.")
    out = ROOT / "media" / f"giorno{giorno:02d}_{slot}"; res = genera(giorno, slot, s, str(out))
    if res["tipo"] == "reel":
        mid = ig.reel(res["file"][0], res["didascalia"])
        for f in res["file"]: os.remove(f)
    else:
        git_push(f"media giorno {giorno}"); urls = [F_url for F_url in map(url_pubblico, res["file"])]
        for u in urls: attendi_url(u)
        mid = ig.carosello(urls, res["didascalia"]) if len(urls) > 1 else ig.immagine(urls[0], res["didascalia"])
    s["pubblicati"].append(dict(giorno=giorno, slot=slot, data=OGGI.isoformat(), formato=res["formato"], param=str(res["param"]), media_id=mid))
    salva(s); git_push(f"pubblicato giorno {giorno} {slot} {res['formato']}"); print("✅ pubblicato", giorno, slot, res["formato"], mid)

def invia(s, ig, res, msg):
    if res["tipo"] == "reel":
        mid = ig.reel(res["file"][0], res["didascalia"])
        for f in res["file"]: os.remove(f)
    else:
        git_push(msg); urls = list(map(url_pubblico, res["file"]))
        for u in urls: attendi_url(u)
        mid = ig.carosello(urls, res["didascalia"]) if len(urls) > 1 else ig.immagine(urls[0], res["didascalia"])
    return mid

def pubblica_extra(s, ig, slot=None):
    """Contenuti extra (in più rispetto al calendario) con data di oggi o passata, non ancora usciti."""
    fatti = set(s.setdefault("extra_fatti", []))
    for sp in tutti_speciali():
        chiave = f"{sp['data']}:{sp.get('slot', 'carosello')}:{sp.get('titolo', sp.get('tipo'))}"
        if not sp.get("in_piu") or chiave in fatti or sp["data"] > OGGI.isoformat(): continue
        if slot and sp.get("slot", "carosello") != slot: continue
        F.foto.CREDITI.clear(); res = con_crediti(genera_speciale(sp, str(ROOT / "media" / f"extra_{sp['data']}_{sp.get('slot', 'carosello')}")))
        mid = invia(s, ig, res, f"media extra {sp['data']}")
        s["extra_fatti"].append(chiave); s["pubblicati"].append(dict(extra=chiave, data=OGGI.isoformat(), formato=res["formato"], media_id=mid))
        salva(s); git_push(f"pubblicato extra {chiave}"); print("✅ extra pubblicato", chiave, mid)

def cmd_extra():
    if senza_token(): return
    s = stato(); pubblica_extra(s, client(s), "carosello")

def scaduti(adesso=None):
    """Gli slot di oggi il cui orario è già passato (gli orari sono in ora italiana)."""
    adesso = adesso or datetime.datetime.now()
    return [s for s, (h, mi) in SLOT_ORE if (adesso.hour, adesso.minute) >= (h, mi)]

def recupera(s, ig, slots):
    """Pubblica tutto ciò che è dovuto e non è ancora uscito. Un errore su un contenuto non blocca gli altri."""
    g, errori = giorno_di(s), []
    for slot in slots:
        try: pubblica(s, ig, g, slot)
        except Exception as e: errori.append(f"{slot}: {e}"); registra_errore(f"pubblica {slot}")
    for slot in SLOT:
        try: pubblica_extra(s, ig, slot)
        except Exception as e: errori.append(f"extra {slot}: {e}"); registra_errore(f"extra {slot}")
    if errori: raise RuntimeError("Alcuni contenuti non sono usciti: " + " | ".join(errori))

def cmd_pubblica(slot):
    """Run programmato: pubblica lo slot richiesto e recupera quelli di oggi rimasti indietro."""
    if senza_token(): return
    s = stato()
    if not s.get("inizio"): s["inizio"] = OGGI.isoformat(); salva(s)
    da_fare = [x for x in SLOT if x in scaduti() or x == slot]
    ig = client(s); recupera(s, ig, da_fare)
    if slot == "sera" and OGGI.weekday() == 6:
        try: report(s, ig)
        except Exception as e: print("Resoconto non riuscito:", e)

def report(s, ig):
    """Resoconto settimanale in stato/report.md: per ogni post, copertura, visualizzazioni, interazioni e (se disponibili) follower portati."""
    righe = ["| data | formato | copertura | visualizz. | like | commenti | condivisioni | salvataggi | follower | visite profilo |", "|" + "---|" * 10]
    limite = (OGGI - datetime.timedelta(days=14)).isoformat()
    for p in sorted(s["pubblicati"], key=lambda p: p.get("data", "")):
        if p.get("data", "") < limite or not p.get("media_id"): continue
        val = {}
        for metriche in ("reach,views,likes,comments,shares,saved,follows,profile_visits", "reach,views,likes,comments,shares,saved", "reach,likes,comments,saved"):
            try:
                for x in ig.get(f"{p['media_id']}/insights", metric=metriche).get("data", []):
                    val[x["name"]] = x.get("values", [{}])[0].get("value", x.get("total_value", {}).get("value"))
                break
            except Exception: continue
        righe.append("| " + " | ".join(str(v) for v in [p.get("data"), p.get("formato"), *(val.get(k, "–") for k in
                     ("reach", "views", "likes", "comments", "shares", "saved", "follows", "profile_visits"))]) + " |")
    (ROOT / "stato" / "report.md").write_text(f"# Resoconto al {OGGI:%d/%m/%Y}\n\nUltime due settimane. «–» = dato non disponibile "
                                              f"(serve il permesso instagram_manage_insights).\n\n" + "\n".join(righe) + "\n")
    git_push("resoconto settimanale")

def cmd_report():
    if senza_token(): return
    s = stato(); report(s, client(s))

def cmd_recupero():
    """A mano: fa uscire subito tutto quello che oggi doveva già essere uscito, più gli extra in sospeso."""
    if senza_token(): return
    s = stato(); recupera(s, client(s), scaduti())

def cmd_lancio():
    """Primo avvio: i giorni 1, 2 e 3 escono subito (6 contenuti); da domani si prosegue col giorno 4."""
    if senza_token(): return
    s = stato()
    if s.get("inizio"): return print("Il lancio è già stato fatto.")
    s["inizio"] = (OGGI - datetime.timedelta(days=2)).isoformat(); salva(s); ig = client(s)
    for g in (1, 2, 3):
        for slot in ("carosello", "reel"):
            pubblica(s, ig, g, slot); time.sleep(20)

def cmd_intro():
    """Post di presentazione: esce una volta sola, poi va fissato in alto dal profilo."""
    if senza_token(): return
    s = stato()
    if s.get("intro"): return print("Il post di presentazione è già stato pubblicato.")
    res = F.carosello_intro(str(ROOT / "media" / "intro"))
    git_push("media presentazione"); urls = list(map(url_pubblico, res["file"]))
    for u in urls: attendi_url(u)
    s["intro"] = ig_id = client(s).carosello(urls, res["didascalia"])
    salva(s); git_push("pubblicato post di presentazione"); print("✅ presentazione pubblicata", ig_id)

# ------------------------------------------------------------ commenti: schede e voti
_idx = None
def indice():
    global _idx
    if _idx is None:
        comuni, _ = load(); _idx = {}
        for c in comuni:
            for var in {c["nome"], *re.split(r"[/]", c["nome"]), *re.split(r"[-]", c["nome"].split("/")[0])}:
                k = norm(var)
                if len(k) >= 3: _idx.setdefault(k, []).append(c)
    return _idx
def norm_caps(testo):
    return " ".join(norm(w) for w in re.findall(r"\b[A-ZÀ-Ý][\wÀ-ÿ']*", testo))
def trova_comune(testo):
    idx = indice(); words = norm(testo).split()
    sig = {w.upper() for w in re.findall(r"\b[A-Za-z]{2}\b", testo)}
    for n in range(min(7, len(words)), 0, -1):
        for i in range(len(words) - n + 1):
            k = " ".join(words[i:i + n])
            if k in idx:
                if n == 1 and len(words) > 3 and not re.search(r"\b" + re.escape(k) + r"\b", norm_caps(testo)): continue
                hits = idx[k]; pick = [c for c in hits if c["prov"] in sig] or hits
                return pick[0]
    if 1 <= len(words) <= 5:
        m = difflib.get_close_matches(" ".join(words), list(idx), n=1, cutoff=0.88)
        if m: return idx[m[0]][0]
    return None
def voto(testo, dz):
    t = norm(testo); w = t.split()
    a = "1" in w or any(k in t for k in dz["chiavi_a"]); b = "2" in w or any(k in t for k in dz["chiavi_b"])
    return 1 if a and not b else 2 if b and not a else None

def cmd_commenti():
    if senza_token(): return
    s = stato()
    if not s["pubblicati"]: return print("Nessun post pubblicato ancora.")
    ig = client(s); cs = stato_commenti(); gestiti = set(cs["commenti_gestiti"]); fatti = 0
    derby_di = {p["media_id"]: p["param"] for p in s["pubblicati"] if p.get("formato") == "reel_derby" and p.get("media_id")}
    derby = {d["id"]: d for d in J("derby.json")}
    limite = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=6)
    try: recenti = ig.media_recenti(30)
    except Exception as e: return print("Non riesco a leggere i post recenti:", e)
    post_di = {p["media_id"]: p for p in s["pubblicati"] if p.get("media_id")}
    for m in recenti:
        dz = derby.get(derby_di.get(m["id"])); post = post_di.get(m["id"])
        try: commenti = ig.commenti(m["id"])
        except Exception as e:
            print(f"Commenti del post {m['id']} non leggibili:", e); continue
        for cm in commenti:
            if cm["id"] in gestiti: continue
            gestiti.add(cm["id"]); user = (cm.get("username") or (cm.get("from") or {}).get("username") or cm["id"])
            if user.lower() == (s.get("username") or "").lower(): continue
            try:
                quando_utc = datetime.datetime.fromisoformat(cm["timestamp"].replace("+0000", "+00:00"))
                if quando_utc < limite: continue
                quando = quando_utc.astimezone().replace(tzinfo=None)          # ora italiana (TZ del workflow)
            except Exception: quando = datetime.datetime.now()
            testo = cm.get("text", ""); c = trova_comune(testo); msg = None
            try: gioco = G.registra(cs, post, user, testo, c, quando, G.voto_sfida)
            except Exception as e: print("Gioco non registrato:", e); gioco = False
            if dz:
                v = voto(testo, dz)
                if v:
                    cs["voti"].setdefault(dz["id"], {})[user] = dict(v=v, reg=c["reg"] if c else None)
                    continue                     # il voto si conta in silenzio, senza rispondere
            if not c or gioco or fatti >= 10: continue          # niente messaggi privati per le risposte ai giochi
            try:
                path = ROOT / "media" / "schede" / f"{c['istat']}.png"
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True); F.scheda(c, str(path)); git_push(f"scheda {c['nome']}")
                url = url_pubblico(str(path)); attendi_url(url)
                righe = "\n".join(f"• {v} {k}" for v, k in F.stats(c))
                msg = f"Ciao! Ecco la scheda di {F.nome(c)} ({c['prov']}) 📍\n{righe}\n\nLa scheda illustrata: {url}\n\nIl tuo comune ora è acceso sulla nostra mappa d'Italia 🇮🇹"
            except Exception as e:
                print(f"Scheda di {c['nome']} non pronta:", e); continue
            try: ig.risposta_privata(cm["id"], msg)
            except Exception as e:
                print("DM non riuscito:", e)
            fatti += 1
    cs["commenti_gestiti"] = list(gestiti)[-5000:]; salva_commenti(cs); git_push("commenti e voti"); print("risposte inviate:", fatti)

def registra_errore(azione):
    """Scrive l'ultimo errore in stato/, così si può leggere dal repository senza aprire i log di GitHub."""
    import traceback
    gruppo = "commenti" if azione == "commenti" else "pubblicazione"
    (ROOT / "stato" / f"errore_{gruppo}.txt").write_text(
        f"{datetime.datetime.now():%Y-%m-%d %H:%M} · azione: {azione}\n\n{traceback.format_exc()}")
    try: git_push(f"errore durante {azione}")
    except Exception: pass

if __name__ == "__main__":
    a = sys.argv[1]
    try:
        if a == "pubblica": cmd_pubblica(sys.argv[2] if len(sys.argv) > 2 else os.environ.get("SLOT", "reel"))
        else: {"lancio": cmd_lancio, "verifica": cmd_verifica, "anteprima": cmd_anteprima, "calendario": cmd_calendario, "commenti": cmd_commenti, "intro": cmd_intro, "extra": cmd_extra, "recupero": cmd_recupero, "report": cmd_report}[a]()
    except Exception:
        registra_errore(" ".join(sys.argv[1:])); raise
