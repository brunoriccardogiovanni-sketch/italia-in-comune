"""Regia di Italia in comune.
python -m bot.main verifica   -> controlla token e account (non pubblica nulla)
python -m bot.main anteprima  -> genera il contenuto di oggi in anteprima/ senza pubblicarlo
python -m bot.main pubblica   -> genera e pubblica il contenuto di oggi
python -m bot.main commenti   -> risponde ai commenti con il nome di un comune
"""
import os, sys, json, datetime, subprocess, shutil, time, itertools, difflib, re
import requests
from . import formati as F
from .base import load, norm, ROOT, fmt
from .instagram import IG, rileva, APIError

STATO = ROOT / "stato" / "stato.json"
OGGI = datetime.date.fromisoformat(os.environ["DATA"]) if os.environ.get("DATA") else datetime.date.today()
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")

def stato():
    s = json.loads(STATO.read_text() or "{}")
    for k, v in dict(pubblicati=[], commenti_gestiti=[], usati={}).items(): s.setdefault(k, v)
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

# ------------------------------------------------------------ calendario
# lun countdown · mar storia · mer comune del giorno · gio carosello classifica · ven sfida · sab cibo · dom mappa
METR = list(F.METRICHE); MAPPE = list(F.MAPPE)
def piano(giorno, s):
    w = giorno.isocalendar()[1]; wd = giorno.weekday(); usati = s["usati"]
    def prossimo(nome_file, chiave):
        items = json.load(open(ROOT / "contenuti" / nome_file))
        fatti = usati.get(chiave, [])
        for it in items:
            if it["comune"] not in fatti: return it
        return None
    if wd == 0: return ("reel_countdown", METR[w % len(METR)])
    if wd == 1:
        it = prossimo("storie.json", "storie")
        return ("carosello_storia", it) if it else ("carosello_classifica", METR[(w + 3) % len(METR)])
    if wd == 2: return ("reel_comune", None)
    if wd == 3: return ("carosello_classifica", METR[(w + 2) % len(METR)])
    if wd == 4: return ("reel_sfida", None)
    if wd == 5:
        it = prossimo("cibo.json", "cibo")
        return ("carosello_cibo", it) if it else ("reel_comune", None)
    return ("reel_mappa", MAPPE[w % len(MAPPE)])

def genera(giorno, s, out):
    os.makedirs(out, exist_ok=True); formato, par = piano(giorno, s); seed = giorno.isoformat()
    comuni, _ = load()
    if formato == "reel_comune":
        import random
        fatti = set(s["usati"].get("comuni_giorno", []))
        cand = [c for c in comuni if c["istat"] not in fatti and c["pop"]]
        c = random.Random(seed).choice(cand); par = c["istat"]
        res = F.reel_comune(c, out)
    elif formato == "reel_sfida":
        a, b = F.coppia(seed); par = f"{a['istat']}-{b['istat']}"; res = F.reel_sfida(a, b, out)
    elif formato in ("carosello_storia", "carosello_cibo"):
        res = getattr(F, formato)(par, out); par = par["comune"]
    else:
        res = getattr(F, formato)(par, out)
    res["formato"], res["param"] = formato, par
    return res

def segna_usato(s, res):
    key = {"carosello_storia": "storie", "carosello_cibo": "cibo", "reel_comune": "comuni_giorno"}.get(res["formato"])
    if key: s["usati"].setdefault(key, []).append(res["param"])

# ------------------------------------------------------------ comandi
def client(s):
    tok = os.environ.get("IG_TOKEN")
    if not tok: sys.exit("Manca il secret IG_TOKEN.")
    if not s.get("host"):
        host, ig, user, log = rileva(tok, os.environ.get("GRAPH_HOST") or None, os.environ.get("IG_USER_ID") or None)
        if not ig: print("\n".join(log)); sys.exit("Non riesco a trovare l'account Instagram con questo token.")
        s.update(host=host, ig_id=ig, username=user); salva(s)
    return IG(tok, s["host"], s["ig_id"])

def cmd_verifica():
    tok = os.environ.get("IG_TOKEN")
    if not tok: sys.exit("Manca il secret IG_TOKEN: aggiungilo in Settings → Secrets and variables → Actions.")
    host, ig, user, log = rileva(tok, os.environ.get("GRAPH_HOST") or None, os.environ.get("IG_USER_ID") or None)
    print("Prove effettuate:\n  " + "\n  ".join(log))
    if not ig: sys.exit("\n❌ Token non valido o account non trovato.")
    print(f"\n✅ Collegato a @{user} (id {ig}) tramite {host}")
    s = stato(); s.update(host=host, ig_id=ig, username=user); salva(s); git_push("verifica collegamento")

def cmd_anteprima():
    s = stato(); out = ROOT / "anteprima"; shutil.rmtree(out, ignore_errors=True)
    for k in range(int(os.environ.get("GIORNI", "7"))):
        g = OGGI + datetime.timedelta(days=k); res = genera(g, s, str(out / f"{g.isoformat()}_{piano(g, s)[0]}"))
        (out / f"{g.isoformat()}_didascalia.txt").write_text(res["didascalia"]); segna_usato(s, res)
        print("ok", g, res["formato"], res["param"] if isinstance(res["param"], str) else "")

def senza_token():
    if os.environ.get("IG_TOKEN"): return False
    print("Il token non è ancora configurato: non faccio nulla."); return True

def cmd_lancio():
    """Riempie il profilo al primo avvio: pubblica i contenuti dei 6 giorni precedenti."""
    global OGGI
    if senza_token(): return
    base = OGGI
    for k in range(6, 0, -1):
        OGGI = base - datetime.timedelta(days=k); cmd_pubblica(); time.sleep(30)
    OGGI = base

def cmd_pubblica():
    if senza_token(): return
    s = stato()
    if any(p["data"] == OGGI.isoformat() for p in s["pubblicati"]): return print("Oggi è già stato pubblicato.")
    ig = client(s); out = ROOT / "media" / OGGI.isoformat(); res = genera(OGGI, s, str(out))
    if res["tipo"] == "reel":
        mid = ig.reel(res["file"][0], res["didascalia"])
        for f in res["file"]: os.remove(f)          # i video non servono nel repository
    else:
        git_push(f"media {OGGI}"); urls = [url_pubblico(f) for f in res["file"]]
        for u in urls: attendi_url(u)
        mid = ig.carosello(urls, res["didascalia"]) if len(urls) > 1 else ig.immagine(urls[0], res["didascalia"])
    segna_usato(s, res)
    s["pubblicati"].append(dict(data=OGGI.isoformat(), formato=res["formato"], param=res["param"] if isinstance(res["param"], str) else "", media_id=mid))
    salva(s); git_push(f"pubblicato {OGGI} {res['formato']}"); print("✅ pubblicato", res["formato"], mid)

# riconoscimento del comune nel testo di un commento
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
    """Solo le parole che iniziano con la maiuscola, normalizzate."""
    return " ".join(norm(w) for w in re.findall(r"\b[A-ZÀ-Ý][\wÀ-ÿ']*", testo))
def trova_comune(testo):
    idx = indice(); words = norm(testo).split()
    sig = {w.upper() for w in re.findall(r"\b[A-Za-z]{2}\b", testo)}
    for n in range(min(7, len(words)), 0, -1):
        for i in range(len(words) - n + 1):
            k = " ".join(words[i:i + n])
            if k in idx:
                # parole singole in frasi lunghe ("vita", "ponte", "cento"...) valgono solo se scritte con la maiuscola
                if n == 1 and len(words) > 3 and not re.search(r"\b" + re.escape(k) + r"\b", norm_caps(testo)): continue
                hits = idx[k]; pick = [c for c in hits if c["prov"] in sig] or hits
                return pick[0]
    if 1 <= len(words) <= 5:
        m = difflib.get_close_matches(" ".join(words), list(idx), n=1, cutoff=0.88)
        if m: return idx[m[0]][0]
    return None

def cmd_commenti():
    if senza_token(): return
    s = stato()
    if not s["pubblicati"]: return print("Nessun post pubblicato ancora."); ig = client(s); gestiti = set(s["commenti_gestiti"]); fatti = 0
    limite = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=6)
    for m in ig.media_recenti():
        for cm in ig.commenti(m["id"]):
            if cm["id"] in gestiti or fatti >= 25: continue
            gestiti.add(cm["id"])
            if (cm.get("username") or "").lower() == (s.get("username") or "").lower(): continue
            ts = datetime.datetime.fromisoformat(cm["timestamp"].replace("+0000", "+00:00"))
            if ts < limite: continue
            c = trova_comune(cm.get("text", ""))
            if not c: continue
            path = ROOT / "media" / "schede" / f"{c['istat']}.png"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True); F.scheda(c, str(path)); git_push(f"scheda {c['nome']}")
            url = url_pubblico(str(path)); attendi_url(url)
            righe = "\n".join(f"• {v} {k}" for v, k in F.stats(c))
            testo = f"Ciao! Ecco la scheda di {F.nome(c)} ({c['prov']}) 📍\n{righe}\n\nLa scheda illustrata: {url}\n\nGrazie per aver commentato 🇮🇹"
            try: ig.risposta_privata(cm["id"], testo)
            except APIError as e:
                print("DM non riuscito, rispondo nel post:", e)
                v = F.stats(c)
                ig.risposta_pubblica(cm["id"], f"{F.nome(c)} ({c['prov']}): {v[0][0]} abitanti (2011), {v[1][0]}, {v[3][0]} per estensione in regione 📍")
            fatti += 1
    s["commenti_gestiti"] = list(gestiti)[-5000:]; salva(s); git_push("commenti gestiti"); print("risposte inviate:", fatti)

if __name__ == "__main__":
    {"lancio": cmd_lancio, "verifica": cmd_verifica, "anteprima": cmd_anteprima, "pubblica": cmd_pubblica, "commenti": cmd_commenti}[sys.argv[1]]()
