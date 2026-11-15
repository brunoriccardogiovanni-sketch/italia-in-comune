"""Chiamate all'API ufficiale di Instagram (pubblicazione, commenti, risposte)."""
import os, time, json, requests

VERSION = os.environ.get("GRAPH_VERSION", "v24.0")

class APIError(Exception): pass

class IG:
    def __init__(self, token, host, ig_id):
        self.t, self.host, self.id = token, host, ig_id
        self.base = f"https://{host}/{VERSION}"

    def _r(self, method, path, **kw):
        kw.setdefault("timeout", 120)
        params = kw.pop("params", {}); params["access_token"] = self.t
        r = requests.request(method, f"{self.base}/{path.lstrip('/')}", params=params, **kw)
        try: j = r.json()
        except Exception: j = {"raw": r.text[:300]}
        if r.status_code >= 400 or "error" in j:
            err = j.get("error", j); raise APIError(f"{method} {path}: {err.get('message', err)} (code {err.get('code')})")
        return j
    def get(self, path, **params): return self._r("GET", path, params=params)
    def post(self, path, **data): return self._r("POST", path, data=data)

    # ---------------- pubblicazione
    def _wait(self, cid, minutes=10):
        for _ in range(minutes * 6):
            s = self.get(cid, fields="status_code").get("status_code")
            if s == "FINISHED": return
            if s == "ERROR": raise APIError(f"elaborazione fallita per il contenitore {cid}")
            time.sleep(10)
        raise APIError("tempo scaduto in attesa dell'elaborazione")
    def _publish(self, cid):
        self._wait(cid); return self.post(f"{self.id}/media_publish", creation_id=cid)["id"]

    def immagine(self, url, caption):
        return self._publish(self.post(f"{self.id}/media", image_url=url, caption=caption)["id"])

    def carosello(self, urls, caption):
        kids = [self.post(f"{self.id}/media", image_url=u, is_carousel_item="true")["id"] for u in urls[:20]]
        for k in kids: self._wait(k, 3)
        cid = self.post(f"{self.id}/media", media_type="CAROUSEL", children=",".join(kids), caption=caption)["id"]
        return self._publish(cid)

    def reel(self, path, caption):
        j = self.post(f"{self.id}/media", media_type="REELS", upload_type="resumable", caption=caption, share_to_feed="true")
        cid, uri = j["id"], j.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VERSION}/{j['id']}"
        data = open(path, "rb").read()
        r = requests.post(uri, headers={"Authorization": f"OAuth {self.t}", "offset": "0", "file_size": str(len(data))}, data=data, timeout=600)
        if r.status_code >= 400: raise APIError(f"upload video: {r.text[:300]}")
        return self._publish(cid)

    # ---------------- commenti
    def media_recenti(self, n=12):
        return self.get(f"{self.id}/media", fields="id,timestamp", limit=n).get("data", [])
    def commenti(self, media_id):
        return self.get(f"{media_id}/comments", fields="id,text,timestamp,username,from", limit=50).get("data", [])
    def risposta_privata(self, comment_id, text):
        return self._r("POST", f"{self.id}/messages", json={"recipient": {"comment_id": comment_id}, "message": {"text": text}})
    def risposta_pubblica(self, comment_id, text):
        return self.post(f"{comment_id}/replies", message=text)


def rileva(token, forced_host=None, forced_id=None):
    """Capisce da solo quale API accetta il token e qual è l'ID dell'account Instagram.
    Stampa solo esiti e ID, mai il token."""
    log = []
    hosts = [forced_host] if forced_host else ["graph.instagram.com", "graph.facebook.com"]
    for host in hosts:
        base = f"https://{host}/{VERSION}"
        def g(path, **p):
            p["access_token"] = token
            r = requests.get(f"{base}/{path}", params=p, timeout=60)
            try: return r.status_code, r.json()
            except Exception: return r.status_code, {"raw": r.text[:200]}
        if forced_id:
            s, j = g(forced_id, fields="id,username")
            log.append(f"{host} /{forced_id}: {s} {j}")
            if s == 200: return host, forced_id, j.get("username"), log
            continue
        if host == "graph.instagram.com":
            s, j = g("me", fields="user_id,username")
            log.append(f"{host} /me: {s} {j.get('username') or j.get('error', {}).get('message')}")
            if s == 200: return host, str(j.get("user_id") or j.get("id")), j.get("username"), log
        else:
            s, j = g("me", fields="id,name")
            log.append(f"{host} /me: {s} {j.get('name') or j.get('error', {}).get('message')}")
            if s != 200: continue
            tries = [("me/accounts", dict(fields="instagram_business_account{id,username}")),
                     ("me", dict(fields="instagram_business_account{id,username}")),
                     ("me/businesses", dict(fields="id,name,instagram_business_accounts{id,username},owned_instagram_accounts{id,username}"))]
            for path, p in tries:
                s, j = g(path, **p); log.append(f"{host} /{path}: {s} {json.dumps(j)[:300]}")
                if s != 200: continue
                items = j.get("data", [j])
                for it in items:
                    for key in ("instagram_business_account", "instagram_business_accounts", "owned_instagram_accounts"):
                        v = it.get(key)
                        if isinstance(v, dict) and "data" in v: v = v["data"][0] if v["data"] else None
                        if isinstance(v, dict) and v.get("id"): return host, v["id"], v.get("username"), log
    return None, None, None, log
