"use strict";
// ---------------------------------------------------------------- microfone do PC e timer de energia
function renderMicTimer(s) {
  const m = s.mic;
  for (const id of ["mic-chip", "mic-chip2"]) {
    const b = $(id); b.classList.toggle("hidden", !m);
    if (m) { b.classList.toggle("on", m.muted); b.textContent = m.muted ? "MIC OFF" : "MIC"; b.title = m.name; }
  }
  const t = s.timer;
  $("tmr-chip").classList.toggle("hidden", !t);
  $("tmr-on").classList.toggle("hidden", !t); $("tmr-off").classList.toggle("hidden", !!t);
  if (t) {
    $("tmr-chip").textContent = "TIMER " + fmtTime(t.left);
    $("tmr-left").textContent = fmtTime(t.left); $("tmr-what").textContent = `${t.label} quando chegar a zero`;
  }
}
async function micToggle() {
  buzz();
  try {
    const r = await send("mic.set", { muted: "toggle" });
    if (r && state.stats) { state.stats.mic = r; renderMicTimer(state.stats); }
    toast(r?.muted ? "Microfone do PC no mudo" : "Microfone do PC ligado", "ok");
  } catch (e) { if (e.message !== "offline") toast(e.message, "bad"); }
}
$("mic-chip").onclick = $("mic-chip2").onclick = micToggle;
$("tmr-chip").onclick = () => { buzz(8); showView("power"); };
document.querySelectorAll("[data-min]").forEach((b) => (b.onclick = () => {
  const min = +b.dataset.min;
  act("timer.start", { action: $("tmr-act").value, minutes: min }).then((r) => {
    if (!r) return;
    if (state.stats) { state.stats.timer = r; renderMicTimer(state.stats); }
    toast(`${r.label} em ${fmtTime(min * 60)}`, "ok");
  });
}));
$("tmr-cancel").onclick = () => act("timer.cancel", {}, "Timer cancelado").then(() => {
  if (state.stats) { state.stats.timer = null; renderMicTimer(state.stats); }
});

// ---------------------------------------------------------------- comandos de voz ("PC, ...")
const VOZ_ST = { off: "Desligado", loading: "Carregando o reconhecimento de fala…", listening: "Ouvindo", error: "Erro" };
let vozDevs = false;
let vozFlash = 0;
function renderVoice(v) {
  const ok = !!(v && v.available);
  $("voz-sec").classList.toggle("hidden", !ok);
  $("voz-na").classList.toggle("hidden", ok || !v);
  $("voz-sec").parentElement.classList.toggle("hidden", !ok && !v);
  $("voz-row").classList.toggle("hidden", !ok);
  for (const id of ["voz-chip", "voz-chip2"]) $(id).classList.toggle("hidden", !ok);
  if (!ok) return;
  if (performance.now() > vozFlash) {
    for (const id of ["voz-chip", "voz-chip2"]) {
      const b = $(id); b.classList.remove("on"); b.textContent = "VOZ";
      b.classList.toggle("voz-off", !v.on || v.status !== "listening");
    }
  }
  $("voz-dash").textContent = !v.on ? "desligada" : v.status === "listening"
    ? "ouvindo" + (v.fallback ? " (webcam, mic no mudo)" : "") : v.status === "loading" ? "carregando" : "erro";
  $("voz-row2").classList.toggle("hidden", !v.last);
  if (v.last) { const d = $("voz-dash-last"); d.textContent = v.last.msg; d.title = v.last.text; d.classList.toggle("bad", !v.last.ok); }
  $("sw-voz").classList.toggle("on", v.on);
  $("sw-voz-fala").classList.toggle("on", v.speak);
  $("sw-voz-ov").classList.toggle("on", v.overlay);
  let st = v.on ? VOZ_ST[v.status] || v.status : "Desligado";
  if (v.on && v.status === "listening") st = `Ouvindo: ${v.device}` + (v.fallback ? " (o microfone principal está no mudo)" : "") + ` · diga "PC" e o comando`;
  if (v.on && v.status === "error") st = "Erro: " + v.error;
  $("voz-st").textContent = st;
  if (v.last) {
    const el = $("voz-last");
    el.textContent = `"${v.last.text}" > ${v.last.msg}`; el.classList.toggle("bad", !v.last.ok);
  }
  if (!vozDevs && vis("voz")) {
    vozDevs = true;
    send("voice.devices", {}, true).then((list) => {
      const sel = $("voz-dev");
      sel.innerHTML = `<option value="">Automático (padrão do Windows)</option>` + (list || []).map((n) => `<option value="${esc(n)}">${esc(n + ((n.split("(").length > n.split(")").length) ? ")" : ""))}</option>`).join("");
      sel.value = v.pick && (list || []).some((n) => n === v.pick) ? v.pick : "";
    }).catch(() => { vozDevs = false; });
  }
}
function vozChip(text, ms) {
  vozFlash = performance.now() + ms;
  for (const id of ["voz-chip", "voz-chip2"]) { const b = $(id); b.textContent = text; b.classList.add("on"); b.classList.remove("voz-off"); }
  setTimeout(() => { if (performance.now() >= vozFlash && state.stats) renderVoice(state.stats.voice); }, ms + 50);
}
$("voz-chip").onclick = $("voz-chip2").onclick = () => { buzz(8); showView("voz"); };
const VOZ_HELP = [
  ["Música", [["próxima música", "pula para a próxima (também: pula, avança)"], ["volta", "faixa anterior"], ["pausa", "pausa o que está tocando"],
    ["toca", "continua tocando"], ["que música é essa", "mostra o nome e o artista"]]],
  ["Volume", [["volume 30", "põe o volume em 30%"], ["aumenta o volume", "+10 (ou \"aumenta 20\")"], ["abaixa o volume 20", "-20"],
    ["volume no máximo", "100%"], ["muta o som", "liga/desliga o mudo do PC"]]],
  ["Abrir programas e jogos", [["abre o Spotify", "qualquer atalho de \"Seus atalhos\""], ["abre o navegador", "também entende apelidos"],
    ["joga Counter Strike", "abre um jogo da biblioteca"], ["abre o GTA", "siglas funcionam"]]],
  ["Microfone e Discord", [["muta o microfone", "microfone do PC no mudo"], ["desmuta o microfone", "liga de novo"],
    ["muta o Discord", "aperta o atalho de mudo do Discord"], ["ensurdece", "ensurdecer no Discord"]]],
  ["Energia", [["desliga em 1 hora", "timer: desligar"], ["suspende em meia hora", "timer: suspender"], ["desliga a tela em 20 minutos", "timer: monitor"],
    ["cancela o timer", "cancela qualquer timer"], ["bloqueia", "bloqueia o PC agora"], ["desliga a tela", "apaga o monitor agora"]]],
  ["Outros", [["troca a saída de som", "fone / caixas"], ["tira um print", "salva em Imagens > Capturas de tela"]]],
];
let vozHelpT = 0;
function vexBtn(say, what) { return `<button class="vex" data-say="${esc(say)}"><b>PC, ${esc(say)}</b>${what ? `<small>${esc(what)}</small>` : ""}</button>`; }
function renderVoiceHelp(cat) {
  let h = VOZ_HELP.map(([t, items]) => `<div class="card vgrp"><h3><span>${t}</span></h3>${items.map(([a, b]) => vexBtn(a, b)).join("")}</div>`).join("");
  if (cat) {
    if (cat.deck?.length) h += `<div class="card vgrp"><h3><span>Seus botões</span><span>PC, (nome)</span></h3><div class="vchips">${cat.deck.map((l) => `<button class="vchip" data-say="${esc(l)}">${esc(l)}</button>`).join("")}</div></div>`;
    if (cat.apps?.length) h += `<div class="card vgrp"><h3><span>Seus atalhos</span><span>PC, abre o ...</span></h3><div class="vchips">${cat.apps.map((a) => `<button class="vchip" data-say="abre o ${esc(a.name)}">${esc(a.name)}${a.say.length ? `<small>ou: ${esc(a.say.join(", "))}</small>` : ""}</button>`).join("")}</div></div>`;
    if (cat.games?.length) h += `<div class="card vgrp"><h3><span>Seus jogos</span><span>PC, joga ...</span></h3><div class="vchips">${cat.games.map((g) => `<button class="vchip" data-say="joga ${esc(g)}">${esc(g)}</button>`).join("")}</div></div>`;
  }
  $("voz-help").innerHTML = h;
}
function loadVoiceHelp() {
  if (!$("voz-help").innerHTML) renderVoiceHelp(null);
  if ((vozHelpT && performance.now() - vozHelpT < 60000) || !ws || ws.readyState !== 1) return;
  vozHelpT = performance.now();
  send("voice.help", {}, true).then(renderVoiceHelp).catch(() => { vozHelpT = 0; });
}
$("voz-help").onclick = (e) => {
  const b = e.target.closest("[data-say]"); if (!b) return;
  buzz(8); $("voz-try").value = b.dataset.say;
  $("voz-try-out").textContent = "Toque em Executar para rodar no PC.";
  $("voz-try").scrollIntoView({ block: "center", behavior: "smooth" });
};
async function voiceTry() {
  const text = $("voz-try").value.trim(); if (!text) return;
  buzz();
  try {
    const r = await send("voice.try", { text });
    $("voz-try-out").textContent = "OK: " + r.msg; toast(r.msg, "ok");
  } catch (e) { if (e.message !== "offline") { $("voz-try-out").textContent = "Não deu: " + e.message; toast(e.message, "bad"); } }
}
$("voz-try-go").onclick = voiceTry;
$("voz-try").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); voiceTry(); } };

function voiceEvent(m) {
  if (m.phase === "wake") { vozChip("OUVINDO", (m.secs || 6) * 1000); toast("PC ouvindo... diga o comando", "warn"); return; }
  vozChip(m.ok ? "VOZ OK" : "VOZ ?", 2500);
  if (state.stats?.voice) { state.stats.voice.last = { text: m.text, ok: m.ok, msg: m.msg }; renderVoice(state.stats.voice); }
  toast(`Voz: ${m.msg}`, m.ok ? "ok" : "bad");
}
async function voiceSet(p) {
  buzz(8);
  try { const r = await send("voice.set", p); if (state.stats) { state.stats.voice = r; renderVoice(r); } }
  catch (e) { if (e.message !== "offline") toast(e.message, "bad"); }
}
$("sw-voz").onclick = () => voiceSet({ on: !$("sw-voz").classList.contains("on") });
$("sw-voz-fala").onclick = () => voiceSet({ speak: !$("sw-voz-fala").classList.contains("on") });
$("sw-voz-ov").onclick = () => voiceSet({ overlay: !$("sw-voz-ov").classList.contains("on") });
$("voz-dev").onchange = () => voiceSet({ device: $("voz-dev").value });

