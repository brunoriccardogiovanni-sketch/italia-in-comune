"""Foto dei comuni da Wikimedia Commons, con autore e licenza per i crediti.

Per ogni comune si usa l'immagine principale della sua scheda Wikidata (proprietà P18), cercata
con il codice ISTAT o, in mancanza, con il nome. Se qualcosa non va (rete, nessuna foto, licenza
non libera) la funzione restituisce None e il post usa l'illustrazione disegnata.
"""
import io, json, re, html, urllib.parse
import requests
from PIL import Image, ImageDraw
from .base import CACHE

UA = {"User-Agent": "ItaliaInComuneBot/1.0 (Instagram @italia_incomune; bot divulgativo sui comuni italiani)"}
DIR = CACHE / "foto"
CREDITI = []            # crediti delle foto usate nel post in preparazione (li legge main.py per la didascalia)

def _sparql(q):
    r = requests.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"}, headers=UA, timeout=20)
    r.raise_for_status(); return [b["img"]["value"] for b in r.json()["results"]["bindings"]]

def _file_wikidata(c):
    imgs = _sparql(f'SELECT ?img WHERE {{ ?i wdt:P635 "{c["istat"]}"; wdt:P18 ?img }} LIMIT 1')
    if not imgs:
        nome = c["nome"].split("/")[0].replace('"', '')
        imgs = _sparql(f'SELECT ?img WHERE {{ ?i wdt:P31 wd:Q747074; rdfs:label "{nome}"@it; wdt:P18 ?img }} LIMIT 2')
        if len(imgs) != 1: return None          # nome ambiguo (o assente): meglio nessuna foto che quella sbagliata
    return urllib.parse.unquote(imgs[0].rsplit("/", 1)[-1])

def licenza_libera(lic):
    l = lic.lower()
    if re.search(r"\bn[cd]\b", l.replace("-", " ")): return False      # niente "non commerciale" o "non modificabile"
    return "public domain" in l or l.startswith("pd") or "cc0" in l or l.startswith("cc by") or l.startswith("cc-by")

def _pulisci(s, n=48):
    s = html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()
    s = re.sub(r"\s+", " ", s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"

def prendi(c):
    """Restituisce (immagine PIL RGB, credito) oppure None."""
    DIR.mkdir(parents=True, exist_ok=True); meta_p, img_p = DIR / f"{c['istat']}.json", DIR / f"{c['istat']}.jpg"
    try:
        if meta_p.exists():
            meta = json.loads(meta_p.read_text())
            if not meta.get("file") or not img_p.exists(): return None
        else:
            meta = {}
            f = _file_wikidata_cache.get(c["istat"]) or (None if str(c["istat"]).startswith("s_") else _file_wikidata(c))
            if f:
                r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=20, params=dict(
                    action="query", titles=f"File:{f}", prop="imageinfo", iiprop="url|extmetadata", iiurlwidth=1400, format="json"))
                info = next(iter(r.json()["query"]["pages"].values()))["imageinfo"][0]; em = info.get("extmetadata", {})
                lic = _pulisci(em.get("LicenseShortName", {}).get("value", ""), 30)
                if licenza_libera(lic):
                    autore = _pulisci(em.get("Artist", {}).get("value", "")) or "autore sconosciuto"
                    img_p.write_bytes(requests.get(info.get("thumburl") or info["url"], headers=UA, timeout=30).content)
                    meta = dict(file=f, autore=autore, licenza=lic)
            meta_p.write_text(json.dumps(meta, ensure_ascii=False))
            if not meta: return None
        im = Image.open(img_p).convert("RGB")
        if min(im.size) < 400: return None
        return im, dict(meta, comune=c["nome"].split("/")[0])
    except Exception as e:
        print(f"foto di {c['nome']} non disponibile: {e}")
        return None

def prendi_soggetto(etichetta):
    """Foto di un luogo o di un oggetto (es. «Forte di Fenestrelle») dalla sua scheda Wikidata, cercata per nome."""
    chiave = "s_" + re.sub(r"[^a-z0-9]+", "_", etichetta.lower())
    finto = dict(istat=chiave, nome=etichetta)
    DIR.mkdir(parents=True, exist_ok=True); meta_p = DIR / f"{chiave}.json"
    if not meta_p.exists():
        try:
            e = etichetta.replace('"', "")
            imgs = _sparql(f'SELECT ?img WHERE {{ ?i rdfs:label "{e}"@it; wdt:P18 ?img }} LIMIT 1')
            if not imgs: meta_p.write_text("{}"); return None
            _file_wikidata_cache[chiave] = urllib.parse.unquote(imgs[0].rsplit("/", 1)[-1])
        except Exception as ex:
            print(f"foto di {etichetta} non disponibile: {ex}"); return None
    return prendi(finto)

_file_wikidata_cache = {}

def credito_breve(cr): return f"Foto: {cr['autore']} · {cr['licenza']} · Wikimedia Commons"

def riquadro(im, w, h, raggio=28):
    """Ritaglia la foto a riempire w×h e arrotonda gli angoli."""
    s = max(w / im.width, h / im.height); im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, max(0, int((im.height - h) * .4)); im = im.crop((x, y, x + w, y + h)).convert("RGBA")
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), raggio, fill=255); im.putalpha(m)
    return im
