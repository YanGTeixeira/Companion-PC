"use strict";
// ---------------------------------------------------------------- Conquistas: nível, metas do dia e conquistas
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
  const pct = Math.max(0, Math.min(100, ((d.xp - d.lvl_lo) / Math.max(1, d.lvl_hi - d.lvl_lo)) * 100));
  $("cq-streak").textContent = d.streak ? `sequência: ${d.streak} dia${d.streak > 1 ? "s" : ""}` : "";
  $("cq-lvl").innerHTML = `<div class="cqlvl"><b>${d.level}</b><div><div>Nível ${d.level}</div>
      <small>${d.xp - d.lvl_lo} / ${d.lvl_hi - d.lvl_lo} XP para o nível ${d.level + 1}</small></div></div>
    <div class="bar"><i style="width:${pct}%"></i></div>
    <div class="dayg cqnums"><div><b>+${d.today_xp}</b><small>XP hoje</small></div><div><b>${d.week_xp}</b><small>XP na semana</small></div>
      <div><b>${d.streak}</b><small>dias seguidos (2 metas)</small></div><div><b>${d.best_streak}</b><small>recorde</small></div></div>`;
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
// troféu em SVG; a cor vem do degradê da raridade (index.html), ou apagado se ainda não ganhou
function trophy(tier, got) {
  const f = got ? `url(#tg-${tier})` : "var(--p4)";
  return `<svg class="tro ${got ? tier : "off"}" viewBox="0 0 64 64" aria-hidden="true">
    <path d="M18 14h-7v3a10 10 0 0 0 10 10M46 14h7v3a10 10 0 0 1-10 10" fill="none" stroke="${f}" stroke-width="4" stroke-linecap="round"/>
    <path d="M18 7h28v15a14 14 0 0 1-28 0z" fill="${f}"/>
    <path d="M29 35h6v8h-6z" fill="${f}"/><path d="M23 50l3-7h12l3 7z" fill="${f}"/><rect x="18" y="50" width="28" height="7" rx="1.5" fill="${f}"/>
    ${got ? '<path d="M24 11v9a8 8 0 0 0 4 7" fill="none" stroke="#fff" stroke-opacity=".45" stroke-width="2.5" stroke-linecap="round"/>'
      : '<text x="32" y="25" text-anchor="middle" font-size="14" font-family="sans-serif" fill="var(--bg)">?</text>'}</svg>`;
}
// ---------------------------------------------------------------- modal: como ganhar, com setas para passear pela galeria
let cqmI = 0;
function cqmShow() {
  const list = state.conq?.conq || [], c = list[cqmI]; if (!c) return;
  const day = c.day && new Date(c.day + "T12:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
  $("cqm-n").textContent = `${cqmI + 1} de ${list.length}`;
  $("cqm-body").innerHTML = `<div class="cqm-tro${c.day ? " got " + c.tier : ""}">${trophy(c.tier, !!c.day)}</div>
    <h1>${esc(c.name)}</h1><div class="cqm-tier ${c.tier}">${CQ_TIER[c.tier]} · ${c.xp} XP</div>
    <div class="cqm-how"><small>COMO GANHAR</small>${esc(c.desc)}</div>
    ${c.day ? `<div class="cqm-st ok">Conquistada em ${day}</div>`
      : `${c.goal > 1 ? `<div class="bar"><i style="width:${Math.min(100, (c.cur / c.goal) * 100)}%"></i></div><div class="cqm-st">${Math.floor(c.cur)} de ${c.goal}</div>` : '<div class="cqm-st">Ainda não conquistada</div>'}`}`;
  $("cqm-prev").disabled = cqmI === 0; $("cqm-next").disabled = cqmI === list.length - 1;
}
$("cq-list").onclick = (e) => { const b = e.target.closest("[data-cq]"); if (!b) return; buzz(8); cqmI = +b.dataset.cq; $("cqm").classList.remove("hidden"); cqmShow(); };
const cqmStep = (d) => { const n = (state.conq?.conq || []).length; if (cqmI + d < 0 || cqmI + d >= n) return; cqmI += d; buzz(6); cqmShow(); };
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
function onConqEvent(e) {
  if (PREVIEW || !e) return;
  const msg = e.kind === "conq" ? `Conquista: ${e.name} (+${e.xp} XP)`
    : e.kind === "meta" ? `Meta cumprida: ${e.text.replace("{t}", cqFmt(e.unit, e.target))} (+${e.xp} XP)`
    : e.kind === "level" ? `Subiu para o nível ${e.level}!` : "";
  if (!msg) return;
  toast(msg, "ok"); snd("ok");
  if (prefs.vib && navigator.vibrate) try { navigator.vibrate([40, 50, 40, 50, 120]); } catch {}
}
