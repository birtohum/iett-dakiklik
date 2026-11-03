"""İETT'nin herkese açık SOAP servislerine küçük istemci.

Anahtar gerekmiyor; WSDL'deki AuthHeader isteğe bağlı (minOccurs=0).
Kaynak: İBB Açık Veri Portalı, İBB Açık Veri Lisansı.
"""
import json
import re
import time
import xml.etree.ElementTree as ET

import requests

KONUM = "https://api.ibb.gov.tr/iett/FiloDurum/SeferGerceklesme.asmx"
PLAN = "https://api.ibb.gov.tr/iett/UlasimAnaVeri/PlanlananSeferSaati.asmx"
DURAK = "https://api.ibb.gov.tr/iett/ibb/ibb.asmx"
HAT = "https://api.ibb.gov.tr/iett/UlasimAnaVeri/HatDurakGuzergah.asmx"

_oturum = requests.Session()
_oturum.headers["User-Agent"] = "iett-gecikme-olcumu/0.1 (+github.com/birtohum)"


class SinirAsildi(Exception):
    """Ağ geçidi "Rate limit exceeded" döndü. Ölçüldü (3 Kasım 2026): konum servisi
    (SeferGerceklesme) için saatte 100 istek; sayaç saat başında sıfırlanıyor."""


def _cagir(url, islem, parametreler, deneme=3):
    govde = "".join(f"<{k}>{v}</{k}>" for k, v in parametreler.items())
    zarf = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><{islem} xmlns="http://tempuri.org/">{govde}</{islem}></soap:Body>'
        "</soap:Envelope>"
    )
    for i in range(deneme):
        try:
            r = _oturum.post(
                url,
                data=zarf.encode("utf-8"),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": f'"http://tempuri.org/{islem}"',
                },
                timeout=60,
            )
            if "Rate limit exceeded" in r.text:
                raise SinirAsildi(islem)
            r.raise_for_status()
            return r.text
        except requests.RequestException:
            if i == deneme - 1:
                raise
            time.sleep(5 * (i + 1))


def _json_sonuc(metin, islem):
    m = re.search(rf"<{islem}Result>(.*?)</{islem}Result>", metin, re.S)
    if not m:
        return []
    # Sonuç XML içinde metin olarak geliyor; &amp; vb. kaçışları çöz.
    ham = ET.fromstring(f"<x>{m.group(1)}</x>").text or "[]"
    return json.loads(ham)


def hat_konumlari(hat):
    """Hattaki araçların anlık konumu: kapino, enlem, boylam, guzergahkodu, yon,
    son_konum_zamani, yakinDurakKodu."""
    islem = "GetHatOtoKonum_json"
    return _json_sonuc(_cagir(KONUM, islem, {"HatKodu": hat}), islem)


def filo_konumlari():
    """Tüm filonun anlık konumu (hat bilgisi yok)."""
    islem = "GetFiloAracKonum_json"
    return _json_sonuc(_cagir(KONUM, islem, {}), islem)


def planlanan_seferler(hat):
    """Güzergâh, gün tipi (I/C/P) ve ilk duraktan kalkış saati (DT)."""
    islem = "GetPlanlananSeferSaati_json"
    return _json_sonuc(_cagir(PLAN, islem, {"HatKodu": hat}), islem)


def hat_bilgisi(hat):
    islem = "GetHat_json"
    return _json_sonuc(_cagir(HAT, islem, {"HatKodu": hat}), islem)


def hat_duraklari(hat):
    """Yön (G/D) ve sıra numarasıyla durak listesi."""
    metin = _cagir(DURAK, "DurakDetay_GYY", {"hat_kodu": hat})
    kok = ET.fromstring(metin)
    duraklar = []
    for t in kok.iter("Table"):
        d = {c.tag: (c.text or "").strip() for c in t}
        duraklar.append(
            {
                "yon": d.get("YON"),
                "sira": int(d.get("SIRANO") or 0),
                "kod": d.get("DURAKKODU"),
                "ad": d.get("DURAKADI"),
                "boylam": float(d.get("XKOORDINATI") or 0),
                "enlem": float(d.get("YKOORDINATI") or 0),
                "ilce": d.get("ILCEADI"),
            }
        )
    return duraklar
