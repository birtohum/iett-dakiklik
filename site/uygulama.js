"use strict";
(() => {
  const $ = (s) => document.querySelector(s);
  const bicim = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 });
  const sayi = (x) => (x == null ? "–" : bicim.format(x));
  const isaretli = (x) => (x == null ? "–" : (x > 0 ? "+" : x < 0 ? "−" : "") + bicim.format(Math.abs(x)));
  const css = (ad) => getComputedStyle(document.documentElement).getPropertyValue(ad).trim();
  const tarih = (g) => new Date(g + "T12:00:00").toLocaleDateString("tr-TR", { day: "numeric", month: "long" });

  // metro haritası gibi: her hatta sabit bir renk
  const RENKLER = ["#e8452c", "#2f8fdc", "#1fa36b", "#9b59d0", "#e08a00", "#d6337f", "#00a3a3", "#7a8b1f", "#c1502e", "#4f6bd6", "#b0428f", "#2a9d8f"];
  const renk = {};

  let OZET = null, harita = null, katman = null, secili = null;
  const onbellek = {};
  const getir = (yol) => (onbellek[yol] ||= fetch(yol).then((r) => { if (!r.ok) throw new Error(yol); return r.json(); }));

  // "sabah 8'de", "öğlen 13'te"
  function saatAdi(h) {
    const k = h % 24;
    const dilim = k < 5 ? "gece" : k < 11 ? "sabah" : k < 16 ? "öğlen" : k < 19 ? "akşamüstü" : "akşam";
    const ek = k === 10 ? "da" : k === 20 ? "de" : ["da", "de", "de", "te", "te", "te", "da", "de", "de", "da"][k % 10];
    return `${dilim} ${k}'${ek}`;
  }

  function kapsamMetni(meta) {
    const g = meta.gunler;
    const aralik = g.length === 1 ? tarih(g[0]) : `${tarih(g[0])}–${tarih(g[g.length - 1])}`;
    return `${g.length} gün (${aralik}) · ${sayi(meta.kapsam_saat)} saat gözlem`;
  }

  // ---------- PANO
  function panoYaz(d) {
    $("#t-hat").textContent = d.hat;
    $("#t-hat").style.background = renk[d.hat];
    $("#t-yon").textContent = d.ad;
    const ls = $("#t-sayi");
    // öne çıkan: en çok kalkışı olan saat (≥3), yoksa tüm gün
    const saat = d.saatler.filter((s) => s.n >= 3).sort((a, b) => b.n - a.n)[0];
    const m = saat ? saat.medyan : d.sapma_medyan;
    if (m == null) {
      ls.innerHTML = `<span class="led-sayi">--</span>`;
      $("#t-cumle").textContent = `${d.hat} için henüz eşleşen kalkış yok.`;
    } else {
      const mutlak = Math.abs(m) < 0.05 ? "0" : bicim.format(Math.abs(m));
      ls.innerHTML = `<span class="led-sayi">${mutlak}</span><span class="led-birim">dk</span>`;
      ls.classList.toggle("iyi", m <= 1);
      const ne = m >= 0.5 ? `${mutlak} dk geç kalkıyor` : m <= -0.5 ? `${mutlak} dk erken kalkıyor` : "neredeyse tam zamanında kalkıyor";
      $("#t-cumle").textContent = `${d.hat} ${saat ? saatAdi(saat.saat) + " " : ""}hat başından genelde ${ne}.`;
    }
    $("#t-alt").textContent = `Medyan, planlanan kalkışa göre · ${saat ? saat.n + " kalkış o saatte, " : ""}${d.kalkis} kalkış toplam · ${kapsamMetni(OZET.meta)}` +
      (d.yeterli ? "" : " · ön sonuç, veri toplanıyor");
  }

  // ---------- LİG
  function ligYaz() {
    const hatlar = OZET.hatlar.filter((h) => h.kalkis > 0);
    const yeterli = hatlar.filter((h) => h.yeterli);
    const lig = yeterli.length >= 2;
    const sirali = lig
      ? [...yeterli].sort((a, b) => b.dakik - a.dakik || a.sapma_medyan - b.sapma_medyan)
      : [...hatlar].sort((a, b) => b.kalkis - a.kalkis);
    $("#lig-giris").innerHTML = lig
      ? "Planlanan saatin 1 dk öncesi ile 5 dk sonrası arasında kalkan seferlerin payı. En dakikten aşağı."
      : `<strong>Lig henüz yok.</strong> Bir hattı diğerinin önüne koymak için her hatta en az ${OZET.meta.esik.kalkis} kalkış ve ${OZET.meta.esik.gun} gün gerekiyor; şu an ${kapsamMetni(OZET.meta)}. Aşağıdaki sıra yalnızca gözlem sayısına göre.`;
    const ol = $("#lig");
    ol.innerHTML = "";
    sirali.forEach((h, i) => {
      const li = document.createElement("li");
      li.tabIndex = 0;
      li.dataset.hat = h.hat;
      li.innerHTML = `
        <span class="sira">${lig ? String(i + 1).padStart(2, "0") : "··"}</span>
        <span class="rozet" style="background:${renk[h.hat]}">${h.hat}</span>
        <span class="ad"><b>${h.ad}</b><small>${h.kalkis} kalkış · medyan ${isaretli(h.sapma_medyan)} dk${h.yeterli ? "" : '<span class="etiket">az veri</span>'}</small></span>
        <span class="deger"><small class="yuzde">%</small>${h.dakik ?? "–"}<small>dakik</small></span>`;
      const ac = () => { hatSec(h.hat); $("#ust").scrollIntoView({ behavior: "smooth" }); };
      li.addEventListener("click", ac);
      li.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ac(); } });
      ol.appendChild(li);
    });
  }

  // ---------- GRAFİKLER
  const SAATLER = Array.from({ length: 20 }, (_, i) => i + 5);

  function saatGrafik(d) {
    const nok = SAATLER.map((h) => d.saatler.find((q) => q.saat === h)).filter((q) => q && q.n);
    if (!nok.length) return `<p class="bos">Bu hatta henüz eşleşen kalkış yok.</p>`;
    const W = 900, H = 300, sol = 44, sag = 12, ust = 16, alt = 44;
    const ymin = -5, ymax = Math.max(10, Math.ceil(Math.max(...nok.map((s) => s.p75 ?? s.medyan)) / 5) * 5);
    const x = (h) => sol + (h - 5) / 19 * (W - sol - sag);
    const y = (v) => ust + (ymax - Math.max(ymin, Math.min(ymax, v))) / (ymax - ymin) * (H - ust - alt);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${d.hat} için saat saat medyan kalkış sapması">`;
    for (let v = ymin; v <= ymax; v += 5) {
      s += `<line class="${v === 0 ? "sifir" : "eksen"}" x1="${sol}" x2="${W - sag}" y1="${y(v)}" y2="${y(v)}"/>`;
      s += `<text x="${sol - 8}" y="${y(v) + 4}" text-anchor="end">${v > 0 ? "+" : ""}${v}</text>`;
    }
    for (const h of SAATLER) if (h % 3 === 0) s += `<text x="${x(h)}" y="${H - 22}" text-anchor="middle">${String(h % 24).padStart(2, "0")}:00</text>`;
    // çeyrekler arası bant; çizgi yalnız ardışık saatleri birleştirir
    for (const q of nok) if (q.n >= 3) s += `<line x1="${x(q.saat)}" x2="${x(q.saat)}" y1="${y(q.p25)}" y2="${y(q.p75)}" stroke="${renk[d.hat]}" stroke-width="10" stroke-linecap="round" opacity=".35"/>`;
    let yol = "";
    nok.forEach((q, i) => { yol += (i && q.saat - nok[i - 1].saat === 1 ? "L" : "M") + x(q.saat) + " " + y(q.medyan); });
    s += `<path d="${yol}" fill="none" stroke="${css("--led")}" stroke-width="3"/>`;
    for (const q of nok) {
      s += `<circle cx="${x(q.saat)}" cy="${y(q.medyan)}" r="${q.n < 5 ? 4 : 6}" fill="${q.n < 5 ? css("--zemin") : css("--led")}" stroke="${css("--led")}" stroke-width="2.5"><title>${String(q.saat).padStart(2, "0")}:00 · medyan ${isaretli(q.medyan)} dk · ${q.n} kalkış</title></circle>`;
      s += `<text x="${x(q.saat)}" y="${H - 4}" text-anchor="middle" font-size="11">${q.n}</text>`;
    }
    return s + "</svg>";
  }

  function bekleGrafik(d) {
    const dolu = d.saatler.filter((s) => s.bekleme != null);
    if (!dolu.length) return `<p class="bos">Bekleme için henüz yeterli durak geçişi yok.</p>`;
    const W = 900, H = 260, sol = 44, sag = 12, ust = 22, alt = 34;
    const ymax = Math.max(10, Math.ceil(Math.max(...dolu.map((q) => Math.max(q.bekleme, q.bekleme_plan || 0))) / 5) * 5);
    const bw = (W - sol - sag) / SAATLER.length;
    const x = (h) => sol + (h - 5) * bw + bw / 2;
    const y = (v) => ust + (ymax - Math.min(ymax, v)) / ymax * (H - ust - alt);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${d.hat} için saat saat tahmini bekleme">`;
    for (let v = 0; v <= ymax; v += 5) s += `<line class="eksen" x1="${sol}" x2="${W - sag}" y1="${y(v)}" y2="${y(v)}"/><text x="${sol - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
    for (const h of SAATLER) if (h % 3 === 0) s += `<text x="${x(h)}" y="${H - 8}" text-anchor="middle">${String(h % 24).padStart(2, "0")}:00</text>`;
    for (const q of dolu) {
      s += `<rect x="${x(q.saat) - bw * .34}" y="${y(q.bekleme)}" width="${bw * .68}" height="${y(0) - y(q.bekleme)}" rx="3" fill="${renk[d.hat]}"><title>${q.saat}:00 · gözlenen ${sayi(q.bekleme)} dk${q.bekleme_plan != null ? " · plana göre " + sayi(q.bekleme_plan) + " dk" : ""}</title></rect>`;
      s += `<text x="${x(q.saat)}" y="${y(Math.max(q.bekleme, q.bekleme_plan || 0)) - 8}" text-anchor="middle" fill="${css("--metin")}" font-size="12">${sayi(q.bekleme)}</text>`;
      if (q.bekleme_plan != null) s += `<line x1="${x(q.saat) - bw * .5}" x2="${x(q.saat) + bw * .5}" y1="${y(q.bekleme_plan)}" y2="${y(q.bekleme_plan)}" stroke="${css("--led")}" stroke-width="3"/>`;
    }
    return s + "</svg>";
  }

  function seferYaz(d) {
    const top = OZET.hatlar.reduce((a, h) => [a[0] + h.gozlenen, a[1] + h.planli], [0, 0]);
    const k = (b, t) => `<div><b>${b}</b><span>${t}</span></div>`;
    const yuzde = (x) => `<small class="yuzde">%</small>${x}`;
    $("#sefer-sayilar").innerHTML =
      k(d.planli ? yuzde(Math.round(100 * d.gozlenen / d.planli)) : "–", `${d.hat}: ${d.gozlenen} / ${d.planli} planlı kalkışı gördük`) +
      k(top[1] ? yuzde(Math.round(100 * top[0] / top[1])) : "–", `izlenen 10 hat: ${top[0]} / ${top[1]}`) +
      k(d.gec5 == null ? "–" : yuzde(d.gec5), `${d.hat}: 5 dakikadan geç kalkan seferler`);
  }

  // ---------- HARİTA
  const bekleRenk = (b) => (b == null ? "#55534c" : b <= 5 ? css("--iyi") : b <= 10 ? css("--orta") : css("--kotu"));
  function haritaCiz(d) {
    if (!window.L) { $("#harita").innerHTML = `<p class="bos">Harita yüklenemedi.</p>`; return; }
    if (!harita) {
      harita = L.map("harita", { scrollWheelZoom: false });
      // OSM karoları; koyu görünüm CSS filtresiyle (stil.css: .koyu-karo)
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: "© OpenStreetMap", className: "koyu-karo",
      }).addTo(harita);
    }
    if (katman) katman.remove();
    katman = L.layerGroup().addTo(harita);
    const sinir = [];
    Object.entries(d.cizgiler).forEach(([kod, c], i) => {
      const ll = c.map(([b, e]) => [e, b]);
      sinir.push(...ll);
      L.polyline(ll, { color: renk[d.hat], weight: i ? 4 : 8, opacity: i ? 0.95 : 0.4 }).bindTooltip(d.yonler[kod] || kod).addTo(katman);
    });
    for (const s of d.duraklar) {
      L.circleMarker([s.e, s.b], {
        radius: s.bekleme == null ? 3 : 5.5, color: "#000", weight: 1.5,
        fillColor: bekleRenk(s.bekleme), fillOpacity: s.bekleme == null ? 0.6 : 1,
      }).bindPopup(`<b>${s.ad}</b><br>` + (s.bekleme == null ? "Bekleme için henüz yeterli geçiş yok."
        : `Tahmini bekleme: <b>${sayi(s.bekleme)} dk</b>` + (s.planli != null ? `<br>Plana göre: ${sayi(s.planli)} dk` : "") + `<br><span style="opacity:.7">${s.n} otobüs aralığı</span>`)).addTo(katman);
    }
    requestAnimationFrame(() => { harita.invalidateSize(); if (sinir.length) harita.fitBounds(sinir, { padding: [18, 18] }); });
    $("#lejant").innerHTML = `<span><i style="background:${css("--iyi")}"></i>≤5 dk</span><span><i style="background:${css("--orta")}"></i>5–10 dk</span><span><i style="background:${css("--kotu")}"></i>&gt;10 dk</span><span><i style="background:#55534c"></i>yetersiz veri</span>` +
      Object.keys(d.cizgiler).map((k, i) => `<span>${i ? "ince" : "kalın"} çizgi: ${d.yonler[k]}</span>`).join("");
  }

  // ---------- PAYLAŞIM KARTI (1200×630 tabela görüntüsü)
  async function kartCiz(d) {
    try { await Promise.all([document.fonts.load('900 200px "Doto"'), document.fonts.load('800 60px "Barlow Condensed"')]); } catch (e) { /* yedek yazı tipiyle çizer */ }
    const c = $("#kart"), g = c.getContext("2d");
    const W = c.width, H = c.height;
    g.fillStyle = "#0b0b0a"; g.fillRect(0, 0, W, H);
    g.fillStyle = "rgba(255,176,0,0.06)";
    for (let x = 6; x < W; x += 12) for (let y = 6; y < H; y += 12) { g.beginPath(); g.arc(x, y, 1.6, 0, 6.3); g.fill(); }
    g.strokeStyle = "#2a2925"; g.lineWidth = 4; g.strokeRect(24, 24, W - 48, H - 48);
    g.font = '800 64px "Barlow Condensed", sans-serif';
    const rw = g.measureText(d.hat).width + 36;
    g.fillStyle = renk[d.hat]; yuvarlak(g, 64, 64, rw, 84, 10); g.fill();
    g.fillStyle = "#fff"; g.textBaseline = "middle"; g.fillText(d.hat, 82, 108);
    g.font = '600 30px "Barlow Condensed", sans-serif'; g.fillStyle = "#9a968b";
    g.fillText(kisalt(g, d.ad.toUpperCase(), W - 64 - rw - 100), 64 + rw + 22, 108);
    const sayiMetni = $("#t-sayi .led-sayi")?.textContent || "--";
    const iyi = $("#t-sayi").classList.contains("iyi");
    g.font = '900 230px "Doto", monospace';
    g.fillStyle = iyi ? "#4fd18b" : "#ffb000"; g.shadowColor = iyi ? "rgba(79,209,139,.5)" : "rgba(255,176,0,0.6)"; g.shadowBlur = 30;
    g.textBaseline = "alphabetic"; g.fillText(sayiMetni, 58, 400);
    const sw = g.measureText(sayiMetni).width;
    g.font = '900 80px "Doto", monospace'; g.fillText("dk", 58 + sw + 18, 400);
    g.shadowBlur = 0;
    g.font = '700 42px "Barlow Condensed", sans-serif'; g.fillStyle = "#efece4";
    satirlar(g, $("#t-cumle").textContent, W - 128).slice(0, 2).forEach((s, i) => g.fillText(s, 64, 470 + i * 48));
    g.font = '500 22px "Barlow", sans-serif'; g.fillStyle = "#9a968b";
    g.fillText(`İBB açık verisinden ölçüm · ${kapsamMetni(OZET.meta)}${d.yeterli ? "" : " · ön sonuç"}`, 64, H - 60);
  }
  function yuvarlak(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function kisalt(g, t, w) { if (g.measureText(t).width <= w) return t; while (t.length && g.measureText(t + "…").width > w) t = t.slice(0, -1); return t + "…"; }
  function satirlar(g, t, w) { const out = []; let s = ""; for (const k of t.split(" ")) { const d = s ? s + " " + k : k; if (g.measureText(d).width > w && s) { out.push(s); s = k; } else s = d; } if (s) out.push(s); return out; }

  const kartBlob = () => new Promise((r) => $("#kart").toBlob(r, "image/png"));
  async function indir() {
    const url = URL.createObjectURL(await kartBlob());
    const a = Object.assign(document.createElement("a"), { href: url, download: `otobus-${secili}.png` });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
  async function paylas() {
    const dosya = new File([await kartBlob()], `otobus-${secili}.png`, { type: "image/png" });
    if (navigator.canShare && navigator.canShare({ files: [dosya] })) {
      try { await navigator.share({ files: [dosya], text: $("#t-cumle").textContent }); return; } catch (e) { if (e.name === "AbortError") return; }
    }
    indir();
  }

  // ---------- SEÇİM
  async function hatSec(hat) {
    const aranan = String(hat).trim().toLocaleUpperCase("tr");
    const h = OZET.hatlar.find((x) => x.hat.toLocaleUpperCase("tr") === aranan);
    if (!h) {
      $("#t-hat").textContent = aranan || "?";
      $("#t-hat").style.background = "#555";
      $("#t-yon").textContent = "";
      $("#t-sayi").className = "led-buyuk";
      $("#t-sayi").innerHTML = `<span class="led-sayi">--</span>`;
      $("#t-cumle").textContent = `"${hat}" izlediğimiz hatlar arasında yok. Şimdilik: ${OZET.hatlar.map((x) => x.hat).join(", ")}.`;
      $("#t-alt").textContent = "Konum servisi saatte 100 istekle sınırlı olduğu için şimdilik 10 hat izleniyor.";
      return;
    }
    secili = h.hat;
    const d = await getir(`veri/hat/${encodeURIComponent(h.hat)}.json`);
    $("#hat-girdi").value = h.hat;
    document.querySelectorAll(".cip").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.hat === h.hat)));
    document.querySelectorAll(".lig li").forEach((li) => li.classList.toggle("secili", li.dataset.hat === h.hat));
    document.querySelectorAll("[data-hat-yazi]").forEach((e) => (e.textContent = h.hat));
    panoYaz(d);
    $("#g-saat").innerHTML = saatGrafik(d);
    $("#g-bekle").innerHTML = bekleGrafik(d);
    seferYaz(d);
    haritaCiz(d);
    kartCiz(d);
    try { history.replaceState(null, "", "#" + encodeURIComponent(h.hat)); } catch (e) { /* önizlemede olmayabilir */ }
  }

  async function basla() {
    try { OZET = await getir("veri/ozet.json"); } catch (e) { $("#t-cumle").textContent = "Veri yüklenemedi."; return; }
    OZET.hatlar.forEach((h, i) => (renk[h.hat] = RENKLER[i % RENKLER.length]));
    const m = OZET.meta;
    const yeterli = OZET.hatlar.filter((h) => h.yeterli).length >= 2;
    $("#durum-led").textContent = yeterli ? `${m.gunler.length} GÜN VERİ` : `VERİ TOPLANIYOR · ${m.gunler.length} GÜN`;
    $("#durum-led").classList.toggle("yanip", !yeterli);
    $("#esik-kalkis").textContent = m.esik.kalkis;
    $("#esik-gun").textContent = m.esik.gun;
    $("#hat-listesi").innerHTML = OZET.hatlar.map((h) => `<option value="${h.hat}">${h.ad}</option>`).join("");
    $("#cipler").innerHTML = OZET.hatlar.map((h) => `<button type="button" class="cip" data-hat="${h.hat}" aria-pressed="false" style="background:${renk[h.hat]}">${h.hat}</button>`).join("");
    document.querySelectorAll(".cip").forEach((b) => b.addEventListener("click", () => hatSec(b.dataset.hat)));
    $("#hat-form").addEventListener("submit", (e) => { e.preventDefault(); hatSec($("#hat-girdi").value); });
    $("#paylas").addEventListener("click", paylas);
    $("#indir").addEventListener("click", indir);
    ligYaz();
    const istenen = decodeURIComponent(location.hash.slice(1));
    const ilk = OZET.hatlar.find((h) => h.hat === istenen) || [...OZET.hatlar].sort((a, b) => b.kalkis - a.kalkis)[0];
    if (ilk) hatSec(ilk.hat);
    window.addEventListener("hashchange", () => { const h = decodeURIComponent(location.hash.slice(1)); if (h && h !== secili) hatSec(h); });
  }
  basla();
})();
