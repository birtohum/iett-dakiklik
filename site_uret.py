"""Günlük özetlerden statik sitenin verisini üretir: site/veri/*.json

Ölçüler (yöntem README'de):
  - Kalkış dakikliği: hat başından kalkış − planlı kalkış; "dakik" = −1…+5 dk.
  - Gözlenen/planlı: kapsam içindeki planlı kalkışlardan gözlenen bir kalkışla eşleşen pay.
  - Durakta bekleme: ardışık iki otobüsün durak geçişleri arası h; rastgele gelen yolcunun
    ortalama beklemesi Σh² / (2Σh). Planlı karşılığı aynı formül, planlı kalkışlara
    gözlenen medyan yolculuk süresi eklenerek bulunan planlı geçişlerle.
"""
import collections
import gzip
import json
import math
import pathlib
import statistics as st

from iett.geo import M_BOYLAM, M_ENLEM

KOK = pathlib.Path(__file__).resolve().parent
OZET = KOK / "veri" / "ozet"
STATIK = KOK / "veri" / "statik"
CIKTI = KOK / "site" / "veri"
HATLAR = [h.strip() for h in (KOK / "hatlar.txt").read_text(encoding="utf-8").split() if h.strip()]

DAKIK = (-1.0, 5.0)
MAKS_ARALIK = 90 * 60  # sn; daha uzun aralık bekleme hesabına girmez
KAPSAM_BOSLUK = 3  # dk
# sıralama iddiası için en az bu kadar veri
SIRALAMA_MIN_KALKIS = 40
SIRALAMA_MIN_GUN = 5
GUN_ADI = {"I": "hafta içi", "C": "cumartesi", "P": "pazar"}


def gunleri_oku():
    for p in sorted(OZET.glob("*.json.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            yield json.load(f)


def yuzdelik(a, p):
    a = sorted(a)
    if not a:
        return None
    k = (len(a) - 1) * p
    i = math.floor(k)
    return a[i] if i + 1 >= len(a) else a[i] + (a[i + 1] - a[i]) * (k - i)


def kapsam_surekli(kapsam, t1, t2):
    """t1..t2 (sn) arası toplayıcı kesintisiz çalışmış mı?"""
    a, b = t1 / 60, t2 / 60
    return any(x - KAPSAM_BOSLUK <= a and b <= y + KAPSAM_BOSLUK for x, y in kapsam)


def bekleme(araliklar_):
    toplam = sum(araliklar_)
    return sum(h * h for h in araliklar_) / (2 * toplam) if toplam else None


def sadelestir(nokta, tolerans=15.0):
    """Douglas–Peucker (metre)."""
    if len(nokta) < 3:
        return nokta
    xy = [(b * M_BOYLAM, e * M_ENLEM) for b, e in nokta]
    tut = [False] * len(nokta)
    tut[0] = tut[-1] = True
    yigin = [(0, len(nokta) - 1)]
    while yigin:
        i, j = yigin.pop()
        (x1, y1), (x2, y2) = xy[i], xy[j]
        L = math.hypot(x2 - x1, y2 - y1) or 1e-9
        en, k = 0.0, None
        for m in range(i + 1, j):
            x, y = xy[m]
            d = abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / L
            if d > en:
                en, k = d, m
        if k is not None and en > tolerans:
            tut[k] = True
            yigin += [(i, k), (k, j)]
    return [[round(nokta[i][0], 5), round(nokta[i][1], 5)] for i in range(len(nokta)) if tut[i]]


def main():
    gunler = list(gunleri_oku())
    statik = {h: json.loads((STATIK / f"{h}.json").read_text(encoding="utf-8"))["varyantlar"] for h in HATLAR}
    planlar_json = {}
    for g in gunler:
        for h in HATLAR:
            p = KOK / "veri" / "plan" / g["gun"] / f"{h}.json"
            if p.exists():
                planlar_json[(g["gun"], h)] = json.loads(p.read_text(encoding="utf-8"))

    # --- kalkış dakikliği
    sapma = collections.defaultdict(list)  # hat -> [dk]
    sapma_saat = collections.defaultdict(lambda: collections.defaultdict(list))  # hat -> saat -> [dk]
    gun_say = collections.defaultdict(set)
    plan_say = collections.Counter()
    plan_esles = collections.Counter()
    for g in gunler:
        for hat, guz, k_sn, p_dk, s_dk, tahmini in g["kalkislar"]:
            if s_dk is None:
                continue
            sapma[hat].append(s_dk)
            sapma_saat[hat][p_dk // 60].append(s_dk)
            gun_say[hat].add(g["gun"])
        for hat, guz, p_dk, eslesti, gozlenebilir in g["planlar"]:
            if gozlenebilir:
                plan_say[hat] += 1
                plan_esles[hat] += eslesti

    # --- yolculuk süresi: (güzergâh, durak) -> medyan (geçiş − kalkış) sn
    yol = collections.defaultdict(list)
    for g in gunler:
        for hat, guz, durak, t, k in g["gecisler"]:
            if k is not None and t >= k:
                yol[(guz, durak)].append(t - k)
    yol_med = {k: st.median(v) for k, v in yol.items() if len(v) >= 2}

    # --- durakta bekleme
    gozlenen_h = collections.defaultdict(list)  # (hat, durak) -> [h sn]
    planli_h = collections.defaultdict(list)
    saat_bekle = collections.defaultdict(lambda: collections.defaultdict(lambda: [[], []]))  # hat->saat->[göz, plan]
    for g in gunler:
        kap = g["kapsam"]
        gecis = collections.defaultdict(list)
        for hat, guz, durak, t, k in g["gecisler"]:
            gecis[(hat, durak)].append(t)
        # planlı geçişler: planlı kalkış + medyan yolculuk süresi
        planli = collections.defaultdict(list)
        for hat in HATLAR:
            pj = planlar_json.get((g["gun"], hat))
            if not pj:
                continue
            for sf in pj["seferler"]:
                if sf["SGUNTIPI"] != g["gun_tipi"]:
                    continue
                v = statik[hat].get(sf["SGUZERAH"])
                if not v:
                    continue
                hh, mm = map(int, sf["DT"].split(":"))
                for dk_ in v["duraklar"]:
                    y = yol_med.get((sf["SGUZERAH"], dk_["kod"]))
                    if y is not None:
                        planli[(hat, dk_["kod"])].append(hh * 3600 + mm * 60 + y)
        for anahtar, ts in gecis.items():
            ts.sort()
            pl = sorted(planli.get(anahtar, []))
            hat = anahtar[0]
            for t1, t2 in zip(ts, ts[1:]):
                if 0 < t2 - t1 <= MAKS_ARALIK and kapsam_surekli(kap, t1, t2):
                    gozlenen_h[anahtar].append(t2 - t1)
                    saat_bekle[hat][int(t2 // 3600)][0].append(t2 - t1)
            # planlı aralıklar yalnız gözlemin olduğu ve kesintisiz kapsanan pencerelerde
            if len(ts) >= 2:
                for t1, t2 in zip(pl, pl[1:]):
                    if ts[0] <= t1 and t2 <= ts[-1] and 0 < t2 - t1 <= MAKS_ARALIK and kapsam_surekli(kap, t1, t2):
                        planli_h[anahtar].append(t2 - t1)
                        saat_bekle[hat][int(t2 // 3600)][1].append(t2 - t1)

    # --- çıktı
    CIKTI.mkdir(parents=True, exist_ok=True)
    (CIKTI / "hat").mkdir(exist_ok=True)
    toplam_dk = sum(b - a for g in gunler for a, b in g["kapsam"])
    ozet_hatlar = []
    for hat in HATLAR:
        vs = statik[hat]
        ana = [k for k in vs if k.endswith("_D0")]
        ad = next((planlar_json[k]["bilgi"][0]["SHATADI"] for k in planlar_json if k[1] == hat and planlar_json[k]["bilgi"]), hat)
        sp = sapma[hat]
        satir = {
            "hat": hat, "ad": ad, "gun": len(gun_say[hat]), "kalkis": len(sp),
            "sapma_medyan": round(st.median(sp), 1) if sp else None,
            "sapma_p90": round(yuzdelik(sp, 0.9), 1) if sp else None,
            "dakik": round(100 * sum(DAKIK[0] <= x <= DAKIK[1] for x in sp) / len(sp)) if sp else None,
            "gec5": round(100 * sum(x > DAKIK[1] for x in sp) / len(sp)) if sp else None,
            "planli": plan_say[hat], "gozlenen": plan_esles[hat],
            "yeterli": len(sp) >= SIRALAMA_MIN_KALKIS and len(gun_say[hat]) >= SIRALAMA_MIN_GUN,
        }
        gb, pb = [], []
        duraklar = {}
        for kod in sorted(vs):
            for d in vs[kod]["duraklar"]:
                a = (hat, d["kod"])
                if d["kod"] in duraklar:
                    continue
                go, pl = bekleme(gozlenen_h.get(a, [])), bekleme(planli_h.get(a, []))
                duraklar[d["kod"]] = {
                    "kod": d["kod"], "ad": d["ad"], "e": round(d["enlem"], 5), "b": round(d["boylam"], 5),
                    "n": len(gozlenen_h.get(a, [])),
                    "bekleme": round(go / 60, 1) if go else None,
                    "planli": round(pl / 60, 1) if pl else None,
                }
                if go and pl and len(gozlenen_h[a]) >= 3:
                    gb.append(go)
                    pb.append(pl)
        satir["bekleme_fazla"] = round((st.median(gb) - st.median(pb)) / 60, 1) if gb else None
        saatler = []
        for s in range(5, 25):
            x = sapma_saat[hat].get(s, [])
            bg, bp = saat_bekle[hat].get(s, [[], []])
            saatler.append({
                "saat": s, "n": len(x),
                "medyan": round(st.median(x), 1) if x else None,
                "p25": round(yuzdelik(x, .25), 1) if x else None,
                "p75": round(yuzdelik(x, .75), 1) if x else None,
                "bekleme": round(bekleme(bg) / 60, 1) if bg else None,
                "bekleme_plan": round(bekleme(bp) / 60, 1) if bp else None,
            })
        detay = dict(satir, saatler=saatler, duraklar=list(duraklar.values()),
                     cizgiler={k: sadelestir(vs[k]["cizgi"]) for k in ana},
                     yonler={k: vs[k]["ad"].replace(" - ", " → ") for k in ana})
        (CIKTI / "hat" / f"{hat}.json").write_text(json.dumps(detay, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        ozet_hatlar.append(satir)
    meta = {
        "gunler": [g["gun"] for g in gunler],
        "gun_tipleri": {g["gun"]: GUN_ADI[g["gun_tipi"]] for g in gunler},
        "kapsam_saat": round(toplam_dk / 60, 1),
        "kalkis": sum(len(sapma[h]) for h in HATLAR),
        "gecis": sum(len(g["gecisler"]) for g in gunler),
        "esik": {"kalkis": SIRALAMA_MIN_KALKIS, "gun": SIRALAMA_MIN_GUN, "dakik": DAKIK},
    }
    (CIKTI / "ozet.json").write_text(json.dumps({"meta": meta, "hatlar": ozet_hatlar}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    for s in ozet_hatlar:
        print(s)


if __name__ == "__main__":
    main()
