"use strict";
// ---------------------------------------------------------------- seções e vistas
// 5 seções na barra; cada uma tem vistas (sub-abas). Em tablet deitado as vistas
// da seção aparecem lado a lado.
// ---------------------------------------------------------------- layout (menu e cartões), um em pé e um deitado
// O layout fica no PC (layout.json) e é editado na página /editor; vale para todos os aparelhos.
const VIEW_LABEL = { dash: "Sistema", games: "Jogos", usage: "Tempo", media: "Tocando", mix: "Mixer", mouse: "Mouse e teclado",
  screen: "Tela do PC", deck: "Botões", send: "Arquivos", power: "Energia", voz: "Voz", sys: "Ajustes", play: "Jogando", meet: "Reunião", today: "Hoje" };
const DEFAULT_NAV = [
  { id: "status", label: "Status", views: ["dash", "today", "games", "usage"] }, { id: "radio", label: "Rádio", views: ["media", "mix"] },
  { id: "ctrl", label: "Controle", views: ["mouse", "screen"] }, { id: "deck", label: "Botões", views: ["deck"] },
  { id: "pc", label: "PC", views: ["send", "power", "voz", "sys"] }];
const SPLIT_DEFAULT = { status: "minmax(0,1.7fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)", radio: "minmax(0,1fr) minmax(0,1.1fr)",
  ctrl: "minmax(0,1fr) minmax(0,1.7fr)", pc: "minmax(0,1.1fr) minmax(0,.7fr) minmax(0,1.3fr) minmax(0,1.1fr)" };
const BASE_VIEWS = Object.keys(VIEW_LABEL).filter((v) => v !== "play" && v !== "meet");
let LAYOUT = store.get("layout", null) || {};
let NAV = DEFAULT_NAV, SECTIONS = {}, SPLIT = {}, VIEWS = [];
const LIVE = {};   // abas que só existem enquanto algo acontece no PC (jogo, reunião)
const orient = () => (innerWidth > innerHeight ? "landscape" : "portrait");
// abas que existiam antes de o layout guardar "known" (1.8); as que vieram depois entram sozinhas no menu salvo
const LEGACY_VIEWS = ["dash", "games", "usage", "media", "mix", "mouse", "screen", "deck", "send", "power", "voz", "sys"];
function addNewViews(nav, known) {
  const k = new Set(known || LEGACY_VIEWS), used = new Set(nav.flatMap((s) => s.views || []));
  for (const v of BASE_VIEWS) {
    if (used.has(v) || k.has(v)) continue;
    const def = DEFAULT_NAV.find((d) => d.views.includes(v)), sec = nav.find((s) => s.id === def?.id) || nav.find((s) => (s.views || []).some((x) => def?.views.includes(x))) || nav[0];
    if (!sec) continue;
    const prev = def ? def.views[def.views.indexOf(v) - 1] : null, i = sec.views.indexOf(prev);
    sec.views = [...sec.views]; sec.views.splice(i >= 0 ? i + 1 : sec.views.length, 0, v);
  }
  return nav;
}
function cleanNav(nav, known) {
  nav = addNewViews((Array.isArray(nav) ? nav : []).map((s) => ({ ...s, views: [...(s.views || [])] })), known);
  // aceita só abas que existem, sem repetir; Ajustes nunca some (senão não dá para voltar atrás)
  const seen = new Set(), out = [];
  for (const sec of Array.isArray(nav) ? nav : []) {
    const views = (sec.views || []).filter((v) => BASE_VIEWS.includes(v) && !seen.has(v));
    views.forEach((v) => seen.add(v));
    if (views.length) out.push({ id: String(sec.id || "s" + out.length), label: String(sec.label || VIEW_LABEL[views[0]]).slice(0, 14), views });
  }
  if (!seen.has("sys")) (out.at(-1) || out[out.push({ id: "pc", label: "PC", views: [] }) - 1]).views.push("sys");
  return out.length ? out : DEFAULT_NAV;
}
function buildSections() {
  const L = LAYOUT[orient()] || {};
  NAV = cleanNav(L.nav || DEFAULT_NAV, L.known);
  const home = (NAV.find((s) => s.views.includes("dash")) || NAV[0]).id;
  SECTIONS = {}; SPLIT = {};
  for (const sec of NAV) {
    const live = sec.id === home ? Object.keys(LIVE) : [];
    SECTIONS[sec.id] = [...live, ...sec.views].map((v) => [v, VIEW_LABEL[v]]);
    const def = DEFAULT_NAV.find((d) => d.id === sec.id);
    SPLIT[sec.id] = !live.length && def && def.views.join() === sec.views.join() ? SPLIT_DEFAULT[sec.id] : "";
  }
  VIEWS = Object.values(SECTIONS).flat().map(([n]) => n);
  const nav = $("nav");
  nav.querySelectorAll(".nb").forEach((b) => b.remove());
  for (const sec of NAV) {
    const b = document.createElement("button");
    b.className = "nb"; b.dataset.sec = sec.id; b.textContent = sec.label;
    b.onclick = () => { buzz(8); showView(lastView[sec.id] && VIEWS.includes(lastView[sec.id]) ? lastView[sec.id] : SECTIONS[sec.id][0][0]); };
    nav.appendChild(b);
  }
  applyDashLayout(L.dash);
  applyBlocks(L.blocks);
}
// blocos das outras telas (data-b): ordem, escondido e largura inteira, por orientação
function applyBlocks(blocks) {
  document.querySelectorAll("main [data-b]").forEach((el) => { el.style.order = ""; el.style.removeProperty("grid-column"); el.classList.remove("lhide"); });
  document.querySelectorAll("main .bhide").forEach((el) => el.classList.remove("bhide"));
  if (!blocks || typeof blocks !== "object") return;
  for (const [view, list] of Object.entries(blocks)) {
    const tab = $("t-" + view); if (!tab || !Array.isArray(list)) continue;
    const els = [...tab.querySelectorAll("[data-b]")], pos = new Map(list.map((b, i) => [b.id, [b, i]]));
    let prevOrder = -1;   // bloco que o layout salvo não conhece (veio numa versão nova): fica logo depois do vizinho de cima
    for (const el of els) {
      const hit = pos.get(el.dataset.b);
      if (!hit) { el.style.order = prevOrder; continue; }
      prevOrder = hit[1];
      const [b, i] = hit;
      el.style.order = i;
      el.classList.toggle("lhide", !!b.hidden);
      if (b.wide) el.style.setProperty("grid-column", "1 / -1", "important");
    }
    for (const p of new Set(els.map((e) => e.parentElement))) {
      if (p === tab) continue;
      const kids = [...p.children].filter((c) => c.dataset.b);
      p.classList.toggle("bhide", kids.every((c) => c.classList.contains("lhide")));
    }
  }
}
// cartões do Status: ordem, largura (colunas) e escondidos
const DASH_CARDS = { cpu: "CPU", ram: "Memória", gpu: "GPU", net: "Rede", procs: "Processos", disks: "Discos", bat: "Bateria", sys: "Sistema" };
function applyDashLayout(dash) {
  const grid = document.querySelector(".grid.dash");
  const cards = [...grid.children];
  cards.forEach((c) => { const id = [...c.classList].find((k) => k.startsWith("c-"))?.slice(2); c.dataset.card = id; });
  const custom = Array.isArray(dash) && dash.length;
  grid.classList.toggle("custom", !!custom);
  cards.forEach((c) => { c.style.order = ""; c.style.removeProperty("grid-column"); c.classList.remove("lhide"); });
  if (!custom) return;
  const pos = Object.fromEntries(dash.map((d, i) => [d.id, { ...d, i }]));
  cards.forEach((c) => {
    const d = pos[c.dataset.card];
    if (!d) { c.style.order = 99; return; }
    c.style.order = d.i;
    c.classList.toggle("lhide", !!d.hidden);
    const span = Math.max(1, Math.min(4, +d.span || 1));
    c.style.setProperty("grid-column", `span ${span}`, "important");
  });
  grid.style.setProperty("--rows", Math.max(1, Math.ceil(dash.filter((d) => !d.hidden).reduce((a, d) => a + Math.max(1, +d.span || 1), 0) / (orient() === "landscape" ? 4 : 2))));
}
function setLive(view, label, on, real = true) {
  if (real) LIVE_REAL[view] = on;
  if (!on && PREVIEW_LIVE.has(view)) return;
  if (!!LIVE[view] === on) return;
  if (on) LIVE[view] = label; else delete LIVE[view];
  buildSections();
  if (!on && prefs.tab === view) { const home = secOf("dash"); showView(lastView[home] && lastView[home] !== view && VIEWS.includes(lastView[home]) ? lastView[home] : "dash", true); }
  else showView(prefs.tab, true);
}
function applyLayout(l, fromServer) {
  if (l && typeof l === "object") { LAYOUT = l; store.set("layout", l); }
  if (LAYOUT.skin || LAYOUT.theme) {
    prefs.skin = LAYOUT.skin || prefs.skin; prefs.theme = LAYOUT.theme || prefs.theme;
    if (typeof LAYOUT.crt === "boolean") prefs.crt = LAYOUT.crt;
    store.set("skin", prefs.skin); store.set("theme", prefs.theme); store.set("crt", prefs.crt);
    if (typeof applyTheme === "function" && fromServer) applyTheme();
  } else if (typeof autoTheme === "function" && fromServer) autoTheme();
  buildSections();
  if (fromServer) showView(prefs.tab, true);
}
let lastOrient = orient();
addEventListener("resize", () => { if (orient() !== lastOrient) { lastOrient = orient(); buildSections(); showView(prefs.tab, true); } });
const secOf = (v) => Object.keys(SECTIONS).find((s) => SECTIONS[s].some(([n]) => n === v)) || Object.keys(SECTIONS)[0];
const wideMQ = matchMedia("(min-width: 1000px) and (min-height: 600px) and (orientation: landscape)");
const MAIN = $("main"), lastView = store.get("views", {});
let shown = new Set();
const vis = (v) => shown.has(v);
function showView(name, temp) {
  if (!VIEWS.includes(name)) name = VIEWS.includes("dash") ? "dash" : VIEWS[0];
  const sec = secOf(name), views = SECTIONS[sec], multi = wideMQ.matches && views.length > 1;
  shown = new Set(multi ? views.map(([n]) => n) : [name]);
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", shown.has(t.id.slice(2))));
  document.querySelectorAll("nav .nb").forEach((b) => b.classList.toggle("on", b.dataset.sec === sec));
  MAIN.classList.toggle("multi", multi);
  MAIN.style.gridTemplateColumns = multi ? SPLIT[sec] || "" : "";
  const sub = $("subtabs"), showSub = !multi && views.length > 1;
  sub.classList.toggle("hidden", !showSub);
  sub.innerHTML = showSub ? views.map(([n, l]) => `<button role="tab" data-view="${n}" aria-selected="${n === name}"${n === name ? ' class="on"' : ""}>${l}</button>`).join("") : "";
  document.querySelectorAll(".tab.on").forEach((t) => (t.scrollTop = 0));
  prefs.tab = name;
  if (!temp) { store.set("tab", name); lastView[sec] = name; store.set("views", lastView); }
  if (!vis("mouse")) $("kbd").blur();
  if (vis("dash")) requestAnimationFrame(drawSparks);
  if (vis("games") && welcome) loadHist();
  if (vis("mix") && welcome) loadProfiles();
  if (vis("today")) { renderToday(); setTimeout(() => loadDay(true)); }
  if (vis("games")) { renderSteam(); renderPost(); }
  if (vis("screen")) requestAnimationFrame(() => { layoutScreen(); screenLoop(); });
  if (vis("media") || vis("mix")) { mixT = 0; renderMixer(); pollMixer(); }
  if (vis("games")) loadGamesExtra();
  if (vis("usage")) setTimeout(loadUsage);
  if (vis("voz")) setTimeout(loadVoiceHelp);  // no início, as funções da voz ainda nem foram declaradas
  if (state.meet !== undefined) setTimeout(renderMeet);
  if (vis("play")) setTimeout(() => { renderPlay(); state.stats && renderPlayPerf(state.stats); });
}
$("subtabs").onclick = (e) => { const b = e.target.closest("[data-view]"); if (b) { buzz(8); showView(b.dataset.view); } };
buildSections();
wideMQ.addEventListener("change", () => showView(prefs.tab));

// ---------------------------------------------------------------- abertura (uma vez por carregamento)
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
function bootLine(t, dim) {
  const box = $("boot-lines"); if ($("boot").classList.contains("done")) return;
  box.querySelector(".cur")?.classList.remove("cur");
  const d = document.createElement("div"); d.className = "l cur" + (dim ? " dim" : ""); d.textContent = t; box.appendChild(d);
}
function bootDone(now) { setTimeout(() => $("boot").classList.add("done"), now || REDUCED ? 0 : 500); }
bootLine("PC COMPANION 1.9");
bootLine("Terminal de bolso para o seu PC", true);
bootLine(`Conectando pelo ${["localhost", "127.0.0.1"].includes(location.hostname) ? "cabo USB" : "Wi-Fi"}…`);
setTimeout(() => bootDone(true), 5000);   // sem PC: mostra o app com o aviso de conexão

