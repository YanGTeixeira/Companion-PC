"use strict";
// ---------------------------------------------------------------- Jogador (1.18): cartão, desafios e chefão da semana,
// vitrine e recompensas (título, moldura, som e temas). Tudo vem do PC (conquistas.py) em state.conq.
const KIND_LABEL = { title: "título", frame: "moldura", sound: "som", theme: "tema" };
const WEEKDAY = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
const dayName = (d) => WEEKDAY[new Date(d + "T12:00").getDay()];
const dayShort = (d) => new Date(d + "T12:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" }).replace(".", "");
// nomes das recompensas (vale também para o título/moldura dos outros no ranking)
const rewardName = (id) => state.conq?.rewards?.find((r) => r.id === id)?.name || "";
const reqText = (r) => (r.req ? `nível ${r.req}` : `conquista ${r.conq}`);

// selo do nível com a moldura equipada (frame: id da recompensa, ex. "f_ouro")
function badge(level, frame, size = "") {
  const f = /^f_[a-z]+$/.test(frame || "") ? frame : "f_simples";
  return `<span class="badge ${f}${size ? " " + size : ""}"><b>${+level || 1}</b></span>`;
}

// ---------------------------------------------------------------- sons das conquistas (recompensa "som")
Object.assign(SOUNDS, {
  s_fanfarra: [[523, 0.09], [659, 0.09], [784, 0.09], [1047, 0.22]],
  s_moeda: [[988, 0.06], [1319, 0.2]],
  s_arcade: [[660, 0.05], [880, 0.05], [1100, 0.05], [1320, 0.05], [1760, 0.12]],
  s_sino: [[1568, 0.12], [2093, 0.3]],
  s_vitoria: [[784, 0.1], [784, 0.06], [784, 0.06], [1047, 0.12], [988, 0.1], [1047, 0.28]],
});
SOUNDS.s_bipe = SOUNDS.ok;
const cqSound = () => { const s = state.conq?.equip?.sound; return SOUNDS[s] ? s : "ok"; };

// ---------------------------------------------------------------- Resumo: cartão do jogador
function renderPlayer() {
  const d = state.conq, box = $("cq-lvl"); if (!d || !box) return;
  const pct = Math.max(0, Math.min(100, ((d.xp - d.lvl_lo) / Math.max(1, d.lvl_hi - d.lvl_lo)) * 100));
  const eq = d.equip || {}, nick = (typeof rankSt !== "undefined" && rankSt?.joined && rankSt.nick) || "";
  const chips = [];
  if (d.mult > 1) chips.push(`<span class="pchip hot" title="Sequência de ${d.streak} dias">🔥 XP ×${String(d.mult).replace(".", ",")}</span>`);
  if (d.x2) chips.push('<span class="pchip x2">⚡ XP em dobro hoje</span>');
  chips.push(`<span class="pchip ice" title="Salva a sequência num dia perdido">${"❄".repeat(d.freezes) || "–"} ${d.freezes}/${d.freeze_max} congelamento${d.freeze_max > 1 ? "s" : ""}</span>`);
  const hints = [];
  if (d.freeze_next) hints.push(`próximo congelamento: mais ${d.freeze_next} dia${d.freeze_next > 1 ? "s" : ""} seguidos`);
  if (!d.x2 && d.x2_next) hints.push(`próximo XP em dobro: ${dayShort(d.x2_next)}`);
  $("cq-streak").textContent = d.streak ? `🔥 ${d.streak} dia${d.streak > 1 ? "s" : ""}` : "";
  box.innerHTML = `<div class="pcard">${badge(d.level, eq.frame, "big")}
      <div class="pinfo"><div class="ptitle">${esc(rewardName(eq.title) || "Novato")}</div>
        <div class="pnick">${nick ? esc(nick) + " · " : ""}nível ${d.level}</div>
        <small>${d.xp - d.lvl_lo} / ${d.lvl_hi - d.lvl_lo} XP para o nível ${d.level + 1}</small></div></div>
    <div class="bar"><i style="width:${pct}%"></i></div>
    <div class="pchips">${chips.join("")}</div>
    <div class="dayg cqnums"><div><b>+${d.today_xp}</b><small>XP hoje</small></div><div><b>${d.week_xp}</b><small>XP na semana</small></div>
      <div><b>${d.streak}</b><small>dias seguidos (2 metas)</small></div><div><b>${d.best_streak}</b><small>recorde</small></div></div>
    ${hints.length ? `<small class="phint">${esc(hints.join(" · "))}</small>` : ""}`;
}

// ---------------------------------------------------------------- Desafios e chefão da semana
function renderQuests() {
  const w = state.conq?.week, box = $("qs-list"); if (!box) return;
  if (!w) { box.innerHTML = '<div class="empty">Os desafios começam na próxima semana.</div>'; $("bs-body").innerHTML = ""; return; }
  const left = Math.round((new Date(w.end + "T23:59") - Date.now()) / 86400000);
  $("qs-left").textContent = left > 0 ? `termina em ${left} dia${left > 1 ? "s" : ""}` : "último dia";
  const done = w.quests.filter((q) => q.day).length;
  box.innerHTML = w.quests.map((q) => {
    const p = Math.max(0, Math.min(100, (q.value / Math.max(0.01, q.target)) * 100));
    const st = q.day ? `FEITO · ${dayName(q.day)}` : q.status === "failed" ? "não deu" : `+${q.xp} XP`;
    return `<div class="cqmeta${q.day ? " done" : q.status === "failed" ? " bad" : ""}"><div class="cqrow"><span>${esc(q.text.replace("{t}", cqFmt(q.unit, q.target)))}</span><small>${st}</small></div>
      <div class="bar"><i style="width:${p}%"></i></div><small class="cqv">${cqFmt(q.unit, q.value)} de ${cqFmt(q.unit, q.target)}</small></div>`;
  }).join("") + `<div class="qsall${w.all ? " done" : ""}">${w.all ? `Os 3 desafios feitos: +${w.all_xp} XP de bônus` : `Faça os 3 (${done}/3) para ganhar +${w.all_xp} XP de bônus`}</div>`;
  renderBoss(w.boss, w);
}
function renderBoss(b, w) {
  const box = $("bs-body"); if (!box) return;
  const left = Math.max(0, b.hp - b.dmg), pct = Math.max(0, Math.min(100, (left / b.hp) * 100));
  $("bs-hp").textContent = b.dead ? "derrotado" : `${left} / ${b.hp} HP`;
  box.innerHTML = `<div class="boss${b.dead ? " dead" : ""}"><div class="bicon" aria-hidden="true">${b.icon}</div>
      <div class="binfo"><b>${esc(b.name)}</b>
        <div class="bar hp"><i style="width:${pct}%"></i></div>
        <small>${b.dead ? `Derrotado na ${dayName(b.dead)}! +${b.xp} XP` : `Vale +${b.xp} XP · dano hoje: ${b.today}`}</small></div></div>
    <div class="bhow">Cada <b>minuto de foco</b> tira 1 de vida, cada <b>meta cumprida</b> tira 15 e cada <b>vitória</b> tira 20.
      Derrote até domingo, senão ele foge. Um chefão novo chega toda segunda.</div>`;
}

// ---------------------------------------------------------------- Vitrine (até 3 troféus; aparece no seu perfil do ranking)
function renderShowcase() {
  const d = state.conq, box = $("sh-body"); if (!d || !box) return;
  const show = d.equip?.show || [], list = d.conq;
  $("sh-n").textContent = `${show.length}/3`;
  box.innerHTML = `<div class="shrow">${[0, 1, 2].map((i) => {
    const c = list.find((x) => x.id === show[i]);
    return c ? `<button class="cqt got" data-cq="${list.indexOf(c)}">${trophy(c.tier, true)}<span>${esc(c.name)}</span></button>`
      : '<div class="shslot">vazio</div>';
  }).join("")}</div><div class="sub" style="white-space:normal;margin-top:6px">Toque num troféu que você já ganhou e escolha <b>Pôr na vitrine</b>. Quem abrir o seu perfil no ranking vê estes.</div>`;
  box.querySelectorAll("[data-cq]").forEach((b) => (b.onclick = () => { buzz(8); cqmI = +b.dataset.cq; $("cqm").classList.remove("hidden"); cqmShow(); }));
}
async function toggleShow(id) {
  const show = [...(state.conq?.equip?.show || [])];
  const i = show.indexOf(id);
  if (i >= 0) show.splice(i, 1);
  else { if (show.length >= 3) return toast("A vitrine tem 3 lugares: tire um antes", "bad"); show.push(id); }
  try { onConq(await send("conq.equip", { kind: "show", ids: show })); toast(i >= 0 ? "Saiu da vitrine" : "Na vitrine", "ok"); }
  catch (e) { toast(e.message, "bad"); }
}

// ---------------------------------------------------------------- Recompensas
function renderInv() {
  const d = state.conq; if (!d || !$("iv-title")) return;
  const eq = d.equip || {};
  for (const kind of ["title", "frame", "sound", "theme"]) {
    const list = d.rewards.filter((r) => r.kind === kind);
    $("iv-n-" + kind).textContent = `${list.filter((r) => r.got).length}/${list.length}`;
    $("iv-" + kind).innerHTML = list.map((r) => {
      const on = kind === "theme" ? r.id === `${prefs.skin}:${prefs.theme}` : eq[kind] === r.id;
      const prev = kind === "title" ? `<span class="ivtitle">${esc(r.name)}</span>`
        : kind === "frame" ? badge(d.level, r.id, "sm")
        : kind === "sound" ? '<span class="ivplay" aria-hidden="true">▶</span>'
        : `<span class="ivsw" style="background:${themeSwatch(r.id)}"></span>`;
      return `<button class="ivit${r.got ? "" : " lock"}${on ? " on" : ""}" data-rw="${esc(r.id)}" data-kind="${kind}">${prev}
        ${kind === "title" ? "" : `<span>${esc(r.name)}</span>`}<small>${on ? "em uso" : r.got ? "" : "🔒 " + esc(reqText(r))}</small></button>`;
    }).join("");
  }
  const next = d.rewards.filter((r) => !r.got && r.req).sort((a, b) => a.req - b.req).slice(0, 4);
  $("iv-next").innerHTML = next.length ? `<div class="ivnext">${next.map((r) => `<div><b>Nível ${r.req}</b><span>${esc(r.name)}</span><small>${KIND_LABEL[r.kind]}</small></div>`).join("")}</div>`
    : '<div class="empty">Você liberou tudo o que o nível dá. Lenda!</div>';
  $("sw-cqpc").classList.toggle("on", d.pc_overlay !== false);
}
function themeSwatch(id) {
  const [skin, v] = id.split(":");
  return THEMES.find((t) => t.id === skin)?.variants.find((x) => x[0] === v)?.[2] || "var(--p3)";
}
// tema liberado? (variantes com cadeado só valem com a recompensa)
function themeLocked(skin, variant) {
  const r = state.conq?.rewards?.find((x) => x.id === `${skin}:${variant}`);
  return !!r && !r.got;
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest(".ivit[data-rw]"); if (!b) return;
  const d = state.conq, r = d?.rewards.find((x) => x.id === b.dataset.rw); if (!r) return;
  buzz(8);
  if (r.kind === "sound") snd(r.id);
  if (!r.got) return toast(`Libera com ${reqText(r)}`, "bad");
  if (r.kind === "theme") { const [skin, v] = r.id.split(":"); pickTheme(skin, v); renderInv(); return toast(`Tema: ${r.name}`, "ok"); }
  try { onConq(await send("conq.equip", { kind: r.kind, id: r.id })); if (r.kind !== "sound") toast(`${r.name} equipado`, "ok"); }
  catch (err) { toast(err.message, "bad"); }
});
$("sw-cqpc").onclick = async () => {
  buzz(8);
  try { onConq(await send("conq.cfg", { overlay: !(state.conq?.pc_overlay !== false) })); } catch (e) { toast(e.message, "bad"); }
};

// tudo da seção Jogador (chamado pelo renderConq)
function renderJogador() {
  renderPlayer(); renderQuests(); renderShowcase(); renderInv();
  const locks = state.conq.rewards.filter((r) => r.kind === "theme" && r.got).length;
  if (locks !== renderJogador.themes) { renderJogador.themes = locks; renderThemePicker(); }   // cadeados dos temas
}
