"""Basit düzlem geometri: İstanbul ölçeğinde eşdikdörtgen izdüşüm yeterli
(80 km boyunca ölçek hatası binde birin altında)."""
import bisect
import math

ENLEM0 = 41.0
M_ENLEM = 111_320.0
M_BOYLAM = 111_320.0 * math.cos(math.radians(ENLEM0))


def xy(enlem, boylam):
    return boylam * M_BOYLAM, enlem * M_ENLEM


def mesafe(e1, b1, e2, b2):
    x1, y1 = xy(e1, b1)
    x2, y2 = xy(e2, b2)
    return math.hypot(x2 - x1, y2 - y1)


class Cizgi:
    """Güzergâh çizgisi; bir noktayı çizgiye izdüşürüp baştan uzaklığını (m) verir."""

    def __init__(self, koordinatlar):  # [[boylam, enlem], ...]
        self.p = [xy(e, b) for b, e in koordinatlar]
        self.s = [0.0]
        for (x1, y1), (x2, y2) in zip(self.p, self.p[1:]):
            self.s.append(self.s[-1] + math.hypot(x2 - x1, y2 - y1))
        self.uzunluk = self.s[-1]
        # kaba ızgara: yakın parçaları hızlı bulmak için
        self.izgara = {}
        for i in range(len(self.p) - 1):
            for k in self._hucreler(i):
                self.izgara.setdefault(k, []).append(i)

    def _hucreler(self, i, h=500.0):
        (x1, y1), (x2, y2) = self.p[i], self.p[i + 1]
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) // h) + 1)
        g = set()
        for j in range(n + 1):
            t = j / n
            g.add((int((x1 + t * (x2 - x1)) // h), int((y1 + t * (y2 - y1)) // h)))
        return g

    def izdusur(self, enlem, boylam, adaylar=None):
        """(baştan uzaklık m, çizgiye dik uzaklık m). Çizgiden >1 km uzaksa (None, d)."""
        x, y = xy(enlem, boylam)
        hx, hy = int(x // 500), int(y // 500)
        parcalar = set()
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                parcalar.update(self.izgara.get((hx + dx, hy + dy), ()))
        if adaylar is not None:
            parcalar &= adaylar
        en_iyi = (None, float("inf"))
        for i in parcalar:
            (x1, y1), (x2, y2) = self.p[i], self.p[i + 1]
            vx, vy = x2 - x1, y2 - y1
            L2 = vx * vx + vy * vy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / L2))
            px, py = x1 + t * vx, y1 + t * vy
            d = math.hypot(x - px, y - py)
            if d < en_iyi[1]:
                en_iyi = (self.s[i] + t * math.sqrt(L2), d)
        return en_iyi

    def adaylar(self, enlem, boylam, esik=150.0):
        """Çizgiye esik metreden yakın tüm izdüşümler [(s, d)], s'ye göre sıralı.
        Gidiş-dönüşü aynı yoldan yapan güzergâhlarda birden çok aday çıkar."""
        x, y = xy(enlem, boylam)
        hx, hy = int(x // 500), int(y // 500)
        parcalar = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                parcalar.update(self.izgara.get((hx + dx, hy + dy), ()))
        sonuc = []
        onceki_i = None
        for i in sorted(parcalar):
            (x1, y1), (x2, y2) = self.p[i], self.p[i + 1]
            vx, vy = x2 - x1, y2 - y1
            L2 = vx * vx + vy * vy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / L2))
            d = math.hypot(x - (x1 + t * vx), y - (y1 + t * vy))
            if d > esik:
                continue
            s = self.s[i] + t * math.sqrt(L2)
            # ardışık parçalar aynı geçiştir: her ardışık grupta yalnız en yakın izdüşüm kalsın
            if sonuc and onceki_i == i - 1:
                if d < sonuc[-1][1]:
                    sonuc[-1] = (s, d)
            else:
                sonuc.append((s, d))
            onceki_i = i
        return sonuc

    def nokta(self, s):
        """Baştan s metredeki nokta (x, y)."""
        i = max(0, min(len(self.s) - 2, bisect.bisect_right(self.s, s) - 1))
        L = self.s[i + 1] - self.s[i]
        t = 0 if L == 0 else (s - self.s[i]) / L
        (x1, y1), (x2, y2) = self.p[i], self.p[i + 1]
        return x1 + t * (x2 - x1), y1 + t * (y2 - y1)
