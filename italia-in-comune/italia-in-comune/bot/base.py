"""Dati, font e mattoncini grafici comuni a tutti i formati."""
import json, os, pathlib, unicodedata, re
import numpy as np
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPoly
import shapely
from shapely.geometry import shape
from pyproj import Transformer
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"; CACHE.mkdir(exist_ok=True)
HANDLE = "@italia_incomune"

SOURCES = {
    "comuni.json": "https://raw.githubusercontent.com/matteocontrini/comuni-json/master/comuni.json",
    "municipalities.geojson": "https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_municipalities.geojson",
    "regions.geojson": "https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_regions.geojson",
    "Unbounded.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/unbounded/Unbounded%5Bwght%5D.ttf",
}

def fetch(name):
    p = CACHE / name
    if not p.exists():
        r = requests.get(SOURCES[name], timeout=120); r.raise_for_status(); p.write_bytes(r.content)
    return p

THEMES = {
    "indaco": dict(bg="#1A1446", ink="#FFFFFF", muted="#B9B4E0", acc="#FFD23F", acc2="#FF3E7F", land="#3A3277", line="#1A1446"),
    "giallo": dict(bg="#FFD23F", ink="#1A1446", muted="#5B4E8C", acc="#FF3E7F", acc2="#1A1446", land="#FFF1A8", line="#FFD23F"),
    "rosa":   dict(bg="#FF3E7F", ink="#FFFFFF", muted="#FFE0EA", acc="#FFD23F", acc2="#1A1446", land="#FF8DB1", line="#FF3E7F"),
}
CYCLE = ["indaco", "giallo", "rosa"]
WGT = {"r": 400, "m": 500, "b": 700, "x": 800, "k": 900}
_fc = {}
def font(w, s):
    k = (w, s)
    if k not in _fc:
        f = ImageFont.truetype(str(fetch("Unbounded.ttf")), s); f.set_variation_by_axes([WGT[w]]); _fc[k] = f
    return _fc[k]
fmt = lambda n: f"{n:,.0f}".replace(",", ".")
fmt1 = lambda x: f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

def norm(s):
    s = unicodedata.normalize("NFKD", s.lower()); s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

_data = None
def load():
    """Comuni con geometria proiettata (m, EPSG:3035), superficie, popolazione (censimento 2011)."""
    global _data
    if _data: return _data
    pop = {c["codice"]: c for c in json.load(open(fetch("comuni.json")))}
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True)
    proj = lambda g: shapely.transform(g, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1])))
    comuni = []
    for f in json.load(open(fetch("municipalities.geojson")))["features"]:
        p = f["properties"]; g0 = shape(f["geometry"]); g = proj(g0); c = pop.get(p["com_istat_code"])
        comuni.append(dict(nome=p["name"], prov=p["prov_acr"], reg=p["reg_name"], geom=g, ll=g0.representative_point(),
                           area=g.area / 1e6, pop=c["popolazione"] if c else None, istat=p["com_istat_code"]))
    regioni = [proj(shape(f["geometry"])) for f in json.load(open(fetch("regions.geojson")))["features"]]
    from .city import tag_comuni
    tag_comuni(comuni, regioni)
    _data = (comuni, regioni); return _data

def find(nome, prov=None):
    comuni, _ = load(); n = norm(nome)
    hits = [c for c in comuni if norm(c["nome"].split("/")[0]) == n or norm(c["nome"]) == n]
    if prov: hits = [c for c in hits if c["prov"] == prov] or hits
    return hits[0] if hits else None

def _polys(g): return [MplPoly(list(p.exterior.coords)) for p in (g.geoms if g.geom_type == "MultiPolygon" else [g])]

def draw_map(T, color_fn=None, highlight=None, point=None, px=900):
    comuni, regioni = load()
    b = [r.bounds for r in regioni]; x0, y0, x1, y1 = min(v[0] for v in b), min(v[1] for v in b), max(v[2] for v in b), max(v[3] for v in b)
    wi = px / 100; fig = plt.figure(figsize=(wi, wi * (y1 - y0) / (x1 - x0)), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off(); fig.patch.set_alpha(0)
    for r in regioni: ax.add_collection(PatchCollection(_polys(r), facecolor=T["land"], edgecolor="none"))
    if color_fn:
        pp, cc = [], []
        for c in comuni:
            col = color_fn(c)
            if col:
                for p in _polys(c["geom"]): pp.append(p); cc.append(col)
        ax.add_collection(PatchCollection(pp, facecolor=cc, edgecolor=cc, linewidth=0.2))
    for r in regioni: ax.add_collection(PatchCollection(_polys(r), facecolor="none", edgecolor=T["line"], linewidth=1.0))
    if highlight is not None: ax.add_collection(PatchCollection(_polys(highlight), facecolor=T["acc"], edgecolor=T["acc"], linewidth=2))
    if point is not None: ax.scatter([point.x], [point.y], s=1400 * (px / 900) ** 2, facecolor="none", edgecolor=T["acc"], linewidth=6 * px / 900, zorder=5)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    tmp = CACHE / "_map.png"; fig.savefig(tmp, transparent=True); plt.close(fig)
    return Image.open(tmp).convert("RGBA")

def map_bounds():
    _, regioni = load(); b = [r.bounds for r in regioni]
    return min(v[0] for v in b), min(v[1] for v in b), max(v[2] for v in b), max(v[3] for v in b)

def wrap(d, text, f, maxw):
    out, line = [], ""
    for w in text.split():
        t = (line + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: line = t
        else: out.append(line); line = w
    return out + [line]

def text_block(img, text, xy, f, fill, maxw, lh=1.1):
    d = ImageDraw.Draw(img); x, y = xy
    for l in wrap(d, text, f, maxw):
        d.text((x, y), l, font=f, fill=fill); y += int(f.size * lh)
    return y

def fit_font(img, text, w, maxw, maxlines, start, minsize=30):
    d = ImageDraw.Draw(img); s = start
    while s > minsize and len(wrap(d, text, font(w, s), maxw)) > maxlines: s -= 4
    return font(w, s)

def pill(img, text, xy, f, bg, fg, pad=(26, 14)):
    d = ImageDraw.Draw(img); w = d.textlength(text, font=f)
    x, y = xy; d.rounded_rectangle((x, y, x + w + 2 * pad[0], y + f.size + 2 * pad[1]), 40, fill=bg)
    d.text((x + pad[0], y + pad[1] - f.size * 0.08), text, font=f, fill=fg)
    return x + w + 2 * pad[0]

def place(img, m, cx, top, maxw, maxh):
    m = m.copy(); m.thumbnail((maxw, maxh)); img.paste(m, (int(cx - m.width // 2), int(top)), m); return top + m.height
