"""Hatların güzergâh varyantlarını (çizgi + sıralı duraklar) çıkarır.

Kaynaklar (İBB Açık Veri Portalı, veri/kaynak/ altına bir kez indirilir):
  - İETT Hat Güzergâhları (GeoJSON, ~250 MB): her varyantın çizgisi
  - İETT Otobüs Durakları (GeoJSON): durak koordinatları
  - İETT GTFS (routes, trips, stops, stop_times.zip): varyantın durak sırası
    (GTFS'teki saatler kullanılmaz: yalnızca ilk durakta dolu ve güncel plandan farklı)

Çıktı: veri/statik/<hat>.json
"""
import csv
import io
import json
import pathlib
import sys
import zipfile

import requests

from iett.geo import Cizgi

KOK = pathlib.Path(__file__).resolve().parent
KAYNAK = KOK / "veri" / "kaynak"
STATIK = KOK / "veri" / "statik"
HATLAR = [h.strip() for h in (KOK / "hatlar.txt").read_text(encoding="utf-8").split() if h.strip()]

P = "https://data.ibb.gov.tr/dataset"
DOSYALAR = {
    "guzergah.geojson": f"{P}/b48d2095-851c-413c-8d36-87d2310a22b5/resource/4ccb4d29-c2b6-414a-b324-d2c9962b18e2/download/iett-hat-guzergahlar-verisi.geojson",
    "duraklar.geojson": f"{P}/af3c70e8-82d6-44e2-84cf-2e364c242227/resource/4f28ec8d-7c2d-477b-873d-d17ce5b5e3be/download/iett-otobus-duraklar..geojson",
    "routes.csv": f"{P}/8540e256-6df5-4719-85bc-e64e91508ede/resource/46dbe388-c8c2-45c4-ac72-c06953de56a2/download/routes.csv",
    "trips.csv": f"{P}/8540e256-6df5-4719-85bc-e64e91508ede/resource/7ff49bdd-b0d2-4a6e-9392-b598f77f5070/download/trips.csv",
    "stops.csv": f"{P}/8540e256-6df5-4719-85bc-e64e91508ede/resource/2299bc82-983b-4bdf-8520-5cef8c555e29/download/stops.csv",
    # CSV sürümü Excel sınırında (1.048.576 satır) kesik; tam hali zip'te
    "stop_times.zip": f"{P}/8540e256-6df5-4719-85bc-e64e91508ede/resource/80401c1c-c240-4a32-8f40-ef697100a681/download/stop_times.zip",
}


def indir():
    KAYNAK.mkdir(parents=True, exist_ok=True)
    for ad, url in DOSYALAR.items():
        hedef = KAYNAK / ad
        if hedef.exists():
            continue
        print("indiriliyor", ad, file=sys.stderr)
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(hedef.with_suffix(".part"), "wb") as f:
                for parca in r.iter_content(1 << 20):
                    f.write(parca)
        hedef.with_suffix(".part").rename(hedef)


def _csv(ad):
    return csv.DictReader(open(KAYNAK / ad, encoding="utf-8-sig", errors="replace", newline=""), delimiter=";")


def varyant_cizgileri(onekler):
    """GeoJSON'u satır satır tarar (her özellik tek satırda); yalnız bizim hatları ayrıştırır."""
    sonuc = {}
    with open(KAYNAK / "guzergah.geojson", encoding="utf-8") as f:
        for satir in f:
            if '"GUZERGAH_KODU"' not in satir or not any(o in satir for o in onekler):
                continue
            oz = json.loads(satir.rstrip().rstrip(","))
            p = oz["properties"]
            kod = p["GUZERGAH_KODU"].strip()
            if not kod.startswith(onekler):
                continue
            g = oz["geometry"]
            koor = g["coordinates"] if g["type"] == "LineString" else [c for parca in g["coordinates"] for c in parca]
            sonuc[kod] = {
                "kod": kod,
                "hat": p["HAT_KODU"],
                "ad": " ".join(p["GUZERGAH_ADI"].split()),
                "bas": p.get("HAT_BASI"),
                "son": p.get("HAT_SONU"),
                "yon": p.get("YON"),
                "uzunluk_resmi": float((p.get("UZUNLUK") or "0").replace(",", ".")),
                "cizgi": [[round(b, 6), round(e, 6)] for b, e in koor],
            }
    return sonuc


def durak_koordinatlari():
    d = json.load(open(KAYNAK / "duraklar.geojson", encoding="utf-8"))
    return {
        o["properties"]["DURAK_KODU"]: (o["properties"]["ADI"], o["geometry"]["coordinates"][1], o["geometry"]["coordinates"][0])
        for o in d["features"]
        if o.get("geometry")
    }


def varyant_duraklari(kodlar):
    """GTFS'ten her varyant için en çok durağı olan bir seferin durak sırası."""
    rota = {r["route_id"].strip(): r["route_code"].strip() for r in _csv("routes.csv")}
    sefer = {}
    for t in _csv("trips.csv"):
        rc = rota.get(t["route_id"].strip())
        if rc in kodlar:
            sefer[t["trip_id"].strip()] = rc
    kod_of = {s["stop_id"].strip(): s["stop_code"].strip() for s in _csv("stops.csv")}
    dizi = {}
    with zipfile.ZipFile(KAYNAK / "stop_times.zip") as z:
        ad = [n for n in z.namelist() if n.endswith(".txt") or n.endswith(".csv")][0]
        with z.open(ad) as ham:
            metin = io.TextIOWrapper(ham, encoding="utf-8-sig", newline="")
            ilk = metin.readline()
            ayrac = ";" if ";" in ilk else ","
            alanlar = [a.strip() for a in ilk.split(ayrac)]
            for r in csv.DictReader(metin, fieldnames=alanlar, delimiter=ayrac):
                t = r["trip_id"].strip()
                if t in sefer:
                    dizi.setdefault(t, []).append((int(r["stop_sequence"]), kod_of.get(r["stop_id"].strip())))
    en_iyi = {}
    for t, d in dizi.items():
        rc = sefer[t]
        if len(d) > len(en_iyi.get(rc, [])):
            en_iyi[rc] = [k for _, k in sorted(d)]
    return en_iyi


def main():
    indir()
    onekler = tuple(f"{h}_" for h in HATLAR)
    print("güzergâhlar okunuyor", file=sys.stderr)
    varyantlar = varyant_cizgileri(onekler)
    print("duraklar okunuyor", file=sys.stderr)
    koor = durak_koordinatlari()
    sira = varyant_duraklari(set(varyantlar))
    STATIK.mkdir(parents=True, exist_ok=True)
    for hat in HATLAR:
        cikti = {"hat": hat, "varyantlar": {}}
        for kod, v in sorted(varyantlar.items()):
            if v["hat"] != hat:
                continue
            c = Cizgi(v["cizgi"])
            duraklar = []
            onceki = -1.0
            for dk in sira.get(kod, []):
                if dk not in koor:
                    continue
                ad, e, b = koor[dk]
                # durak sırası ile çizgi üzerindeki konum tutarlı olsun:
                # gidiş-dönüşü aynı yoldan olanlarda önceki duraktan sonraki ilk adayı al
                aday = [a for a in c.adaylar(e, b, 120) if a[0] >= onceki - 30]
                if not aday:
                    continue
                s, d = aday[0]
                duraklar.append({"kod": dk, "ad": ad, "enlem": e, "boylam": b, "s": round(s), "sapma": round(d)})
                onceki = s
            v = dict(v, uzunluk=round(c.uzunluk), duraklar=duraklar)
            cikti["varyantlar"][kod] = v
        (STATIK / f"{hat}.json").write_text(json.dumps(cikti, ensure_ascii=False), encoding="utf-8")
        n = cikti["varyantlar"]
        print(hat, len(n), "varyant;", {k: len(x["duraklar"]) for k, x in n.items()}, file=sys.stderr)


if __name__ == "__main__":
    main()
