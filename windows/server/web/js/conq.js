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
  const got = d.conq.filter((c) => c.day).sort((a, b) => (b.day > a.day ? 1 : -1)), left = d.conq.filter((c) => !c.day);
  $("cq-count").textContent = `${got.length}/${d.conq.length}`;
  const item = (c) => `<div class="cqc ${c.tier}${c.day ? " got" : ""}"><div class="cqrow"><b>${esc(c.name)}</b><small>${CQ_TIER[c.tier]}</small></div>
    <small>${esc(c.desc)}</small>
    ${c.day ? `<small class="cqv">${new Date(c.day + "T12:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} · +${c.xp} XP</small>`
      : c.goal > 1 ? `<div class="bar"><i style="width:${Math.min(100, (c.cur / c.goal) * 100)}%"></i></div><small class="cqv">${Math.floor(c.cur)} / ${c.goal}</small>` : ""}</div>`;
  $("cq-list").innerHTML = [...got, ...left].map(item).join("");
}
function onConqEvent(e) {
  if (PREVIEW || !e) return;
  const msg = e.kind === "conq" ? `Conquista: ${e.name} (+${e.xp} XP)`
    : e.kind === "meta" ? `Meta cumprida: ${e.text.replace("{t}", cqFmt(e.unit, e.target))} (+${e.xp} XP)`
    : e.kind === "level" ? `Subiu para o nível ${e.level}!` : "";
  if (!msg) return;
  toast(msg, "ok"); snd("ok");
  if (prefs.vib && navigator.vibrate) try { navigator.vibrate([40, 50, 40, 50, 120]); } catch {}
}
