"""Ham günlük konumları ölçüp küçük bir günlük özete çevirir.

  python ozetle.py              # özeti olmayan ya da ham verisi daha yeni olan tüm günler
  python ozetle.py 2026-11-03   # tek gün

Çıktı: veri/ozet/GG.json.gz (depoya girer; ham veri girmez)
  kapsam    : toplayıcının çalıştığı dakika aralıkları [[bas_dk, bit_dk], ...]
  kalkislar : [hat, güzergâh, kalkış_sn, plan_dk|None, sapma_dk|None, tahmini]
  planlar   : [hat, güzergâh, plan_dk, eşleşti, gözlenebilir]
  gecisler  : [hat, güzergâh, durak, geçiş_sn, sefer_kalkış_sn|None]
"""
import gzip
import json
import pathlib
import sys

from iett import olcum

KOK = pathlib.Path(__file__).resolve().parent
HAM = KOK / "veri" / "ham"
OZET = KOK / "veri" / "ozet"
KAPSAM_BOSLUK = 3  # dk; bundan kısa veri kesintileri kapsamı bölmez
ONCE, SONRA = 15, olcum.GEC  # planlı kalkış, bu pencere tamamen kapsamdaysa "gözlenebilir"


def sn(s):
    h, m, x = map(int, s.split(":"))
    return h * 3600 + m * 60 + x


def dk(s):
    return int(s[:2]) * 60 + int(s[3:5])


def araliklar(dakikalar):
    sonuc = []
    for d in sorted(dk(x) for x in dakikalar):
        if sonuc and d - sonuc[-1][1] <= KAPSAM_BOSLUK:
            sonuc[-1][1] = d
        else:
            sonuc.append([d, d])
    return sonuc


def kapsamda(araliklar_, bas, bit):
    return any(a <= bas and bit <= b for a, b in araliklar_)


def ozetle(gun):
    o = olcum.gun_olc(gun, HAM / f"{gun}.jsonl", KOK / "veri" / "statik", KOK / "veri" / "plan")
    kapsam = araliklar(o["kapsam"])
    kalkis_sn = {}
    kalkislar = []
    for s in o["seferler"]:
        if "kalkis" not in s:
            continue
        kalkis_sn[s["id"]] = sn(s["kalkis"])
        kalkislar.append([s["hat"], s["guzergah"], sn(s["kalkis"]),
                          dk(s["plan"]) if "plan" in s else None, s.get("sapma_dk"),
                          s["kalkis_aralik_sn"] is None])
    planlar = [[p["hat"], p["guzergah"], dk(p["plan"]), p["eslesti"],
                kapsamda(kapsam, dk(p["plan"]) - ONCE, dk(p["plan"]) + SONRA)]
               for p in o["planlar"]]
    gecisler = [[g["hat"], g["guzergah"], g["durak"], sn(g["t"]), kalkis_sn.get(g["sefer"])]
                for g in o["gecisler"]]
    OZET.mkdir(parents=True, exist_ok=True)
    veri = {"gun": gun, "gun_tipi": o["gun_tipi"], "kapsam": kapsam,
            "kalkislar": kalkislar, "planlar": planlar, "gecisler": gecisler}
    with gzip.open(OZET / f"{gun}.json.gz", "wt", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    gozlenebilir = [p for p in planlar if p[4]]
    print(f"{gun}: kapsam {sum(b - a for a, b in kapsam)} dk, {len(kalkislar)} kalkış, "
          f"{sum(p[3] for p in gozlenebilir)}/{len(gozlenebilir)} gözlenebilir plan eşleşti, "
          f"{len(gecisler)} durak geçişi")


def main():
    if len(sys.argv) > 1:
        gunler = sys.argv[1:]
    else:
        gunler = []
        for h in sorted(HAM.glob("????-??-??.jsonl")):
            oz = OZET / f"{h.stem}.json.gz"
            if not oz.exists() or oz.stat().st_mtime < h.stat().st_mtime:
                gunler.append(h.stem)
    for g in gunler:
        ozetle(g)


if __name__ == "__main__":
    main()
