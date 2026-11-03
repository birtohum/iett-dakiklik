# İstanbul otobüsleri planına ne kadar uyuyor?

İETT'nin planlanan kalkış saatlerini, otobüslerin dakikada bir yayımlanan konumlarıyla
karşılaştıran küçük bir ölçüm projesi ve statik site. Hepsi herkese açık İBB verisi;
anahtar ya da kayıt gerekmiyor.

Durum (3 Kasım 2026): 10 hat izleniyor, ilk gün verisi var. Rakamlar ön sonuç; hatlar arası
sıralama yeterli veri birikince (hat başına ≥40 kalkış, ≥5 gün) gösteriliyor.
Fizibilite ayrıntısı: [FIZIBILITE.md](FIZIBILITE.md).

## Ne ölçüyor

| Ölçü | Tanım |
|---|---|
| Kalkış sapması | Hat başından gözlenen kalkış − planlı kalkış (dk, + geç) |
| Dakik | 1 dk erken ile 5 dk geç arasında kalkanların payı |
| Gözlenen / planlı | Toplayıcının çalıştığı süre içindeki planlı kalkışlardan gözlenen bir kalkışla eşleşenler |
| Durakta bekleme | Ardışık otobüs aralıkları *h* için Σh²/(2Σh): rastgele gelen yolcunun ortalama beklemesi |
| Fazladan bekleme | Gözlenen bekleme − planlı aralıklardan aynı formülle hesaplanan bekleme (durakların medyanı) |

**Ne ölçmüyor:** Ara duraklarda "plana göre gecikme". İETT planı yalnızca hat başından
kalkış saatlerini içeriyor (GTFS'te de ara durak saatleri boş). İETT'nin kendi "plana uyum"
ve "sefer zayi" servisleri var ama herkese kapalı.

## Kaynaklar

- İETT web servisleri (İBB Açık Veri Portalı): `SeferGerceklesme.asmx` (konum),
  `PlanlananSeferSaati.asmx` (plan), `HatDurakGuzergah.asmx` ve `ibb.asmx` (hat, durak sırası)
- Portal dosyaları: İETT Hat Güzergâhları (GeoJSON), İETT Otobüs Durakları (GeoJSON), İETT GTFS
- Lisans: [İBB Açık Veri Lisansı](https://data.ibb.gov.tr/license) — atıfla serbest kullanım.
  Bu proje İBB ya da İETT'yle ilişkili değildir; ölçümler projenin kendisine aittir.

## Yöntem

1. **Toplama** (`toplayici.py`). Konum servisi saatte 100 istekle sınırlı (ölçüldü; saat
   başında sıfırlanıyor). Her dakika tüm filonun konumu tek çağrıyla alınıyor (60/saat), iki
   dakikada bir sıradaki hattın çağrısıyla araç → hat ve güzergâh kodu eşlemesi tazeleniyor
   (~30/saat). Yalnızca izlenen hatlardaki araçlar saklanıyor. Plan ve durak listesi günde bir
   kez alınıyor.
2. **Güzergâh** (`hazirla.py`). Her varyantın (`500T_D_D0`, `28_G_D2605` …) çizgisi GeoJSON'dan,
   durak sırası GTFS'ten (portaldaki `stop_times.csv` 1.048.576 satırda kesik; tam hali zip'te),
   durak koordinatları durak GeoJSON'undan. Duraklar çizgiye izdüşürülüp çizgi üzerindeki
   konumları (m) bulunuyor.
3. **Seferler** (`iett/olcum.py`). Aracın konumları, hat çağrısından gelen güzergâh
   etiketleriyle seferlere bölünüyor: etiket değiştiğinde yeni sefer, aracın yeni güzergâhın
   başına ilk vardığı anda başlıyor. Konumlar güzergâh çizgisine izdüşürülüyor (≤150 m;
   ilerleme geri gitmez).
4. **Kalkış**: aracın hat başındaki 150 m'lik bölgeden çıktığı an; son "içeride" ve ilk
   "dışarıda" konum arasından 6 m/s başlangıç hızı varsayımıyla kestiriliyor. Araç bölgede hiç
   görülmediyse (toplama başlamadan kalkmış vb.) ve ilk konumu ≤600 m ise geriye kestirim
   yapılıp "tahmini" işaretleniyor.
5. **Eşleştirme**: aynı güzergâh ve gün tipinin (hafta içi / cumartesi / pazar) planlı
   kalkışlarıyla, sırayı koruyan en düşük maliyetli eşleştirme (dinamik programlama, −10…+30 dk
   penceresi, eşleştirmeden bırakma maliyeti 12 dk).
6. **Durak geçişi**: durağı çevreleyen iki ardışık konum arasında doğrusal ara değerleme
   (konumlar en çok 3 dk arayla).
7. **Bekleme**: aynı durakta ardışık geçişler arası *h*; yalnızca toplayıcının kesintisiz
   çalıştığı aralıklar ve h ≤ 90 dk. Planlı karşılık: planlı kalkış + o durağa gözlenen medyan
   yolculuk süresi.

## Hata payı ve doğrulama

İlk deneme (3 Kasım 2026, 10:00–11:55, 10 hat, 15.705 konum):

- Konumlar arası medyan 61 sn; konumun güzergâh çizgisine uzaklığı medyan 5 m (%90: 26 m).
- Planlı 68 kalkıştan 61'i (%90) gözlenen bir kalkışla eşleşti; sapma medyan +0,9 dk.
- **Seyreltme testi**: konumların yarısı atılıp hesap tekrarlandığında durak geçiş anı farkı
  medyan 4 sn (%90: 18 sn), kalkış anı farkı medyan 4 sn (%90: 46 sn). Gerçek örnekleme
  bunun iki katı sık olduğundan gerçek hata daha küçük olmalı.
- Kalkış anını çevreleyen iki konum arası ~62 sn: kalkış ±1 dk belirsiz. Dakika altı farklar
  yorumlanmamalı.

Tekrar üretmek için: `python araclar/fizibilite_analiz.py 2026-11-03`.

## Sınırlar

- Eşleşmeyen planlı kalkış **gelmeyen sefer demek değil**: GPS kesintisi, araç eşlemeye geç
  girmesi, hat başında GPS'in güzergâh dışında görünmesi (ör. 28 hattında görüldü) de eşleşmeyen
  sefer bırakıyor.
- İstek sınırı nedeniyle en fazla ~20–30 hat izlenebilir; şimdilik 10.
- Toplama bilgisayar açıkken sürüyor; kapalı saatler ölçüme girmiyor (sitede gözlem süresi yazıyor).
- Resmî tatil günleri ayrıca işaretlenmiyor; gün tipi haftanın gününden.
- Çok sık seferli hatlarda (≤5 dk aralık) kalkış eşleştirmesi belirsizleşebilir; bekleme
  ölçüsü bu hatlar için daha anlamlı.
- Planın biçimi ya da servis adresleri değişirse toplama kırılır; ham veri saklandığı için
  yeniden hesaplanabilir.

## Çalıştırma

Python 3.12, Windows'ta denendi.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python hazirla.py        # bir kez: ~280 MB kaynak indirir, veri/statik/ üretir
.venv/Scripts/python toplayici.py      # süresiz toplama; veri/ham/GG.jsonl
.venv/Scripts/python ozetle.py         # ham → veri/ozet/GG.json.gz
.venv/Scripts/python site_uret.py      # özetler → site/veri/
.venv/Scripts/python -m http.server 8793 --directory site
```

İzlenen hatlar `hatlar.txt` içinde; değiştirince `hazirla.py` yeniden çalıştırılmalı.

## Dosyalar

| | |
|---|---|
| `iett/servis.py` | SOAP istemcisi |
| `iett/geo.py` | düzlem geometri, çizgiye izdüşüm |
| `iett/olcum.py` | sefer bölme, kalkış ve durak geçişi, planla eşleştirme |
| `toplayici.py`, `hazirla.py`, `ozetle.py`, `site_uret.py` | iş akışı |
| `araclar/` | fizibilite analizi, istek sınırı ölçümü |
| `veri/ozet/` | günlük özetler (depoda). Ham konumlar (`veri/ham/`) depoya girmiyor. |
| `site/` | statik site (HTML, CSS, JS; Leaflet ve OpenStreetMap karoları) |
