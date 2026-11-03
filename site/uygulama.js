"use strict";
(() => {
  const $ = (s) => document.querySelector(s);
  const bicim = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 });
  const sayi = (x) => (x == null ? "–" : bicim.format(x));
  const isaretli = (x) => (x == null ? "–" : (x > 0 ? "+" : x < 0 ? "−" : "") + bicim.format(Math.abs(x)));
  const css = (ad) => getComputedStyle(document.documentElement).getPropertyValue(ad).trim();
  const tarih = (g) => new Date(g + "T12:00:00").toLocaleDateString("tr-TR", { day: "numeric", month: "long" });

  let OZET = null;
  let harita = null;
  let katman = null;
  const onbellek = {};

  async function getir(yol) {
    if (!onbellek[yol]) {
      onbellek[yol] = fetch(yol).then((r) => {
        if (!r.ok) throw new Error(yol + " " + r.status);
        return r.json();
      });
    }
    return onbellek[yol];
  }

  function durumYaz(meta, yeterliVar) {
    const g = meta.gunler;
    const aralik = g.length === 1 ? tarih(g[0]) : `${tarih(g[0])} – ${tarih(g[g.length - 1])}`;
    const d = $("#durum");
    d.innerHTML = `<strong>${g.length} gün</strong> (${aralik}), toplam <strong>${sayi(meta.kapsam_saat)} saat</strong> gözlem,
      ${meta.kalkis.toLocaleString("tr-TR")} kalkış, ${meta.gecis.toLocaleString("tr-TR")} durak geçişi.` +
      (yeterliVar ? "" : " <br>Veri birikiyor: rakamlar ön sonuçtur, hatları karşılaştırmak için henüz erken.");
    d.classList.toggle("tamam", yeterliVar);
    $("#esik-kalkis").textContent = meta.esik.kalkis;
    $("#esik-gun").textContent = meta.esik.gun;
  }

  function tabloYaz(hatlar) {
    const yeterli = hatlar.filter((h) => h.yeterli);
    let sirali;
    if (yeterli.length >= 2) {
      sirali = [...yeterli].sort((a, b) => b.dakik - a.dakik || a.sapma_medyan - b.sapma_medyan)
        .concat(hatlar.filter((h) => !h.yeterli).sort((a, b) => b.kalkis - a.kalkis));
      $("#siralama-notu").textContent = "En dakikten en az dakike sıralı (yeterli verisi olan hatlar). Satıra dokunun.";
    } else {
      sirali = [...hatlar].sort((a, b) => b.kalkis - a.kalkis);
      $("#siralama-notu").textContent = "Gözlem sayısına göre sıralı; bu bir başarı sıralaması değil. Satıra dokunun.";
    }
    const tb = $("#hatlar tbody");
    tb.innerHTML = "";
    for (const h of sirali) {
      const tr = document.createElement("tr");
      tr.tabIndex = 0;
      tr.dataset.hat = h.hat;
      const az = !h.yeterli ? `<span class="az">az veri</span>` : "";
      tr.innerHTML = `
        <td><span class="hat-kod">${h.hat}</span><span class="hat-ad">${h.ad}</span></td>
        <td class="sayi">${h.kalkis}${az}</td>
        <td class="sayi">${h.sapma_medyan == null ? "–" : isaretli(h.sapma_medyan) + " dk"}</td>
        <td class="sayi">${h.dakik == null ? "–" : "%" + h.dakik}<span class="cubuk" aria-hidden="true"><i style="width:${h.dakik || 0}%"></i></span></td>
        <td class="sayi gizle-dar">${h.planli ? `${h.gozlenen} / ${h.planli}` : "–"}</td>
        <td class="sayi gizle-dar">${h.bekleme_fazla == null ? "–" : isaretli(h.bekleme_fazla) + " dk"}</td>`;
      const ac = () => hatAc(h.hat, true);
      tr.addEventListener("click", ac);
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ac(); } });
      tb.appendChild(tr);
    }
    const sec = $("#hat-sec");
    sec.innerHTML = sirali.map((h) => `<option value="${h.hat}">${h.hat} · ${h.ad}</option>`).join("");
    sec.addEventListener("change", () => hatAc(sec.value, false));
  }

  // --- grafikler (yalın SVG)
  const SAATLER = Array.from({ length: 20 }, (_, i) => i + 5);

  function sapmaGrafik(saatler) {
    const dolu = saatler.filter((s) => s.n);
    if (!dolu.length) return `<p class="bos">Bu hatta henüz planla eşleşen kalkış yok.</p>`;
    const W = 440, H = 210, sol = 30, alt = 36, ust = 10;
    const ymin = -5, ymax = 15;
    const y = (v) => ust + (ymax - Math.max(ymin, Math.min(ymax, v))) / (ymax - ymin) * (H - ust - alt);
    const bw = (W - sol - 6) / SAATLER.length;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Saat saat medyan kalkış sapması">`;
    for (const v of [-5, 0, 5, 10, 15]) {
      s += `<line class="${v === 0 ? "sifir" : "eksen"}" x1="${sol}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/>`;
      s += `<text x="${sol - 5}" y="${y(v) + 3}" text-anchor="end">${v > 0 ? "+" : ""}${v}</text>`;
    }
    SAATLER.forEach((h, i) => {
      const d = saatler.find((x) => x.saat === h);
      const cx = sol + i * bw + bw / 2;
      if (h % 3 === 0) s += `<text x="${cx}" y="${H - alt + 13}" text-anchor="middle">${String(h % 24).padStart(2, "0")}</text>`;
      if (!d || !d.n) return;
      const renk = d.medyan > 5 ? css("--kotu") : d.medyan > 2 ? css("--orta") : css("--iyi");
      const y0 = y(0), y1 = y(d.medyan);
      s += `<rect x="${cx - bw * 0.32}" y="${Math.min(y0, y1)}" width="${bw * 0.64}" height="${Math.max(1.5, Math.abs(y1 - y0))}" rx="2" fill="${renk}" opacity="${d.n < 5 ? 0.45 : 0.9}"><title>${h}:00 · medyan ${isaretli(d.medyan)} dk · ${d.n} kalkış</title></rect>`;
      if (d.n >= 3) s += `<line x1="${cx}" x2="${cx}" y1="${y(d.p25)}" y2="${y(d.p75)}" stroke="${css("--metin")}" stroke-width="1.2" opacity=".55"/>`;
      s += `<text x="${cx}" y="${H - 4}" text-anchor="middle" font-size="10">${d.n}</text>`;
    });
    s += "</svg>";
    return s;
  }

  function beklemeGrafik(saatler) {
    const dolu = saatler.filter((s) => s.bekleme != null);
    if (!dolu.length) return `<p class="bos">Bekleme için henüz yeterli durak geçişi yok.</p>`;
    const W = 440, H = 210, sol = 30, alt = 36, ust = 10;
    const ymax = Math.max(10, Math.ceil(Math.max(...dolu.map((d) => Math.max(d.bekleme, d.bekleme_plan || 0))) / 5) * 5);
    const y = (v) => ust + (ymax - Math.min(ymax, v)) / ymax * (H - ust - alt);
    const bw = (W - sol - 6) / SAATLER.length;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Saat saat tahmini bekleme">`;
    for (let v = 0; v <= ymax; v += ymax > 20 ? 10 : 5) {
      s += `<line class="eksen" x1="${sol}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/><text x="${sol - 5}" y="${y(v) + 3}" text-anchor="end">${v}</text>`;
    }
    SAATLER.forEach((h, i) => {
      const d = saatler.find((x) => x.saat === h);
      const cx = sol + i * bw + bw / 2;
      if (h % 3 === 0) s += `<text x="${cx}" y="${H - alt + 13}" text-anchor="middle">${String(h % 24).padStart(2, "0")}</text>`;
      if (!d || d.bekleme == null) return;
      s += `<rect x="${cx - bw * 0.32}" y="${y(d.bekleme)}" width="${bw * 0.64}" height="${y(0) - y(d.bekleme)}" rx="2" fill="${css("--vurgu")}" opacity=".8"><title>${h}:00 · gözlenen ${sayi(d.bekleme)} dk${d.bekleme_plan != null ? " · plana göre " + sayi(d.bekleme_plan) + " dk" : ""}</title></rect>`;
      if (d.bekleme_plan != null) s += `<line x1="${cx - bw * 0.45}" x2="${cx + bw * 0.45}" y1="${y(d.bekleme_plan)}" y2="${y(d.bekleme_plan)}" stroke="${css("--plan")}" stroke-width="2.5"/>`;
    });
    s += "</svg>";
    return s;
  }

  function kartlar(d) {
    const k = (b, s) => `<div class="kart"><b>${b}</b><span>${s}</span></div>`;
    return [
      k(d.sapma_medyan == null ? "–" : isaretli(d.sapma_medyan) + " dk", "medyan kalkış sapması"),
      k(d.dakik == null ? "–" : "%" + d.dakik, "dakik kalkış (−1…+5 dk)"),
      k(d.gec5 == null ? "–" : "%" + d.gec5, "5 dk'dan geç kalkış"),
      k(d.planli ? `${d.gozlenen}/${d.planli}` : "–", "planlı kalkıştan gözlenen"),
      k(`${d.kalkis}`, `kalkış · ${d.gun} gün`),
    ].join("");
  }

  // --- harita
  function renkBekleme(b) {
    if (b == null) return css("--soluk");
    return b <= 5 ? css("--iyi") : b <= 10 ? css("--orta") : css("--kotu");
  }

  function haritaCiz(d) {
    if (!window.L) { $("#harita").innerHTML = `<p class="bos">Harita yüklenemedi.</p>`; return; }
    if (!harita) {
      harita = L.map("harita", { scrollWheelZoom: false, attributionControl: true });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18, attribution: "© OpenStreetMap",
      }).addTo(harita);
    }
    if (katman) katman.remove();
    katman = L.layerGroup().addTo(harita);
    const renkler = [css("--plan"), css("--vurgu")];
    const sinir = [];
    Object.entries(d.cizgiler).forEach(([kod, c], i) => {
      const ll = c.map(([b, e]) => [e, b]);
      sinir.push(...ll);
      L.polyline(ll, { color: renkler[i % 2], weight: 3, opacity: 0.55 }).bindTooltip(d.yonler[kod] || kod).addTo(katman);
    });
    for (const s of d.duraklar) {
      const m = L.circleMarker([s.e, s.b], {
        radius: s.bekleme == null ? 3 : 5, color: renkBekleme(s.bekleme), weight: 1.5,
        fillColor: renkBekleme(s.bekleme), fillOpacity: s.bekleme == null ? 0.3 : 0.85,
      });
      const satir = s.bekleme == null
        ? "Bekleme için henüz yeterli geçiş yok."
        : `Tahmini bekleme: <b>${sayi(s.bekleme)} dk</b>` + (s.planli != null ? `<br>Plana göre: ${sayi(s.planli)} dk` : "") + `<br><span style="opacity:.7">${s.n} otobüs aralığı</span>`;
      m.bindPopup(`<b>${s.ad}</b><br>${satir}`).addTo(katman);
    }
    // bölüm az önce görünür oldu: önce boyutu tazele, sonra sığdır
    requestAnimationFrame(() => {
      harita.invalidateSize();
      if (sinir.length) harita.fitBounds(sinir, { padding: [16, 16] });
    });
    $("#lejant").innerHTML =
      Object.keys(d.cizgiler).map((k, i) => `<span><i style="background:${renkler[i % 2]};border-radius:2px"></i>${d.yonler[k]}</span>`).join("") +
      `<span><i style="background:${css("--iyi")}"></i>≤5 dk</span><span><i style="background:${css("--orta")}"></i>5–10 dk</span><span><i style="background:${css("--kotu")}"></i>&gt;10 dk</span>`;
  }

  async function hatAc(hat, kaydir) {
    const d = await getir(`veri/hat/${encodeURIComponent(hat)}.json`);
    $("#detay").hidden = false;
    $("#d-hat").textContent = d.hat;
    $("#d-ad").textContent = d.ad;
    $("#hat-sec").value = d.hat;
    $("#d-kartlar").innerHTML = kartlar(d);
    $("#g-sapma").innerHTML = sapmaGrafik(d.saatler);
    $("#g-bekleme").innerHTML = beklemeGrafik(d.saatler);
    document.querySelectorAll("#hatlar tbody tr").forEach((tr) => tr.classList.toggle("secili", tr.dataset.hat === hat));
    haritaCiz(d);
    try { history.replaceState(null, "", "#" + encodeURIComponent(hat)); } catch (e) { /* önizlemede olmayabilir */ }
    if (kaydir) $("#detay").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function basla() {
    try {
      OZET = await getir("veri/ozet.json");
    } catch (e) {
      $("#durum").textContent = "Veri yüklenemedi.";
      return;
    }
    const yeterliVar = OZET.hatlar.filter((h) => h.yeterli).length >= 2;
    durumYaz(OZET.meta, yeterliVar);
    tabloYaz(OZET.hatlar);
    const istenen = decodeURIComponent(location.hash.slice(1));
    const ilk = OZET.hatlar.find((h) => h.hat === istenen) || [...OZET.hatlar].sort((a, b) => b.kalkis - a.kalkis)[0];
    if (ilk) hatAc(ilk.hat, false);
    window.addEventListener("hashchange", () => {
      const h = decodeURIComponent(location.hash.slice(1));
      if (OZET.hatlar.some((x) => x.hat === h) && h !== $("#d-hat").textContent) hatAc(h, true);
    });
  }
  basla();
})();
