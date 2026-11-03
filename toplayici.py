"""Seçili hatlardaki otobüslerin konumlarını dakikada bir toplar.

İETT'nin konum servisi saatte 100 istekle sınırlı (ölçüldü, saat başında sıfırlanıyor).
Bu yüzden iki çağrı birlikte kullanılıyor:
  - GetFiloAracKonum (F): her dakika, TÜM filo tek yanıtta; hat bilgisi yok.  60/saat
  - GetHatOtoKonum   (H): iki dakikada bir, sıradaki hat; araç → hat ve güzergâh
    kodu eşlemesini tazeler. 10 hatla her hat ~20 dk'da bir.                  30/saat
Filo yanıtından yalnızca eşlemede olan araçlar saklanır.

Kullanım:
  python toplayici.py                 # süresiz
  python toplayici.py --sure 110      # 110 dakika

Ham kayıt: veri/ham/GG.jsonl, satır başına
  [alındı, kaynak(F/H), hat, kapino, güzergâh, konum_zamanı, enlem, boylam, ek]
  ek: F için hız (km/sa), H için en yakın durak kodu.
  F satırlarındaki güzergâh, aracın son H gözlemindeki koddur (yön değişmiş olabilir).
"""
import argparse
import datetime as dt
import json
import pathlib
import time

from iett import servis

KOK = pathlib.Path(__file__).resolve().parent
VERI = KOK / "veri"
HATLAR = [h.strip() for h in (KOK / "hatlar.txt").read_text(encoding="utf-8").split() if h.strip()]
TZ = dt.timezone(dt.timedelta(hours=3))
SAATLIK_TAVAN = 95  # 100'ün biraz altı
ESLEME_OMRU = 60 * 60  # sn; hat çağrısında bu kadar görünmeyen araç eşlemeden düşer


def simdi():
    return dt.datetime.now(TZ).replace(tzinfo=None)


def log(*a):
    print(f"{simdi():%H:%M:%S}", *a, flush=True)


def plani_sakla(gun):
    """Günün planı ve durak listesi; günde bir kez (bu servislerin kotası ayrı)."""
    hedef = VERI / "plan" / gun
    hedef.mkdir(parents=True, exist_ok=True)
    for hat in HATLAR:
        dosya = hedef / f"{hat}.json"
        if dosya.exists():
            continue
        try:
            kayit = {
                "hat": hat,
                "alindi": simdi().isoformat(timespec="seconds"),
                "bilgi": servis.hat_bilgisi(hat),
                "seferler": servis.planlanan_seferler(hat),
                "duraklar": servis.hat_duraklari(hat),
            }
        except Exception as e:  # sonraki turda yeniden dener
            log(f"plan alınamadı {hat}: {e}")
            continue
        dosya.write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")


class Butce:
    def __init__(self):
        self.saat, self.sayi = None, 0

    def _tazele(self):
        s = simdi().strftime("%Y%m%d%H")
        if s != self.saat:
            self.saat, self.sayi = s, 0

    def harca(self):
        self._tazele()
        if self.sayi >= SAATLIK_TAVAN:
            return False
        self.sayi += 1
        return True

    def hat_payi_var(self):
        """Saatin kalan dakikalarındaki filo çağrılarına yer bırakarak bir hat çağrısı sığar mı?"""
        self._tazele()
        return self.sayi + (59 - simdi().minute) < SAATLIK_TAVAN

    def tuket(self):
        """Sınır aşıldı: bu saatin kalanında istek atma."""
        self.sayi = SAATLIK_TAVAN


class Toplayici:
    def __init__(self):
        self.butce = Butce()
        self.esleme = {}  # kapino -> (hat, guzergah, görüldüğü an)
        self.son_hat = {h: None for h in HATLAR}
        self.gorulen = set()
        self.gun = None

    def _dosya(self):
        gun = simdi().strftime("%Y-%m-%d")
        if gun != self.gun:
            self.gun = gun
            self.gorulen = set()
            plani_sakla(gun)
        d = VERI / "ham" / f"{gun}.jsonl"
        d.parent.mkdir(parents=True, exist_ok=True)
        return d

    def _yaz(self, satirlar):
        yeni = 0
        with self._dosya().open("a", encoding="utf-8") as f:
            for s in satirlar:
                anahtar = (s[1], s[3], s[5])
                if anahtar in self.gorulen:
                    continue
                self.gorulen.add(anahtar)
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
                yeni += 1
        return yeni

    def _cagir(self, fn, *a):
        if not self.butce.harca():
            return None
        try:
            return fn(*a)
        except servis.SinirAsildi:
            log("istek sınırı aşıldı; saat başına kadar bekleniyor")
            self.butce.tuket()
        except Exception as e:
            log(f"hata {fn.__name__}{a}: {e}")
        return None

    def hat_turu(self):
        """Eşlemesi en eski hattı sorgula."""
        hat = min(HATLAR, key=lambda h: self.son_hat[h] or dt.datetime.min)
        araclar = self._cagir(servis.hat_konumlari, hat)
        if araclar is None:
            return None
        an = simdi()
        self.son_hat[hat] = an
        satirlar = []
        for a in araclar:
            k = a.get("kapino")
            self.esleme[k] = (hat, a.get("guzergahkodu"), an)
            satirlar.append([an.strftime("%H:%M:%S"), "H", hat, k, a.get("guzergahkodu"),
                             a.get("son_konum_zamani"), float(a.get("enlem") or 0),
                             float(a.get("boylam") or 0), a.get("yakinDurakKodu")])
        return self._yaz(satirlar)

    def filo_turu(self):
        araclar = self._cagir(servis.filo_konumlari)
        if araclar is None:
            return None
        an = simdi()
        for k in [k for k, (_, _, t) in self.esleme.items() if (an - t).total_seconds() > ESLEME_OMRU]:
            del self.esleme[k]
        satirlar = []
        for a in araclar:
            k = a.get("KapiNo")
            if k not in self.esleme or not a.get("Saat"):
                continue
            hat, guz, _ = self.esleme[k]
            t = dt.datetime.combine(an.date(), dt.time.fromisoformat(a["Saat"]))
            if t > an + dt.timedelta(minutes=5):  # gece yarısını geçen kayıt
                t -= dt.timedelta(days=1)
            satirlar.append([an.strftime("%H:%M:%S"), "F", hat, k, guz, t.strftime("%Y-%m-%d %H:%M:%S"),
                             float(a.get("Enlem") or 0), float(a.get("Boylam") or 0),
                             float(a.get("Hiz") or 0)])
        return self._yaz(satirlar)

    def dakika(self):
        f = self.filo_turu()
        eksik = any(v is None for v in self.son_hat.values())
        # başta eşlemesi olmayan hat varsa her dakika, sonra iki dakikada bir hat çağrısı
        h = None
        if self.butce.hat_payi_var() and (eksik or simdi().minute % 2 == 0):
            h = self.hat_turu()
        log(f"filo={f} hat={h} eşleme={len(self.esleme)} istek={self.butce.sayi}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sure", type=float, default=0, help="dakika; 0 = süresiz")
    a = p.parse_args()
    t = Toplayici()
    bitis = time.time() + a.sure * 60 if a.sure else float("inf")
    while time.time() < bitis:
        bas = time.time()
        t.dakika()
        time.sleep(max(0, 60 - (time.time() - bas)))


if __name__ == "__main__":
    main()
