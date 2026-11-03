"""Deneme toplamasının fizibilite analizi.

  python araclar/fizibilite_analiz.py 2026-11-03 [--bas 09:30 --bit 11:20]

Çıktı: düz metin özet (FIZIBILITE.md'ye aktarılır) + veri/fizibilite_<gün>.json
"""
import argparse
import collections
import datetime as dt
import json
import pathlib
import statistics as st
import sys

KOK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
from iett import olcum  # noqa: E402
from iett.geo import Cizgi  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def yuzdelik(a, p):
    a = sorted(a)
    return a[min(len(a) - 1, int(p * len(a)))] if a else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gun")
    ap.add_argument("--bas", help="analiz penceresi başı SS:DD")
    ap.add_argument("--bit")
    a = ap.parse_args()
    ham = KOK / "veri" / "ham" / f"{a.gun}.jsonl"
    satirlar = list(olcum.ham_oku(ham))
    if a.bas:
        satirlar = [r for r in satirlar if a.bas <= r[5][11:16] < (a.bit or "99")]
    t0 = min(olcum.zaman(r[5]) for r in satirlar)
    t1 = max(olcum.zaman(r[5]) for r in satirlar)
    print(f"Pencere: {t0:%H:%M} – {t1:%H:%M}, {len(satirlar)} konum, {len({(r[2], r[3]) for r in satirlar})} araç")

    # 1) kaynak güncelleme aralığı ve gecikmesi
    arac = collections.defaultdict(list)
    gecikme = []
    for r in satirlar:
        t = olcum.zaman(r[5])
        if r[1] != "F":
            continue
        arac[(r[2], r[3])].append(t)
        alindi = dt.datetime.combine(t.date(), dt.time.fromisoformat(r[0]))
        gecikme.append((alindi - t).total_seconds())
    araliklar = []
    for ts in arac.values():
        ts.sort()
        araliklar += [(b - a_).total_seconds() for a_, b in zip(ts, ts[1:])]
    print(f"Ardışık konumlar arası (sn): medyan {yuzdelik(araliklar, .5):.0f}, %10 {yuzdelik(araliklar, .1):.0f}, %90 {yuzdelik(araliklar, .9):.0f}")
    print(f"Konum zamanı → bizim alış (sn): medyan {yuzdelik(gecikme, .5):.0f}, %90 {yuzdelik(gecikme, .9):.0f}")

    # 2) ölçüm
    gecici = KOK / "veri" / f"_pencere_{a.gun}.jsonl"
    gecici.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in satirlar), encoding="utf-8")
    o = olcum.gun_olc(a.gun, gecici, KOK / "veri" / "statik", KOK / "veri" / "plan")
    sf = o["seferler"]
    print(f"Gözlenen sefer parçası: {len(sf)}; güzergâhı bilinen: {sum('izlenen' in s for s in sf)}")
    sapmalar = [s["sapma_medyan"] for s in sf if s.get("sapma_medyan") is not None]
    print(f"Konumun güzergâh çizgisine dik uzaklığı (sefer medyanları, m): medyan {yuzdelik(sapmalar, .5)}, %90 {yuzdelik(sapmalar, .9)}")
    atilan = sum(s["nokta"] - s.get("izlenen", 0) for s in sf if "izlenen" in s)
    toplam = sum(s["nokta"] for s in sf if "izlenen" in s)
    print(f"Çizgiye {olcum.ESIK_CIZGI:.0f} m'den uzak ya da tutarsız diye atılan konum: {atilan}/{toplam} (%{100 * atilan / max(1, toplam):.1f})")
    kalkisli = [s for s in sf if "kalkis" in s]
    eslesen = [s for s in kalkisli if "plan" in s]
    print(f"Kalkışı gözlenen sefer: {len(kalkisli)}; planla eşleşen: {len(eslesen)}")
    ka = [s["kalkis_aralik_sn"] for s in kalkisli if s["kalkis_aralik_sn"] is not None]
    print(f"  bunların {len(kalkisli) - len(ka)} tanesi geriye kestirim (araç hat başında görülmedi)")
    if ka:
        print(f"Kalkış anını çevreleyen iki konum arası (sn): medyan {yuzdelik(ka, .5)}, %90 {yuzdelik(ka, .9)}")
    sp = [s["sapma_dk"] for s in eslesen]
    if sp:
        print(f"Kalkış sapması (dk, + geç): medyan {st.median(sp):.1f}, %10 {yuzdelik(sp, .1)}, %90 {yuzdelik(sp, .9)}; "
              f"−1…+5 dk içinde: %{100 * sum(-1 <= x <= 5 for x in sp) / len(sp):.0f}")

    # 3) planlı seferlerin gerçekleşmesi: pencerenin içinde kalan planlılar
    bas_dk = t0.hour * 60 + t0.minute + 15  # ilk 15 dk: araç hat başına gelmeden toplama başlamış olabilir
    bit_dk = t1.hour * 60 + t1.minute - olcum.GEC
    pen = [p for p in o["planlar"] if bas_dk <= int(p["plan"][:2]) * 60 + int(p["plan"][3:]) <= bit_dk]
    print(f"Pencere içinde planlı kalkış: {len(pen)}; gözlenen bir kalkışla eşleşen: {sum(p['eslesti'] for p in pen)} "
          f"(%{100 * sum(p['eslesti'] for p in pen) / max(1, len(pen)):.0f})")
    hat_ozet = collections.defaultdict(lambda: [0, 0, []])
    for p in pen:
        hat_ozet[p["hat"]][0] += 1
        hat_ozet[p["hat"]][1] += p["eslesti"]
    for s in eslesen:
        hat_ozet[s["hat"]][2].append(s["sapma_dk"])
    print("Hat | planlı | eşleşen | medyan sapma (dk)")
    for h, (n, e, d) in sorted(hat_ozet.items()):
        print(f"  {h:5} | {n:3} | {e:3} | {st.median(d):5.1f}" if d else f"  {h:5} | {n:3} | {e:3} |   -")

    # 4) seyreltme testi: her iki konumdan birini at, geçiş zamanlarını yeniden hesapla
    statik = {h: json.loads((KOK / "veri" / "statik" / f"{h}.json").read_text(encoding="utf-8"))["varyantlar"]
              for h in {s["hat"] for s in sf}}
    cizgiler = {}
    farklar, kfark = [], []
    for s in olcum.gozlenen_seferler(satirlar, olcum.baslangiclar(statik)):
        v = statik.get(s["hat"], {}).get(s["guzergah"])
        if not v:
            continue
        c = cizgiler.setdefault(s["guzergah"], Cizgi(v["cizgi"]))
        tam = olcum.ilerleme(c, s["noktalar"])
        for kaydir in (0, 1):
            seyrek = olcum.ilerleme(c, s["noktalar"][kaydir::2])
            g_tam = {d: t for d, t, _ in olcum.durak_gecisleri(tam, v["duraklar"])}
            for d, t, _ in olcum.durak_gecisleri(seyrek, v["duraklar"]):
                if d in g_tam:
                    farklar.append((t - g_tam[d]).total_seconds())
            k1, k2 = olcum.kalkis_kestir(tam), olcum.kalkis_kestir(seyrek)
            if k1 and k2:
                kfark.append((k2[0] - k1[0]).total_seconds())
    mutlak = [abs(x) for x in farklar]
    print(f"Seyreltme testi (≈2 dk örnekleme vs ≈1 dk): durak geçişi |fark| medyan {yuzdelik(mutlak, .5):.0f} sn, "
          f"%90 {yuzdelik(mutlak, .9):.0f} sn, n={len(mutlak)}")
    km = [abs(x) for x in kfark]
    if km:
        print(f"  kalkış |fark| medyan {yuzdelik(km, .5):.0f} sn, %90 {yuzdelik(km, .9):.0f} sn, n={len(km)}")
    print(f"Durak geçişi kaydı: {len(o['gecisler'])}")

    ornek = sorted(eslesen, key=lambda s: (s["hat"], s["kalkis"]))
    print("Örnek eşleşmeler (hat, güzergâh, kapı no, plan, gözlenen kalkış, sapma dk):")
    for s in ornek[:: max(1, len(ornek) // 15)][:15]:
        print(f"  {s['hat']:5} {s['guzergah']:13} {s['kapino']:7} {s['plan']}  {s['kalkis']}  {s['sapma_dk']:+.1f}")
    gecici.unlink()
    (KOK / "veri" / f"fizibilite_{a.gun}.json").write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
