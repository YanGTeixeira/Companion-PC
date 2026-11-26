"use strict";
// ---------------------------------------------------------------- Cartão do perfil para o OBS (/cartao), 1.21
// Fonte de navegador com fundo transparente: o cartão do jogador ao vivo (troca de item, nível, prestígio...).
// Token só de leitura (não é o do app) e só funciona no próprio PC. Opções no endereço:
//   ?blocos=1 mostra os blocos do perfil (frase, números, vitrine) · ?largura=480 muda a largura (px)
const $ = (id) => document.getElementById(id);
const Q = new URLSearchParams(location.search);
const TOKEN = (location.hash.match(/[#&]t=([^&]+)/) || [])[1] || "";
const BLOCKS = Q.get("blocos") === "1";
let CQ = null, NICK = "", WEB = null;
document.documentElement.style.setProperty("--w", Math.max(240, Math.min(1200, +Q.get("largura") || 420)) + "px");
document.body.insertAdjacentHTML("afterbegin", TROPHY_DEFS);
ANIM.pref = Q.get("anim") !== "0"; animSync();

function msg(t) { $("msg").textContent = t; $("msg").hidden = !t; }
function render() {
  if (!CQ) return;
  const d = CQ, eq = d.equip || {}, nm = (id) => d.rewards.find((r) => r.id === id)?.name || "";
  const got = d.conq.filter((c) => c.day);
  const show = (eq.show || []).map((id) => d.conq.find((c) => c.id === id)).filter(Boolean);
  $("card").innerHTML = profileCard({ nick: NICK, level: d.level, prestige: d.prestige, title: nm(eq.title) || "Novato", frame: eq.frame,
    avatar: eq.avatar, effect: eq.effect, bg: eq.bg, bio: eq.bio, lay: BLOCKS ? eq.lay : [],
    sub: d.streak ? `🔥 ${d.streak} dia${d.streak > 1 ? "s" : ""}` : "",
    stats: [[d.level, "nível"], [d.week_xp, "XP na semana"], [d.best_streak, "recorde"], [`${got.length}/${d.conq.length}`, "troféus"]],
    show: show.length ? `<div class="shrow">${show.map((c) => `<div class="cqt got">${trophy(c.tier, true)}<span>${cEsc(c.name)}</span></div>`).join("")}</div>` : "" });
  accentApply($("card"), eq.accent, eq.color);
}
function applyTheme(lay) {
  if (!lay) return;
  const h = document.documentElement.dataset;
  if (lay.skin) h.skin = lay.skin;
  h.theme = lay.theme || (THEMES.find((t) => t.id === lay.skin)?.variants[0][0]) || "green";
}
function connect() {
  if (!TOKEN) return msg("Falta o token: copie o link pela página Jogador do PC (Perfil › Cartão para lives).");
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => ws.send(JSON.stringify({ t: "hello", token: decodeURIComponent(TOKEN), role: "card" }));
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.t === "welcome") { if (WEB && m.web && m.web !== WEB) return location.reload(); WEB = m.web; applyTheme(m.layout); msg(""); }
    else if (m.t === "conq" && m.d) { CQ = m.d; render(); }
    else if (m.t === "rank" && m.d) { NICK = m.d.joined ? m.d.nick : ""; render(); }
    else if (m.t === "layout" && m.d) applyTheme(m.d);
  };
  ws.onclose = (e) => {
    if (e.code === 4001) return msg("Link inválido. Copie de novo pela página Jogador do PC. (Só funciona no próprio PC.)");
    setTimeout(connect, 3000);
  };
}
connect();
