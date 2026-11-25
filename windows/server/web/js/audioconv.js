"use strict";
// Áudio da mesa de som (soundboard.py): o PC toca WAV 16 bits mono 48 kHz de até SB_MAX segundos.
// Aqui o navegador abre qualquer formato que ele conhece, deixa escolher o trecho (sbTrim) e gera o WAV.
// Usado pelo app (sons.js) e pelo editor no PC (editor.js).
const SB_MAX = 20, SB_RATE = 48000, SB_LONG = 600;

// arquivo (File/Blob) ou ArrayBuffer -> Float32Array mono 48 kHz
async function sbDecode(src) {
  const buf = src instanceof ArrayBuffer ? src : await src.arrayBuffer();
  const AC = window.AudioContext || window.webkitAudioContext, ac = new AC();
  let audio;
  try { audio = await ac.decodeAudioData(buf); } finally { ac.close?.(); }
  if (audio.duration > SB_LONG) throw new Error(`áudio longo demais (máximo ${SB_LONG / 60} min)`);
  const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(audio.duration * SB_RATE)), SB_RATE);
  const s = off.createBufferSource(); s.buffer = audio; s.connect(off.destination); s.start();
  const x = (await off.startRendering()).getChannelData(0);
  let peak = 0; for (let i = 0; i < x.length; i++) peak = Math.max(peak, Math.abs(x[i]));
  if (peak < 1e-4) throw new Error("o áudio está mudo");
  return x;
}
const sbPeak = (x, a = 0, b = x.length) => { let p = 0; for (let i = a; i < b; i++) p = Math.max(p, Math.abs(x[i])); return p; };
// trecho sem o silêncio das pontas (com um respiro curto), em amostras; no máximo SB_MAX segundos
function sbAuto(x, cap = true) {
  const thr = Math.max(sbPeak(x) * 0.02, 0.002);
  let a = 0, b = x.length - 1;
  while (a < b && Math.abs(x[a]) < thr) a++;
  while (b > a && Math.abs(x[b]) < thr) b--;
  a = Math.max(0, a - SB_RATE * 0.01); b = Math.min(x.length, b + SB_RATE * 0.05);
  return [a, cap ? Math.min(b, a + SB_MAX * SB_RATE) : b];
}
// ganho para o volume ficar parecido entre os sons: -18 dB de média sem passar de -0,5 dB de pico
function sbGain(x, a, b) {
  const peak = sbPeak(x, a, b), thr = Math.max(peak * 0.02, 0.002); let sum = 0, cnt = 0;
  for (let i = a; i < b; i++) { const v = Math.abs(x[i]); if (v > thr) { sum += v * v; cnt++; } }
  if (peak < 1e-6) return 1;
  return Math.min(0.944 / peak, 0.126 / Math.max(Math.sqrt(sum / Math.max(cnt, 1)), 1e-6));
}
// trecho [a, b) em amostras -> WAV; norm = igualar volume, fade = suavizar as pontas (evita estalo)
function sbEncode(x, a, b, { norm = true, fade = true } = {}) {
  a = Math.max(0, Math.floor(a)); b = Math.min(x.length, Math.floor(b), a + SB_MAX * SB_RATE);
  const n = b - a, g = norm ? sbGain(x, a, b) : 1, fi = fade ? Math.min(n / 4, SB_RATE * 0.008) : 0, fo = fade ? Math.min(n / 4, SB_RATE * 0.03) : 0;
  const out = new DataView(new ArrayBuffer(44 + n * 2)), str = (o, s) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF"); out.setUint32(4, 36 + n * 2, true); str(8, "WAVEfmt "); out.setUint32(16, 16, true);
  out.setUint16(20, 1, true); out.setUint16(22, 1, true); out.setUint32(24, SB_RATE, true); out.setUint32(28, SB_RATE * 2, true);
  out.setUint16(32, 2, true); out.setUint16(34, 16, true); str(36, "data"); out.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    let v = x[a + i] * g;
    if (i < fi) v *= i / fi; else if (n - 1 - i < fo) v *= (n - 1 - i) / fo;
    out.setInt16(44 + i * 2, Math.max(-1, Math.min(1, v)) * 32767, true);
  }
  return { wav: out.buffer, secs: n / SB_RATE };
}
// sem escolher trecho (vários arquivos de uma vez): corta o silêncio e iguala o volume
async function sbConvert(file) {
  const x = await sbDecode(file), [a, b] = sbAuto(x, false);
  return { ...sbEncode(x, a, b), cut: b - a > SB_MAX * SB_RATE };
}
function sbB64(buf) {
  const u = new Uint8Array(buf); let x = "";
  for (let i = 0; i < u.length; i += 0x8000) x += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
  return btoa(x);
}
function sbUnB64(s) { const t = atob(s), u = new Uint8Array(t.length); for (let i = 0; i < t.length; i++) u[i] = t.charCodeAt(i); return u.buffer; }
const sbName = (f) => f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 40) || "Som";

// ---------------------------------------------------------------- cortador (janela com a onda)
// Resolve com { wav, secs } ou null (cancelado). whole = começa com tudo selecionado (som já cortado antes).
function sbTrim(x, title, whole = false) {
  sbTrimStyle();
  return new Promise((done) => {
    const R = SB_RATE, dur = x.length / R, MIN = 0.05;
    let [a, b] = (whole ? [0, Math.min(x.length, SB_MAX * R)] : sbAuto(x)).map((i) => i / R), v0 = 0, v1 = dur;
    const ov = document.createElement("div"); ov.className = "sbt-ov";
    ov.innerHTML = `<div class="sbt" role="dialog" aria-label="Cortar áudio">
      <div class="sbt-h"><b>Cortar áudio</b><span class="sbt-name"></span><span class="sbt-total"></span></div>
      <canvas class="sbt-wave" aria-label="Onda do áudio"></canvas>
      <div class="sbt-row"><button type="button" class="btn sm" data-k="zout" aria-label="Afastar">−</button><button type="button" class="btn sm" data-k="zin" aria-label="Aproximar">+</button>
        <button type="button" class="btn sm" data-k="zsel">Ver a seleção</button><button type="button" class="btn sm" data-k="zall">Ver tudo</button>
        <span class="sbt-sp"></span><button type="button" class="btn sm" data-k="auto">Cortar silêncio</button></div>
      <div class="sbt-row"><label>Início <input type="text" inputmode="decimal" class="fi sbt-a" autocomplete="off"></label><label>Fim <input type="text" inputmode="decimal" class="fi sbt-b" autocomplete="off"></label>
        <span class="sbt-len"></span><span class="sbt-sp"></span><button type="button" class="btn sbt-play" data-k="play">Ouvir</button></div>
      <div class="sbt-row"><label class="chk"><input type="checkbox" class="sbt-norm" checked> Igualar volume</label><label class="chk"><input type="checkbox" class="sbt-fade" checked> Suavizar as pontas</label></div>
      <div class="sbt-hint">Arraste as bordas da seleção ou arraste na onda para marcar outro trecho. Um toque toca dali em diante. Zoom: roda do mouse ou os botões − e +. Máximo ${SB_MAX} s.</div>
      <div class="sbt-acts"><button type="button" class="btn" data-k="no">Cancelar</button><button type="button" class="btn primary pri" data-k="ok">Salvar este trecho</button></div></div>`;
    document.body.appendChild(ov);
    const q = (c) => ov.querySelector(c), cv = q(".sbt-wave"), g2 = cv.getContext("2d");
    q(".sbt-name").textContent = title || ""; q(".sbt-total").textContent = `${dur.toFixed(1)} s no total`;
    // picos por bloco: desenha rápido mesmo com minutos de áudio
    const BK = 256, nb = Math.ceil(x.length / BK), pmin = new Float32Array(nb), pmax = new Float32Array(nb);
    for (let i = 0; i < nb; i++) { let lo = 0, hi = 0; for (let j = i * BK, e = Math.min(x.length, j + BK); j < e; j++) { const s = x[j]; if (s < lo) lo = s; if (s > hi) hi = s; } pmin[i] = lo; pmax[i] = hi; }
    const scale = 0.48 / Math.max(sbPeak(x), 1e-4);
    const css = getComputedStyle(document.documentElement), cvar = (...n) => n.map((k) => css.getPropertyValue(k).trim()).find(Boolean);
    const ACC = cvar("--p", "--acc") || "#4c8dff", DIM = cvar("--p3", "--faint") || "#667", TXT = cvar("--p2", "--text") || "#ddd";
    let ac = null, src = null, head = -1, raf = 0, drag = null;
    const fmt = (t) => t.toFixed(2);
    const tx = (t) => ((t - v0) / (v1 - v0)) * cv.clientWidth;
    const tAt = (px) => Math.max(0, Math.min(dur, v0 + (px / cv.clientWidth) * (v1 - v0)));
    function sync() {
      if (document.activeElement !== q(".sbt-a")) q(".sbt-a").value = fmt(a);
      if (document.activeElement !== q(".sbt-b")) q(".sbt-b").value = fmt(b);
      q(".sbt-len").textContent = `trecho: ${(b - a).toFixed(2)} s`;
      draw();
    }
    function draw() {
      const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
      if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
      g2.setTransform(dpr, 0, 0, dpr, 0, 0); g2.clearRect(0, 0, W, H);
      const xa = tx(a), xb = tx(b), mid = H / 2, spp = ((v1 - v0) * R) / W;
      g2.globalAlpha = 0.16; g2.fillStyle = ACC; g2.fillRect(xa, 0, xb - xa, H); g2.globalAlpha = 1;
      for (let px = 0; px < W; px++) {
        const s0 = Math.floor((v0 + (px / W) * (v1 - v0)) * R), s1 = Math.max(s0 + 1, Math.floor(s0 + spp));
        let lo = 0, hi = 0;
        if (spp > BK * 2) { for (let k = Math.floor(s0 / BK), e = Math.min(nb, Math.ceil(s1 / BK)); k < e; k++) { if (pmin[k] < lo) lo = pmin[k]; if (pmax[k] > hi) hi = pmax[k]; } }
        else for (let j = Math.max(0, s0), e = Math.min(x.length, s1); j < e; j++) { const s = x[j]; if (s < lo) lo = s; if (s > hi) hi = s; }
        g2.fillStyle = px >= xa && px <= xb ? ACC : DIM;
        g2.fillRect(px, mid - hi * scale * H, 1, Math.max(1, (hi - lo) * scale * H));
      }
      g2.fillStyle = ACC;
      for (const xx of [xa, xb]) { g2.fillRect(xx - 1, 0, 2, H); g2.fillRect(xx - 6, 0, 12, 14); g2.fillRect(xx - 6, H - 14, 12, 14); }
      if (head >= 0) { g2.fillStyle = TXT; g2.fillRect(tx(head) - 0.5, 0, 1.5, H); }
      // régua: alguns tempos ao longo da vista
      g2.fillStyle = TXT; g2.globalAlpha = 0.6; g2.font = "11px system-ui, sans-serif";
      const span = v1 - v0, step = [0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120].find((s) => span / s <= 8) || 300;
      for (let t = Math.ceil(v0 / step) * step; t < v1; t += step) g2.fillText((step < 1 ? t.toFixed(2) : t.toFixed(0)) + "s", tx(t) + 3, H - 3);
      g2.globalAlpha = 1;
    }
    function setView(n0, n1) {
      const span = Math.max(0.1, Math.min(dur, n1 - n0));
      n0 = Math.max(0, Math.min(dur - span, n0)); v0 = n0; v1 = n0 + span; draw();
    }
    function zoom(f, at) { const c = at ?? (a + b) / 2, s = (v1 - v0) * f; setView(c - (c - v0) * f, c - (c - v0) * f + s); }
    function stop() { if (src) { try { src.stop(); } catch {} src = null; } cancelAnimationFrame(raf); head = -1; q(".sbt-play").textContent = "Ouvir"; draw(); }
    function play(t0, t1) {
      stop();
      if (!ac) { const AC = window.AudioContext || window.webkitAudioContext; ac = new AC({ sampleRate: R }); }
      if (!ac._buf) { ac._buf = ac.createBuffer(1, x.length, R); ac._buf.copyToChannel(x, 0); }
      const gn = ac.createGain(); gn.gain.value = q(".sbt-norm").checked ? Math.min(sbGain(x, Math.floor(a * R), Math.floor(b * R)), 8) : 1;
      src = ac.createBufferSource(); src.buffer = ac._buf; src.connect(gn).connect(ac.destination);
      const at = ac.currentTime + 0.02; src.start(at, t0, Math.max(0.01, t1 - t0));
      const me = src; src.onended = () => { if (src === me) stop(); };
      q(".sbt-play").textContent = "Parar";
      const tick = () => { head = Math.min(t1, t0 + Math.max(0, ac.currentTime - at)); draw(); raf = requestAnimationFrame(tick); };
      raf = requestAnimationFrame(tick);
    }
    function close(res) { stop(); ac?.close?.(); removeEventListener("resize", draw); removeEventListener("keydown", onKey, true); ov.remove(); done(res); }
    function onKey(e) {
      if (e.key === "Escape") { e.preventDefault(); close(null); }
      else if (e.key === " " && !/INPUT|BUTTON/.test(document.activeElement?.tagName)) { e.preventDefault(); src ? stop() : play(a, b); }
    }
    addEventListener("resize", draw); addEventListener("keydown", onKey, true);
    cv.addEventListener("pointerdown", (e) => {
      const px = e.offsetX, t = tAt(px), da = Math.abs(px - tx(a)), db = Math.abs(px - tx(b)), tol = e.pointerType === "touch" ? 22 : 10;
      drag = { mode: da <= tol && da <= db ? "a" : db <= tol ? "b" : "new", t0: t, px0: px, moved: false };
      cv.setPointerCapture(e.pointerId);
    });
    cv.addEventListener("pointermove", (e) => {
      const px = e.offsetX, t = tAt(px), da = Math.abs(px - tx(a)), db = Math.abs(px - tx(b));
      cv.style.cursor = drag ? (drag.mode === "new" ? "crosshair" : "ew-resize") : (Math.min(da, db) <= 10 ? "ew-resize" : "crosshair");
      if (!drag) return;
      if (Math.abs(px - drag.px0) > 4) drag.moved = true;
      if (!drag.moved) return;
      if (drag.mode === "a") { a = Math.max(0, Math.min(t, b - MIN)); if (b - a > SB_MAX) a = b - SB_MAX; }
      else if (drag.mode === "b") { b = Math.min(dur, Math.max(t, a + MIN)); if (b - a > SB_MAX) b = a + SB_MAX; }
      else if (t >= drag.t0) { a = drag.t0; b = Math.min(Math.max(t, a + MIN), a + SB_MAX, dur); }
      else { b = drag.t0; a = Math.max(Math.min(t, b - MIN), b - SB_MAX, 0); }
      sync();
    });
    const up = () => {
      if (!drag) return;
      if (!drag.moved) { const t = drag.t0; play(t, t < b ? b : dur); }
      drag = null;
    };
    cv.addEventListener("pointerup", up); cv.addEventListener("pointercancel", () => { drag = null; });
    cv.addEventListener("wheel", (e) => {
      e.preventDefault();
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) { const s = v1 - v0; setView(v0 + (e.deltaX / cv.clientWidth) * s, v1 + (e.deltaX / cv.clientWidth) * s); return; }
      zoom(e.deltaY > 0 ? 1.25 : 0.8, tAt(e.offsetX));
    }, { passive: false });
    const num = (el, set) => el.addEventListener("change", () => { const v = parseFloat(el.value.replace(",", ".")); if (!isNaN(v)) set(v); el.blur(); sync(); });
    num(q(".sbt-a"), (v) => { a = Math.max(0, Math.min(v, b - MIN)); if (b - a > SB_MAX) b = a + SB_MAX; });
    num(q(".sbt-b"), (v) => { b = Math.min(dur, Math.max(v, a + MIN)); if (b - a > SB_MAX) a = b - SB_MAX; });
    ov.addEventListener("click", (e) => {
      const k = e.target.closest("[data-k]")?.dataset.k; if (!k) return;
      if (k === "zin") zoom(0.6); else if (k === "zout") zoom(1 / 0.6);
      else if (k === "zsel") { const m = Math.max(0.1, (b - a) * 0.15); setView(a - m, b + m); }
      else if (k === "zall") setView(0, dur);
      else if (k === "auto") { [a, b] = sbAuto(x).map((i) => i / R); sync(); }
      else if (k === "play") src ? stop() : play(a, b);
      else if (k === "no") close(null);
      else if (k === "ok") close(sbEncode(x, a * R, b * R, { norm: q(".sbt-norm").checked, fade: q(".sbt-fade").checked }));
    });
    ov.addEventListener("pointerdown", (e) => { if (e.target === ov) close(null); });
    // áudio longo: já abre mostrando a seleção de perto
    if (dur > 40) { const m = Math.max(1, (b - a) * 0.5); v0 = Math.max(0, a - m); v1 = Math.min(dur, b + m); }
    requestAnimationFrame(sync);
  });
}
function sbTrimStyle() {
  if (document.getElementById("sbt-css")) return;
  const st = document.createElement("style"); st.id = "sbt-css";
  st.textContent = `.sbt-ov{position:fixed;inset:0;z-index:9999;background:#000b;display:flex;align-items:center;justify-content:center;padding:12px}
.sbt{width:min(900px,100%);max-height:100%;overflow:auto;background:var(--panel,var(--bg,#151821));background-color:var(--bg2,var(--panel,#151821));border:1px solid var(--p,var(--acc,#4c8dff));border-radius:12px;padding:14px 16px;display:grid;gap:10px}
.sbt-h{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}.sbt-h b{font-size:16px}.sbt-name{opacity:.85;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:50%}.sbt-total{opacity:.6;font-size:13px;margin-left:auto}
.sbt-wave{width:100%;height:150px;display:block;background:#0005;border-radius:8px;touch-action:none;cursor:crosshair}
.sbt-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.sbt-row label{display:flex;gap:6px;align-items:center;margin:0}.sbt-sp{flex:1}
.sbt-a,.sbt-b{width:96px !important;padding:4px 6px;background:#0004 !important;color:inherit !important;border:1px solid var(--p3,var(--line,#555)) !important;border-radius:6px;font:inherit}.sbt-len{opacity:.8;font-size:13px}
.sbt-hint{font-size:12px;opacity:.65}.sbt-acts{display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap}`;
  document.head.appendChild(st);
}
