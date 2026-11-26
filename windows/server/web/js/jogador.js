"use strict";
// ---------------------------------------------------------------- Jogador: cartão do perfil, desafios e chefão da semana,
// vitrine (3 a 6 lugares), inventário (títulos, molduras, avatares, fundos, efeitos, cores, temas, sons), loja da semana
// com créditos e o evento sazonal. Tudo vem do PC (conquistas.py + colecao.py) em state.conq; o visual, de catalogo.js.
const WEEKDAY = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
const dayName = (d) => WEEKDAY[new Date(d + "T12:00").getDay()];
const dayShort = (d) => new Date(d + "T12:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" }).replace(".", "");
const dayBr = (d) => new Date(d + "T12:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
// nomes das recompensas (vale também para o título/moldura dos outros no ranking)
const rewardName = (id) => state.conq?.rewards?.find((r) => r.id === id)?.name || "";
const INV_KINDS = ["title", "frame", "avatar", "bg", "effect", "accent", "theme", "sound"];

// ---------------------------------------------------------------- sons das conquistas (recompensa "som")
Object.assign(SOUNDS, {
  s_fanfarra: [[523, 0.09], [659, 0.09], [784, 0.09], [1047, 0.22]],
  s_moeda: [[988, 0.06], [1319, 0.2]],
  s_arcade: [[660, 0.05], [880, 0.05], [1100, 0.05], [1320, 0.05], [1760, 0.12]],
  s_sino: [[1568, 0.12], [2093, 0.3]],
  s_vitoria: [[784, 0.1], [784, 0.06], [784, 0.06], [1047, 0.12], [988, 0.1], [1047, 0.28]],
  s_powerup: [[392, 0.04], [523, 0.04], [659, 0.04], [784, 0.04], [1047, 0.04], [1319, 0.04], [1568, 0.12]],
  s_laser: [[2400, 0.03], [1800, 0.03], [1300, 0.03], [900, 0.05], [600, 0.08]],
  s_harpa: [[523, 0.07], [659, 0.07], [784, 0.07], [988, 0.07], [1175, 0.07], [1568, 0.25]],
  s_natal: [[1319, 0.1], [1319, 0.1], [1319, 0.2], [1319, 0.1], [1319, 0.1], [1319, 0.2], [1319, 0.1], [1568, 0.1], [1047, 0.12], [1175, 0.1], [1319, 0.3]],
});
SOUNDS.s_bipe = SOUNDS.ok;
const cqSound = () => { const s = state.conq?.equip?.sound; return SOUNDS[s] ? s : "ok"; };

// ---------------------------------------------------------------- cor de destaque (vale no app inteiro, em cima do tema)
let accTry = null;
function applyAccent() {
  const eq = state.conq?.equip || {};
  if (accTry) return accentApply(document.documentElement, accTry.id, accTry.color);
  accentApply(document.documentElement, eq.accent, eq.color);
}

// ---------------------------------------------------------------- cartão do jogador (o mesmo desenho do ranking e do PC)
function myCard(over = {}) {
  const d = state.conq, eq = { ...(d.equip || {}), ...over };
  const nick = (typeof rankSt !== "undefined" && rankSt?.joined && rankSt.nick) || "";
  const got = d.conq.filter((c) => c.day);
  const show = (eq.show || []).map((id) => d.conq.find((c) => c.id === id)).filter(Boolean);
  const recent = [...got].sort((a, b) => (a.day < b.day ? 1 : -1)).slice(0, 3);
  const lg = typeof rankData !== "undefined" && rankData.league && !rankData.league.error ? rankData.league : null;
  return profileCard({ nick, level: d.level, title: rewardName(eq.title) || "Novato", frame: eq.frame, avatar: eq.avatar, effect: eq.effect,
    bg: eq.bg, bio: eq.bio, lay: eq.lay, sub: d.streak ? `🔥 ${d.streak} dia${d.streak > 1 ? "s" : ""}` : "",
    stats: [[d.level, "nível"], [d.week_xp, "XP na semana"], [d.best_streak, "recorde"], [`${got.length}/${d.conq.length}`, "troféus"]],
    show: show.length ? `<div class="shrow">${show.map((c) => `<div class="cqt got">${trophy(c.tier, true)}<span>${esc(c.name)}</span></div>`).join("")}</div>` : "",
    recent: recent.length ? recent.map((c) => `<span>🏆 ${esc(c.name)}</span>`).join("") : "",
    league: lg ? leagueTag(lg.league) : "" });
}

// ---------------------------------------------------------------- Resumo: cartão do jogador
function renderPlayer() {
  const d = state.conq, box = $("cq-lvl"); if (!d || !box) return;
  const pct = Math.max(0, Math.min(100, ((d.xp - d.lvl_lo) / Math.max(1, d.lvl_hi - d.lvl_lo)) * 100));
  const chips = [];
  if (d.mult > 1) chips.push(`<span class="pchip hot" title="Sequência de ${d.streak} dias">🔥 XP ×${String(d.mult).replace(".", ",")}</span>`);
  if (d.x2) chips.push('<span class="pchip x2">⚡ XP em dobro hoje</span>');
  chips.push(`<span class="pchip ice" title="Salva a sequência num dia perdido">${"❄".repeat(d.freezes) || "–"} ${d.freezes}/${d.freeze_max} congelamento${d.freeze_max > 1 ? "s" : ""}</span>`);
  if (d.credits) chips.push(`<span class="pchip"><i class="crcoin"></i>${d.credits.bal} créditos</span>`);
  const hints = [];
  if (d.freeze_next) hints.push(`próximo congelamento: mais ${d.freeze_next} dia${d.freeze_next > 1 ? "s" : ""} seguidos`);
  if (!d.x2 && d.x2_next) hints.push(`próximo XP em dobro: ${dayShort(d.x2_next)}`);
  $("cq-streak").textContent = d.streak ? `🔥 ${d.streak} dia${d.streak > 1 ? "s" : ""}` : "";
  box.innerHTML = `${myCard()}
    <small class="cqv" style="display:block;margin-top:8px">${d.xp - d.lvl_lo} / ${d.lvl_hi - d.lvl_lo} XP para o nível ${d.level + 1} · +${d.today_xp} XP hoje</small>
    <div class="bar"><i style="width:${pct}%"></i></div>
    <div class="pchips">${chips.join("")}</div>
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
function renderBoss(b) {
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

// ---------------------------------------------------------------- Vitrine (3 lugares, 4 no nível 15, 5 no 30, 6 no 50)
const SHOW_LV = [[3, 1], [4, 15], [5, 30], [6, 50]];
function renderShowcase() {
  const d = state.conq, box = $("sh-body"); if (!d || !box) return;
  const show = d.equip?.show || [], list = d.conq, max = d.show_max || 3;
  $("sh-n").textContent = `${show.length}/${max}`;
  const slots = [];
  for (let i = 0; i < 6; i++) {
    const c = list.find((x) => x.id === show[i]);
    if (i >= max) { slots.push(`<div class="shslot lock">🔒 nível ${SHOW_LV.find(([n]) => n === i + 1)[1]}</div>`); continue; }
    slots.push(c ? `<div><button class="cqt got" data-cq="${list.indexOf(c)}">${trophy(c.tier, true)}<span>${esc(c.name)}</span></button>
      ${show.length > 1 ? `<div class="shmv">${i > 0 ? `<button data-mv="${i}" data-to="${i - 1}" aria-label="Mover para a esquerda">◀</button>` : ""}${i < show.length - 1 ? `<button data-mv="${i}" data-to="${i + 1}" aria-label="Mover para a direita">▶</button>` : ""}</div>` : ""}</div>`
      : '<div class="shslot">vazio</div>');
  }
  box.innerHTML = `<div class="shrow">${slots.join("")}</div><div class="sub" style="white-space:normal;margin-top:6px">Toque num troféu que você já ganhou e escolha <b>Pôr na vitrine</b>; as setas mudam a ordem. Quem abrir o seu perfil no ranking vê estes.</div>`;
  box.querySelectorAll("[data-cq]").forEach((b) => (b.onclick = () => { buzz(8); cqmI = +b.dataset.cq; $("cqm").classList.remove("hidden"); cqmShow(); }));
  box.querySelectorAll("[data-mv]").forEach((b) => (b.onclick = () => {
    buzz(8); const s = [...show], [x] = s.splice(+b.dataset.mv, 1); s.splice(+b.dataset.to, 0, x); sendShow(s, "");
  }));
}
async function sendShow(ids, msg) {
  try { onConq(await send("conq.equip", { kind: "show", ids })); if (msg) toast(msg, "ok"); } catch (e) { toast(e.message, "bad"); }
}
function toggleShow(id) {
  const show = [...(state.conq?.equip?.show || [])], max = state.conq?.show_max || 3;
  const i = show.indexOf(id);
  if (i >= 0) show.splice(i, 1);
  else { if (show.length >= max) return toast(`A vitrine tem ${max} lugares: tire um antes`, "bad"); show.push(id); }
  sendShow(show, i >= 0 ? "Saiu da vitrine" : "Na vitrine");
}

// ---------------------------------------------------------------- Recompensas (inventário)
function isOn(r) {
  const eq = state.conq?.equip || {};
  return r.kind === "theme" ? r.id === `${prefs.skin}:${prefs.theme}` : eq[r.kind] === r.id;
}
function ivItem(r) {
  const d = state.conq, on = isOn(r);
  const st = on ? "em uso" : r.got ? "" : "🔒 " + reqText(r);
  return `<button class="ivit rar-${r.rarity}${r.got ? "" : " lock tryable"}${on ? " on" : ""}" data-rw="${esc(r.id)}" title="${esc(RARITY[r.rarity])}">
    ${itemPreview(r, d.level, d.equip)}${r.kind === "title" || r.kind === "effect" ? "" : `<span>${esc(r.name)}</span>`}
    ${r.kind === "effect" ? `<span>${esc(r.name)}</span>` : ""}<small>${esc(st)}</small></button>`;
}
function renderInv() {
  const d = state.conq; if (!d || !$("iv-title")) return;
  for (const kind of INV_KINDS) {
    const box = $("iv-" + kind); if (!box) continue;
    const list = d.rewards.filter((r) => r.kind === kind);
    $("iv-n-" + kind).textContent = `${list.filter((r) => r.got).length}/${list.length}`;
    box.innerHTML = list.map(ivItem).join("");
  }
  const next = d.rewards.filter((r) => !r.got && r.req).sort((a, b) => a.req - b.req).slice(0, 5);
  $("iv-next").innerHTML = next.length ? `<div class="ivnext">${next.map((r) => `<div><b>Nível ${r.req}</b><span>${esc(r.name)}</span><small>${KIND_LABEL[r.kind]}</small></div>`).join("")}</div>`
    : '<div class="empty">Você liberou tudo o que o nível dá. Lenda!</div>';
  if ($("iv-sets") && d.sets) {
    $("iv-n-sets").textContent = `${d.sets.filter((s) => s.done).length}/${d.sets.length}`;
    $("iv-sets").innerHTML = [...d.sets].sort((a, b) => !!a.done - !!b.done || b.have / b.items.length - a.have / a.items.length)
      .map((s) => setCard(s, d, "data-rw")).join("");
  }
  $("sw-cqpc").classList.toggle("on", d.pc_overlay !== false);
  renderPfEdit();
}
// perfil: frase, blocos (ordem e quais aparecem) e a cor livre
function renderPfEdit() {
  const d = state.conq, box = $("pf-edit"); if (!box) return;
  const eq = d.equip || {}, lay = eq.lay || [], free = d.rewards.find((r) => r.id === "a_livre")?.got;
  const all = [...lay, ...Object.keys(LAY_LABEL).filter((b) => !lay.includes(b))];
  if (document.activeElement?.id === "pf-bio") return;     // não apaga o que está digitando
  box.innerHTML = `<div class="set" style="display:block"><label>Frase<small>Aparece no seu perfil e no ranking (até 60 letras)</small></label>
      <div class="brow"><input class="fi" id="pf-bio" maxlength="60" value="${esc(eq.bio || "")}" placeholder="Ex.: só mais uma partida" autocomplete="off"><button class="btn" id="pf-bio-ok">Salvar</button></div></div>
    <div class="set" style="display:block"><label>Blocos do perfil<small>Toque para mostrar ou esconder; as setas mudam a ordem</small></label>
      <div class="pflay">${all.map((b) => { const i = lay.indexOf(b); return `<div class="pflb${i >= 0 ? " on" : ""}"><button class="chip2${i >= 0 ? " on" : ""}" data-lt="${b}">${LAY_LABEL[b]}</button>
        ${i > 0 ? `<button class="btn sm" data-lu="${b}" aria-label="Subir">▲</button>` : ""}</div>`; }).join("")}</div></div>
    ${free ? `<div class="set"><label>Cor livre<small>Vale quando a cor de destaque é "Cor livre"</small></label><input type="color" id="pf-color" value="${esc(eq.color || "#4c8dff")}"></div>` : ""}`;
  const saveP = async (p, msg) => { try { onConq(await send("conq.profile", p)); if (msg) toast(msg, "ok"); } catch (e) { toast(e.message, "bad"); } };
  $("pf-bio-ok").onclick = () => { buzz(8); $("pf-bio").blur(); saveP({ bio: $("pf-bio").value }, "Frase salva"); };
  $("pf-bio").onkeydown = (e) => { if (e.key === "Enter") $("pf-bio-ok").click(); };
  box.querySelectorAll("[data-lt]").forEach((b) => (b.onclick = () => {
    buzz(8); const x = b.dataset.lt, l = lay.includes(x) ? lay.filter((y) => y !== x) : [...lay, x]; saveP({ lay: l });
  }));
  box.querySelectorAll("[data-lu]").forEach((b) => (b.onclick = () => {
    buzz(8); const l = [...lay], i = l.indexOf(b.dataset.lu); [l[i - 1], l[i]] = [l[i], l[i - 1]]; saveP({ lay: l });
  }));
  if ($("pf-color")) $("pf-color").onchange = () => saveP({ color: $("pf-color").value }, eq.accent === "a_livre" ? "Cor salva" : "Cor salva: equipe a Cor livre em Cor de destaque");
}
function themeSwatch(id) { return themeVariant(id)?.[2] || "var(--p3)"; }
// tema liberado? (variantes com cadeado só valem com a recompensa)
function themeLocked(skin, variant) {
  const r = state.conq?.rewards?.find((x) => x.id === `${skin}:${variant}`);
  return !!r && !r.got;
}

// ---------------------------------------------------------------- Loja: créditos, itens da semana e evento
function renderLoja() {
  const d = state.conq; if (!d || !$("lj-shop")) return;
  const c = d.credits, R = c.rules;
  $("lj-bal").innerHTML = `<div class="crbal"><b><i class="crcoin"></i>${c.bal}</b><small>créditos · +${c.today} hoje · +${c.week} na semana</small></div>
    <div class="crhow">Ganha: meta do dia <b>${R.meta}</b> (as 3: +${R.metas3}) · desafio da semana <b>${R.quest}</b> · chefão <b>${R.boss}</b> · cada nível <b>${R.level}</b> ·
      a cada 7 dias seguidos <b>${R.streak7}</b> · conquista <b>${R.conq.bronze}/${R.conq.prata}/${R.conq.ouro}</b> · evento <b>${R.event}</b>${R.set ? ` · conjunto <b>${R.set.raro}–${R.set.lendario}</b>` : ""}</div>`;
  const left = Math.max(0, Math.round((new Date(d.shop.end + "T23:59") - Date.now()) / 86400000));
  $("lj-left").textContent = left ? `troca em ${left} dia${left > 1 ? "s" : ""}` : "troca amanhã";
  $("lj-shop").innerHTML = d.shop.items.length ? `<div class="shopgrid">${d.shop.items.map((id) => {
    const r = d.rewards.find((x) => x.id === id); if (!r) return "";
    return `<button class="shopit rar-${r.rarity}${r.got ? " own" : c.bal < r.price ? " poor" : ""}" data-shop="${esc(id)}">
      ${itemPreview(r, d.level, d.equip)}<span class="shn">${esc(r.name)}</span><span class="rartag">${RARITY[r.rarity]} · ${KIND_LABEL[r.kind]}</span>
      <span class="shp">${r.got ? "já é seu" : `<i class="crcoin"></i>${r.price}`}</span></button>`;
  }).join("")}</div><div class="shopend">Itens da loja não saem por nível. A cada segunda chegam 4 novos (pelo menos 1 raro ou melhor).</div>`
    : '<div class="empty">Você já tem tudo o que a loja vende!</div>';
  renderEvent();
}
function renderEvent() {
  const d = state.conq, box = $("lj-ev"); if (!box) return;
  const e = d.event;
  if (!e) { box.innerHTML = '<div class="empty">Nenhum evento à vista.</div>'; return; }
  const fmtV = (v) => (e.kind === "foco" ? humanDur(v * 60) : String(v));
  const items = e.items.map((id) => d.rewards.find((r) => r.id === id)).filter(Boolean);
  const pct = Math.min(100, (e.value / Math.max(1, e.target)) * 100);
  const days = Math.round((new Date((e.live ? e.end : e.start) + "T12:00") - Date.now()) / 86400000);
  box.innerHTML = `<div class="evcard"><div class="evicon" aria-hidden="true">${e.icon}</div><div class="evinfo"><b>${esc(e.name)}</b>
      <small>${e.live ? `até ${dayBr(e.end)} · faltam ${Math.max(0, days)} dia${days === 1 ? "" : "s"}` : `começa em ${dayBr(e.start)} (daqui a ${Math.max(0, days)} dia${days === 1 ? "" : "s"})`}</small>
      <div style="margin-top:6px">${esc(e.text)}</div>
      ${e.live ? `<div class="bar"><i style="width:${e.done ? 100 : pct}%"></i></div><small class="${e.done ? "evdone" : ""}">${e.done ? "Completo! Itens liberados." : `${fmtV(e.value)} de ${fmtV(e.target)}`}</small>` : ""}</div></div>
    <div class="evitems">${items.map((r) => `<span class="rar-${r.rarity}" style="border-color:var(--rar)">${r.got ? "✓ " : ""}${esc(r.name)} · ${KIND_LABEL[r.kind]}</span>`).join("")}</div>
    <div class="evlist">${(d.events || []).map((x) => `<span class="${x.done ? "ok" : ""}">${x.icon} ${esc(x.name)}${x.done ? " ✓" : ""}</span>`).join("")}</div>
    <div class="sub" style="white-space:normal;margin-top:6px">Os itens de evento só saem durante o evento. Perdeu? Ele volta no ano seguinte.</div>`;
}

// ---------------------------------------------------------------- item: equipar, experimentar e comprar
let tryT = null;
function tryStop() {
  clearTimeout(tryT); tryT = null; accTry = null;
  document.querySelector(".trybar")?.remove();
  applyTheme(); applyAccent();
}
// tema ou cor: vale no app inteiro por 10 s
function tryApp(r) {
  tryStop();
  if (r.kind === "theme") { const [s, v] = r.id.split(":"); document.documentElement.dataset.skin = s; document.documentElement.dataset.theme = v; }
  else { accTry = { id: r.id, color: state.conq.equip?.color }; applyAccent(); }
  const bar = document.createElement("div");
  bar.className = "trybar"; bar.innerHTML = `<span>Experimentando <b>${esc(r.name)}</b> · 10 s</span><button>voltar</button>`;
  bar.querySelector("button").onclick = () => { buzz(8); tryStop(); };
  document.body.appendChild(bar);
  tryT = setTimeout(tryStop, 10000);
}
// janela do item: prévia grande, como liberar, experimentar/comprar
function itemModal(r) {
  const d = state.conq, profKinds = ["title", "frame", "avatar", "bg", "effect"];
  const prev = profKinds.includes(r.kind) ? myCard({ [r.kind]: r.id })
    : r.kind === "theme" ? `<div class="thm" data-skin="${esc(r.id.split(":")[0])}" data-theme="${esc(r.id.split(":")[1])}" style="padding:14px;border-radius:var(--r)">
        <span class="thn" style="font-family:var(--display);font-size:22px;color:var(--p)">${esc(r.name)}</span><div class="bar" style="margin-top:8px"><i style="width:62%"></i></div></div>`
    : `<div style="display:grid;place-items:center;padding:14px">${itemPreview(r, d.level, d.equip)}</div>`;
  const inShop = r.shop && d.shop.items.includes(r.id);
  $("pfm").classList.remove("hidden");
  $("pfm-body").innerHTML = `<div class="cqm-tier" style="color:var(--rar)"><span class="rar-${r.rarity}"><span class="rartag">${RARITY[r.rarity]}</span></span> ${esc(KIND_LABEL[r.kind])}${r.anim ? " · animado" : ""}</div>
    <h1 style="margin:6px 0 10px">${esc(r.name)}</h1>${prev}
    <div class="cqm-how" style="margin-top:10px"><small>COMO LIBERAR</small>${r.got ? "Já é seu." : esc(r.req ? `Chegue ao nível ${r.req}` : r.shop ? `Loja da semana: ${r.price} créditos${inShop ? "" : " (não está na loja agora; ela muda toda segunda)"}` : r.event ? `Complete o evento ${EVENT_NAME[r.event] || r.event}` : r.set ? `Complete o conjunto ${SET_NAME[r.set] || r.set} (Recompensas › Conjuntos)` : `Ganhe a conquista ${r.conq}`)}</div>
    <div class="brow pfbtns">${r.got ? `<button class="btn" id="im-eq">${r.kind === "theme" ? "Usar este tema" : "Equipar"}</button>`
      : `${["theme", "accent"].includes(r.kind) ? '<button class="btn" id="im-try">Experimentar 10 s</button>' : ""}${r.kind === "sound" ? '<button class="btn" id="im-try">Ouvir</button>' : ""}
         ${inShop ? `<button class="btn" id="im-buy" ${d.credits.bal < r.price ? "disabled" : ""}>Comprar · ${r.price} créditos</button>` : ""}`}</div>
    ${inShop && d.credits.bal < r.price ? `<small class="cqv">Faltam ${r.price - d.credits.bal} créditos.</small>` : ""}`;
  const close = () => $("pfm").classList.add("hidden");
  if ($("im-eq")) $("im-eq").onclick = () => { buzz(8); close(); equipItem(r); };
  if ($("im-try")) $("im-try").onclick = () => { buzz(8); if (r.kind === "sound") return snd(r.id); close(); tryApp(r); };
  if ($("im-buy")) $("im-buy").onclick = async () => {
    buzz(8);
    try { onConq(await send("conq.buy", { id: r.id })); snd(cqSound()); toast(`${r.name} é seu!`, "ok"); close(); }
    catch (e) { toast(e.message, "bad"); }
  };
}
async function equipItem(r) {
  if (r.kind === "theme") { const [skin, v] = r.id.split(":"); tryStop(); pickTheme(skin, v); renderInv(); return toast(`Tema: ${r.name}`, "ok"); }
  try { onConq(await send("conq.equip", { kind: r.kind, id: r.id })); if (r.kind !== "sound") toast(`${r.name} equipado`, "ok"); }
  catch (err) { toast(err.message, "bad"); }
}
document.addEventListener("click", (e) => {
  const b = e.target.closest(".ivit[data-rw], .shopit[data-shop]"); if (!b) return;
  const d = state.conq, r = d?.rewards.find((x) => x.id === (b.dataset.rw || b.dataset.shop)); if (!r) return;
  buzz(8);
  if (r.kind === "sound") snd(r.id);
  if (b.dataset.shop || !r.got) return itemModal(r);
  equipItem(r);
});
$("sw-cqpc").onclick = async () => {
  buzz(8);
  try { onConq(await send("conq.cfg", { overlay: !(state.conq?.pc_overlay !== false) })); } catch (e) { toast(e.message, "bad"); }
};

// tudo da seção Jogador (chamado pelo renderConq)
function renderJogador() {
  applyAccent();
  renderPlayer(); renderQuests(); renderShowcase(); renderInv(); renderLoja();
  const locks = state.conq.rewards.filter((r) => r.kind === "theme" && r.got).length;
  if (locks !== renderJogador.themes) { renderJogador.themes = locks; renderThemePicker(); }   // cadeados dos temas
}
