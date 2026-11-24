"use strict";
// ---------------------------------------------------------------- loop de tela
setInterval(() => {
  if (vis("media")) tickProgress();
  if (vis("games") && state.games?.game) renderGames();
}, 1000);

// tamanho da tela em Ajustes > Conexão (ajuda a acertar o layout de cada aparelho)
let CONN = "";
function showConn() { $("conn-info").textContent = [CONN, `tela ${innerWidth}×${innerHeight}`].filter(Boolean).join(" · "); }
addEventListener("resize", showConn); showConn();
if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("sw.js").catch(() => {});
// visual: cor do terminal e efeito de tubo
prefs.theme = store.get("theme", "green"); prefs.crt = store.get("crt", true); prefs.skin = store.get("skin", "fallout");
// temas: cada um tem variantes (cores) e alguns têm o efeito de tubo
const THEMES = [
  { id: "fallout", name: "Fallout", desc: "Terminal de fósforo", crt: true, variants: [["green", "Verde", "#5cff8a"], ["amber", "Âmbar", "#ffbf47"], ["cyan", "Ciano", "#7cf4ff"], ["blue", "Azul", "#8fd3ff"], ["white", "Branco", "#e8f0f2"]] },
  { id: "synth", name: "Synthwave", desc: "Neon rosa e ciano", crt: true, variants: [["neon", "Neon", "#ff4fd8"], ["sunset", "Pôr do sol", "#ffb347"], ["ice", "Gelo", "#7df9ff"]] },
  { id: "minimal", name: "Minimal", desc: "Limpo e moderno", variants: [["dark", "Escuro", "#171a20"], ["light", "Claro", "#f3f5f8"], ["amoled", "Preto (AMOLED)", "#000000"]] },
  { id: "hud", name: "Cockpit", desc: "HUD laranja e branco", variants: [["orange", "Laranja", "#ff8a1f"], ["aviation", "Aviônica", "#3fd3ff"]] },
  { id: "lcd", name: "LCD 8-bit", desc: "Tela de pixel verde", variants: [["olive", "Oliva", "#a4b465"]] },
  { id: "paper", name: "Papel", desc: "E-ink, preto no creme", variants: [["cream", "Creme", "#f2ede2"]] },
  { id: "pocket", name: "Portátil", desc: "4 tons, tela de bolso", variants: [["dmg", "Verde", "#9bbc0f"], ["gray", "Cinza", "#c4c4b2"]] },
  { id: "code", name: "Código", desc: "Editor escuro, cores de sintaxe", variants: [["dark", "Escuro", "#1e1e1e"], ["mocha", "Mocha", "#1e1e2e"]] },
  { id: "rpg", name: "Fantasia", desc: "Pedra, ouro e moldura", variants: [["stone", "Pedra", "#d9ad4f"], ["crimson", "Carmim", "#c23b32"]] },
  { id: "tac", name: "Tático", desc: "Mapa de missão", variants: [["olive", "Oliva", "#ff7a1a"], ["urban", "Urbano", "#ffb020"]] },
  { id: "jp", name: "Japão", desc: "Washi, sakura e carimbo", variants: [["sakura", "Sakura", "#f7f1e8"], ["night", "Noite em Tóquio", "#17193a"]] },
  { id: "exec", name: "Executivo", desc: "Marinho e champanhe", variants: [["navy", "Marinho", "#111a2c"], ["ivory", "Marfim", "#f6f3ec"], ["black", "Preto", "#131313"]] },
];
function themeOk() {
  const t = THEMES.find((x) => x.id === prefs.skin) || THEMES[0];
  prefs.skin = t.id;
  if (!t.variants.some(([v]) => v === prefs.theme)) prefs.theme = t.variants[0][0];
  return t;
}
function renderThemePicker() {
  $("themes").innerHTML = THEMES.map((t) => `<div class="thm${t.id === prefs.skin ? " on" : ""}" data-skin="${t.id}" data-theme="${t.variants[0][0]}">
    <button class="thb" data-pick="${t.id}"><span class="thn">${t.name}</span><small>${t.desc}</small></button>
    ${t.variants.length > 1 ? `<div class="thv">${t.variants.map(([v, l, c]) => `<button data-pick="${t.id}" data-var="${v}" class="${t.id === prefs.skin && v === prefs.theme ? "on" : ""}" style="background:${c}" aria-label="${l}" title="${l}"></button>`).join("")}</div>` : ""}</div>`).join("");
}
function pickTheme(skin, variant) {
  prefs.skin = skin; prefs.theme = variant || (THEMES.find((t) => t.id === skin)?.variants[0][0]);
  store.set("skin", prefs.skin); store.set("theme", prefs.theme); applyTheme();
  // o tema vale para todos os aparelhos: grava no PC
  if (ws && ws.readyState === 1) send("layout.set", { layout: { ...LAYOUT, skin: prefs.skin, theme: prefs.theme, crt: prefs.crt } }).catch(() => {});
}
// troca automática (Personalizar > Tema): o jogo aberto vence o horário; os dois vencem a escolha manual
const toMin = (hm) => { const [h, m] = String(hm || "0:0").split(":").map(Number); return (h || 0) * 60 + (m || 0); };
function autoPick() {
  const a = LAYOUT?.auto || {};
  if (a.game?.on) {
    const g = state.games?.game?.name || "", k = /dota/i.test(g) ? "dota2" : /counter-strike/i.test(g) ? "cs2" : null;
    if (k && a.game[k]) return a.game[k];
  }
  if (a.time?.on && a.time.night) {
    const d = new Date(), m = d.getHours() * 60 + d.getMinutes(), f = toMin(a.time.from || "19:00"), t = toMin(a.time.to || "07:00");
    const night = f > t ? m >= f || m < t : m >= f && m < t;
    return night ? a.time.night : a.time.day || null;
  }
  return null;
}
let themeEff = "";
function applyTheme() {
  themeOk();
  let skin = prefs.skin, theme = prefs.theme;
  const ap = autoPick();
  if (ap) {
    const [s2, v2] = ap.split(":"), t2 = THEMES.find((x) => x.id === s2);
    if (t2) { skin = s2; theme = t2.variants.some(([v]) => v === v2) ? v2 : t2.variants[0][0]; }
  }
  const t = THEMES.find((x) => x.id === skin);
  themeEff = skin + ":" + theme;
  document.documentElement.dataset.skin = skin;
  document.documentElement.dataset.theme = theme;
  document.body.classList.toggle("crt", prefs.crt && !!t.crt);
  $("sw-crt").closest(".set").classList.toggle("hidden", !t.crt);
  renderThemePicker();
  document.querySelector('meta[name="theme-color"]').content = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
  if (vis("dash")) drawSparks();
}
function autoTheme() {
  const ap = autoPick(), want = ap || prefs.skin + ":" + prefs.theme;
  if (want !== themeEff) applyTheme();
}
setInterval(autoTheme, 30000);
$("themes").onclick = (e) => { const b = e.target.closest("[data-pick]"); if (!b) return; buzz(8); pickTheme(b.dataset.pick, b.dataset.var); };
bindSwitch("sw-crt", "crt", () => { applyTheme(); if (ws && ws.readyState === 1) send("layout.set", { layout: { ...LAYOUT, skin: prefs.skin, theme: prefs.theme, crt: prefs.crt } }).catch(() => {}); });
bindSwitch("sw-deckauto", "deckAuto", () => { lastApp = null; });
bindSwitch("sw-snd", "snd", () => snd("ok"));
bindSwitch("sw-pcnotif", "pcnotif", () => { if (ws && welcome.features?.notif) subNotif(); });
applyTheme();
showView(prefs.tab == "apps" ? "deck" : prefs.tab);
handleShared();
renderPower();
applyWake();
connect();
