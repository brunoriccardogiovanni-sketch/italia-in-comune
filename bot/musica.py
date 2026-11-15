"""Musiche originali per i Reel, generate al momento: niente diritti, ogni Reel ha la sua.

Tre atmosfere:
- "pop": allegra, cassa dritta, accordi luminosi e arpeggio (comune del giorno, mappe, derby)
- "chill": più lenta e morbida, stile lo-fi (storie, curiosità)
- "tensione": minore, con tic-tac, per conti alla rovescia e sfide
Il seme cambia tonalità, giro di accordi, tempo e melodia, così le musiche non si ripetono.
"""
import random, wave, zlib
import numpy as np

SR = 44100
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
MAGG = [0, 2, 4, 5, 7, 9, 11]; MIN = [0, 2, 3, 5, 7, 8, 10]
GIRI = {"pop": [[0, 4, 5, 3], [5, 3, 0, 4], [0, 5, 3, 4], [3, 4, 0, 5], [0, 3, 4, 4]],
        "chill": [[1, 4, 0, 5], [3, 2, 1, 4], [0, 5, 3, 4], [5, 3, 0, 4]],
        "tensione": [[0, 5, 3, 4], [0, 0, 5, 4], [0, 3, 5, 4], [0, 6, 5, 4]]}

def hz(midi): return 440.0 * 2 ** ((midi - 69) / 12)
def env(n, a=.005, r=.2, dec=None):
    t = np.arange(n) / SR; e = np.minimum(1, t / max(a, 1e-4))
    return e * (np.exp(-t / dec) if dec else np.clip((n / SR - t) / max(r, 1e-4), 0, 1))
def lp(x, k):
    """Filtro passa-basso a un polo (k tra 0 e 1: più è basso, più il suono è morbido)."""
    a = 1 - k; L = max(1, int(np.ceil(np.log(1e-6) / np.log(a)))) if a > 0 else 1
    return np.convolve(x, k * a ** np.arange(L))[: len(x)]
def osc(f, n, forma="saw", armoniche=8, det=0.0):
    t = np.arange(n) / SR; s = np.zeros(n)
    for d in ([-det, det] if det else [0]):
        ff = f * (1 + d)
        if forma == "sine": s += np.sin(2 * np.pi * ff * t)
        elif forma == "tri": s += sum(((-1) ** k) * np.sin(2 * np.pi * ff * (2 * k + 1) * t) / (2 * k + 1) ** 2 for k in range(4)) * .8
        else:
            for h in range(1, armoniche + 1):
                if ff * h < 9000: s += np.sin(2 * np.pi * ff * h * t) / h ** (1.25 if forma == "saw" else 1.0) * (1 if forma == "saw" or h % 2 else 0)
    return s / (2 if det else 1)

def genera(durata, seme, umore="pop", path=None):
    r = random.Random(f"{seme}-{umore}")
    bpm = {"pop": r.randint(112, 124), "chill": r.randint(84, 94), "tensione": r.randint(100, 112)}[umore]
    radice = 45 + r.choice([0, 2, 3, 5, 7, -2]) if umore != "chill" else 45 + r.choice([0, 2, 5, -4])
    scala = MIN if umore == "tensione" else MAGG
    giro = r.choice(GIRI[umore]); beat = 60 / bpm; bar = 4 * beat
    n = int((durata + .5) * SR); L, R = np.zeros(n), np.zeros(n); DL, DR = np.zeros(n), np.zeros(n); duck = np.ones(n)
    def mix(seg, start, gain=1.0, pan=0.0, batteria=False):
        i = int(start * SR)
        if i >= n: return
        seg = seg[: n - i]; a, b = (DL, DR) if batteria else (L, R)
        a[i:i + len(seg)] += seg * gain * (1 - pan); b[i:i + len(seg)] += seg * gain * (1 + pan)
    def accordo(grado):
        return [radice + 12 + scala[(grado + k) % 7] + 12 * ((grado + k) // 7) for k in (0, 2, 4)]
    battute = int(durata / bar) + 2
    # tamburi già pronti
    kn = int(.35 * SR); tk = np.arange(kn) / SR
    kick = np.sin(2 * np.pi * np.cumsum(50 + 110 * np.exp(-tk / .045)) / SR) * np.exp(-tk / .16)
    rng = np.random.default_rng(zlib.crc32(str(seme).encode()))
    sn = int(.22 * SR); snare = (rng.standard_normal(sn) * .6 + np.sin(2 * np.pi * 190 * np.arange(sn) / SR) * .5) * env(sn, .001, dec=.07)
    snare = lp(snare - lp(snare, .08), .7)
    hn = int(.06 * SR); hat = rng.standard_normal(hn); hat = lp(hat - lp(hat, .35), .75) * env(hn, .001, dec=.018)
    tic = np.sin(2 * np.pi * 1800 * np.arange(int(.03 * SR)) / SR) * env(int(.03 * SR), .001, dec=.008)
    melodia = [r.choice([0, 1, 2]) for _ in range(8)]
    for b in range(battute):
        t0 = b * bar; grado = giro[b % len(giro)]; acc = accordo(grado); finale = t0 > durata - bar * .6
        # pad / accordi
        pn = int(bar * SR)
        for k, m in enumerate(acc):
            forma = "tri" if umore == "chill" else "saw"
            p = osc(hz(m), pn, forma, 6, det=.003) * env(pn, .08 if umore != "pop" else .02, r=.25)
            mix(p, t0, {"pop": .05, "chill": .07, "tensione": .05}[umore], pan=(k - 1) * .3)
        # basso
        radb = radice + scala[grado % 7] - 12 * (grado // 7 > 0) - 0
        passi = [0, 1.5, 2, 3, 3.5] if umore == "pop" else ([0, 2.5] if umore == "chill" else [0, .5, 1, 1.5, 2, 2.5, 3, 3.5])
        for s in passi:
            ln = int(beat * (.45 if umore != "chill" else 1.4) * SR)
            bs = osc(hz(radb), ln, "saw" if umore != "chill" else "sine", 5) * env(ln, .004, dec=.18 if umore != "chill" else .5)
            mix(bs, t0 + s * beat, .16 if umore != "tensione" else .12)
        # batteria
        if not (umore == "chill" and b == 0):
            for q in range(4):
                if umore != "chill" or q in (0, 2):
                    mix(kick, t0 + q * beat, .55 if umore != "chill" else .45, batteria=True)
                    i = int((t0 + q * beat) * SR); d = np.ones(int(beat * SR)); d[: len(d)] = 1 - .45 * np.exp(-np.arange(len(d)) / SR / .09)
                    duck[i:i + len(d)] *= d[: max(0, n - i)][: len(duck[i:i + len(d)])]
                if q in (1, 3) and umore != "tensione": mix(snare, t0 + q * beat + (.012 if umore == "chill" else 0), .22, batteria=True)
            for e in range(8):
                sw = .03 * beat if (umore == "chill" and e % 2) else 0
                mix(hat, t0 + e * beat / 2 + sw, .07 if e % 2 else .045, pan=.25, batteria=True)
            if umore == "tensione":
                for e in range(4): mix(tic, t0 + e * beat, .18, pan=-.3, batteria=True)
                mix(snare, t0 + 3.5 * beat, .12, batteria=True)
        # arpeggio / melodia
        if umore == "pop" or (umore == "tensione" and b % 2) or (umore == "chill" and b % 2 == 0):
            note = acc + [acc[0] + 12]; passo = .5 if umore != "pop" else .25
            for j in range(int(4 / passo)):
                m = note[(j + melodia[j % 8]) % len(note)] + 12 * (umore == "pop")
                ln = int(.32 * SR)
                pl = osc(hz(m), ln, "tri" if umore != "tensione" else "sine") * env(ln, .002, dec=.09 if umore == "pop" else .16)
                mix(pl, t0 + j * passo * beat, .055 if umore == "pop" else .05, pan=.35 * (1 if j % 2 else -1))
        if finale: break
    # "sidechain": accordi, basso e melodia si abbassano un attimo a ogni colpo di cassa
    L = L * duck + DL; R = R * duck + DR
    if umore == "chill":
        crack = lp(rng.standard_normal(n), .3) * .003; L += crack; R += crack
    st = np.stack([L, R], 1)
    st = np.tanh(st * 1.6) / 1.6
    st *= .8 / max(1e-6, np.abs(st).max())
    fi, fo = int(.03 * SR), int(min(1.2, durata * .15) * SR); m = np.ones(n)
    m[:fi] = np.linspace(0, 1, fi); end = int(durata * SR); m[end - fo:end] = np.linspace(1, 0, fo); m[end:] = 0
    st *= m[:, None]
    pcm = (st[:end] * 32767).astype("<i2")
    if path:
        with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    return pcm
