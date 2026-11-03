"""Ham konumlardan sefer, kalkış ve durak geçiş zamanı çıkarımı; planla eşleştirme.

Yöntem (ayrıntısı README'de):
  1. Her aracın konumları, aynı güzergâh kodu sürdükçe ve 15 dk'dan uzun boşluk
     olmadıkça tek bir "gözlenen sefer" sayılır.
  2. Her konum, güzergâh çizgisine izdüşürülür (çizgiye en çok ESIK_CIZGI metre);
     gidiş-dönüşü aynı yoldan olan çizgilerde ilerlemenin geri gitmeyeceği varsayılır.
  3. Kalkış: aracın baştaki BAS_BOLGE metreden çıktığı an. Son "içeride" ve ilk
     "dışarıda" konum arasından, aracın V_REF hızla ilerlediği varsayılarak kestirilir.
  4. Durak geçişi: durağın çizgi üzerindeki konumunu çevreleyen iki ardışık konum
     arasında doğrusal ara değerleme (iki konum en çok MAKS_ARALIK saniye arayla).
  5. Planla eşleştirme: aynı güzergâh kodu ve gün tipindeki planlı kalkışlarla,
     sırayı koruyan en düşük maliyetli eşleştirme (dinamik programlama).
"""
import collections
import datetime as dt
import json
import pathlib

from iett.geo import Cizgi

ESIK_CIZGI = 150.0  # m; güzergâha bundan uzak konumlar atılır
BAS_BOLGE = 150.0  # m; hat başı bölgesi
V_REF = 6.0  # m/s (~22 km/sa) kalkış kestiriminde başlangıç hızı varsayımı
YAKIN_ILK = 600.0  # m; hat başında görülmemiş seferde geriye kestirim için ilk konum en çok
MAKS_ARALIK = 180  # sn; durak geçişi için iki konum arası en fazla
SEFER_BOSLUK = 15 * 60  # sn
ERKEN = -10  # dk; plan eşleştirmede kabul edilen en erken kalkış
GEC = 30  # dk; en geç kalkış
ATLA = 12.0  # dk; bir planlı ya da gözlenen seferi eşleştirmeden bırakmanın maliyeti

GUN_TIPI = {0: "I", 1: "I", 2: "I", 3: "I", 4: "I", 5: "C", 6: "P"}


def zaman(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def ham_oku(dosya):
    """Satırlar: [alındı, kaynak F/H, hat, kapino, güzergâh, konum_zamanı, enlem, boylam, ek]"""
    with open(dosya, encoding="utf-8") as f:
        for satir in f:
            yield json.loads(satir)


UZAK = 1000.0  # m; aracın hat başından "ayrıldı" sayılması için


def _bolge(noktalar, bas):
    """Konumlara güzergâh kodu ata. noktalar: [(t, e, b, etiket|None)] sıralı;
    etiket H çağrısından gelen gerçek güzergâh kodu. bas: kod -> (enlem, boylam).
    Döner: [(kod|None, t, e, b)]"""
    from iett.geo import mesafe

    def yakin(i, kod):
        if kod not in bas:
            return False
        return mesafe(noktalar[i][1], noktalar[i][2], *bas[kod]) < BAS_BOLGE

    def uzak(i, kod):
        return kod in bas and mesafe(noktalar[i][1], noktalar[i][2], *bas[kod]) > UZAK

    n = len(noktalar)
    kod = [None] * n
    etiketli = [i for i in range(n) if noktalar[i][3]]
    if not etiketli:
        return []
    # ilk etiketten geriye: hat başındaki bekleme dahil, daha öncesi bilinmiyor
    i0 = etiketli[0]
    g = noktalar[i0][3]
    j = i0
    basta = yakin(i0, g)
    while j - 1 >= 0:
        if basta and not yakin(j - 1, g):
            break
        if yakin(j - 1, g):
            basta = True
        j -= 1
    for k in range(j, i0 + 1):
        kod[k] = g
    # etiketler arası ve son etiketten sonrası
    sinirlar = etiketli[1:] + [n]
    for i1, i2 in zip(etiketli, sinirlar):
        g1 = noktalar[i1][3]
        g2 = noktalar[i2][3] if i2 < n else None
        if g2 is not None and g2 != g1:
            # yön/varyant değişti: aracın g2'nin başına ilk vardığı an
            gecis = next((k for k in range(i1 + 1, i2 + 1) if yakin(k, g2)), i2)
            for k in range(i1 + 1, gecis):
                kod[k] = g1
            for k in range(gecis, i2 + 1):
                kod[k] = g2
            continue
        # aynı kod (ya da son etiket): uzaklaşıp yeniden başa dönerse yeni sefer
        ayrildi = False
        k = i1 + 1
        while k < i2:
            if uzak(k, g1):
                ayrildi = True
            if ayrildi and yakin(k, g1):
                break
            kod[k] = g1
            k += 1
        if k >= i2 and i2 < n:
            kod[i2] = g1  # etiketli noktanın kendisi de aynı seferde
        if k < i2:
            # başa döndü: aynı koddan yeni sefer başlıyor (araya etiketsiz bir sefer sığmışsa
            # o sefer önceki seferin parçası gibi görünür; ilerleme geri gitmediği için zararsız)
            if g2 is None:
                break  # son etiketten sonra yeni seferin kodu bilinmiyor
            for m in range(k, i2 + 1):
                kod[m] = (g1, "yeni")  # bölme işareti
            kod[k] = (g1, "yeni-bas")
    return [(kod[i], *noktalar[i][:3]) for i in range(n)]


def gozlenen_seferler(satirlar, bas=None):
    """[{hat, kapino, guzergah, noktalar:[(t, enlem, boylam)]}]
    bas: güzergâh kodu -> (enlem, boylam) hat başı noktası."""
    bas = bas or {}
    arac = collections.defaultdict(dict)
    for r in satirlar:
        if not r[5] or not r[6]:
            continue
        t = zaman(r[5])
        onceki = arac[(r[2], r[3])].get(t)
        etiket = r[4] if r[1] == "H" else None
        if onceki is None or (etiket and not onceki[3]):
            arac[(r[2], r[3])][t] = (t, r[6], r[7], etiket)
    seferler = []
    for (hat, kapi), sozluk in arac.items():
        noktalar = [sozluk[t] for t in sorted(sozluk)]
        mevcut = None
        for kod, t, e, b in _bolge(noktalar, bas):
            if kod is None:
                if mevcut:
                    seferler.append(mevcut)
                mevcut = None
                continue
            yeni_bas = isinstance(kod, tuple) and kod[1] == "yeni-bas"
            g = kod[0] if isinstance(kod, tuple) else kod
            if mevcut and (g != mevcut["guzergah"] or yeni_bas
                           or (t - mevcut["noktalar"][-1][0]).total_seconds() > SEFER_BOSLUK):
                seferler.append(mevcut)
                mevcut = None
            if mevcut is None:
                mevcut = {"hat": hat, "kapino": kapi, "guzergah": g, "noktalar": []}
            mevcut["noktalar"].append((t, e, b))
        if mevcut:
            seferler.append(mevcut)
    return seferler


def ilerleme(cizgi, noktalar):
    """Konumları çizgi üzerindeki ilerlemeye (m) çevirir; [(t, s, d)]."""
    sonuc = []
    onceki = None
    for t, e, b in noktalar:
        adaylar = cizgi.adaylar(e, b, ESIK_CIZGI)
        if not adaylar:
            continue
        if onceki is None:
            s, d = adaylar[0]
        else:
            ps, pt = onceki
            sn = max(1.0, (t - pt).total_seconds())
            uygun = [a for a in adaylar if ps - 100 <= a[0] <= ps + 25 * sn + 300]
            if not uygun:
                continue
            s, d = uygun[0]  # en erken uygun geçiş: gidiş-dönüş aynı yoldaysa dönüş ilerde kalır
            s = max(s, ps)  # GPS titreşimiyle geri gitme yok
        sonuc.append((t, s, d))
        onceki = (s, t)
    return sonuc


def kalkis_kestir(iz):
    """Hat başı bölgesinden çıkış anı ve onu çevreleyen konumlar arası süre (sn).
    Araç bölgede hiç gözlenmemiş ama ilk konumu YAKIN_ILK metreden yakınsa geriye
    V_REF hızla kestirilir; o zaman süre None döner ("tahmini")."""
    icerde = None
    for t, s, _ in iz:
        if s < BAS_BOLGE:
            icerde = (t, s)
            continue
        if icerde is None:
            if s < YAKIN_ILK:
                return t - dt.timedelta(seconds=s / V_REF), None
            return None
        t0, s0 = icerde
        gecen = (t - t0).total_seconds()
        geri = (s - BAS_BOLGE) / V_REF
        return t - dt.timedelta(seconds=min(gecen, max(0.0, geri))), gecen
    return None


def durak_gecisleri(iz, duraklar):
    """Her durak için ara değerlenmiş geçiş anı (yalnız çevreleyen iki konum varsa)."""
    sonuc = []
    j = 0
    for dk in duraklar:
        hedef = dk["s"]
        while j + 1 < len(iz) and iz[j + 1][1] < hedef:
            j += 1
        if j + 1 >= len(iz) or iz[j][1] > hedef:
            continue
        (t1, s1, _), (t2, s2, _) = iz[j], iz[j + 1]
        aralik = (t2 - t1).total_seconds()
        if aralik > MAKS_ARALIK or s2 <= s1:
            continue
        oran = (hedef - s1) / (s2 - s1)
        sonuc.append((dk["kod"], t1 + dt.timedelta(seconds=oran * aralik), aralik))
    return sonuc


def esle(planli, gozlenen):
    """Sırayı koruyan eşleştirme. planli, gozlenen: dakika cinsinden sıralı listeler.
    Döner: [(i_plan, j_gozlenen)]."""
    n, m = len(planli), len(gozlenen)
    INF = float("inf")
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    Y = [[None] * (m + 1) for _ in range(n + 1)]
    D[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            if D[i][j] == INF:
                continue
            if i < n and D[i][j] + ATLA < D[i + 1][j]:
                D[i + 1][j], Y[i + 1][j] = D[i][j] + ATLA, (i, j, False)
            if j < m and D[i][j] + ATLA < D[i][j + 1]:
                D[i][j + 1], Y[i][j + 1] = D[i][j] + ATLA, (i, j, False)
            if i < n and j < m:
                fark = gozlenen[j] - planli[i]
                if ERKEN <= fark <= GEC:
                    c = D[i][j] + abs(fark)
                    if c < D[i + 1][j + 1]:
                        D[i + 1][j + 1], Y[i + 1][j + 1] = c, (i, j, True)
    ciftler = []
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj, eslesti = Y[i][j]
        if eslesti:
            ciftler.append((pi, pj))
        i, j = pi, pj
    return ciftler[::-1]


def baslangiclar(statik):
    """{hat: {kod: varyant}} -> {kod: (enlem, boylam)} hat başı noktaları."""
    return {k: (v["cizgi"][0][1], v["cizgi"][0][0]) for vs in statik.values() for k, v in vs.items()}


def dakika(t, gun):
    return (t - gun).total_seconds() / 60


def gun_olc(gun_str, ham_dosya, statik_dizin, plan_dizin):
    """Bir günün ölçümü. Döner: sefer listesi ve durak geçişleri."""
    gun = dt.datetime.strptime(gun_str, "%Y-%m-%d")
    tip = GUN_TIPI[gun.weekday()]
    satirlar = list(ham_oku(ham_dosya))
    statik, plan = {}, {}
    for hat in {r[2] for r in satirlar}:
        p = pathlib.Path(statik_dizin) / f"{hat}.json"
        if p.exists():
            statik[hat] = json.loads(p.read_text(encoding="utf-8"))["varyantlar"]
        pp = pathlib.Path(plan_dizin) / gun_str / f"{hat}.json"
        if pp.exists():
            plan[hat] = json.loads(pp.read_text(encoding="utf-8"))
    seferler = gozlenen_seferler(satirlar, baslangiclar(statik))
    cizgiler = {}
    gecisler = []
    kalkislar = collections.defaultdict(list)  # guzergah -> [sefer kaydı]
    kayitlar = []
    for s in seferler:
        v = statik.get(s["hat"], {}).get(s["guzergah"])
        kayit = {
            "hat": s["hat"], "guzergah": s["guzergah"], "kapino": s["kapino"],
            "ilk": s["noktalar"][0][0].strftime("%H:%M:%S"),
            "son": s["noktalar"][-1][0].strftime("%H:%M:%S"),
            "nokta": len(s["noktalar"]),
        }
        kayitlar.append(kayit)
        if not v:
            kayit["durum"] = "güzergâh yok"
            continue
        if s["guzergah"] not in cizgiler:
            cizgiler[s["guzergah"]] = Cizgi(v["cizgi"])
        iz = ilerleme(cizgiler[s["guzergah"]], s["noktalar"])
        kayit["izlenen"] = len(iz)
        kayit["sapma_medyan"] = round(sorted(d for _, _, d in iz)[len(iz) // 2]) if iz else None
        if iz:
            kayit["ilerleme_m"] = round(iz[-1][1] - iz[0][1])
        k = kalkis_kestir(iz)
        if k:
            t, aralik = k
            kayit["kalkis"] = t.strftime("%H:%M:%S")
            kayit["kalkis_aralik_sn"] = round(aralik) if aralik is not None else None
            kalkislar[s["guzergah"]].append(kayit)
        for durak, t, aralik in durak_gecisleri(iz, v["duraklar"]):
            gecisler.append({
                "hat": s["hat"], "guzergah": s["guzergah"], "kapino": s["kapino"],
                "durak": durak, "t": t.strftime("%H:%M:%S"), "aralik_sn": round(aralik),
            })
    # planla eşleştir
    planlar = []
    for hat, p in plan.items():
        grup = collections.defaultdict(list)
        for sf in p["seferler"]:
            if sf["SGUNTIPI"] == tip:
                hh, mm = map(int, sf["DT"].split(":"))
                grup[sf["SGUZERAH"]].append(hh * 60 + mm)
        for g, dakikalar in grup.items():
            dakikalar.sort()
            gz = sorted(kalkislar.get(g, []), key=lambda k: k["kalkis"])
            gd = [dakika(dt.datetime.combine(gun.date(), dt.time.fromisoformat(k["kalkis"])), gun) for k in gz]
            ciftler = esle(dakikalar, gd)
            eslenen = {i for i, _ in ciftler}
            for i, j in ciftler:
                gz[j]["plan"] = f"{dakikalar[i] // 60:02d}:{dakikalar[i] % 60:02d}"
                gz[j]["sapma_dk"] = round(gd[j] - dakikalar[i], 1)
            for i, d in enumerate(dakikalar):
                planlar.append({"hat": hat, "guzergah": g, "plan": f"{d // 60:02d}:{d % 60:02d}", "eslesti": i in eslenen})
    return {"gun": gun_str, "gun_tipi": tip, "seferler": kayitlar, "gecisler": gecisler, "planlar": planlar}
