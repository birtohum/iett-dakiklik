"""İETT ağ geçidinin istek sınırını ölçer (bir kezlik deneme).

1. Sınır kalkana kadar dakikada bir istek atar.
2. Sonra 6 sn arayla istek atıp kaçıncıda "Rate limit exceeded" geldiğini sayar.
3. Yeniden kalkana kadar geçen süreyi ölçer.
"""
import sys
import time

sys.path.insert(0, __file__.rsplit("araclar", 1)[0])
from iett import servis  # noqa: E402


def dene(hat="15F"):
    try:
        servis._cagir(servis.KONUM, "GetHatOtoKonum_json", {"HatKodu": hat}, deneme=1)
        return True
    except Exception:
        return False


def bekle_kalksin():
    bas = time.time()
    while not dene():
        print(f"{time.strftime('%H:%M:%S')} hâlâ sınırda", flush=True)
        time.sleep(60)
    return time.time() - bas


print("kalkması beklendi:", round(bekle_kalksin()), "sn", flush=True)
n = 1
bas = time.time()
while True:
    time.sleep(6)
    if not dene():
        break
    n += 1
print(f"{time.strftime('%H:%M:%S')} sınır: {n} başarılı istek, {round(time.time() - bas)} sn içinde", flush=True)
print("yeniden kalkması:", round(bekle_kalksin()), "sn", flush=True)
