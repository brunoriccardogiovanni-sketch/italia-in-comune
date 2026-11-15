"""Regia di Italia in comune.
python -m bot.main verifica            -> controlla token e account (non pubblica nulla)
python -m bot.main anteprima           -> genera in anteprima/ i contenuti dei prossimi GIORNI (default 7), senza pubblicare
python -m bot.main calendario          -> stampa il piano dei prossimi 60 giorni
python -m bot.main lancio              -> primo avvio: pubblica i primi 3 giorni (6 contenuti)
python -m bot.main pubblica carosello  -> pubblica il carosello di oggi (12:23)
python -m bot.main pubblica reel       -> pubblica il Reel di oggi (18:23)
python -m bot.main commenti            -> schede in DM a chi scrive un comune, conteggio voti dei derby
"""
import os, sys, json, datetime, subprocess, shutil, time, difflib, re, random
import requests
from . import formati as F
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

def git_push(msg):
    if not REPO: return
    subprocess.run(["git", "add", "-A", "media", "stato"], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0: return
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
    for _ in range(3):
        if subprocess.run(["git", "push"], cwd=ROOT).returncode == 0: return
        subprocess.run(["git", "pull", "--rebase"], cwd=ROOT)
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
ORD_COUNTDOWN = ["area_max", "confinanti", "area_min", "nome_corto", "pezzi", "dens_max", "nome_lungo"]
ORD_CLASSIFICA = ["dens_max", "nome_lungo", "pezzi", "area_max", "nome_corto", "area_min", "confinanti"]

def piano(giorno):
    """Restituisce {"carosello": (formato, parametro), "reel": (formato, parametro)} per il giorno n (da 1)."""
    storie, cibo, derby, mappe = J("storie.json"), J("cibo.json"), J("derby.json"), list(F.MAPPE)
    prov = F.province(); random.Random(7).shuffle(prov)
    if "TO" in prov: prov.remove("TO"); prov.insert(0, "TO")        # la Città metropolitana di Torino apre la serie
    n = dict(storia=0, cibo=0, provincia=0, classifica=0, countdown=0, mappa=0, derby=0)
    out = None
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
        if tipo == "storia" and n["storia"] < len(storie): c = ("carosello_storia", storie[n["storia"]]["comune"]); n["storia"] += 1
        elif tipo == "cibo" and n["cibo"] < len(cibo): c = ("carosello_cibo", cibo[n["cibo"]]["comune"]); n["cibo"] += 1
        elif tipo == "classifica" and n["classifica"] < len(ORD_CLASSIFICA): c = ("carosello_classifica", ORD_CLASSIFICA[n["classifica"]]); n["classifica"] += 1
        elif tipo == "risultati" and sett < len(derby): c = ("carosello_risultati", derby[sett]["id"])
        else: c = ("carosello_provincia", prov[n["provincia"] % len(prov)]); n["provincia"] += 1
        out = {"carosello": c, "reel": r}
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
    else: raise ValueError(f"Tipo di speciale sconosciuto: {tipo}")
    res["formato"], res["param"] = f"speciale_{tipo}", sp["data"]
    return res

def _genera(giorno, slot, s, out):
    os.makedirs(out, exist_ok=True); comuni, _ = load()
    sp = speciale(s, giorno, slot)
    if sp: return genera_speciale(sp, out)
    formato, par = piano(giorno_piano(s, giorno, slot))[slot]
    if formato == "reel_comune":
        fatti = {p.get("param") for p in s["pubblicati"]}
        cand = [c for c in comuni if c["istat"] not in fatti and c["pop"]]
        c = random.Random(par).choice(cand); res = F.reel_comune(c, out); par = c["istat"]
    elif formato == "reel_sfida":
        tipo, seme = par.split(":"); a, b = F.coppia(seme, tipo); res = F.reel_sfida(a, b, out, tipo); par = f"{tipo}:{a['istat']}-{b['istat']}"
    elif formato in ("carosello_storia", "carosello_cibo"):
        item = next(x for x in J("storie.json" if formato == "carosello_storia" else "cibo.json") if x["comune"] == par)
        res = getattr(F, formato)(item, out)
    elif formato == "reel_derby":
        res = F.reel_derby(next(d for d in J("derby.json") if d["id"] == par), out)
    elif formato == "carosello_risultati":
        voti = s["voti"].get(par, {})
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
        for slot in ("carosello", "reel"):
            sp = speciale(s, g, slot)
            f, p = (f"SPECIALE {sp.get('tipo', 'carosello')}", sp.get("titolo", "")[:30]) if sp else piano(giorno_piano(s, g, slot))[slot]
            riga.append(f"{slot}: {f} {p}")
        print("  ".join(riga))

def cmd_anteprima():
    s = stato(); s.setdefault("inizio", OGGI.isoformat()); out = ROOT / "anteprima"; shutil.rmtree(out, ignore_errors=True)
    g0 = giorno_di(s); d = out / "00_presentazione"; res = F.carosello_intro(str(d)); (d / "didascalia.txt").write_text(res["didascalia"])
    for i, sp in enumerate(x for x in tutti_speciali() if x.get("in_piu") and x["data"] >= OGGI.isoformat()):
        d = out / f"00_extra_{sp['data']}_{sp.get('slot', 'carosello')}"; F.foto.CREDITI.clear()
        res = con_crediti(genera_speciale(sp, str(d))); (d / "didascalia.txt").write_text(res["didascalia"])
    for k in range(int(os.environ.get("GIORNI", "7"))):
        for slot in ("carosello", "reel"):
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

def cmd_pubblica(slot):
    if senza_token(): return
    s = stato()
    if not s.get("inizio"): s["inizio"] = OGGI.isoformat(); salva(s)
    ig = client(s); pubblica(s, ig, giorno_di(s), slot); pubblica_extra(s, ig, slot)

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
    ig = client(s); gestiti = set(s["commenti_gestiti"]); fatti = 0
    derby_di = {p["media_id"]: p["param"] for p in s["pubblicati"] if p.get("formato") == "reel_derby" and p.get("media_id")}
    derby = {d["id"]: d for d in J("derby.json")}
    limite = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=6)
    for m in ig.media_recenti(15):
        dz = derby.get(derby_di.get(m["id"]))
        for cm in ig.commenti(m["id"]):
            if cm["id"] in gestiti or fatti >= 25: continue
            gestiti.add(cm["id"]); user = (cm.get("username") or (cm.get("from") or {}).get("username") or cm["id"])
            if user.lower() == (s.get("username") or "").lower(): continue
            if datetime.datetime.fromisoformat(cm["timestamp"].replace("+0000", "+00:00")) < limite: continue
            testo = cm.get("text", ""); c = trova_comune(testo); msg = None
            if dz:
                v = voto(testo, dz)
                if v:
                    s["voti"].setdefault(dz["id"], {})[user] = dict(v=v, reg=c["reg"] if c else None)
                    continue                     # il voto si conta in silenzio, senza rispondere
            if c and not msg:
                path = ROOT / "media" / "schede" / f"{c['istat']}.png"
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True); F.scheda(c, str(path)); git_push(f"scheda {c['nome']}")
                url = url_pubblico(str(path)); attendi_url(url)
                righe = "\n".join(f"• {v} {k}" for v, k in F.stats(c))
                msg = f"Ciao! Ecco la scheda di {F.nome(c)} ({c['prov']}) 📍\n{righe}\n\nLa scheda illustrata: {url}\n\nGrazie per aver commentato 🇮🇹"
            if not msg: continue
            try: ig.risposta_privata(cm["id"], msg)
            except APIError as e:
                print("DM non riuscito, rispondo nel post:", e)
                try: ig.risposta_pubblica(cm["id"], msg.split("\n")[0])
                except APIError as e2: print("Anche la risposta pubblica non è riuscita:", e2)
            fatti += 1
    s["commenti_gestiti"] = list(gestiti)[-5000:]; salva(s); git_push("commenti e voti"); print("risposte inviate:", fatti)

if __name__ == "__main__":
    a = sys.argv[1]
    if a == "pubblica": cmd_pubblica(sys.argv[2] if len(sys.argv) > 2 else os.environ.get("SLOT", "reel"))
    else: {"lancio": cmd_lancio, "verifica": cmd_verifica, "anteprima": cmd_anteprima, "calendario": cmd_calendario, "commenti": cmd_commenti, "intro": cmd_intro, "extra": cmd_extra}[a]()
