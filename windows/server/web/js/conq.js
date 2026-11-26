"use strict";
// ---------------------------------------------------------------- Conquistas: metas do dia, galeria de troféus e avisos
// Tudo é calculado no PC (conquistas.py) com o tempo de tela, foco, partidas e voz que ele já grava.
const CQ_TIER = { bronze: "BRONZE", prata: "PRATA", ouro: "OURO" };
async function loadConq() { try { onConq(await send("conq.get")); } catch {} }
function onConq(d) { if (!d) return; state.conq = d; renderConq(); }
function cqFmt(unit, v) {
  return unit === "dur" ? humanDur(v) : unit === "min" ? humanDur(v * 60) : unit === "kda" ? (+v).toFixed(1).replace(/\.0$/, "") : String(Math.round(v));
}
const CQ_STATUS = { done: "FEITA", failed: "passou", ok: "dentro até agora", skip: "PC quase não usado", open: "" };
function renderConq() {
  const d = state.conq; if (!d) return;
  renderJogador();
  const done = d.metas.filter((m) => m.status === "done").length;
  $("cq-today").textContent = d.metas.length ? `${done}/${d.metas.length}` : "";
  $("cq-metas").innerHTML = d.metas.map((m) => {
    const p = Math.max(0, Math.min(100, (m.value / Math.max(0.01, m.target)) * 100));
    const cls = m.status === "done" ? " done" : m.status === "failed" ? " bad" : "";
    return `<div class="cqmeta${cls}"><div class="cqrow"><span>${esc(m.text.replace("{t}", cqFmt(m.unit, m.target)))}</span><small>${esc(CQ_STATUS[m.status])}</small></div>
      <div class="bar${m.status === "failed" ? " bad" : ""}"><i style="width:${p}%"></i></div>
      <small class="cqv">${cqFmt(m.unit, m.value)}${m.kind === "max" ? " de no máximo " : " de "}${cqFmt(m.unit, m.target)}</small></div>`;
  }).join("") || '<div class="empty">Use o PC um pouco para ganhar metas.</div>';
  const got = d.conq.filter((c) => c.day);
  $("cq-count").textContent = `${got.length}/${d.conq.length}`;
  // galeria: sempre na mesma ordem (cada troféu tem o seu lugar na estante); as que faltam ficam apagadas
  $("cq-list").innerHTML = d.conq.map((c, i) => `<button class="cqt${c.day ? " got" : ""}" data-cq="${i}" aria-label="${esc(c.name)}${c.day ? "" : " (bloqueada)"}">
    ${trophy(c.tier, !!c.day)}<span>${esc(c.name)}</span></button>`).join("");
  if (!$("cqm").classList.contains("hidden")) cqmShow();
}
// trophy(): catalogo.js
// ---------------------------------------------------------------- modal: como ganhar, com setas para passear pela galeria
let cqmI = 0;
function cqmShow() {
  const list = state.conq?.conq || [], c = list[cqmI]; if (!c) return;
  const day = c.day && new Date(c.day + "T12:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
  $("cqm-n").textContent = `${cqmI + 1} de ${list.length}`;
  $("cqm-body").innerHTML = `<div class="cqm-tro${c.day ? " got " + c.tier : ""}">${trophy(c.tier, !!c.day)}</div>
    <h1>${esc(c.name)}</h1><div class="cqm-tier ${c.tier}">${CQ_TIER[c.tier]} · ${c.xp} XP</div>
    <div class="cqm-how"><small>COMO GANHAR</small>${esc(c.desc)}</div>
    ${c.day ? `<div class="cqm-st ok">Conquistada em ${day}</div>
      <button class="btn sm cqm-show" data-show="${esc(c.id)}">${(state.conq.equip?.show || []).includes(c.id) ? "Tirar da vitrine" : "Pôr na vitrine"}</button>`
      : `${c.goal > 1 ? `<div class="bar"><i style="width:${Math.min(100, (c.cur / c.goal) * 100)}%"></i></div><div class="cqm-st">${Math.floor(c.cur)} de ${c.goal}</div>` : '<div class="cqm-st">Ainda não conquistada</div>'}`}`;
  $("cqm-prev").disabled = cqmI === 0; $("cqm-next").disabled = cqmI === list.length - 1;
}
$("cq-list").onclick = (e) => { const b = e.target.closest("[data-cq]"); if (!b) return; buzz(8); cqmI = +b.dataset.cq; $("cqm").classList.remove("hidden"); cqmShow(); };
const cqmStep = (d) => { const n = (state.conq?.conq || []).length; if (cqmI + d < 0 || cqmI + d >= n) return; cqmI += d; buzz(6); cqmShow(); };
$("cqm-body").onclick = (e) => { const b = e.target.closest("[data-show]"); if (b) { buzz(8); toggleShow(b.dataset.show); } };
$("cqm-prev").onclick = () => cqmStep(-1);
$("cqm-next").onclick = () => cqmStep(1);
$("cqm-x").onclick = () => $("cqm").classList.add("hidden");
$("cqm").onclick = (e) => { if (e.target === $("cqm")) $("cqm").classList.add("hidden"); };
document.addEventListener("keydown", (e) => {
  if ($("cqm").classList.contains("hidden")) return;
  if (e.key === "Escape") $("cqm").classList.add("hidden");
  if (e.key === "ArrowLeft") cqmStep(-1);
  if (e.key === "ArrowRight") cqmStep(1);
});
// arrastar para o lado também troca de troféu
let cqmX = null;
$("cqm").addEventListener("touchstart", (e) => { cqmX = e.touches[0].clientX; }, { passive: true });
$("cqm").addEventListener("touchend", (e) => {
  if (cqmX === null) return;
  const dx = e.changedTouches[0].clientX - cqmX; cqmX = null;
  if (Math.abs(dx) > 50) cqmStep(dx < 0 ? 1 : -1);
});
const CQ_EVENT = {
  conq: (e) => `Conquista: ${e.name} (+${e.xp} XP)`,
  meta: (e) => `Meta cumprida: ${e.text.replace("{t}", cqFmt(e.unit, e.target))} (+${e.xp} XP)`,
  level: (e) => `Subiu para o nível ${e.level}!`,
  quest: (e) => `Desafio da semana: ${e.text.replace("{t}", cqFmt(e.unit, e.target))} (+${e.xp} XP)`,
  quests_all: (e) => `Os 3 desafios da semana! (+${e.xp} XP)`,
  boss: (e) => `${e.icon} ${e.name} derrotado! (+${e.xp} XP)`,
  reward: (e) => `Liberou ${KIND_LABEL[e.type] || ""}: ${e.name}`,
  x2: () => "Hoje é dia de XP em dobro!",
  freeze: (e) => `Um congelamento salvou a sua sequência (${e.left} sobrando)`,
  event: (e) => `Evento ${e.name} completo! Itens liberados (+${e.credits} créditos)`,
  duel_in: (e) => `${e.nick} desafiou você para um duelo (Jogador › Ranking)`,
};
function onConqEvent(e) {
  if (PREVIEW || !e) return;
  const msg = CQ_EVENT[e.kind]?.(e);
  if (!msg) return;
  toast(msg, "ok", false); snd(cqSound());
  if (prefs.vib && navigator.vibrate) try { navigator.vibrate([40, 50, 40, 50, 120]); } catch {}
}
