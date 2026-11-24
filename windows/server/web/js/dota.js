"use strict";
// ---------------------------------------------------------------- Dota 2: draft e build (estatísticas do STRATZ, servidor: dota_draft.py)
// O GSI do jogador não mostra o time inimigo: você marca os heróis aqui. A build abre sozinha com o herói do GSI.
// Fila: antes da partida você escolhe posição e heróis preferidos (plano guardado no PC, igual em todos os aparelhos);
// o plano zera quando a partida termina.
const DOTA_POS = [[1, "1 Carry"], [2, "2 Mid"], [3, "3 Off"], [4, "4 Sup"], [5, "5 Sup"]];
const DOTA_BR = [["auto", "Meu rank"], ["HERALD_GUARDIAN", "Arauto–Guardião"], ["CRUSADER_ARCHON", "Cruzado–Arconte"], ["LEGEND_ANCIENT", "Lenda–Ancestral"], ["DIVINE_IMMORTAL", "Divino–Imortal"]];
const dota = {
  mode: store.get("dotaMode", "plan"), pos: null, fav: [], br: store.get("dotaBr", "auto"),
  en: store.get("dotaEn", []), al: store.get("dotaAl", []), onlyMine: store.get("dotaMine", false),
  hero: store.get("dotaHero", null), heroes: store.get("dotaHeroes", null),
  pick: null,        // {side: "en"|"al", i} enquanto escolhe um herói; {side: "build"} para a build; {side: "fav"} preferidos
  q: "", placed: null, draft: null, build: null, err: "", busy: false, seq: 0, gsiHero: null, gsiState: null,
};
const heroName = (id) => (dota.heroes || []).find((h) => h.id === id)?.n || `herói ${id}`;
const sgn = (x) => (x > 0 ? "+" : x < 0 ? "−" : "±") + Math.abs(x).toFixed(1);
function dotaSave() {
  store.set("dotaMode", dota.mode); store.set("dotaBr", dota.br); store.set("dotaEn", dota.en);
  store.set("dotaAl", dota.al); store.set("dotaMine", dota.onlyMine); store.set("dotaHero", dota.hero);
}

// o mesmo painel vive na aba Jogos e, com o Dota aberto, na tela Jogando
const dotaRunning = () => /dota 2/i.test(state.games?.game?.name || "");
function dotaPlace(running) {
  running = !!running;
  if (running === dota.placed) return;
  dota.placed = running;
  const ui = $("dota-ui"), host = running ? $("pl-dota") : $("g-dota");
  if (ui.parentElement !== host) host.appendChild(ui);
  $("pl-dota").classList.toggle("hidden", !running);
  $("g-dota").classList.toggle("hidden", running);
}
// tela Jogos/Jogando aberta ou conexão nova
function dotaShown() {
  dotaPlace(dotaRunning());
  if (vis("games") || vis("play")) dotaLoad();
}

// chamado pelo GSI (jogos.js): draft novo limpa os heróis marcados; herói escolhido abre a build dele
function dotaGsi(d) {
  if (!d || d.g !== "dota2") return;
  const st = d.raw_state;
  if (st === "DOTA_GAMERULES_STATE_HERO_SELECTION" && dota.gsiState && dota.gsiState !== st) {
    dota.en = []; dota.al = []; dota.mode = "draft"; dota.draft = null; dotaSave(); dotaFetch();
  }
  dota.gsiState = st;
  if (d.hero_id && d.hero_id !== dota.gsiHero) {
    dota.gsiHero = d.hero_id;
    if (dota.hero !== d.hero_id) { dota.hero = d.hero_id; dota.build = null; }
    dota.mode = "build"; dotaSave(); dotaFetch();
  }
}

// plano da próxima partida (do PC): chega na conexão e sempre que algum aparelho muda ou a partida termina
function onDotaPlan(d, reset) {
  if (!d) return;
  const changed = d.pos !== dota.pos || d.heroes.join() !== dota.fav.join();
  dota.pos = d.pos; dota.fav = d.heroes.slice();
  if (reset) { dota.en = []; dota.al = []; dota.mode = "plan"; dota.pick = null; dotaSave(); }
  if (changed || reset) { dota.draft = null; dota.build = null; dotaFetch(); }
}
function planSet(p) {
  if ("pos" in p) dota.pos = p.pos;
  if ("heroes" in p) dota.fav = p.heroes.slice();
  dota.draft = null; dota.build = null; dotaFetch();
  send("dota.plan.set", p).then(onDotaPlan).catch((e) => e.message !== "offline" && toast(e.message, "bad"));
}

let dotaLoaded = false;
async function dotaLoad() {
  if (dotaLoaded || !ws || ws.readyState !== 1) { dotaRender(); return; }
  dotaLoaded = true;
  if (!dota.heroes) {
    try { dota.heroes = await send("dota.heroes", {}, true, 30000); store.set("dotaHeroes", dota.heroes); }
    catch (e) { dota.err = e.message; dotaLoaded = false; dotaRender(); return; }
  }
  try { const pl = await send("dota.plan.get"); dota.pos = pl.pos; dota.fav = pl.heroes; } catch {}
  dotaFetch();
}

async function dotaFetch() {
  if (!dota.heroes) { dotaRender(); return; }
  const seq = ++dota.seq;
  dota.busy = true; dota.err = ""; dotaRender();
  try {
    if (dota.mode !== "build") {
      const r = await send("dota.draft", { pos: dota.pos, bracket: dota.br, enemies: dota.en, allies: dota.al, prefer: dota.fav }, true, 45000);
      if (seq === dota.seq) dota.draft = r;
    } else if (dota.hero) {
      const r = await send("dota.build", { hero: dota.hero, pos: dota.pos, bracket: dota.br, enemies: dota.en }, true, 45000);
      if (seq === dota.seq) dota.build = r;
    }
  } catch (e) { if (seq === dota.seq) dota.err = e.message === "offline" ? "Sem conexão com o PC" : e.message; }
  if (seq === dota.seq) { dota.busy = false; dotaRender(); }
}

function dotaRender() {
  const ui = $("dota-ui"); if (!ui) return;
  const chip = (attr, v, label, on) => `<button class="chip2${on ? " on" : ""}" data-${attr}="${v}">${esc(label)}</button>`;
  let h = `<h3><span>Dota 2</span><span class="chips" style="flex:none">${[["plan", "Fila"], ["draft", "Draft"], ["build", "Build"]].map(([m, l]) => chip("dm", m, l, dota.mode === m)).join("")}</span></h3>
    <div class="chips dpos${dota.pos ? "" : " ask"}">${DOTA_POS.map(([p, l]) => chip("dp", p, l, dota.pos === p)).join("")}</div>
    ${dota.pos ? "" : `<div class="dnote warn">Qual posição você vai jogar? Escolha aqui (vale até a partida acabar).</div>`}
    <div class="dbar"><select class="sel" id="dota-br">${DOTA_BR.map(([v, l]) => `<option value="${v}"${dota.br === v ? " selected" : ""}>${l}</option>`).join("")}</select>
      <span class="sub">${dota.busy ? "carregando…" : esc(dotaBrNote())}</span></div>`;
  if (dota.pick) h += dotaPicker();
  else if (!dota.heroes) h += `<div class="empty">${esc(dota.err || "Carregando heróis…")}</div>`;
  else h += dota.mode === "plan" ? dotaPlanHtml() : dota.mode === "draft" ? dotaDraftHtml() : dotaBuildHtml();
  ui.innerHTML = h;
  const f = $("dota-q"); if (f && dota.pick) { f.value = dota.q; if (!f.dataset.touched) f.focus({ preventScroll: true }); }
}
function dotaBrNote() {
  const r = dota.mode === "build" ? dota.build : dota.draft; if (!r) return "";
  return r.auto ? (r.auto === "matches" ? `pelas suas partidas: ${r.bname}` : `seu rank: ${r.bname}`) : dota.br === "auto" ? `${r.bname} (rank não encontrado)` : "";
}
function dotaSlots(side, n, label) {
  const list = dota[side];
  return `<div class="dslots"><small>${label}</small>${Array.from({ length: n }, (_, i) => {
    const id = list[i];
    return `<button class="dslot${id ? " on" : ""}" data-slot="${side}:${i}">${id ? esc(heroName(id)) : "+"}</button>`;
  }).join("")}</div>`;
}
function dotaDraftHtml() {
  let h = dotaSlots("en", 5, "Inimigos") + dotaSlots("al", 4, "Aliados") +
    `<div class="dbar"><button class="chip2${dota.onlyMine ? " on" : ""}" data-dx="mine">Só os que eu jogo</button><button class="chip2" data-dx="clear">Limpar</button></div>`;
  if (dota.err) return h + `<div class="empty">${esc(dota.err)}</div>`;
  const r = dota.draft; if (!r) return h + `<div class="empty">${dota.busy ? "Calculando…" : ""}</div>`;
  let list = r.list || [];
  if (dota.onlyMine) list = list.filter((x) => x.mine);
  const what = r.enemies.length ? "vantagem contra os inimigos" + (r.allies.length ? " e sinergia com aliados" : "") + " + força no meta" : "força no meta (marque os inimigos para ver counters)";
  h += `<div class="dnote">Pos ${r.pos} · ordenado por ${what}. Toque num herói para ver a build.</div>`;
  if (!list.length) return h + `<div class="empty">${dota.onlyMine ? "Nenhum herói seu nesta posição (pelas suas partidas públicas no STRATZ)." : "Sem dados."}</div>`;
  const favs = list.filter((x) => x.fav), rest = list.filter((x) => !x.fav);
  if (favs.length) h += `<h4 class="dh">Seus preferidos</h4>` + sugList(favs);
  if (!r.enemies.length && r.bans?.length) h += bansHtml(r.bans);
  return h + (favs.length ? `<h4 class="dh">Outras opções</h4>` : "") + sugList(rest.slice(0, 12));
}
function sugList(list) {
  return `<div class="dsug">${list.map((x) => `<button class="dsg${x.fav ? " fav" : ""}" data-hero="${x.id}">
      <span class="dsn"><b>${esc(x.n)}</b>${x.mine ? ` <small class="mine">você: ${x.mine[0]} jogos · ${x.mine[1]}%</small>` : ""}</span>
      <span class="dss ${x.score >= 0 ? "up" : "dn"}">${sgn(x.score)}</span>
      <small class="dsd">${x.vs.map(([e, a, wr]) => `<i class="${a > 0 ? "up" : a < 0 ? "dn" : ""}">${esc(heroName(e))} ${sgn(a)}${wr != null ? ` (${Math.round(wr)}%)` : ""}</i>`).join("")}
        ${x.with.filter(([, s]) => s).map(([a, s]) => `<i class="${s > 0 ? "up" : "dn"}">com ${esc(heroName(a))} ${sgn(s)}</i>`).join("")}
        <i>meta ${x.wr}% · ${x.share}% dos jogos</i></small></button>`).join("")}</div>`;
}
function bansHtml(bans) {
  return `<h4 class="dh">Bom banir <small>(counters dos seus preferidos)</small></h4><div class="dbans">${bans.map((b) =>
    `<div class="row"><span><b>${esc(b.n)}</b> <small>${b.pick}% dos jogos</small><br><small class="dn">${b.vs.map(([p, a]) => `${esc(heroName(p))} ${sgn(a)}`).join(" · ")}</small></span><span class="dn">${sgn(-b.score)}</span></div>`).join("")}</div>`;
}
function dotaPlanHtml() {
  let h = `<div class="dnote">Escolha enquanto está na fila: a posição acima e os heróis que quer jogar. O draft e a build já abrem com isso, e tudo zera quando a partida termina.</div>
    <h4 class="dh">Heróis preferidos <small>(até 6)</small></h4>
    <div class="dfav">${dota.fav.map((id) => `<button class="chip2 on" data-fx="${id}">${esc(heroName(id))} ×</button>`).join("")}
      ${dota.fav.length < 6 ? `<button class="chip2 add" data-dx="fav">+ Adicionar</button>` : ""}</div>`;
  if (dota.err) return h + `<div class="empty">${esc(dota.err)}</div>`;
  const r = dota.draft;
  if (!dota.fav.length) return h + `<div class="empty">Com preferidos, aparece aqui como cada um vai na posição e quem banir contra eles.</div>`;
  if (!r) return h + `<div class="empty">${dota.busy ? "Calculando…" : ""}</div>`;
  if (r.pos) {
    const favs = (r.list || []).filter((x) => x.fav);
    h += `<h4 class="dh">Na pos ${r.pos} <small>(toque para ver a build)</small></h4><div class="dbans">${dota.fav.map((id) => {
      const x = favs.find((f) => f.id === id);
      if (!x) return `<div class="row"><span>${esc(heroName(id))}</span><span class="dn">quase nunca jogado nessa posição</span></div>`;
      return `<button class="row dfrow" data-hero="${id}"><span><b>${esc(x.n)}</b>${x.mine ? ` <small>· você: ${x.mine[0]} jogos, ${x.mine[1]}%</small>` : ""}</span>
        <span class="${x.wr >= 50 ? "up" : "dn"}">${x.wr}% · ${x.share}% dos jogos${x.share < 1 ? " (raro)" : ""}</span></button>`;
    }).join("")}</div>`;
  }
  return h + (r.bans?.length ? bansHtml(r.bans) : "");
}
function dotaBuildHtml() {
  let h = `<div class="dbar"><button class="btn sm" data-dx="hero">${dota.hero ? esc(heroName(dota.hero)) : "Escolher herói"}</button>
    ${dota.gsiHero && dota.gsiHero !== dota.hero ? `<button class="chip2" data-dx="mine-hero">Meu herói: ${esc(heroName(dota.gsiHero))}</button>` : ""}</div>`;
  if (!dota.hero) return h + `<div class="empty">Escolha um herói, ou ele aparece sozinho quando você pegar o herói no jogo.</div>`;
  if (dota.err) return h + `<div class="empty">${esc(dota.err)}</div>`;
  const b = dota.build; if (!b || b.hero !== dota.hero) return h + `<div class="empty">${dota.busy ? "Carregando a build…" : ""}</div>`;
  const it = (x, extra) => `<div class="row"><span>${esc(x.name)}</span><span>${extra}</span></div>`;
  const sec = (title, body) => body ? `<div class="dsec"><h4>${title}</h4>${body}</div>` : "";
  h += `<div class="dnote">${esc(b.name)} · pos ${b.pos} · ${b.bname} · ${b.games.toLocaleString("pt-BR")} partidas${b.wr != null ? ` · ${b.wr}% de vitórias` : ""}</div>`;
  if (b.moved) h += `<div class="dnote warn">${esc(b.name)} quase não joga na pos ${dota.pos}: mostrando a pos ${b.pos} (${b.pos_share[b.pos]}% dos jogos dele).</div>`;
  if (b.vs?.length) h += `<div class="dvs">${b.vs.map((v) => `<span class="chip3 ${v.adv > 0 ? "up" : v.adv < 0 ? "dn" : ""}">vs ${esc(v.n)} ${v.adv == null ? "–" : sgn(v.adv)}${v.wr != null ? ` · ${Math.round(v.wr)}%` : ""}</span>`).join("")}</div>`;
  h += `<div class="dgrid">`;
  h += sec("Início", b.start.map((x) => it({ name: (x.q > 1 ? x.q + "× " : "") + x.name }, x.pct + "%")).join(""));
  h += sec("Botas", b.boots.map((x) => it(x, `${x.min} min · ${x.pct}%`)).join(""));
  h += sec("Primeiros itens", b.early.map((x) => it(x, `${x.min} min · ${x.pct}%`)).join(""));
  h += sec("Itens principais <small>(na ordem, minuto médio)</small>", b.core.map((x) => it(x, `${x.min} min · ${x.pct}%`)).join(""));
  h += sec("Situacionais", b.situ.map((x) => it(x, `${x.pct}%`)).join(""));
  h += sec("Skills <small>(maximize nesta ordem)</small>", b.skills.length ? b.skills.map((x, i) => it({ name: `${i + 1}. ${x.name}` }, `máx. no nível ${x.max}`)).join("") +
    `<div class="dnote">Ultimate sempre que der (6, 12, 18).</div>` : "");
  h += sec("Talentos", b.talents.map((t) => `<div class="row dtal"><span><b>${t.lvl}</b> ${esc(t.name)}${t.alt ? `<br><small>ou ${esc(t.alt)}</small>` : ""}</span><span>${t.pct}%</span></div>`).join(""));
  return h + `</div><div class="dnote">% = parte das partidas em que compram/escolhem. Fonte: STRATZ, últimos dias.</div>`;
}
function dotaPicker() {
  const side = dota.pick.side, cur = side === "build" ? dota.hero : side === "fav" ? null : dota[side][dota.pick.i];
  const favs = new Set(dota.fav);
  const used = new Set([...dota.en, ...dota.al]);
  const q = dota.q.toLowerCase().replace(/[^a-z0-9 ]/g, "");
  const ini = (n) => n.toLowerCase().split(/[\s-]+/).map((w) => w[0]).join("");
  const list = (dota.heroes || []).filter((x) => !q || x.n.toLowerCase().replace(/[^a-z0-9 ]/g, "").includes(q) || ini(x.n).startsWith(q.replace(/ /g, "")));
  const title = side === "build" ? "Herói da build" : side === "fav" ? `Preferidos (${dota.fav.length}/6)` : side === "en" ? `Inimigo ${dota.pick.i + 1}` : `Aliado ${dota.pick.i + 1}`;
  return `<div class="dbar"><b class="sub">${title}</b><input id="dota-q" class="inp" type="search" placeholder="buscar (ex.: am, pa, sand)" autocomplete="off" enterkeyhint="done">
    ${cur && side !== "build" ? `<button class="chip2" data-pk="0">Tirar</button>` : ""}<button class="chip2${side === "fav" ? " on" : ""}" data-dx="cancel">${side === "fav" ? "Pronto" : "Voltar"}</button></div>
    <div class="dpick">${list.map((x) => `<button class="chip2${x.id === cur || (side === "fav" && favs.has(x.id)) ? " on" : ""}${used.has(x.id) && x.id !== cur && side !== "build" && side !== "fav" ? " used" : ""}" data-pk="${x.id}">${esc(x.n)}</button>`).join("") || '<div class="empty">Nenhum herói com esse nome.</div>'}</div>`;
}

function dotaPickSet(id) {
  const p = dota.pick;
  if (p.side === "fav") {   // liga/desliga e continua escolhendo
    if (!id) return;
    const f = dota.fav.includes(id) ? dota.fav.filter((x) => x !== id) : dota.fav.length < 6 ? [...dota.fav, id] : dota.fav;
    if (f === dota.fav) { toast("No máximo 6 preferidos", "bad"); return; }
    dota.fav = f; dotaRender(); return;
  }
  dota.pick = null; dota.q = "";
  if (p.side === "build") { if (id) { dota.hero = id; dota.build = null; } }
  else {
    const list = dota[p.side].slice();
    for (const s of ["en", "al"]) dota[s] = dota[s].filter((x) => x !== id);   // o mesmo herói não fica nos dois times
    const l2 = p.side === "en" ? dota.en : dota.al;
    const old = list[p.i];
    const at = old ? l2.indexOf(old) : -1;
    if (at >= 0) { if (id) l2[at] = id; else l2.splice(at, 1); } else if (id) l2.push(id);
    dota.draft = null; dota.build = null;
  }
  dotaSave(); dotaFetch();
}

$("dota-ui").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  buzz(8);
  const d = b.dataset;
  if (d.dm) { dota.mode = d.dm; dota.pick = null; dotaSave(); dotaFetch(); }
  else if (d.dp) planSet({ pos: +d.dp === dota.pos ? null : +d.dp });
  else if (d.fx) planSet({ heroes: dota.fav.filter((x) => x !== +d.fx) });
  else if (d.slot) { const [side, i] = d.slot.split(":"); dota.pick = { side, i: +i }; dota.q = ""; dotaRender(); }
  else if (d.pk != null) dotaPickSet(+d.pk || null);
  else if (d.hero) { dota.hero = +d.hero; dota.mode = "build"; dota.build = null; dotaSave(); dotaFetch(); $("dota-ui").scrollIntoView({ block: "start", behavior: "smooth" }); }
  else if (d.dx === "mine") { dota.onlyMine = !dota.onlyMine; dotaSave(); dotaRender(); }
  else if (d.dx === "clear") { dota.en = []; dota.al = []; dota.draft = null; dotaSave(); dotaFetch(); }
  else if (d.dx === "hero") { dota.pick = { side: "build" }; dota.q = ""; dotaRender(); }
  else if (d.dx === "mine-hero") { dota.hero = dota.gsiHero; dota.build = null; dotaSave(); dotaFetch(); }
  else if (d.dx === "fav") { dota.pick = { side: "fav", before: dota.fav.join() }; dota.q = ""; dotaRender(); }
  else if (d.dx === "cancel") {
    const p = dota.pick; dota.pick = null; dota.q = "";
    if (p?.side === "fav" && p.before !== dota.fav.join()) planSet({ heroes: dota.fav }); else dotaRender();
  }
});
$("dota-ui").addEventListener("input", (e) => {
  if (e.target.id !== "dota-q") return;
  dota.q = e.target.value; e.target.dataset.touched = 1;
  const pos = e.target.selectionStart;
  dotaRender();
  const f = $("dota-q"); f.dataset.touched = 1; f.focus({ preventScroll: true }); try { f.setSelectionRange(pos, pos); } catch {}
});
$("dota-ui").addEventListener("change", (e) => {
  if (e.target.id !== "dota-br") return;
  dota.br = e.target.value; dota.draft = null; dota.build = null; dotaSave(); dotaFetch();
});
