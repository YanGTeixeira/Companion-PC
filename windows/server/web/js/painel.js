"use strict";
// ---------------------------------------------------------------- Painel
const hist = { cpu: [], ram: [], gpu: [], down: [], up: [], fps: [] };
const HIST_N = 60;
function pushHist(k, v) { const a = hist[k]; a.push(+v || 0); if (a.length > HIST_N) a.shift(); }
function drawSpark(id, series, max) {
  const c = $(id); if (!c || !c.offsetParent) return;
  const dpr = devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight;
  if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
  const g = c.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
  const css = getComputedStyle(document.documentElement);
  const top = max || Math.max(1, ...series.flatMap((s) => s.data));
  for (const { data, color, fill } of series) {
    if (data.length < 2) continue;
    const col = css.getPropertyValue(color).trim() || color, step = w / (HIST_N - 1), x0 = w - (data.length - 1) * step;
    g.beginPath();
    data.forEach((v, i) => { const x = x0 + i * step, y = h - 1 - (Math.min(v, top) / top) * (h - 3); i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.strokeStyle = col; g.lineWidth = 1.5; g.lineJoin = "miter"; g.stroke();
    if (fill) { g.lineTo(w, h); g.lineTo(x0, h); g.closePath(); g.globalAlpha = 0.15; g.fillStyle = col; g.fill(); g.globalAlpha = 1; }
  }
}
function renderStats() {
  const s = state.stats; if (!s) return;
  pushHist("cpu", s.cpu); pushHist("ram", s.ram_pct); pushHist("gpu", s.gpu?.util); pushHist("down", s.net_down); pushHist("up", s.net_up);
  if (vis("dash")) drawSparks();
  pushHist("fps", s.fps?.fps); renderPlayPerf(s);
  $("clock").textContent = $("clock2").textContent = s.time.slice(0, 5);
  $("cpu").textContent = Math.round(s.cpu) + "%"; setBar("cpu-bar", s.cpu);
  const sen = s.sensors;
  $("cpu-mhz").textContent = [sen?.cpu_temp != null ? Math.round(sen.cpu_temp) + "°C" : "", s.cpu_mhz ? (s.cpu_mhz / 1000).toFixed(2) + " GHz" : ""].filter(Boolean).join(" · ");
  $("fans").innerHTML = (sen?.fans || []).slice(0, 4).map((f) => `<div class="row"><span>${esc(f.name)}</span><span>${f.rpm} RPM</span></div>`).join("");
  $("al-cpu-note").classList.toggle("hidden", !!sen);
  checkAlerts(s);
  renderMicTimer(s); deckFollow(s); renderVoice(s.voice);
  $("ram").textContent = Math.round(s.ram_pct) + "%"; setBar("ram-bar", s.ram_pct);
  $("ram-txt").textContent = `${fmtBytes(s.ram_used)} / ${fmtBytes(s.ram_total)}`;
  const g = s.gpu;
  $("gpu-card").classList.toggle("hidden", !g);
  if (g) {
    $("gpu").textContent = Math.round(g.util) + "%"; setBar("gpu-bar", g.util);
    $("gpu-temp").textContent = Math.round(g.temp) + "°C";
    $("gpu-sub").textContent = [g.name, g.power != null ? Math.round(g.power) + " W" : "", g.fan != null ? `fan ${Math.round(g.fan)}%` : "",
      `${fmtBytes(g.mem_used)} / ${fmtBytes(g.mem_total)}`].filter(Boolean).join(" · ");
  }
  $("net-down").textContent = fmtBytes(s.net_down, true); $("net-up").textContent = fmtBytes(s.net_up, true);
  $("net-ping").textContent = !s.ping ? "–" : s.ping.ok ? s.ping.ms + " ms" : "sem internet";
  $("net-ping").style.color = s.ping && !s.ping.ok ? "var(--alert)" : "";
  netAlert(s.ping);
  const f = s.fps?.fps != null ? s.fps : null;
  $("fps-chip").classList.toggle("hidden", !f); if (f) $("fps-chip").textContent = f.fps + " FPS";
  $("g-fps").classList.toggle("hidden", !f);
  if (f) { $("g-fps-n").textContent = f.fps; $("g-fps-low").textContent = f.low ? `1% baixo: ${f.low}` : ""; }
  const ferr = s.fps?.error;
  $("g-fps-hint").classList.toggle("hidden", !ferr || !s.app_game);
  if (ferr) $("g-fps-hint").textContent = ferr === "perm" ? "Para ver o FPS, o PC precisa liberar o PresentMon uma vez (veja o README)." : "Para ver o FPS, instale o PresentMon Console no PC.";
  $("window").textContent = s.window || "Área de trabalho";
  renderBats(s.bat);
  $("procs").innerHTML = (s.procs || []).map((p) => `<div class="row"><span>${esc(p.name)}</span><span>${p.cpu.toFixed(1)}% · ${fmtBytes(p.mem)}</span></div>`).join("");
  $("disks").innerHTML = (s.disks || []).map((d) => `<div class="row"><span>${esc(d.name)}</span><span>${fmtBytes(d.used)} / ${fmtBytes(d.total)}</span></div>
    <div class="bar ${d.pct >= 90 ? "bad" : d.pct >= 75 ? "warn" : ""}" style="margin:0 0 8px"><i style="width:${d.pct}%"></i></div>`).join("");
  const up = s.uptime_s, d = Math.floor(up / 86400);
  $("uptime").textContent = (d ? d + "d " : "") + humanDur(up % 86400);
  $("bat-row").classList.toggle("hidden", !s.battery);
  if (s.battery) $("bat").textContent = `${Math.round(s.battery.pct)}%${s.battery.plugged ? " · na tomada" : ""}`;
}

const BAT_ICON = { mouse: "MOU", keyboard: "TEC", headset: "FON", gamepad: "CTL", phone: "CEL" };
function renderBats(list) {
  const card = $("bat-card");
  if (!welcome.features?.battery && !list?.length) { $("bats").innerHTML = '<div class="empty">Instale o pacote hidapi no PC (rode o install-server.ps1).</div>'; return; }
  if (!list?.length) { $("bats").innerHTML = '<div class="empty">Nenhum aparelho sem fio encontrado</div>'; $("bat-sum").textContent = ""; return; }
  const live = list.filter((d) => d.status === "ok" && d.pct != null && !d.wired);
  const low = live.filter((d) => d.pct <= 20);
  $("bat-sum").textContent = low.length ? `${low.length} fraca${low.length > 1 ? "s" : ""}` : "";
  $("bat-sum").style.color = low.length ? "var(--alert)" : "";
  card.title = "Toque para atualizar";
  const html = list.map((d) => {
    const st = d.wired ? "no cabo" : d.charging ? "carregando" : d.full ? "carregada" : d.status === "sleep" ? "dormindo" : d.status === "off" ? "desligado" : "";
    const pct = d.pct == null ? "–" : (d.approx ? "~" : "") + d.pct + "%";
    const cls = ["batrow", d.status !== "ok" ? "off" : "", d.status === "ok" && d.pct != null && d.pct <= 20 && !d.charging ? "low" : ""].join(" ");
    return `<div class="${cls}"><span class="bi">${BAT_ICON[d.kind] || "BT"}</span><span class="bn">${esc(d.name)}${st ? ` <span class="bs">${st}</span>` : ""}</span><span class="bp">${pct}</span>`
      + (d.pct != null && d.status !== "off" ? `<div class="bar ${d.pct <= 20 ? "bad" : d.pct <= 40 ? "warn" : ""}"><i style="width:${d.pct}%"></i></div>` : "") + "</div>";
  }).join("");
  if ($("bats").innerHTML !== html) $("bats").innerHTML = html;
}
$("bat-card").onclick = () => { buzz(8); act("bat.refresh"); };

function drawSparks() {
  drawSpark("sp-cpu", [{ data: hist.cpu, color: "--p", fill: true }], 100);
  drawSpark("sp-ram", [{ data: hist.ram, color: "--p", fill: true }], 100);
  drawSpark("sp-gpu", [{ data: hist.gpu, color: "--p", fill: true }], 100);
  drawSpark("sp-net", [{ data: hist.down, color: "--p", fill: true }, { data: hist.up, color: "--p3" }]);
}
addEventListener("resize", () => vis("dash") && drawSparks());

// ---------------------------------------------------------------- Tocando
const ICON_PLAY = '<path d="M8 5v14l11-7z"/>', ICON_PAUSE = '<path d="M6 5h4v14H6zm8 0h4v14h-4z"/>';
let volDragging = false, seekPreview = null;
function mediaPos() {
  const m = state.now?.media; if (!m) return 0;
  let pos = m.pos; if (m.status === "playing") pos += (performance.now() - state.nowT) / 1000;
  return m.dur ? Math.min(pos, m.dur) : pos;
}
function renderNow() {
  const n = state.now || {}, m = n.media;
  if (m) {
    $("m-title").textContent = m.title || "(sem título)";
    $("m-artist").textContent = [m.artist, m.album].filter(Boolean).join(" · ");
    $("m-app").textContent = m.app || "";
    $("play-ico").innerHTML = m.status === "playing" ? ICON_PAUSE : ICON_PLAY;
    $("b-prev").disabled = !m.can_prev; $("b-next").disabled = !m.can_next;
  } else {
    $("m-title").textContent = "Nada tocando"; $("m-artist").textContent = "Abra uma música ou vídeo no PC"; $("m-app").textContent = "";
    $("play-ico").innerHTML = ICON_PLAY; $("b-prev").disabled = $("b-next").disabled = false;
  }
  const art = m?.art && state.art[m.art];
  $("art").style.backgroundImage = art ? `url(${art})` : "";
  $("art").firstElementChild.style.display = art ? "none" : "";
  const v = n.volume;
  $("vol").disabled = !v;
  if (v && !volDragging) { $("vol").value = v.level; $("vol-val").textContent = v.muted ? "mudo" : v.level + "%"; }
  if (!v) $("vol-val").textContent = "";
  $("vol-ico").style.opacity = v?.muted ? 0.4 : 1;
  tickProgress();
}
function tickProgress() {
  const m = state.now?.media;
  const pos = seekPreview ?? mediaPos(), dur = m?.dur || 0;
  $("prog-i").style.width = dur ? (pos / dur) * 100 + "%" : "0";
  $("m-pos").textContent = fmtTime(pos); $("m-dur").textContent = fmtTime(dur);
}
$("b-play").onclick = () => act("media.play_pause");
$("b-prev").onclick = () => act("media.prev");
$("b-next").onclick = () => act("media.next");
$("b-mute").onclick = () => (welcome.features?.volume ? act("media.mute") : act("key.press", { keys: "vol_mute" }));
const volInput = $("vol");
let volT = 0;
volInput.addEventListener("input", () => {
  volDragging = true; $("vol-val").textContent = volInput.value + "%";
  const now = performance.now(); if (now - volT > 80) { volT = now; send("volume.set", { level: +volInput.value }, false).catch(() => {}); }
});
volInput.addEventListener("change", () => { send("volume.set", { level: +volInput.value }, false).catch(() => {}); setTimeout(() => (volDragging = false), 600); });
// arrastar na barra de progresso = pular para o ponto
(() => {
  const el = $("prog");
  const at = (e) => { const r = el.getBoundingClientRect(); return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * (state.now?.media?.dur || 0); };
  el.addEventListener("pointerdown", (e) => { if (!state.now?.media?.can_seek) return; el.setPointerCapture(e.pointerId); seekPreview = at(e); tickProgress(); });
  el.addEventListener("pointermove", (e) => { if (seekPreview !== null) { seekPreview = at(e); tickProgress(); } });
  el.addEventListener("pointerup", (e) => {
    if (seekPreview === null) return;
    const delta = at(e) - mediaPos(); seekPreview = null;
    act("media.seek", { delta });
  });
  el.addEventListener("pointercancel", () => { seekPreview = null; });
})();

