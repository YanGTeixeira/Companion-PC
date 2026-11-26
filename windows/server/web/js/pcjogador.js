"use strict";
// ---------------------------------------------------------------- Página Jogador no PC (/jogador), 1.19
// O mesmo da seção Jogador do celular, em tela grande e com mouse: perfil (frase, blocos, vitrine que se arrasta),
// coleção inteira (passe o mouse para ver no seu cartão), troféus, loja e evento, desafios e o ranking (liga, amigos,
// duelos). Fala com o servidor pelo mesmo WebSocket do app (papel "editor": não conta como aparelho).
const $ = (id) => document.getElementById(id);
const esc = cEsc;
const TABS = [["perfil", "Perfil"], ["colecao", "Coleção"], ["trofeus", "Troféus"], ["loja", "Loja"], ["desafios", "Desafios"], ["ranking", "Ranking"]];
const KINDS = ["title", "frame", "avatar", "bg", "effect", "accent", "theme", "sound"];
const LEAGUES = ["Bronze", "Prata", "Ouro", "Safira", "Rubi", "Diamante"];
const LEAGUE_COLOR = ["#cd7f32", "#c9d1d9", "#ffd23f", "#3b82f6", "#e0245e", "#7df9ff"];
const TIER = { bronze: "BRONZE", prata: "PRATA", ouro: "OURO" };
const SHOW_LV = { 4: 15, 5: 30, 6: 50 };
let TAB = "perfil", CQ = null, LAY = {}, RANK = null, RD = {}, RTAB = "league", RKIND = "week", hover = null, FILTER = "all";
try { TAB = localStorage.getItem("pcj.tab") || "perfil"; } catch {}
if (!TABS.some(([t]) => t === TAB)) TAB = "perfil";

// ------------------------------------------------------------ conexão (igual ao Personalizar)
const hm = location.hash.match(/[#&]t=([^&]+)/);
if (hm) { try { localStorage.setItem("pcc.token", JSON.stringify(decodeURIComponent(hm[1]))); } catch {} history.replaceState(null, "", location.pathname); }
let TOKEN = ""; try { TOKEN = JSON.parse(localStorage.getItem("pcc.token") || '""'); } catch {}
let WEB = +(document.querySelector('meta[name="build"]')?.content || 0) || null, ws = null, rid = 0;
const pending = new Map();
function status(cls, text) { $("status").className = cls; $("status").lastElementChild.textContent = text; }
function send(a, p, timeout) {
  return new Promise((res, rej) => {
    if (!ws || ws.readyState !== 1) return rej(new Error("desconectado"));
    const id = ++rid; pending.set(id, { res, rej }); ws.send(JSON.stringify({ t: "req", id, a, p: p || {} }));
    setTimeout(() => pending.delete(id) && rej(new Error("sem resposta")), timeout || (a.startsWith("rank.") ? 20000 : 8000));
  });
}
function connect() {
  if (!TOKEN) { $("login").hidden = false; $("app").hidden = true; status("bad", "Sem token"); return; }
  ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => ws.send(JSON.stringify({ t: "hello", token: TOKEN, role: "editor" }));
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.t === "welcome" && msg.web && WEB && msg.web !== WEB) { location.reload(); return; }
    if (msg.t === "welcome") {
      WEB = WEB || msg.web; LAY = msg.layout || {}; $("login").hidden = true; $("app").hidden = false; status("ok", "Conectado");
      loadConq(); loadRank(); mountPreview();
    } else if (msg.t === "res") { const p = pending.get(msg.id); if (p) { pending.delete(msg.id); msg.ok ? p.res(msg.d) : p.rej(new Error(msg.e)); } }
    else if (msg.t === "conq" && msg.d) { CQ = msg.d; render(); }
    else if (msg.t === "layout") { LAY = msg.d || {}; if (TAB === "colecao") renderBody(); }
    else if (msg.t === "rank" && msg.d) { const ch = !RANK || RANK.joined !== msg.d.joined || RANK.nick !== msg.d.nick; RANK = msg.d; if (ch) { RD = {}; if (TAB === "ranking") loadRankTab(); } renderSide(); }
    else if (msg.t === "event" && msg.kind === "conq" && msg.d) onEvent(msg.d);
  };
  ws.onclose = (e) => {
    ws = null;
    if (e.code === 4001) { TOKEN = ""; try { localStorage.removeItem("pcc.token"); } catch {} connect(); return; }
    status("bad", "Desconectado · tentando de novo"); setTimeout(connect, 2000);
  };
}
$("tok-ok").onclick = () => { TOKEN = $("tok").value.trim(); try { localStorage.setItem("pcc.token", JSON.stringify(TOKEN)); } catch {} connect(); };
async function loadConq() { try { CQ = await send("conq.get"); render(); } catch (e) { status("bad", e.message); } }
async function loadRank() { try { RANK = await send("rank.state"); renderSide(); if (TAB === "ranking") loadRankTab(); } catch {} }

// ------------------------------------------------------------ avisos
let toastT = null;
function toast(msg, cls = "ok") {
  const t = $("toast"); t.textContent = msg; t.className = "pj-toast " + cls; t.hidden = false;
  clearTimeout(toastT); toastT = setTimeout(() => (t.hidden = true), 3200);
}
const EV_TXT = {
  conq: (e) => `Conquista: ${e.name} (+${e.xp} XP)`, level: (e) => `Subiu para o nível ${e.level}!`,
  quest: () => "Desafio da semana cumprido!", quests_all: (e) => `Os 3 desafios da semana! (+${e.xp} XP)`, boss: (e) => `${e.icon} ${e.name} derrotado!`,
  reward: (e) => `Liberou ${KIND_LABEL[e.type] || ""}: ${e.name}`, event: (e) => `Evento ${e.name} completo!`,
};
function onEvent(e) { const f = EV_TXT[e.kind]; if (f) toast(f(e)); }
async function act(a, p, okMsg) {
  try { const d = await send(a, p); if (a.startsWith("conq.")) { CQ = d; render(); } if (okMsg) toast(okMsg); return d; }
  catch (e) { toast(e.message, "bad"); return null; }
}

// ------------------------------------------------------------ prévia do celular (o app de verdade, num iframe)
function mountPreview() {
  const box = $("pv-frame"); if (box.firstChild) return;
  const [w, h, sc] = [412, 860, 0.62];
  box.style.width = w * sc + "px"; box.style.height = h * sc + "px";
  const f = document.createElement("iframe");
  f.src = `/?preview=1#t=${encodeURIComponent(TOKEN)}`; f.width = w; f.height = h; f.style.transform = `scale(${sc})`; f.title = "Prévia do celular";
  f.onload = () => setTimeout(() => pvView(TAB === "loja" ? "loja" : TAB === "desafios" ? "quests" : TAB === "trofeus" ? "troph" : TAB === "ranking" ? "rank" : "conq"), 1200);
  box.appendChild(f);
}
const pvPost = (msg) => { try { $("pv-frame").firstChild?.contentWindow.postMessage(msg, location.origin); } catch {} };
const pvView = (view) => pvPost({ pcc: "view", view });

// ------------------------------------------------------------ cartão do jogador (à esquerda, sempre à vista)
function card(over = {}) {
  const d = CQ, eq = { ...(d.equip || {}), ...over }, nm = (id) => d.rewards.find((r) => r.id === id)?.name || "";
  const got = d.conq.filter((c) => c.day);
  const show = (eq.show || []).map((id) => d.conq.find((c) => c.id === id)).filter(Boolean);
  const recent = [...got].sort((a, b) => (a.day < b.day ? 1 : -1)).slice(0, 3);
  const lg = RD.league && !RD.league.error ? RD.league : null;
  return profileCard({ nick: RANK?.joined ? RANK.nick : "", level: d.level, title: nm(eq.title) || "Novato", frame: eq.frame, avatar: eq.avatar,
    effect: eq.effect, bg: eq.bg, bio: eq.bio, lay: eq.lay, sub: d.streak ? `🔥 ${d.streak} dia${d.streak > 1 ? "s" : ""}` : "",
    stats: [[d.level, "nível"], [d.week_xp, "XP na semana"], [d.best_streak, "recorde"], [`${got.length}/${d.conq.length}`, "troféus"]],
    show: show.length ? `<div class="shrow">${show.map((c) => `<div class="cqt got">${trophy(c.tier, true)}<span>${esc(c.name)}</span></div>`).join("")}</div>` : "",
    recent: recent.map((c) => `<span>🏆 ${esc(c.name)}</span>`).join(""),
    league: lg ? `<span class="lgtag" style="--lg:${LEAGUE_COLOR[lg.league]}">Liga ${LEAGUES[lg.league]}</span>` : "" });
}
function renderSide() {
  if (!CQ) return;
  const d = CQ, eq = d.equip || {};
  $("me-card").innerHTML = card(hover || {});
  // a cor de destaque vale no cartão (e na página: botões e barras)
  const acc = hover?.accent || eq.accent;
  accentApply($("me-card"), acc, eq.color);
  const pct = Math.max(0, Math.min(100, ((d.xp - d.lvl_lo) / Math.max(1, d.lvl_hi - d.lvl_lo)) * 100));
  $("me-xp").innerHTML = `<div class="pj-xprow"><span>${d.xp - d.lvl_lo} / ${d.lvl_hi - d.lvl_lo} XP para o nível ${d.level + 1}</span><span>+${d.today_xp} hoje</span></div>
    <div class="jg-bar"><i style="width:${pct}%"></i></div>
    <div class="pj-chips"><span class="pj-chip cr"><i class="crcoin"></i>${d.credits.bal} créditos</span>
      ${d.mult > 1 ? `<span class="pj-chip hot">🔥 XP ×${String(d.mult).replace(".", ",")}</span>` : ""}${d.x2 ? '<span class="pj-chip x2">⚡ XP em dobro hoje</span>' : ""}
      <span class="pj-chip">${"❄".repeat(d.freezes) || "–"} congelamento${d.freezes === 1 ? "" : "s"}</span></div>
    ${hover ? '<p class="hint pj-hov">Prévia: é assim que fica no seu cartão.</p>' : ""}`;
}

// ------------------------------------------------------------ abas
function renderTabs() {
  $("tabs").innerHTML = TABS.map(([t, l]) => `<button data-tab="${t}" class="${t === TAB ? "on" : ""}">${l}${t === "ranking" && duelsIn() ? ` <i class="pj-dot">${duelsIn()}</i>` : ""}</button>`).join("");
}
$("tabs").onclick = (e) => {
  const b = e.target.closest("[data-tab]"); if (!b) return;
  TAB = b.dataset.tab; try { localStorage.setItem("pcj.tab", TAB); } catch {}
  hover = null; render();
  pvView({ loja: "loja", desafios: "quests", trofeus: "troph", ranking: "rank", colecao: "inv" }[TAB] || "conq");
  if (TAB === "ranking") loadRankTab();
};
function render() { if (!CQ) return; renderTabs(); renderSide(); renderBody(); }
function renderBody() {
  if (!CQ) return;
  const fn = { perfil: tabPerfil, colecao: tabColecao, trofeus: tabTrofeus, loja: tabLoja, desafios: tabDesafios, ranking: tabRanking }[TAB];
  const keep = document.activeElement?.id;
  if (keep === "pf-bio" || keep === "rk-nick" || keep === "rk-fnick") return;   // não apaga o que está digitando
  $("body").innerHTML = fn();
  bindBody();
}

// ------------------------------------------------------------ Perfil: frase, blocos, cor livre, vitrine
function tabPerfil() {
  const d = CQ, eq = d.equip, lay = eq.lay || [], all = [...lay, ...Object.keys(LAY_LABEL).filter((b) => !lay.includes(b))];
  const free = d.rewards.find((r) => r.id === "a_livre")?.got;
  const nm = (k) => d.rewards.find((r) => r.id === eq[k])?.name || "";
  const cur = ["title", "frame", "avatar", "bg", "effect", "accent", "sound"].map((k) => `<button class="pj-eqit" data-goto="${k}"><small>${KIND_PLURAL[k]}</small><b>${esc(nm(k))}</b></button>`).join("");
  return `<section class="box"><h2>Seu cartão</h2><p class="hint">Aparece no app, aqui ao lado e para quem abre o seu perfil no ranking. Clique num item para trocar.</p>
      <div class="pj-eq">${cur}<button class="pj-eqit" data-goto="theme"><small>Tema do app</small><b>${esc(VAR_NAME[(LAY.skin || "fallout") + ":" + (LAY.theme || "")] ? (THEMES.find((t) => t.id === LAY.skin)?.name + " · " + VAR_NAME[LAY.skin + ":" + LAY.theme]) : (THEMES.find((t) => t.id === LAY.skin)?.name || "Fallout"))}</b></button></div></section>
    <section class="box"><h2>Frase</h2><p class="hint">Até 60 letras. Vai para o ranking (passa por um filtro de palavrões).</p>
      <div class="row"><input type="text" id="pf-bio" maxlength="60" value="${esc(eq.bio || "")}" placeholder="Ex.: só mais uma partida" style="max-width:420px"><button class="pri" id="pf-bio-ok">Salvar</button></div></section>
    <section class="box"><h2>Blocos do perfil</h2><p class="hint">Arraste para mudar a ordem; desmarque para esconder.</p>
      <div class="pj-lay" id="pj-lay">${all.map((b) => `<div class="pj-lb${lay.includes(b) ? "" : " off"}" draggable="true" data-lb="${b}"><span class="grip">::</span>
        <label class="chk"><input type="checkbox" data-lt="${b}"${lay.includes(b) ? " checked" : ""}> ${LAY_LABEL[b]}</label></div>`).join("")}</div></section>
    ${free ? `<section class="box"><h2>Cor livre</h2><p class="hint">Vale quando a cor de destaque é <b>Cor livre</b>${eq.accent === "a_livre" ? "" : " (equipe em Coleção › Cor de destaque)"}.</p>
      <div class="row"><input type="color" id="pf-color" value="${esc(eq.color || "#4c8dff")}"><span class="hint" style="margin:0">${esc(eq.color || "")}</span></div></section>` : ""}
    ${vitrine()}`;
}
function vitrine() {
  const d = CQ, show = d.equip.show || [], max = d.show_max || 3, got = d.conq.filter((c) => c.day);
  const slots = [];
  for (let i = 0; i < 6; i++) {
    const c = d.conq.find((x) => x.id === show[i]);
    if (i >= max) slots.push(`<div class="pj-slot lock">🔒<small>nível ${SHOW_LV[i + 1]}</small></div>`);
    else if (c) slots.push(`<div class="pj-slot full" draggable="true" data-vs="${i}">${trophy(c.tier, true)}<span>${esc(c.name)}</span><button class="pj-rm" data-vrm="${esc(c.id)}" aria-label="Tirar">×</button></div>`);
    else slots.push(`<div class="pj-slot" data-vs="${i}"><small>arraste um troféu</small></div>`);
  }
  return `<section class="box"><h2>Vitrine <span class="hint">${show.length}/${max}</span></h2>
    <p class="hint">Arraste troféus para os lugares (e entre eles para mudar a ordem). Mais lugares nos níveis 15, 30 e 50.</p>
    <div class="pj-vit" id="pj-vit">${slots.join("")}</div>
    <div class="pj-pool">${got.map((c) => `<div class="cqt got${show.includes(c.id) ? " used" : ""}" draggable="true" data-vc="${esc(c.id)}" title="${esc(c.desc)}">${trophy(c.tier, true)}<span>${esc(c.name)}</span></div>`).join("") || '<p class="hint">Você ainda não ganhou troféus.</p>'}</div></section>`;
}
const setShow = (ids, msg) => act("conq.equip", { kind: "show", ids }, msg);

// ------------------------------------------------------------ Coleção: tudo, por tipo
function tabColecao() {
  const d = CQ, all = d.rewards;
  const counts = `${all.filter((r) => r.got).length} de ${all.length} liberados`;
  const filt = (r) => FILTER === "all" || (FILTER === "got" ? r.got : !r.got);
  const next = all.filter((r) => !r.got && r.req).sort((a, b) => a.req - b.req).slice(0, 6);
  return `<section class="box"><div class="row" style="justify-content:space-between"><div><h2>Coleção</h2><p class="hint" style="margin:0">${counts}. Passe o mouse para ver no seu cartão; clique para usar.
      Bloqueados: clique para ver como liberar e experimentar.</p></div>
      <div class="seg" id="pj-filter">${[["all", "Todos"], ["got", "Liberados"], ["lock", "Bloqueados"]].map(([k, l]) => `<button data-f="${k}" class="${FILTER === k ? "on" : ""}">${l}</button>`).join("")}</div></div>
      ${next.length ? `<div class="pj-next">${next.map((r) => `<span><b>nível ${r.req}</b> ${esc(r.name)} <small>${KIND_LABEL[r.kind]}</small></span>`).join("")}</div>` : ""}</section>
    ${KINDS.map((k) => {
      const list = all.filter((r) => r.kind === k);
      const vis = list.filter(filt);
      if (!vis.length) return "";
      return `<section class="box" id="k-${k}"><h2>${KIND_PLURAL[k]} <span class="hint">${list.filter((r) => r.got).length}/${list.length}</span></h2>
        <div class="ivgrid pj-grid">${vis.map(itemBtn).join("")}</div></section>`;
    }).join("")}`;
}
function isOn(r) { return r.kind === "theme" ? r.id === `${LAY.skin || "fallout"}:${LAY.theme || ""}` : CQ.equip[r.kind] === r.id; }
function itemBtn(r) {
  const on = isOn(r), st = on ? "em uso" : r.got ? RARITY[r.rarity] : "🔒 " + reqText(r);
  return `<button class="ivit rar-${r.rarity}${r.got ? "" : " lock tryable"}${on ? " on" : ""}" data-it="${esc(r.id)}" title="${esc(RARITY[r.rarity])}${r.anim ? " · animado" : ""}">
    ${itemPreview(r, CQ.level, CQ.equip)}<span>${esc(r.name)}</span><small>${esc(st)}</small></button>`;
}
async function useItem(r) {
  if (r.kind === "theme") {
    const [skin, theme] = r.id.split(":");
    LAY = { ...LAY, skin, theme };
    try { LAY = await send("layout.set", { layout: LAY }); toast(`Tema: ${r.name}`); renderBody(); } catch (e) { toast(e.message, "bad"); }
    return;
  }
  await act("conq.equip", { kind: r.kind, id: r.id }, r.kind === "sound" ? "" : `${r.name} equipado`);
}
function itemModal(r) {
  const d = CQ, profKinds = ["title", "frame", "avatar", "bg", "effect", "accent"];
  const inShop = r.shop && d.shop.items.includes(r.id);
  const prev = profKinds.includes(r.kind) ? `<div id="im-card">${card({ [r.kind]: r.id })}</div>`
    : r.kind === "theme" ? themeTile(r) : `<div class="pj-bigprev">${itemPreview(r, d.level, d.equip)}</div>`;
  const how = r.got ? "Já é seu." : r.req ? `Chegue ao nível ${r.req} (você está no ${d.level}).` : r.shop ? `Loja da semana: ${r.price} créditos.${inShop ? "" : " Não está na loja agora; ela muda toda segunda."}`
    : r.event ? `Complete o evento ${EVENT_NAME[r.event] || r.event}.` : `Ganhe a conquista ${r.conq}.`;
  openModal(`<div class="rar-${r.rarity}"><span class="rartag">${RARITY[r.rarity]}</span> <span class="hint">${esc(KIND_LABEL[r.kind])}${r.anim ? " · animado" : ""}</span></div>
    <h2 style="margin:6px 0 12px">${esc(r.name)}</h2>${prev}
    <p class="pj-how"><b>Como liberar:</b> ${esc(how)}</p>
    <div class="row">${r.got ? `<button class="pri" id="im-use">${r.kind === "theme" ? "Usar este tema" : "Equipar"}</button>` : ""}
      ${["theme", "accent"].includes(r.kind) ? '<button id="im-try">Experimentar no celular (10 s)</button>' : ""}
      ${inShop && !r.got ? `<button class="pri" id="im-buy" ${d.credits.bal < r.price ? "disabled" : ""}>Comprar · ${r.price} créditos</button>${d.credits.bal < r.price ? `<span class="hint" style="margin:0">faltam ${r.price - d.credits.bal}</span>` : ""}` : ""}</div>`);
  if (r.kind === "accent" && $("im-card")) accentApply($("im-card"), r.id, d.equip.color);
  if ($("im-use")) $("im-use").onclick = () => { closeModal(); useItem(r); };
  if ($("im-try")) $("im-try").onclick = () => { pvPost({ pcc: "try", id: r.id }); toast("Olhe a prévia do celular ao lado"); };
  if ($("im-buy")) $("im-buy").onclick = async () => { if (await act("conq.buy", { id: r.id }, `${r.name} é seu!`)) closeModal(); };
}
function themeTile(r) {
  const v = themeVariant(r.id) || [], t = THEMES.find((x) => x.id === r.id.split(":")[0]) || {};
  return `<div class="pj-theme" style="background:${v[3]};color:${v[4]}"><span style="font-family:'${t.font}';font-size:26px">${esc(t.name)}</span><small>${esc(t.desc || "")} · ${esc(v[1] || "")}</small>
    <div class="bars"><i style="background:${v[4]}"></i><i style="background:${v[5]}"></i><i style="background:${v[4]};opacity:.4"></i></div></div>`;
}

// ------------------------------------------------------------ Troféus
function tabTrofeus() {
  const d = CQ, got = d.conq.filter((c) => c.day);
  const by = { ouro: 0, prata: 0, bronze: 0 }; got.forEach((c) => by[c.tier]++);
  return `<section class="box"><h2>Troféus <span class="hint">${got.length}/${d.conq.length}</span></h2>
      <p class="hint">${by.ouro} de ouro · ${by.prata} de prata · ${by.bronze} de bronze. Clique para ver como ganhar ou pôr na vitrine.</p>
      <div class="cqgrid pj-tro">${d.conq.map((c, i) => `<button class="cqt${c.day ? " got" : ""}" data-cq="${i}">${trophy(c.tier, !!c.day)}<span>${esc(c.name)}</span></button>`).join("")}</div></section>
    ${vitrine()}`;
}
function trophyModal(i) {
  const c = CQ.conq[i]; if (!c) return;
  const show = CQ.equip.show || [], on = show.includes(c.id);
  const day = c.day && new Date(c.day + "T12:00").toLocaleDateString("pt-BR");
  openModal(`<div class="pj-trom">${trophy(c.tier, !!c.day)}</div><h2 style="text-align:center;margin:4px 0">${esc(c.name)}</h2>
    <p class="hint" style="text-align:center">${TIER[c.tier]} · ${c.xp} XP${c.secret ? " · secreta" : ""}</p><p class="pj-how"><b>Como ganhar:</b> ${esc(c.desc)}</p>
    ${c.day ? `<p class="hint">Conquistada em ${day}.</p><div class="row"><button class="pri" id="tm-show">${on ? "Tirar da vitrine" : "Pôr na vitrine"}</button></div>`
      : c.goal > 1 ? `<div class="jg-bar"><i style="width:${Math.min(100, (c.cur / c.goal) * 100)}%"></i></div><p class="hint">${Math.floor(c.cur)} de ${c.goal}</p>` : '<p class="hint">Ainda não conquistada.</p>'}`);
  if ($("tm-show")) $("tm-show").onclick = async () => {
    const s = [...show], k = s.indexOf(c.id);
    if (k >= 0) s.splice(k, 1); else { if (s.length >= CQ.show_max) return toast(`A vitrine tem ${CQ.show_max} lugares: tire um antes`, "bad"); s.push(c.id); }
    if (await setShow(s, k >= 0 ? "Saiu da vitrine" : "Na vitrine")) closeModal();
  };
}

// ------------------------------------------------------------ Loja e evento
function tabLoja() {
  const d = CQ, c = d.credits, R = c.rules;
  const left = Math.max(0, Math.round((new Date(d.shop.end + "T23:59") - Date.now()) / 86400000));
  const bought = (d.bought || []).map((id) => d.rewards.find((r) => r.id === id)).filter(Boolean);
  return `<section class="box"><h2>Créditos</h2>
      <div class="crbal"><b><i class="crcoin"></i>${c.bal}</b><small>+${c.today} hoje · +${c.week} nesta semana · ${c.earned} ganhos no total · ${c.spent} gastos</small></div>
      <div class="crhow">Como ganhar: meta do dia <b>${R.meta}</b> (as 3 no mesmo dia: +${R.metas3}) · desafio da semana <b>${R.quest}</b> · chefão <b>${R.boss}</b> ·
        cada nível <b>${R.level}</b> · a cada 7 dias seguidos <b>${R.streak7}</b> · conquista bronze/prata/ouro <b>${R.conq.bronze}/${R.conq.prata}/${R.conq.ouro}</b> · evento <b>${R.event}</b>.
        O histórico conta: os créditos são recalculados de tudo o que você já fez.</div></section>
    <section class="box"><h2>Loja da semana <span class="hint">${left ? `troca em ${left} dia${left > 1 ? "s" : ""}` : "troca amanhã"}</span></h2>
      <p class="hint">4 itens que não saem por nível, sorteados toda segunda (pelo menos 1 raro ou melhor).</p>
      <div class="shopgrid pj-shop">${d.shop.items.map((id) => {
        const r = d.rewards.find((x) => x.id === id); if (!r) return "";
        return `<button class="shopit rar-${r.rarity}${r.got ? " own" : c.bal < r.price ? " poor" : ""}" data-it="${esc(id)}">${itemPreview(r, d.level, d.equip)}
          <span class="shn">${esc(r.name)}</span><span class="rartag">${RARITY[r.rarity]} · ${KIND_LABEL[r.kind]}</span>
          <span class="shp">${r.got ? "já é seu" : `<i class="crcoin"></i>${r.price}`}</span></button>`;
      }).join("") || '<p class="hint">Você já tem tudo o que a loja vende!</p>'}</div></section>
    ${eventBox()}
    ${bought.length ? `<section class="box"><h2>Comprados</h2><div class="ivgrid pj-grid">${bought.map(itemBtn).join("")}</div></section>` : ""}`;
}
function eventBox() {
  const d = CQ, e = d.event;
  if (!e) return "";
  const fmtV = (v) => (e.kind === "foco" ? (v >= 60 ? `${Math.floor(v / 60)}h${String(v % 60).padStart(2, "0")}` : `${v} min`) : String(v));
  const items = e.items.map((id) => d.rewards.find((r) => r.id === id)).filter(Boolean);
  const days = Math.round((new Date((e.live ? e.end : e.start) + "T12:00") - Date.now()) / 86400000);
  const br = (x) => new Date(x + "T12:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  return `<section class="box"><h2>Evento</h2><div class="evcard"><div class="evicon">${e.icon}</div><div class="evinfo"><b>${esc(e.name)}</b>
      <small>${e.live ? `até ${br(e.end)} · faltam ${Math.max(0, days)} dias` : `começa em ${br(e.start)} (daqui a ${Math.max(0, days)} dias)`}</small>
      <div style="margin-top:6px">${esc(e.text)}</div>
      ${e.live ? `<div class="jg-bar" style="margin:8px 0 4px"><i style="width:${e.done ? 100 : Math.min(100, (e.value / e.target) * 100)}%"></i></div>
        <small class="${e.done ? "evdone" : ""}">${e.done ? "Completo! Itens liberados." : `${fmtV(e.value)} de ${fmtV(e.target)}`}</small>` : ""}</div></div>
    <div class="ivgrid pj-grid" style="margin-top:12px">${items.map(itemBtn).join("")}</div>
    <div class="evlist">${(d.events || []).map((x) => `<span class="${x.done ? "ok" : ""}">${x.icon} ${esc(x.name)}${x.done ? " ✓" : ""}: ${esc(x.text)}</span>`).join("")}</div>
    <p class="hint" style="margin-top:8px">Os itens de evento só saem durante o evento. Perdeu? Ele volta no ano seguinte.</p></section>`;
}

// ------------------------------------------------------------ Desafios (metas do dia, semana, chefão)
function tabDesafios() {
  const d = CQ, w = d.week, hmm = (s) => (s < 3600 ? `${Math.round(s / 60)} min` : `${Math.floor(s / 3600)}h${String(Math.round((s % 3600) / 60)).padStart(2, "0")}`);
  const fmt = (u, v) => (u === "dur" ? hmm(v) : u === "min" ? hmm(v * 60) : u === "kda" ? (+v).toFixed(1) : String(Math.round(v)));
  const row = (text, value, target, unit, st, cls) => `<div class="pj-q ${cls}"><div class="row" style="justify-content:space-between"><span>${esc(text.replace("{t}", fmt(unit, target)))}</span><small>${esc(st)}</small></div>
    <div class="jg-bar"><i style="width:${Math.max(0, Math.min(100, (value / Math.max(0.01, target)) * 100))}%"></i></div><small class="hint">${fmt(unit, value)} de ${fmt(unit, target)}</small></div>`;
  const ST = { done: "FEITA", failed: "passou", ok: "dentro até agora", skip: "PC quase não usado", open: "" };
  let h = `<section class="box"><h2>Metas de hoje <span class="hint">${d.metas.filter((m) => m.status === "done").length}/${d.metas.length}</span></h2>
    ${d.metas.map((m) => row(m.text, m.value, m.target, m.unit, ST[m.status], m.status === "done" ? "done" : m.status === "failed" ? "bad" : "")).join("") || '<p class="hint">Use o PC um pouco para ganhar metas.</p>'}</section>`;
  if (w) {
    const b = w.boss, left = Math.max(0, b.hp - b.dmg);
    h += `<section class="box"><h2>Desafios da semana <span class="hint">até ${new Date(w.end + "T12:00").toLocaleDateString("pt-BR")}</span></h2>
      ${w.quests.map((q) => row(q.text, q.value, q.target, q.unit, q.day ? "FEITO" : q.status === "failed" ? "não deu" : `+${q.xp} XP · +${d.credits.rules.quest} créditos`, q.day ? "done" : "")).join("")}
      <p class="hint">${w.all ? `Os 3 feitos: +${w.all_xp} XP de bônus.` : `Faça os 3 para ganhar +${w.all_xp} XP de bônus.`}</p></section>
      <section class="box"><h2>Chefão da semana</h2><div class="boss${b.dead ? " dead" : ""}"><div class="bicon">${b.icon}</div><div class="binfo"><b>${esc(b.name)}</b>
        <div class="jg-bar hp"><i style="width:${(left / b.hp) * 100}%"></i></div><small class="hint">${b.dead ? "Derrotado!" : `${left} / ${b.hp} HP · dano hoje: ${b.today}`} · vale +${b.xp} XP e ${d.credits.rules.boss} créditos</small></div></div>
        <p class="hint">Cada minuto de foco tira 1 de vida, cada meta cumprida tira 15 e cada vitória tira 20. Derrote até domingo, senão ele foge.</p></section>`;
  }
  return h;
}

// ------------------------------------------------------------ Ranking: liga, amigos, duelos, geral
const duelsIn = () => (RD.duels?.rows || []).filter((x) => x.dir === "in" && x.status === "pending").length;
const RACT = { league: "rank.league", friends: "rank.friends", duels: "rank.duels" };
async function loadRankTab(force) {
  if (!RANK?.joined) { renderBody(); return; }
  const tab = RTAB, key = tab === "board" ? "b:" + RKIND : tab;
  try { RD[key] = tab === "board" ? await send("rank.board", { kind: RKIND }) : await send(RACT[tab], { force: !!force }); } catch (e) { RD[key] = { error: e.message }; }
  for (const k of ["league", "friends", "duels"]) if (k !== tab && !RD[k]) send(RACT[k], {}).then((d) => { RD[k] = d; renderTabs(); renderSide(); }).catch(() => {});
  if (TAB === "ranking") renderBody();
  renderSide();
}
function rkRow(r, right, cls = "") {
  const t = CQ.rewards.find((x) => x.id === r.title)?.name || "";
  return `<li class="${cls}${r.me || r.nick === RANK?.nick ? " me" : ""}"><span class="rkpos">${r.pos ?? ""}</span>
    <button class="rknick" data-pf="${esc(r.nick)}">${badge(r.level, r.frame, "sm", r.av)}${fxName(r.nick, r.fx)}</button>
    <small>${t ? esc(t) + " · " : ""}nível ${r.level}${r.extra ? " · " + r.extra : ""}</small><b>${right}</b></li>`;
}
function tabRanking() {
  if (!RANK) return '<section class="box"><p class="hint">Carregando…</p></section>';
  if (!RANK.available) return '<section class="box"><p class="hint">O ranking online ainda não está no ar.</p></section>';
  if (!RANK.joined) return `<section class="box"><h2>Entrar no ranking</h2><p class="hint">Compare o seu XP, entre numa liga semanal, siga amigos e desafie para duelos.
      Do seu PC sai só: apelido, nível, XP, sequência, quantos troféus e o seu perfil (título, moldura, avatar, fundo, efeito, cor, vitrine e frase). Nada de apps, sites ou tempo de tela.</p>
    <div class="row"><input type="text" id="rk-nick" maxlength="20" placeholder="Seu apelido (3 a 20 letras)" style="max-width:300px"><button class="pri" id="rk-join">Entrar</button></div></section>`;
  const tabs = `<div class="seg" id="rk-tabs">${[["league", "Liga"], ["friends", "Amigos"], ["duels", "Duelos"], ["board", "Geral"]].map(([k, l]) => `<button data-rt="${k}" class="${k === RTAB ? "on" : ""}">${l}${k === "duels" && duelsIn() ? ` (${duelsIn()})` : ""}</button>`).join("")}</div>`;
  const d = RTAB === "board" ? RD["b:" + RKIND] : RD[RTAB];
  let body = !d ? '<p class="hint">Carregando…</p>' : d.error ? `<p class="pj-warn">${esc(d.error)}</p>` : { league: rkLeague, friends: rkFriends, duels: rkDuels, board: rkBoard }[RTAB](d);
  return `<section class="box"><div class="row" style="justify-content:space-between">${tabs}<span class="hint" style="margin:0">você: <b>${esc(RANK.nick)}</b>
      <button id="rk-ren" style="margin-left:8px">Trocar apelido</button><button id="rk-leave" class="danger">Sair</button></span></div>
    ${RANK.error ? `<p class="pj-warn">${esc(RANK.error)}</p>` : ""}<div class="pj-rk">${body}</div></section>`;
}
function rkLeague(d) {
  const n = d.league || 0;
  const head = `<div class="lghead"><b style="color:${LEAGUE_COLOR[n]}">Liga ${LEAGUES[n]}</b>
    <small>${d.joined ? `grupo de ${d.rows.length} · ${n < 5 ? `os ${d.up} primeiros sobem` : "a liga mais alta"}${d.down ? ` · os ${d.down} últimos descem` : ""}` : "ganhe XP nesta semana para entrar num grupo"} · zera na segunda</small></div>
    ${d.res === "up" ? `<p class="lgres up">Você subiu para a liga ${LEAGUES[n]}!</p>` : d.res === "down" ? `<p class="lgres down">Você caiu para a liga ${LEAGUES[n]}.</p>` : ""}`;
  if (!d.joined) return head;
  return head + `<ol class="rklist lg">${d.rows.map((r) => rkRow({ ...r, pos: r.rank }, `${r.xp} XP`, r.rank <= d.up && n < 5 ? "up" : d.down && r.rank > d.rows.length - d.down ? "down" : "")).join("")}</ol>`;
}
function rkFriends(d) {
  const all = [...d.rows, { ...d.me, me: true }].sort((a, b) => b.week_xp - a.week_xp); all.forEach((r, i) => (r.pos = i + 1));
  return `<div class="row" style="margin:10px 0"><input type="text" id="rk-fnick" maxlength="20" placeholder="Apelido de alguém para seguir" style="max-width:300px"><button class="pri" id="rk-follow">Seguir</button></div>
    ${d.rows.length ? `<ol class="rklist">${all.map((r) => rkRow({ ...r, extra: r.me ? "" : r.mutual ? "segue você" : "" }, `${r.week_xp} XP`)).join("")}</ol>
    <p class="hint">XP desta semana · ${d.followers} pessoa${d.followers === 1 ? "" : "s"} segue${d.followers === 1 ? "" : "m"} você</p>` : '<p class="hint">Siga alguém pelo apelido para comparar o XP da semana e desafiar para duelos.</p>'}`;
}
function rkDuels(d) {
  const rows = d.rows || [], who = (x) => `<button class="rknick" data-pf="${esc(x.nick)}">${esc(x.nick)}</button>`;
  const sec = (t, items, fn) => (items.length ? `<h4 class="dlh">${t}</h4>${items.map(fn).join("")}` : "");
  const pin = rows.filter((x) => x.status === "pending" && x.dir === "in"), act = rows.filter((x) => x.status === "active");
  const pout = rows.filter((x) => x.status === "pending" && x.dir === "out"), done = rows.filter((x) => x.status === "done");
  const html = sec("Convites para você", pin, (x) => `<div class="duel">${who(x)} desafiou você <span><button class="pri" data-duel="${x.id}" data-acc="1">Aceitar</button> <button data-duel="${x.id}" data-acc="0">Recusar</button></span></div>`)
    + sec("Valendo nesta semana", act, (x) => { const p = (x.my / Math.max(1, x.my + x.their)) * 100; return `<div class="duel act"><div class="dlrow"><span>Você <b>${x.my}</b></span><span>${who(x)} <b>${x.their}</b></span></div><div class="dlbar"><i style="width:${p}%"></i></div></div>`; })
    + sec("Esperando resposta", pout, (x) => `<div class="duel">Você desafiou ${who(x)} <button data-duel="${x.id}" data-acc="0">Cancelar</button></div>`)
    + sec("Encerrados", done, (x) => `<div class="duel ${x.res}"><span>${x.res === "won" ? "🏆 Venceu" : x.res === "lost" ? "Perdeu" : "Empate"} contra ${who(x)}</span><small>${x.my} × ${x.their} · ${x.week}</small></div>`);
  return (html || '<p class="hint">Nenhum duelo ainda.</p>') + '<p class="hint" style="margin-top:8px">Para desafiar, clique no apelido de quem você segue e escolha <b>Desafiar</b>. Vence quem ganhar mais XP do aceite até domingo.</p>';
}
function rkBoard(d) {
  const kinds = `<div class="seg" id="rk-kinds" style="margin:10px 0">${[["week", "Semana"], ["level", "Nível"], ["streak", "Sequência"]].map(([k, l]) => `<button data-rk="${k}" class="${k === RKIND ? "on" : ""}">${l}</button>`).join("")}</div>`;
  if (!d.rows.length) return kinds + '<p class="hint">Ninguém pontuou ainda.</p>';
  const val = (r) => (RKIND === "week" ? `${r.value} XP` : RKIND === "level" ? `nível ${r.level}` : `${r.value} dias`);
  const my = d.me?.ranks?.[RKIND];
  return kinds + `<ol class="rklist">${d.rows.map((r) => rkRow({ ...r, pos: "#" + r.rank, extra: `${r.unlocked} troféus` }, val(r))).join("")}</ol>
    ${my && my > d.rows.length ? `<p class="hint">… você: #${my}</p>` : ""}<p class="hint">${d.players} jogadores</p>`;
}
async function openProfile(nick) {
  openModal('<p class="hint">Carregando…</p>');
  let p; try { p = await send("rank.profile", { nick }); } catch (e) { $("modal-body").innerHTML = `<p class="pj-warn">${esc(e.message)}</p>`; return; }
  const pf = p.pf || {}, mine = p.nick === RANK?.nick, follows = (RD.friends?.rows || []).some((r) => r.nick === p.nick);
  const show = p.show.map((id) => CQ.conq.find((c) => c.id === id)).filter(Boolean);
  const nm = CQ.rewards.find((x) => x.id === p.title)?.name || "Novato";
  $("modal-body").innerHTML = `<div id="pf-other">${profileCard({ nick: p.nick, level: p.level, title: nm, frame: p.frame, avatar: pf.av, effect: pf.fx, bg: pf.bg,
      bio: pf.bio, lay: pf.lay || ["stats", "show"], sub: p.streak ? `🔥 ${p.streak} dias` : "",
      stats: [[p.level, "nível"], [p.week_xp, "XP na semana"], [p.best_streak ?? p.streak, "recorde"], [p.unlocked, "troféus"]],
      show: show.length ? `<div class="shrow">${show.map((c) => `<div class="cqt got">${trophy(c.tier, true)}<span>${esc(c.name)}</span></div>`).join("")}</div>` : '<p class="hint">Nada na vitrine.</p>',
      league: p.league != null ? `<span class="lgtag" style="--lg:${LEAGUE_COLOR[p.league]}">Liga ${LEAGUES[p.league]}</span>` : "" })}</div>
    ${mine ? "" : `<div class="row" style="margin-top:14px">${follows ? '<button id="pf-unf">Deixar de seguir</button><button class="pri" id="pf-duel">Desafiar para duelo</button>' : '<button class="pri" id="pf-fol">Seguir</button>'}</div>`}`;
  accentApply($("pf-other"), pf.acc, pf.col);
  const doIt = async (a, msg, tab) => { try { RD[tab] = await send(a, { nick: p.nick }); toast(msg); closeModal(); renderBody(); } catch (e) { toast(e.message, "bad"); } };
  if ($("pf-fol")) $("pf-fol").onclick = () => doIt("rank.friend.add", `Seguindo ${p.nick}`, "friends");
  if ($("pf-unf")) $("pf-unf").onclick = () => doIt("rank.friend.del", `Deixou de seguir ${p.nick}`, "friends");
  if ($("pf-duel")) $("pf-duel").onclick = () => { RTAB = "duels"; doIt("rank.duel.new", `Duelo enviado para ${p.nick}`, "duels"); };
}

// ------------------------------------------------------------ janela
function openModal(html) { $("modal-body").innerHTML = html; $("modal").hidden = false; }
function closeModal() { $("modal").hidden = true; }
$("modal-x").onclick = closeModal;
$("modal").onclick = (e) => { if (e.target === $("modal")) closeModal(); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

// ------------------------------------------------------------ eventos do corpo da página
function bindBody() {
  const B = $("body");
  // coleção: passar o mouse mostra no cartão; clicar usa (ou abre a janela, se bloqueado ou da loja)
  B.querySelectorAll("[data-it]").forEach((b) => {
    const r = CQ.rewards.find((x) => x.id === b.dataset.it); if (!r) return;
    if (["title", "frame", "avatar", "bg", "effect", "accent"].includes(r.kind)) {
      b.onmouseenter = () => { hover = { [r.kind]: r.id }; renderSide(); };
      b.onmouseleave = () => { hover = null; renderSide(); };
    }
    b.onclick = () => {
      if (r.kind === "sound") playSound(r.id);
      if (!r.got || b.classList.contains("shopit")) return itemModal(r);
      useItem(r);
    };
  });
  B.querySelectorAll("[data-goto]").forEach((b) => (b.onclick = () => {
    TAB = "colecao"; FILTER = "all"; render(); pvView("inv");
    setTimeout(() => document.getElementById("k-" + b.dataset.goto)?.scrollIntoView({ behavior: "smooth", block: "start" }), 30);
  }));
  B.querySelectorAll("#pj-filter [data-f]").forEach((b) => (b.onclick = () => { FILTER = b.dataset.f; renderBody(); }));
  B.querySelectorAll("[data-cq]").forEach((b) => (b.onclick = () => trophyModal(+b.dataset.cq)));
  // perfil
  if ($("pf-bio-ok")) {
    $("pf-bio-ok").onclick = () => { $("pf-bio").blur(); act("conq.profile", { bio: $("pf-bio").value }, "Frase salva"); };
    $("pf-bio").onkeydown = (e) => { if (e.key === "Enter") $("pf-bio-ok").click(); };
  }
  B.querySelectorAll("[data-lt]").forEach((c) => (c.onchange = () => act("conq.profile", { lay: layFromDom() })));
  if ($("pf-color")) $("pf-color").onchange = () => act("conq.profile", { color: $("pf-color").value }, "Cor salva");
  B.querySelectorAll("[data-vrm]").forEach((b) => (b.onclick = () => setShow((CQ.equip.show || []).filter((x) => x !== b.dataset.vrm), "Saiu da vitrine")));
  // ranking
  if ($("rk-join")) $("rk-join").onclick = async () => {
    const nick = $("rk-nick").value.trim(); if (nick.length < 3) return toast("O apelido precisa de pelo menos 3 letras", "bad");
    try { RANK = await send("rank.join", { nick }); RD = {}; toast(`No ranking como ${RANK.nick}`); loadRankTab(true); } catch (e) { toast(e.message, "bad"); }
  };
  B.querySelectorAll("#rk-tabs [data-rt]").forEach((b) => (b.onclick = () => { RTAB = b.dataset.rt; renderBody(); if (!(RTAB === "board" ? RD["b:" + RKIND] : RD[RTAB])) loadRankTab(); }));
  B.querySelectorAll("#rk-kinds [data-rk]").forEach((b) => (b.onclick = () => { RKIND = b.dataset.rk; renderBody(); if (!RD["b:" + RKIND]) loadRankTab(); }));
  B.querySelectorAll("[data-pf]").forEach((b) => (b.onclick = () => openProfile(b.dataset.pf)));
  B.querySelectorAll("[data-duel]").forEach((b) => (b.onclick = async () => {
    try { RD.duels = await send("rank.duel.answer", { id: +b.dataset.duel, accept: b.dataset.acc === "1" }); renderBody(); renderTabs(); } catch (e) { toast(e.message, "bad"); }
  }));
  if ($("rk-follow")) {
    const go = async () => { const nick = $("rk-fnick").value.trim(); if (!nick) return; try { RD.friends = await send("rank.friend.add", { nick }); toast(`Seguindo ${nick}`); $("rk-fnick").blur(); renderBody(); } catch (e) { toast(e.message, "bad"); } };
    $("rk-follow").onclick = go; $("rk-fnick").onkeydown = (e) => e.key === "Enter" && go();
  }
  if ($("rk-ren")) $("rk-ren").onclick = async () => {
    const nick = prompt("Novo apelido (dá para trocar uma vez por dia):", RANK.nick); if (!nick) return;
    try { RANK = await send("rank.nick", { nick }); RD = {}; toast("Apelido trocado"); loadRankTab(true); } catch (e) { toast(e.message, "bad"); }
  };
  if ($("rk-leave")) $("rk-leave").onclick = async () => {
    if (!confirm("Sair do ranking? A sua conta, a liga, os amigos e os duelos são apagados do servidor.")) return;
    try { RANK = await send("rank.leave", {}); RD = {}; toast("Você saiu do ranking"); renderBody(); } catch (e) { toast(e.message, "bad"); }
  };
}
const layFromDom = () => [...document.querySelectorAll("#pj-lay [data-lb]")].filter((el) => el.querySelector("input").checked).map((el) => el.dataset.lb);

// arrastar: blocos do perfil e vitrine
let drag = null;
document.addEventListener("dragstart", (e) => {
  const el = e.target.closest?.("[data-lb], [data-vc], .pj-slot.full"); if (!el) return;
  drag = el.dataset.lb ? { kind: "lb", id: el.dataset.lb } : el.dataset.vc ? { kind: "vc", id: el.dataset.vc } : { kind: "vs", i: +el.dataset.vs };
  el.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", "x");
});
document.addEventListener("dragend", (e) => { e.target.closest?.(".dragging")?.classList.remove("dragging"); drag = null; document.querySelectorAll(".drop-ok").forEach((x) => x.classList.remove("drop-ok")); });
document.addEventListener("dragover", (e) => {
  if (!drag) return;
  const t = drag.kind === "lb" ? e.target.closest?.("[data-lb]") : e.target.closest?.(".pj-slot[data-vs]");
  if (!t) return;
  e.preventDefault(); document.querySelectorAll(".drop-ok").forEach((x) => x.classList.remove("drop-ok")); t.classList.add("drop-ok");
});
document.addEventListener("drop", (e) => {
  if (!drag) return;
  e.preventDefault();
  if (drag.kind === "lb") {
    const t = e.target.closest?.("[data-lb]"); if (!t || t.dataset.lb === drag.id) return;
    const box = $("pj-lay"), src = box.querySelector(`[data-lb="${drag.id}"]`), r = t.getBoundingClientRect();
    box.insertBefore(src, e.clientY < r.top + r.height / 2 ? t : t.nextSibling);
    act("conq.profile", { lay: layFromDom() });
    return;
  }
  const t = e.target.closest?.(".pj-slot[data-vs]"); if (!t) return;
  const show = [...(CQ.equip.show || [])], to = Math.min(+t.dataset.vs, show.length);
  if (drag.kind === "vc") {
    if (show.includes(drag.id)) show.splice(show.indexOf(drag.id), 1);
    if (to < show.length && show.length >= CQ.show_max) show[to] = drag.id; else show.splice(to, 0, drag.id);
  } else {
    const [x] = show.splice(drag.i, 1); show.splice(Math.min(to, show.length), 0, x);
  }
  setShow(show.slice(0, CQ.show_max));
});

// sons das conquistas (mesmas notas do app)
const SND = { s_bipe: [[1400, 0.045], [2100, 0.06]], s_fanfarra: [[523, 0.09], [659, 0.09], [784, 0.09], [1047, 0.22]], s_moeda: [[988, 0.06], [1319, 0.2]],
  s_arcade: [[660, 0.05], [880, 0.05], [1100, 0.05], [1320, 0.05], [1760, 0.12]], s_sino: [[1568, 0.12], [2093, 0.3]],
  s_vitoria: [[784, 0.1], [784, 0.06], [784, 0.06], [1047, 0.12], [988, 0.1], [1047, 0.28]],
  s_powerup: [[392, 0.04], [523, 0.04], [659, 0.04], [784, 0.04], [1047, 0.04], [1319, 0.04], [1568, 0.12]],
  s_laser: [[2400, 0.03], [1800, 0.03], [1300, 0.03], [900, 0.05], [600, 0.08]],
  s_harpa: [[523, 0.07], [659, 0.07], [784, 0.07], [988, 0.07], [1175, 0.07], [1568, 0.25]],
  s_natal: [[1319, 0.1], [1319, 0.1], [1319, 0.2], [1319, 0.1], [1319, 0.1], [1319, 0.2], [1319, 0.1], [1568, 0.1], [1047, 0.12], [1175, 0.1], [1319, 0.3]] };
let actx = null;
function playSound(id) {
  try {
    actx = actx || new AudioContext();
    let t = actx.currentTime + 0.005;
    for (const [f, d] of SND[id] || []) {
      const o = actx.createOscillator(), g = actx.createGain();
      o.type = "square"; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.04, t + 0.004); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
      o.connect(g).connect(actx.destination); o.start(t); o.stop(t + d + 0.01); t += d;
    }
  } catch {}
}

document.body.insertAdjacentHTML("afterbegin", TROPHY_DEFS);
try { ANIM.pref = JSON.parse(localStorage.getItem("pcc.anim") ?? "true"); } catch {}
animSync();
connect();
