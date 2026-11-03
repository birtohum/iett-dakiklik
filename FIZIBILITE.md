# Fizibilite: İstanbul otobüsleri planına ne kadar uyuyor?

3 Kasım 2026 (Salı). Soru: İETT'nin planlanan sefer saatleri ile otobüslerin gerçek
konumları herkese açık veriden karşılaştırılabilir mi?

**Kısa cevap: evet, sınırlarıyla.** Gerekli üç veri (plan, durak/güzergâh, canlı konum)
anahtarsız ve kayıt olmadan erişilebilir; lisans otomatik çekmeye ve atıfla yayımlamaya
izin veriyor. İki önemli kısıt var: (1) planlı saat yalnızca **hat başından kalkış** için
var, ara duraklar için yok; (2) konum servisi **saatte 100 istekle** sınırlı. İkisi de
ölçümü daraltıyor ama engellemiyor.

## 1. Kaynaklar

| Veri | Nereden | Erişim | Güncellik |
|---|---|---|---|
| Canlı konum, hat bazında | `SeferGerceklesme.asmx` → `GetHatOtoKonum_json(HatKodu)` | Anahtarsız SOAP | Konumlar ~60 sn'de bir yenileniyor |
| Canlı konum, tüm filo | aynı servis → `GetFiloAracKonum_json()` | Anahtarsız, ~1,1 MB, ~2 sn | aynı |
| Planlanan sefer saatleri | `PlanlananSeferSaati.asmx` → `GetPlanlananSeferSaati_json(HatKodu)` | Anahtarsız | Güncel (canlı servis) |
| Hat bilgisi, durak sırası | `HatDurakGuzergah.asmx` → `GetHat_json`, `ibb.asmx` → `DurakDetay_GYY` | Anahtarsız | Güncel |
| Güzergâh çizgileri (varyantlar dahil) | Portal: "İETT Hat Güzergahları" GeoJSON (~250 MB) | Doğrudan indirme | 18 Mart 2026 |
| Duraklar | Portal: "İETT Otobüs Durakları" GeoJSON | Doğrudan indirme | 18 Mart 2026 |
| GTFS | Portal: "İETT GTFS Verisi" | Doğrudan indirme | 17 Mart 2026 |

Servis kullanım dokümanında (V1.5) kimlik doğrulama ya da istek sınırı anlatılmıyor;
WSDL'deki `AuthHeader` isteğe bağlı (`minOccurs=0`).

**Kapalı olanlar.** Aynı WSDL'de `GetPlanaUyum_json` (plana uyum), `GetSeferZayi_json`
(sefer kaybı), `GetKaraKutu_json`, `GetKaraKutuSeferBilgileri_json`, `GetFiloDurum_json`
de listeleniyor ama ağ geçidi "Service Not Found" dönüyor. Yani İETT'nin kendi
gerçekleşme ölçümü var ama herkese açık değil; bu proje onu konumlardan yeniden kuruyor.
Bu verinin açılması ayrıca istenebilir (karar kullanıcının).

## 2. Kullanım şartları

- Tüm veri setleri **İBB Açık Veri Lisansı** ile yayımlanıyor: kopyalama, yayımlama,
  uyarlama, ticari ve ticari olmayan kullanım serbest; şart, kaynağa atıf ve mümkünse
  lisansa bağlantı (belirli ifade yoksa "CC BY 4.0 kapsamında lisanslanan kamu sektörü
  bilgilerini içerir"). Kişisel veri lisans dışı.
- Portalın Kullanım Koşulları verinin **kullanılmasıyla kabul edilmiş sayılıyor**
  (tıklayarak onay yok); veri "olduğu gibi" sunuluyor, doğruluk garantisi yok; İBB'nin
  onayı varmış gibi sunmak yasak.
- Otomatik çekmeyi yasaklayan bir hüküm yok. Pratik sınır ağ geçidinin hız sınırı (aşağıda).
- Kişisel veri: konum kayıtlarında araç kapı numarası ve plaka var, sürücü bilgisi yok.
  Sitede plaka gösterilmeyecek; kapı numarası yalnızca ham veride.

**Değerlendirme:** Hesap açmak ya da açık bir şart kabul etmek gerekmiyor. Kullanmak
koşulları kabul saymak anlamına geliyor; bu tür örtük kabulü kullanıcıya bildiriyorum.

## 3. İstek sınırı (ölçüldü)

İlk denemede 10 hattı 20 sn arayla sorgularken (dakikada 30 istek) 08:33'te
`Policy Falsified / Rate limit exceeded` geldi ve sınır **09:00'a kadar** sürdü.
Ardından 6 sn arayla sayıldı: saat başından itibaren **100. istekte** yine kesildi
(09:10) ve yine saat başına kadar açılmadı. Sonuç: konum servisi (`SeferGerceklesme`)
için **saatte 100 istek, sayaç saat başında sıfırlanıyor**. Hat/durak servisi bu sırada
çalışmaya devam etti, yani sınır servis başına.

Bu yüzden toplama şöyle kuruldu (saatte en çok 95 istek):

- Her dakika bir **tüm filo** çağrısı (60/saat): bütün otobüslerin konumu tek yanıtta,
  ama hat bilgisi yok.
- İki dakikada bir sıradaki hattın **hat çağrısı** (~30/saat): araç → hat ve güzergâh
  kodu eşlemesi. 10 hatla her hat ~20 dakikada bir tazeleniyor.
- Filo yanıtından yalnızca eşlemedeki araçlar saklanıyor.

Sonuç: konum çözünürlüğü kaynağın kendi yenileme hızına (dakikada bir) eşit; hat sayısı
artarsa yalnızca eşleme seyrekleşiyor. Pratik üst sınır ~20–30 hat.

## 4. Planın biçimi

`GetPlanlananSeferSaati_json` her güzergâh varyantı (`500T_D_D0`, `28_G_D2605` …) ve gün
tipi (`I` hafta içi, `C` cumartesi, `P` pazar) için **ilk duraktan kalkış saatlerini**
veriyor. Ara durak saati yok. GTFS'te de ara durak saatleri boş (yalnızca ilk durakta
dolu; 6,2 milyon satırın 271 binında saat var) ve GTFS planı güncel servisle uyuşmuyor
(ör. 500T `D_D0` hafta içi: GTFS 159, canlı servis 116 kalkış). Ayrıca portaldaki
`stop_times.csv`, Excel satır sınırında (1.048.576) kesik; tam hali zip'te.

Bu yüzden ölçülebilen şeyler:

1. **Kalkış dakikliği:** hat başından gerçek kalkış − planlı kalkış.
2. **Sefer gerçekleşmesi:** planlı kalkışlardan kaçı gözlenen bir kalkışla eşleşti.
3. **Duraklarda bekleme:** ara duraklardan geçiş anları → ardışık otobüs aralıkları →
   rastgele gelen yolcunun ortalama beklemesi, planlı aralıklardan hesaplanan beklemeyle
   karşılaştırılarak. (Ara durakta "plana göre gecikme" ölçülemez, çünkü plan yok.)

## 5. Deneme toplaması (3 Kasım 2026, 10:00–11:55)

10 hat: 500T, 15F, 76D, 146T, 40T, 25E, 28, 30D, 59R, 2 (uzun/kısa, Avrupa/Anadolu
karışık). Saatte 83–95 istek, sınır aşılmadı, hiç hata yok. Analiz:
`python araclar/fizibilite_analiz.py 2026-11-03` (tam çıktı `veri/fizibilite_cikti.txt`).

**Veri kalitesi**

| | Değer |
|---|---|
| Konum kaydı / araç | 15.705 / 144 |
| Aynı aracın ardışık konumları arası | medyan 61 sn (%10: 53, %90: 65) |
| Konum zamanı → bizim alış | medyan 28 sn |
| Konumun güzergâh çizgisine dik uzaklığı | medyan 5 m, %90: 26 m |
| Çizgiye 150 m'den uzak (garaj yolu, güzergâh dışı) ya da tutarsız diye atılan konum | %8,7 |

Aynı an için hat çağrısı ile filo çağrısının koordinatları birebir aynı (66/66), yani iki
kaynak aynı ham konumu veriyor.

**Planla eşleştirme**

Planlı kalkışlarla gözlenen kalkışlar, sırayı koruyan en düşük maliyetli eşleştirmeyle
(−10…+30 dk penceresi) eşlendi. Pencerenin ilk 15 ve son 30 dakikası dışarıda bırakıldı.

| | Değer |
|---|---|
| Pencere içinde planlı kalkış | 68 |
| Gözlenen bir kalkışla eşleşen | 61 (%90) |
| Kalkış sapması (eşleşen 102 kalkış, + geç) | medyan +0,9 dk; %10: −0,9; %90: +5,9 |
| −1…+5 dk içinde kalkan | %76 |
| Kalkışı geriye kestirimle bulunan (araç hat başında hiç görülmedi) | 8 / 103 |

Eşleşmelerin gerçek olduğuna dair dolaylı kanıt: sapmalar sıfır etrafında dar
(medyan +0,9 dk). Rastgele eşleşme sefer aralığının yarısı ölçeğinde (5–10 dk) dağılırdı.

Örnek: 500T `G_D0` plan 10:20 → kalkış 10:21:13; 40T `G_D3042` plan 11:25 → 11:25:21;
146T `G_D0` plan 11:16 → 11:21:35.

**Eşleşmeyen 7 planlı kalkış "gelmeyen sefer" demek değil.** Elle bakıldığında bir kısmı
gözlem eksikliği: araç eşlemeye kalkıştan sonra girmiş, hat başı GPS'te güzergâhtan uzakta
duruyor (28 hattında 0 m ilerleyen parçalar) ya da araç önceki seferden geç dönmüş. Sefer
düşmesini iddia etmeden önce her hat için bu ayrımın yapılması ve birkaç gün gözlem
gerekiyor. Sitede bu oran "gözlenen/planlı" diye, sınırıyla gösterilecek.

**Zaman hata payı (seyreltme testi)**

Konumların her ikinciden biri atılıp (≈2 dk örnekleme) aynı hesap tekrarlandı:

| | |fark| medyan | %90 | n |
|---|---|---|---|
| Durak geçiş anı | 4 sn | 18 sn | 12.834 |
| Kalkış anı | 4 sn | 46 sn | 204 |

Gerçek örnekleme 1 dk olduğu için hata bundan küçük olmalı. Ayrıca kalkış anını
çevreleyen iki konum arası medyan 62 sn, yani kalkış anı en kötü durumda ±1 dk
belirsiz. Dakika altı sapmalar yorumlanmayacak.

## 6. Karar

**Fizibilite olumlu.** Ölçülebilecekler: hat başından kalkış dakikliği, planlı seferlerin
gözlenme oranı, duraklarda otobüs aralıkları ve tahmini bekleme. Ölçülemeyenler: ara
duraklarda plana göre gecikme (plan yok), İETT'nin kendi gerçekleşme verisi (servis kapalı).

**Toplama nerede çalışmalı?** Sınır saatte 100 istek (büyük olasılıkla IP başına; doğrulanmadı) ve toplama her dakika
çalışmalı; veri günde ~15–20 MB ham (sıkıştırılmış ~2–3 MB).

- *Yerel zamanlanmış görev (önerilen):* Bilgisayar açık olduğu sürece kesintisiz; kota
  bize ait. Eksi: bilgisayar kapalıyken boşluk oluşur (sitede gün/saat kapsamı gösterilir).
- *GitHub Actions:* Zamanlanmış iş en sık 5 dk'da bir ve gecikmeli tetikleniyor; dakikalık
  toplama için 6 saatlik uzun işler zincirlemek gerekir. Paylaşılan IP'lerde kotanın başka
  kullanıcılarla bölüşülmesi riski var. Ayrıca depo GitHub'a gönderilmeli (karar kullanıcının).

Kalıcı zamanlanmış görevi kurmadan önce kullanıcıya soruluyor.
