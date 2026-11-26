const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const clone = (o) => JSON.parse(JSON.stringify(o));

// mesmos nomes do app (index.html)
const VIEW_LABEL = { dash: "Sistema", today: "Hoje", conq: "Resumo", quests: "Desafios", troph: "Troféus", inv: "Recompensas", loja: "Loja", rank: "Ranking", games: "Jogos", usage: "Tempo", media: "Tocando", mix: "Mixer", mouse: "Mouse e teclado",
  screen: "Tela do PC", deck: "Botões", send: "Arquivos", power: "Energia", voz: "Voz", sys: "Ajustes" };
const BASE_VIEWS = Object.keys(VIEW_LABEL);
const DEFAULT_NAV = [
  { id: "status", label: "Status", views: ["dash", "today", "games", "usage"] },
  { id: "xp", label: "Jogador", views: ["conq", "quests", "troph", "inv", "loja", "rank"] }, { id: "radio", label: "Rádio", views: ["media", "mix"] },
  { id: "ctrl", label: "Controle", views: ["mouse", "screen"] }, { id: "deck", label: "Botões", views: ["deck"] },
  { id: "pc", label: "PC", views: ["send", "power", "voz", "sys"] }];
const CARD_LABEL = { cpu: "CPU", ram: "Memória", gpu: "GPU", net: "Rede", procs: "Processos", disks: "Discos", bat: "Bateria", sys: "Sistema" };
const DEFAULT_DASH = {
  portrait: [["cpu", 1], ["ram", 1], ["gpu", 1], ["net", 1], ["bat", 2], ["procs", 2], ["disks", 2], ["sys", 2]],
  landscape: [["cpu", 1], ["ram", 1], ["gpu", 1], ["net", 1], ["procs", 1], ["disks", 1], ["bat", 1], ["sys", 1]],
};
const COLS = { portrait: 2, landscape: 4 };
// telas e seus blocos (data-b no index.html); cada grupo é um conjunto de irmãos que dá para reordenar
const SCREENS = [["dash", "Sistema"], ["play", "Jogando"], ["meet", "Reunião"], ["today", "Hoje"], ["conq", "Jogador: Resumo"], ["quests", "Jogador: Desafios"],
  ["troph", "Jogador: Troféus"], ["inv", "Jogador: Recompensas"], ["loja", "Jogador: Loja"], ["rank", "Jogador: Ranking"], ["games", "Jogos"], ["usage", "Tempo"], ["media", "Tocando"],
  ["mix", "Mixer"], ["mouse", "Mouse e teclado"], ["send", "Arquivos"], ["power", "Energia"], ["voz", "Voz"], ["sys", "Ajustes"]];
const BLOCKS = {
  play: [{ wide: 1, items: [["hero", "Jogo (capa, tempo e atalhos)"], ["perf", "Desempenho e FPS"], ["gsi", "Partida (CS2 / Dota 2)"], ["post", "Fim de partida (comparação)"], ["agora", "Dota: próximo item, skill e talento"], ["tact", "Timers do Dota / bomba e economia do CS"], ["dota", "Dota 2: draft e build"], ["graph", "Gráficos do Dota / rounds do CS"]] },
    { title: "Atalhos do jogo", items: [["a-mic", "MIC (microfone do PC)"], ["a-dmute", "Discord mudo"], ["a-ddeaf", "Discord surdo"], ["a-shot", "Print F12"], ["a-clip", "Clipe 30 s (Game Bar)"]] }],
  meet: [{ wide: 1, items: [["head", "Título, pessoas e tempo"], ["btns", "Botões"]] },
    { title: "Botões da reunião", items: [["m-mic", "Microfone"], ["m-cam", "Câmera"], ["m-share", "Compartilhar tela"], ["m-hand", "Levantar a mão"],
      ["m-captions", "Legendas"], ["m-chat", "Chat"], ["m-focus", "Mostrar no PC"], ["m-leave", "Sair"]] }],
  today: [{ wide: 1, items: [["weather", "Clima"], ["agenda", "Agenda"], ["day", "Seu dia (resumo)"], ["focus", "Foco"]] }],
  conq: [{ wide: 1, items: [["level", "Jogador (nível, título e sequência)"], ["metas", "Metas de hoje"], ["retro", "Retrospectiva do mês"]] }],
  quests: [{ wide: 1, items: [["week", "Desafios da semana"], ["boss", "Chefão da semana"]] }],
  troph: [{ wide: 1, items: [["show", "Vitrine"], ["conq", "Conquistas (troféus)"]] }],
  inv: [{ wide: 1, items: [["next", "Próximas recompensas"], ["perfil", "Perfil (frase e blocos)"], ["title", "Títulos"], ["frame", "Molduras"], ["avatar", "Avatares"], ["bg", "Fundos do cartão"],
    ["effect", "Efeito no nome"], ["accent", "Cor de destaque"], ["theme", "Temas"], ["sound", "Som das conquistas"], ["alerts", "Avisos"]] }],
  loja: [{ wide: 1, items: [["credits", "Créditos"], ["shop", "Loja da semana"], ["event", "Evento"]] }],
  rank: [{ wide: 1, items: [["rank", "Ranking (liga, amigos, duelos, geral)"]] }],
  games: [{ wide: 1, items: [["now", "Jogo atual"], ["recent", "Jogados recentemente"], ["week", "Esta semana"], ["post", "Fim de partida"], ["dl", "Downloads da Steam"], ["friends", "Amigos da Steam"], ["dota", "Dota 2: draft e build"], ["hist", "Partidas (CS2 / Dota 2)"], ["lib", "Biblioteca"]] }],
  usage: [{ items: [["range", "Hoje / Semana / Mês"]] }, { wide: 1, items: [["total", "Total, gráfico e categorias"], ["apps", "Por aplicativo"]] }],
  media: [{ items: [["art", "Capa"], ["info", "Música e artista"], ["prog", "Barra de progresso"], ["ctrls", "Anterior / tocar / próxima"], ["vol", "Volume"], ["out", "Saída de áudio"]] }],
  mix: [{ wide: 1, items: [["outs", "Saída de áudio"], ["profiles", "Perfis de áudio"], ["apps", "Volume por aplicativo"]] }],
  mouse: [{ items: [["pad", "Touchpad"], ["mbtns", "Botões do mouse"], ["keys1", "Teclas: teclado, Ctrl, Alt, Enter…"], ["keys2", "Teclas: setas, copiar, colar…"]] }],
  send: [{ wide: 1, items: [["text", "Texto para o PC"], ["files", "Arquivos para o PC"], ["get", "PC para o celular"]] }],
  power: [{ wide: 1, items: [["power", "Desligar, suspender, reiniciar…"], ["timer", "Timer"]] }],
  voz: [{ wide: 1, items: [["cfg", "Ajustes de voz"], ["test", "Testar"], ["tips", "Como falar"], ["help", "O que dá para falar"]] }],
  sys: [{ wide: 1, items: [["alerts", "Alertas"], ["visual", "Visual"], ["device", "Este aparelho", 1]] }],
};
const NOTES = {
  play: "Só aparece com um jogo aberto. A prévia mostra a tela vazia.",
  meet: "Só aparece numa chamada do Meet. Entrar aparece sozinho na sala de espera.",
  media: "Deitado, a capa fica sempre à esquerda.",
  mouse: "Deitado, touchpad e botões ficam à esquerda e as teclas à direita; a ordem vale dentro de cada lado.",
  sys: "Este aparelho fica sempre visível: é onde troca o token.",
};
let SCR = "dash";
// THEMES e VAR_NAME ficam em catalogo.js (os mesmos do app)

// ------------------------------------------------------------ conexão
const m = location.hash.match(/[#&]t=([^&]+)/);
if (m) { try { localStorage.setItem("pcc.token", JSON.stringify(decodeURIComponent(m[1]))); } catch {} history.replaceState(null, "", location.pathname); }
let TOKEN = ""; try { TOKEN = JSON.parse(localStorage.getItem("pcc.token") || '""'); } catch {}
let WEB = +(document.querySelector('meta[name="build"]')?.content || 0) || null, ws = null, rid = 0, LAY = {}, DECK = null, O = "portrait", page = 0;
const pending = new Map();
function status(cls, text) { $("status").className = cls; $("status").lastElementChild.textContent = text; }
function send(a, p, timeout) {
  return new Promise((res, rej) => {
    if (!ws || ws.readyState !== 1) return rej(new Error("desconectado"));
    const id = ++rid; pending.set(id, { res, rej }); ws.send(JSON.stringify({ t: "req", id, a, p }));
    setTimeout(() => pending.delete(id) && rej(new Error("sem resposta")), timeout || (a === "daily.set" || a === "steam.set" || a === "stratz.set" ? 45000 : 8000));
  });
}
function connect() {
  if (!TOKEN) { $("login").hidden = false; $("app").hidden = true; status("bad", "Sem token"); return; }
  ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => ws.send(JSON.stringify({ t: "hello", token: TOKEN, role: "editor" }));
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.t === "welcome" && msg.web && WEB && msg.web !== WEB) { location.reload(); return; }   // servidor atualizado: pega o editor novo
    if (msg.t === "welcome") { WEB = WEB || msg.web; LAY = msg.layout || {}; $("login").hidden = true; $("app").hidden = false; status("ok", "Conectado · tudo salvo"); renderAll(); loadDeck(); loadDaily(); loadSteam(); loadStratz(); loadConq(); mountPreviews(); }
    else if (msg.t === "res") { const p = pending.get(msg.id); if (p) { pending.delete(msg.id); msg.ok ? p.res(msg.d) : p.rej(new Error(msg.e)); } }
    else if (msg.t === "layout" && !saveT) { LAY = msg.d || {}; renderAll(); }
    else if (msg.t === "deck" && msg.d) { DECK = msg.d.deck; renderDeck(); }
    else if (msg.t === "conq" && msg.d) { CQ = msg.d; renderConq(); }
  };
  ws.onclose = (e) => {
    ws = null;
    if (e.code === 4001) { TOKEN = ""; try { localStorage.removeItem("pcc.token"); } catch {} connect(); return; }
    status("bad", "Desconectado · tentando de novo"); setTimeout(connect, 2000);
  };
}
$("tok-ok").onclick = () => { TOKEN = $("tok").value.trim(); try { localStorage.setItem("pcc.token", JSON.stringify(TOKEN)); } catch {} connect(); };

// ------------------------------------------------------------ salvar (automático)
let saveT = null;
function save() {
  status("saving", "Salvando…");
  clearTimeout(saveT);
  saveT = setTimeout(async () => {
    try { LAY = await send("layout.set", { layout: LAY }); status("ok", "Conectado · tudo salvo"); }
    catch (e) { status("bad", "Erro ao salvar: " + e.message); }
    saveT = null;
  }, 250);
}

// ------------------------------------------------------------ modelo
const LEGACY_VIEWS = ["dash", "games", "usage", "media", "mix", "mouse", "screen", "deck", "send", "power", "voz", "sys"];
// abas novas (que o layout salvo ainda não conhecia) entram na seção padrão delas, como no app
const XP_VIEWS = ["conq", "quests", "troph", "inv", "loja", "rank"];
function migrateXp(nav, known) {   // igual ao layout.js: menu salvo antes da 1.18 ganha a seção Jogador
  const k = new Set(known || LEGACY_VIEWS);
  if (k.has("quests") || nav.some((s) => s.id === "xp")) return nav;
  const at = nav.findIndex((s) => s.views.includes("conq"));
  const views = at >= 0 || !k.has("conq") ? XP_VIEWS : XP_VIEWS.slice(1);
  nav = nav.map((s) => ({ ...s, views: s.views.filter((v) => !XP_VIEWS.includes(v)) })).filter((s) => s.views.length);
  nav.splice(at >= 0 ? Math.min(at + 1, nav.length) : Math.min(1, nav.length), 0, { id: "xp", label: "Jogador", views });
  return nav;
}
function navOf(o) {
  const nav = migrateXp(clone(LAY[o]?.nav || DEFAULT_NAV), LAY[o]?.known);
  const k = new Set(LAY[o]?.known || LEGACY_VIEWS), used = new Set(nav.flatMap((s) => s.views));
  for (const v of BASE_VIEWS) {
    if (used.has(v) || k.has(v)) continue;
    const def = DEFAULT_NAV.find((d) => d.views.includes(v)), sec = nav.find((s) => s.id === def?.id) || nav[0];
    const prev = def ? def.views[def.views.indexOf(v) - 1] : null, i = sec.views.indexOf(prev);
    sec.views.splice(i >= 0 ? i + 1 : sec.views.length, 0, v);
  }
  return nav;
}
function dashOf(o) { return clone(LAY[o]?.dash || DEFAULT_DASH[o].map(([id, span]) => ({ id, span, hidden: false }))); }
function setNav(nav) { LAY[O] = { ...(LAY[O] || {}), nav, known: BASE_VIEWS }; save(); renderLayout(); }
function setDash(dash) { LAY[O] = { ...(LAY[O] || {}), dash }; save(); renderLayout(); }
function blocksOf(o, v) {
  const cat = BLOCKS[v].flatMap((g) => g.items.map(([id]) => id));
  const saved = (LAY[o]?.blocks?.[v] || []).filter((b) => cat.includes(b.id)), have = new Set(saved.map((b) => b.id));
  return [...saved.map((b) => ({ ...b })), ...cat.filter((id) => !have.has(id)).map((id) => ({ id, hidden: false, wide: false }))];
}
function setBlocks(v, list) {
  const o = { ...(LAY[O] || {}) }, blocks = { ...(o.blocks || {}) };
  if (list) blocks[v] = list; else delete blocks[v];
  o.blocks = blocks; LAY[O] = o; save(); renderScreens(); preview(v);
}

// ------------------------------------------------------------ arrastar e soltar
// Itens com data-drag="tipo:id" vão para listas com data-drop="tipo"; a posição vem do mouse.
let drag = null;
document.addEventListener("dragstart", (e) => {
  const el = e.target.closest?.("[data-drag]"); if (!el) return;
  const [kind, id] = el.dataset.drag.split(":");
  drag = { kind, id, el }; el.classList.add("dragging");
  e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", el.dataset.drag);
});
document.addEventListener("dragend", () => { drag?.el.classList.remove("dragging"); drag = null; clearPh(); });
function clearPh() { document.querySelectorAll(".ph").forEach((p) => p.remove()); document.querySelectorAll(".drop-ok").forEach((d) => d.classList.remove("drop-ok")); }
function dropIndex(list, e, horizontal) {
  const items = [...list.children].filter((c) => c.dataset.drag && !c.classList.contains("dragging"));
  for (let i = 0; i < items.length; i++) {
    const r = items[i].getBoundingClientRect();
    if (horizontal ? e.clientX < r.left + r.width / 2 : e.clientY < r.top + r.height / 2) return [i, items[i]];
  }
  return [items.length, null];
}
document.addEventListener("dragover", (e) => {
  if (!drag) return;
  const pageTab = e.target.closest?.(".pg");
  if (drag.kind === "btn" && pageTab && +pageTab.dataset.i !== page) { e.preventDefault(); clearPh(); pageTab.classList.add("drop-ok"); return; }
  const list = e.target.closest?.(`[data-drop="${drag.kind}"]`); if (!list) return;
  e.preventDefault();
  const horizontal = list.dataset.dir === "h";
  const [, before] = dropIndex(list, e, horizontal);
  clearPh(); list.classList.add("drop-ok");
  const ph = document.createElement("div"); ph.className = "ph" + (horizontal ? " v" : "");
  list.insertBefore(ph, before);
});
document.addEventListener("drop", (e) => {
  if (!drag) return;
  e.preventDefault();
  const pageTab = e.target.closest?.(".pg");
  if (drag.kind === "btn" && pageTab && +pageTab.dataset.i !== page) { moveBtnToPage(+drag.id, +pageTab.dataset.i); clearPh(); return; }
  const list = e.target.closest?.(`[data-drop="${drag.kind}"]`); if (!list) { clearPh(); return; }
  const [idx] = dropIndex(list, e, list.dataset.dir === "h");
  clearPh();
  onDrop(drag.kind, drag.id, list, idx);
});
function onDrop(kind, id, list, idx) {
  if (kind === "view") {
    const nav = navOf(O);
    for (const s of nav) s.views = s.views.filter((v) => v !== id);
    const target = list.dataset.sec;
    if (target === "_hidden") { if (id === "sys") return alert("Ajustes não pode ficar escondido (é onde fica o tema e a conexão)."); }
    else { const s = nav.find((x) => x.id === target); s.views.splice(idx, 0, id); }
    setNav(nav.filter((s) => s.views.length || s._new));
    preview(id);
  } else if (kind === "sec") {
    const nav = navOf(O), from = nav.findIndex((s) => s.id === id);
    const [s] = nav.splice(from, 1); nav.splice(idx > from ? idx - 1 : idx, 0, s);
    setNav(nav);
  } else if (kind === "card") {
    const dash = dashOf(O), from = dash.findIndex((d) => d.id === id);
    const [d] = dash.splice(from, 1); dash.splice(idx > from ? idx - 1 : idx, 0, d);
    setDash(dash); preview("dash");
  } else if (kind.startsWith("blk")) {
    const ids = BLOCKS[SCR][+kind.slice(3)].items.map(([b]) => b), list = blocksOf(O, SCR);
    const grp = list.filter((b) => ids.includes(b.id)), from = grp.findIndex((b) => b.id === id);
    const [x] = grp.splice(from, 1); grp.splice(idx > from ? idx - 1 : idx, 0, x);
    let k = 0; setBlocks(SCR, list.map((b) => (ids.includes(b.id) ? grp[k++] : b)));
  } else if (kind === "btn") {
    const btns = DECK.pages[page].buttons, from = +id;
    const [b] = btns.splice(from, 1); btns.splice(idx > from ? idx - 1 : idx, 0, b);
    saveDeck();
  } else if (kind === "page") {
    const from = +id, [p] = DECK.pages.splice(from, 1); const to = idx > from ? idx - 1 : idx;
    DECK.pages.splice(to, 0, p); page = to; saveDeck();
  }
}

// ------------------------------------------------------------ desenho
function renderAll() { renderThemes(); renderAuto(); renderLayout(); }
function renderThemes() {
  const skin = LAY.skin || "fallout", theme = LAY.theme;
  $("themes").innerHTML = THEMES.map((t) => {
    const free = t.variants.filter(([id]) => !themeLock(t.id, id)), all = !free.length;
    const v = t.variants.find(([id]) => id === theme && t.id === skin) || free[0] || t.variants[0];
    const [, , , bg, fg, acc] = v;
    return `<div class="thm${t.id === skin ? " on" : ""}${all ? " lockall" : ""}" data-skin="${t.id}" style="background:${bg};color:${fg}">
      <span class="tn" style="font-family:'${t.font}';font-size:${t.id === "lcd" ? 12 : 20}px">${all ? "🔒 " : ""}${t.name}</span><small>${t.desc}</small>
      ${t.variants.length > 1 ? `<div class="vars">${t.variants.map(([id, label, sw]) => { const lk = themeLock(t.id, id); return `<button data-var="${id}" class="${t.id === skin && id === (theme || t.variants[0][0]) ? "on" : ""}${lk ? " lock" : ""}" style="background:${sw}" title="${esc(label)}${lk ? " · libera no " + esc(lk) : ""}">${lk ? "🔒" : ""}</button>`; }).join("")}</div>` : ""}
      <div class="bars"><i style="background:${fg}"></i><i style="background:${acc}"></i><i style="background:${fg};opacity:.4"></i></div></div>`;
  }).join("");
  const t = THEMES.find((x) => x.id === skin) || THEMES[0];
  $("crt-wrap").hidden = !t.crt;
  $("crt").checked = LAY.crt !== false;
}
$("themes").onclick = (e) => {
  const card = e.target.closest(".thm"); if (!card) return;
  const t = THEMES.find((x) => x.id === card.dataset.skin);
  let v = e.target.closest("[data-var]")?.dataset.var;
  if (!v && !(LAY.skin === t.id && t.variants.some(([id]) => id === LAY.theme))) v = (t.variants.find(([id]) => !themeLock(t.id, id)) || t.variants[0])[0];
  if (v && themeLock(t.id, v)) { status("bad", `Esse tema libera no ${themeLock(t.id, v)} (Jogador › Recompensas)`); return; }
  LAY.skin = t.id; LAY.theme = v || (LAY.skin === t.id && t.variants.some(([id]) => id === LAY.theme) ? LAY.theme : t.variants[0][0]);
  renderThemes(); save();
};
$("crt").onchange = () => { LAY.crt = $("crt").checked; save(); };
// troca automática
function renderAuto() {
  const opts = '<option value="">(o escolhido acima)</option>' + THEMES.map((t) => t.variants.filter(([v]) => !themeLock(t.id, v)).map(([v, label]) => `<option value="${t.id}:${v}">${esc(t.name)}${t.variants.length > 1 ? " · " + esc(label) : ""}</option>`).join("")).join("");
  const a = LAY.auto || {}, tm = a.time || {}, gm = a.game || {};
  for (const id of ["au-day", "au-night", "au-dota", "au-cs"]) $(id).innerHTML = opts;
  $("au-time").checked = !!tm.on; $("au-day").value = tm.day || ""; $("au-night").value = tm.night || "jp:night";
  $("au-from").value = tm.from || "19:00"; $("au-to").value = tm.to || "07:00";
  $("au-game").checked = !!gm.on; $("au-dota").value = gm.dota2 || "rpg:stone"; $("au-cs").value = gm.cs2 || "tac:olive";
}
function saveAuto() {
  LAY.auto = { time: { on: $("au-time").checked, day: $("au-day").value, night: $("au-night").value, from: $("au-from").value || "19:00", to: $("au-to").value || "07:00" },
               game: { on: $("au-game").checked, dota2: $("au-dota").value, cs2: $("au-cs").value } };
  save();
}
for (const id of ["au-time", "au-day", "au-night", "au-from", "au-to", "au-game", "au-dota", "au-cs"]) $(id).onchange = saveAuto;

function renderLayout() {
  document.querySelectorAll("#orient button").forEach((b) => b.classList.toggle("on", b.dataset.o === O));
  $("pv-portrait").classList.toggle("cur", O === "portrait"); $("pv-landscape").classList.toggle("cur", O === "landscape");
  $("copy-other").textContent = O === "portrait" ? "Copiar de deitado" : "Copiar de em pé";
  const nav = navOf(O), used = new Set(nav.flatMap((s) => s.views));
  const hidden = BASE_VIEWS.filter((v) => !used.has(v));
  const chip = (v) => `<div class="chip${v === "sys" ? " lock" : ""}" draggable="true" data-drag="view:${v}" data-view="${v}"><span>${VIEW_LABEL[v]}</span>${v === "sys" ? "<small>fixa</small>" : ""}</div>`;
  $("nav").innerHTML = `<div class="nav" data-drop="sec" data-dir="h" style="display:contents">${nav.map((s) => `
    <div class="sec" draggable="true" data-drag="sec:${esc(s.id)}">
      <div class="sh"><span class="grip" title="arraste para mudar a ordem">::</span><input type="text" value="${esc(s.label)}" data-label="${esc(s.id)}" maxlength="14">
        <button class="del" data-del="${esc(s.id)}" title="apagar seção (as abas vão para Escondidas)">×</button></div>
      <div class="chips" data-drop="view" data-sec="${esc(s.id)}">${s.views.map(chip).join("")}</div></div>`).join("")}</div>
    <button class="addsec" id="addsec">+ Nova seção</button>
    <div class="sec hiddenzone"><div class="sh"><b style="color:var(--dim)">Escondidas</b></div>
      <div class="chips" data-drop="view" data-sec="_hidden">${hidden.map(chip).join("") || '<div class="empty">Arraste aqui o que não usa</div>'}</div></div>`;
  const dash = dashOf(O), maxSpan = COLS[O];
  $("cards").dataset.drop = "card";
  $("cards").innerHTML = dash.map((d) => `<div class="card${d.hidden ? " off" : ""}" draggable="true" data-drag="card:${d.id}">
    <span class="grip">::</span><span>${CARD_LABEL[d.id]}</span>
    <div class="seg">${[1, 2, 3, 4].filter((n) => n <= maxSpan).map((n) => `<button data-span="${d.id}:${n}" class="${Math.min(d.span, maxSpan) === n ? "on" : ""}">${n === maxSpan ? "inteiro" : n === 1 ? "1 col" : n + " col"}</button>`).join("")}</div>
    <label class="chk"><input type="checkbox" data-show="${d.id}" ${d.hidden ? "" : "checked"}> mostrar</label></div>`).join("");
  $("minigrid").style.gridTemplateColumns = `repeat(${maxSpan}, minmax(0, 1fr))`;
  $("minigrid").innerHTML = dash.filter((d) => !d.hidden).map((d) => `<div style="grid-column:span ${Math.min(d.span, maxSpan)}">${CARD_LABEL[d.id]}</div>`).join("");
  renderScreens();
}
function renderScreens() {
  $("vtabs").innerHTML = SCREENS.map(([v, l]) => `<button data-scr="${v}" class="${v === SCR ? "on" : ""}">${l}</button>`).join("");
  $("dash-ed").hidden = SCR !== "dash"; $("blk-ed").hidden = SCR === "dash";
  if (SCR === "dash") return;
  const list = blocksOf(O, SCR), by = Object.fromEntries(list.map((b, i) => [b.id, { ...b, i }]));
  $("blk-ed").innerHTML = (NOTES[SCR] ? `<p class="hint">${NOTES[SCR]}</p>` : "") + BLOCKS[SCR].map((g, gi) => {
    const items = g.items.map(([id, label, lock]) => ({ label, lock, ...by[id] })).sort((a, b) => a.i - b.i);
    return `${g.title ? `<h4>${g.title}</h4>` : ""}<div class="cards" data-drop="blk${gi}">${items.map((b) => `<div class="card${b.hidden ? " off" : ""}" draggable="true" data-drag="blk${gi}:${b.id}">
      <span class="grip">::</span><span>${b.label}</span>
      ${g.wide ? `<label class="chk" title="Ocupa todas as colunas quando a tela tem mais de uma"><input type="checkbox" data-wide="${b.id}" ${b.wide ? "checked" : ""}> largura inteira</label>` : "<span></span>"}
      ${b.lock ? '<small style="color:var(--faint)">sempre visível</small>' : `<label class="chk"><input type="checkbox" data-bshow="${b.id}" ${b.hidden ? "" : "checked"}> mostrar</label>`}</div>`).join("")}</div>`;
  }).join("") + `<div class="row" style="margin-top:12px"><button id="blk-reset">Voltar esta tela ao padrão</button></div>`;
}
$("vtabs").onclick = (e) => { const b = e.target.closest("[data-scr]"); if (!b) return; SCR = b.dataset.scr; renderScreens(); preview(SCR); };
$("blk-ed").addEventListener("change", (e) => {
  const id = e.target.dataset.bshow || e.target.dataset.wide; if (!id) return;
  const list = blocksOf(O, SCR), b = list.find((x) => x.id === id);
  if (e.target.dataset.bshow) b.hidden = !e.target.checked; else b.wide = e.target.checked;
  setBlocks(SCR, list);
});
$("blk-ed").addEventListener("click", (e) => { if (e.target.id === "blk-reset") setBlocks(SCR, null); });
$("orient").onclick = (e) => { const b = e.target.closest("[data-o]"); if (!b) return; O = b.dataset.o; renderLayout(); preview(SCR); };
$("copy-other").onclick = () => { const other = O === "portrait" ? "landscape" : "portrait"; LAY[O] = { nav: navOf(other), known: BASE_VIEWS, dash: dashOf(other).map((d) => ({ ...d, span: Math.min(d.span, COLS[O]) })), blocks: clone(LAY[other]?.blocks || {}) }; save(); renderLayout(); };
$("reset").onclick = () => { if (!confirm(`Voltar o layout ${O === "portrait" ? "em pé" : "deitado"} ao padrão?`)) return; delete LAY[O]; save(); renderLayout(); };
$("nav").addEventListener("change", (e) => {
  const id = e.target.dataset.label; if (!id) return;
  const nav = navOf(O); nav.find((s) => s.id === id).label = e.target.value.trim() || VIEW_LABEL[nav.find((s) => s.id === id).views[0]];
  LAY[O] = { ...(LAY[O] || {}), nav, known: BASE_VIEWS }; save();
});
$("nav").addEventListener("click", (e) => {
  if (e.target.id === "addsec") {
    const name = prompt("Nome da seção (até 14 letras):", "Nova"); if (!name) return;
    const nav = navOf(O), used = new Set(nav.flatMap((s) => s.views));
    const first = BASE_VIEWS.find((v) => !used.has(v));
    if (!first) return alert("Todas as abas já estão no menu. Tire uma de outra seção primeiro (arraste para Escondidas).");
    nav.push({ id: "s" + Date.now().toString(36), label: name.slice(0, 14), views: [first] }); setNav(nav); return;
  }
  const del = e.target.dataset.del;
  if (del) { const nav = navOf(O); if (nav.length <= 1) return; const s = nav.find((x) => x.id === del); if (s.views.includes("sys")) return alert("Esta seção tem Ajustes: mova Ajustes para outra seção antes."); setNav(nav.filter((x) => x.id !== del)); return; }
  const chip = e.target.closest("[data-view]"); if (chip) preview(chip.dataset.view);
});
$("cards").addEventListener("click", (e) => {
  const sp = e.target.dataset.span; if (!sp) return;
  const [id, n] = sp.split(":"); const dash = dashOf(O); dash.find((d) => d.id === id).span = +n; setDash(dash); preview("dash");
});
$("cards").addEventListener("change", (e) => {
  const id = e.target.dataset.show; if (!id) return;
  const dash = dashOf(O); dash.find((d) => d.id === id).hidden = !e.target.checked; setDash(dash); preview("dash");
});

// ------------------------------------------------------------ hoje
function dailyStatus(d) {
  const parts = [];
  if (d.city) parts.push(d.weather ? `Clima: ${d.weather.city}, ${d.weather.temp}° ${d.weather.desc}` : d.err?.weather ? "Clima: " + d.err.weather : "Clima: carregando…");
  if (d.has_ics) parts.push(d.err?.calendar ? "Agenda: " + d.err.calendar : `Agenda: ${d.events.length} compromisso(s) hoje e amanhã`);
  if (d.busy_only) parts.push("Atenção: esse link só mostra livre/ocupado, sem título nem link do Meet. Use o endereço secreto (abaixo).");
  $("d-st").textContent = parts.join(" · ");
}
async function loadDaily() { try {
  const [d, profs] = await Promise.all([send("daily.get"), send("audio.profiles").catch(() => [])]);
  $("d-mprof").innerHTML = '<option value="">(sem perfil)</option>' + (profs || []).map((p) => `<option>${esc(p.name)}</option>`).join("");
  $("d-mprof").value = d.meet_profile || ""; $("d-mauto").checked = d.meet_auto !== false; $("d-mopen").checked = !!d.meet_open;
  $("d-city").value = d.city || ""; $("d-ics").placeholder = d.has_ics ? "agenda conectada (cole outro link para trocar)" : $("d-ics").placeholder; dailyStatus(d); } catch {} }
$("d-save").onclick = async () => {
  const p = { city: $("d-city").value.trim(), meet_auto: $("d-mauto").checked, meet_open: $("d-mopen").checked, meet_profile: $("d-mprof").value };
  if ($("d-ics").value.trim() || $("d-ics").dataset.clear) p.ics = $("d-ics").value.trim();
  status("saving", "Salvando…"); $("d-st").textContent = "Buscando…";
  try { const d = await send("daily.set", p); $("d-ics").value = ""; dailyStatus(d); status("ok", "Conectado · tudo salvo"); }
  catch (e) { $("d-st").textContent = "Erro: " + e.message; status("bad", "Erro ao salvar"); }
};
$("d-ics").addEventListener("input", () => { $("d-ics").dataset.clear = $("d-ics").value ? "" : "1"; });

// ------------------------------------------------------------ steam
function steamStatus(d) {
  $("st-st").textContent = !d.has_key ? "Sem chave: só downloads" : d.err ? "Erro: " + d.err : d.friends ? `${d.friends.filter((f) => f.on).length} amigo(s) online de ${d.friends.length}` : "Buscando amigos…";
}
async function loadSteam() { try { const d = await send("steam.get"); if (d.has_key) $("st-key").placeholder = "chave salva (cole outra para trocar)"; steamStatus(d); } catch {} }
$("st-save").onclick = async () => {
  const key = $("st-key").value.trim();
  if (!key && !confirm("Tirar a chave da Steam?")) return;
  $("st-st").textContent = "Testando…";
  try {
    const r = await send("steam.set", { key }); $("st-key").value = "";
    $("st-st").textContent = !r.has_key ? "Chave removida: só downloads" : r.err ? "Erro: " + r.err : `Funcionou: ${r.friends} amigo(s)`;
  }
  catch (e) { $("st-st").textContent = "Erro: " + e.message; }
};

// ------------------------------------------------------------ STRATZ (relatório do Dota)
function stratzStatus(d) {
  const last = d.last ? ` · última partida: ${d.last.src === "stratz" ? "STRATZ" : "OpenDota"}${d.last.complete ? "" : " (parcial)"}` : "";
  $("sz-st").textContent = (!d.has_key ? "Sem chave: placar pelo OpenDota" : d.err ? "Erro: " + d.err : "Chave ok") + last;
  if (d.has_key) $("sz-key").placeholder = "token salvo (cole outro para trocar)";
}
async function loadStratz() { try { stratzStatus(await send("stratz.get")); } catch {} }
$("sz-save").onclick = async () => {
  const token = $("sz-key").value.trim();
  if (!token && !confirm("Tirar o token do STRATZ?")) return;
  $("sz-st").textContent = "Testando…";
  try { const r = await send("stratz.set", { token }); $("sz-key").value = ""; stratzStatus(r); if (r.has_key) $("sz-st").textContent = "Funcionou: token salvo"; }
  catch (e) { $("sz-st").textContent = "Erro: " + e.message; }
};

// ------------------------------------------------------------ botões (deck)
async function loadDeck() { try { DECK = (await send("deck.get")).deck; renderDeck(); } catch {} }
function renderDeck() {
  if (!DECK) return;
  page = Math.min(page, DECK.pages.length - 1);
  $("pages").dataset.drop = "page"; $("pages").dataset.dir = "h";
  $("pages").innerHTML = DECK.pages.map((p, i) => `<button class="pg${i === page ? " on" : ""}" draggable="true" data-drag="page:${i}" data-i="${i}">${esc(p.name)}</button>`).join("");
  const pg = DECK.pages[page];
  $("pg-name").value = pg.name;
  $("pg-auto").hidden = pg.auto !== "shortcuts";
  $("btns").dataset.drop = "btn";
  $("btns").innerHTML = pg.auto === "shortcuts" ? "" : (pg.buttons || []).map((b, i) => `<div class="dbtn${b.type === "sound" ? " snd" : ""}" draggable="true" data-drag="btn:${i}" style="--c:${esc(b.color || "transparent")}">
    <b>${esc(b.icon || "")}</b><span>${esc(b.label)}</span></div>`).join("") || '<div class="empty">Página vazia</div>';
  sndRender();
}
$("pages").addEventListener("click", (e) => { const b = e.target.closest(".pg"); if (!b) return; page = +b.dataset.i; renderDeck(); preview("deck"); });
$("pg-name").addEventListener("change", () => { DECK.pages[page].name = $("pg-name").value.trim().slice(0, 24) || "Página"; saveDeck(); });
function moveBtnToPage(i, to) {
  const target = DECK.pages[to];
  if (target.auto === "shortcuts") return alert("Essa página é automática (mostra seus atalhos); não recebe botões.");
  const [b] = DECK.pages[page].buttons.splice(i, 1); (target.buttons = target.buttons || []).push(b); saveDeck();
}
let deckT = null;
function saveDeck() {
  renderDeck(); status("saving", "Salvando botões…");
  clearTimeout(deckT);
  deckT = setTimeout(async () => {
    try { DECK = (await send("deck.save", { deck: DECK })).deck; renderDeck(); status("ok", "Conectado · tudo salvo"); }
    catch (e) { status("bad", "Erro ao salvar botões: " + e.message); loadDeck(); }
  }, 300);
}

// ------------------------------------------------------------ botões de som (mesa de som: soundboard.py)
let sndSel = -1, sndBusy = false, sndPage = null;   // sndPage: índice da página do deck (null = escolhe sozinho; -1 = criar "Sons")
const SND_COLORS = ["", "#58a6ff", "#50c878", "#f0b446", "#eb5757", "#aa82ff", "#5865f2", "#ff7ab6", "#3dd6d0"];
const sndBtn = () => (sndPage >= 0 ? DECK?.pages[sndPage]?.buttons?.[sndSel] : null);
const sndErr = (e) => (e.name === "EncodingError" ? "não consegui abrir esse áudio" : e.message);
function sndPickPage() {
  const ps = DECK.pages, ok = (i) => ps[i] && !ps[i].auto;
  if (sndPage !== null && (sndPage === -1 || ok(sndPage))) return;
  let i = ps.findIndex((p) => !p.auto && /^sons?\b/i.test(p.name));
  if (i < 0) i = ps.findIndex((p) => !p.auto && (p.buttons || []).some((b) => b.type === "sound"));
  sndPage = i;
}
$("snd-page").onchange = () => { sndPage = +$("snd-page").value; sndSel = -1; sndRender(); };
$("snd-btns").addEventListener("click", (e) => {
  const el = e.target.closest(".dbtn.snd"); if (!el) return;
  sndSel = +el.dataset.i === sndSel ? -1 : +el.dataset.i; sndRender();
});
function sndRender() {
  if (!DECK) return;
  sndPickPage();
  $("snd-page").innerHTML = DECK.pages.map((p, i) => (p.auto ? "" : `<option value="${i}">${esc(p.name)}</option>`)).join("")
    + (DECK.pages.some((p) => /^sons?\b/i.test(p.name)) ? "" : '<option value="-1">+ Página nova "Sons"</option>');
  $("snd-page").value = String(sndPage);
  const list = sndPage >= 0 ? (DECK.pages[sndPage].buttons || []).map((b, i) => [b, i]).filter(([b]) => b.type === "sound") : [];
  $("snd-btns").innerHTML = list.map(([b, i]) => `<div class="dbtn snd${i === sndSel ? " sel" : ""}" data-i="${i}" style="--c:${esc(b.color || "transparent")}">
    <b>${esc(b.icon || "")}</b><span>${esc(b.label)}</span></div>`).join("") || '<div class="empty">Nenhum som nesta página ainda.</div>';
  const b = sndBtn();
  if (!b || b.type !== "sound") { sndSel = -1; $("snd-ed").hidden = true; return; }
  $("snd-ed").hidden = false;
  if (document.activeElement !== $("se-name")) $("se-name").value = b.label;
  if (document.activeElement !== $("se-icon")) $("se-icon").value = b.icon || "";
  $("se-vol").value = b.vol ?? 100; $("se-vv").textContent = (b.vol ?? 100) + "%";
  $("se-colors").innerHTML = SND_COLORS.map((c) => `<button type="button" data-c="${c}" class="${(b.color || "") === c ? "on" : ""}" style="background:${c || "var(--bg)"}" aria-label="${c || "sem cor"}"></button>`).join("");
}
$("se-name").addEventListener("change", () => { const b = sndBtn(); if (b) { b.label = $("se-name").value.trim().slice(0, 40) || "Som"; saveDeck(); } });
$("se-icon").addEventListener("change", () => { const b = sndBtn(); if (!b) return; const v = $("se-icon").value.trim().slice(0, 8); v ? (b.icon = v) : delete b.icon; saveDeck(); });
$("se-vol").addEventListener("input", () => { $("se-vv").textContent = $("se-vol").value + "%"; });
$("se-vol").addEventListener("change", () => { const b = sndBtn(); if (b) { b.vol = +$("se-vol").value; saveDeck(); } });
$("se-colors").addEventListener("click", (e) => { const x = e.target.closest("[data-c]"), b = sndBtn(); if (!x || !b) return; x.dataset.c ? (b.color = x.dataset.c) : delete b.color; saveDeck(); });
$("se-test").onclick = async () => {
  const b = sndBtn(); if (!b) return;
  try { const ok = await send("snd.play", { id: b.value, vol: b.vol ?? 100 }); $("se-st").className = "sst"; $("se-st").textContent = ok ? "Tocando…" : "Parado"; }
  catch (e) { $("se-st").className = "sst bad"; $("se-st").textContent = e.message; }
};
$("se-del").onclick = () => {
  const b = sndBtn(); if (!b || !confirm(`Excluir o botão "${b.label}"?`)) return;
  DECK.pages[sndPage].buttons.splice(sndSel, 1); sndSel = -1; saveDeck();
};
$("se-close").onclick = () => { sndSel = -1; sndRender(); };
$("se-swap").onclick = () => $("se-file").click();
// cortar o áudio atual (só dá para encurtar: o PC guarda o trecho, não o arquivo original) ou trocar por outro arquivo
async function sndReplace(idx, getX, title, whole) {
  $("se-st").className = "sst"; $("se-st").textContent = "Abrindo…";
  try {
    const cut = await sbTrim(await getX(), title, whole);
    if (!cut) { $("se-st").textContent = ""; return; }
    const { wav, secs } = cut;
    $("se-st").textContent = "Enviando…";
    const r = await send("snd.add", { data: sbB64(wav) }, 90000);
    const b = DECK.pages[sndPage]?.buttons?.[idx]; if (!b || b.type !== "sound") return;
    b.value = r.id; await saveDeckNow(); $("se-st").textContent = `Salvo (${secs.toFixed(1)} s)`;
  } catch (err) { $("se-st").className = "sst bad"; $("se-st").textContent = "Falhou: " + sndErr(err); }
}
$("se-file").onchange = (e) => {
  const f = e.target.files[0]; e.target.value = ""; const idx = sndSel; if (!f || idx < 0) return;
  sndReplace(idx, () => sbDecode(f), f.name);
};
$("se-cut").onclick = () => {
  const b = sndBtn(), idx = sndSel; if (!b) return;
  sndReplace(idx, async () => sbDecode(sbUnB64((await send("snd.get", { id: b.value }, 30000)).data)), b.label, true);
};
$("snd-pick").onclick = () => $("snd-files").click();
$("snd-files").onchange = (e) => { addSounds([...e.target.files]); e.target.value = ""; };
const isFileDrag = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
$("sons-box").addEventListener("dragover", (e) => { if (!isFileDrag(e)) return; e.preventDefault(); $("snd-drop").classList.add("over"); });
$("sons-box").addEventListener("dragleave", (e) => { if (!e.currentTarget.contains(e.relatedTarget)) $("snd-drop").classList.remove("over"); });
$("sons-box").addEventListener("drop", (e) => {
  if (!isFileDrag(e)) return; e.preventDefault(); $("snd-drop").classList.remove("over");
  addSounds([...e.dataTransfer.files]);
});
async function addSounds(files) {
  if (!DECK || !files.length) return;
  if (sndBusy) return alert("Espere os sons anteriores terminarem de enviar.");
  sndBusy = true; const st = $("snd-st"), done = [], fail = [];
  if (sndPage === -1) {   // primeira vez: cria a página "Sons"
    DECK.pages.push({ name: "Sons", buttons: [] }); sndPage = DECK.pages.length - 1;
    try { await saveDeckNow(); } catch (e) { sndBusy = false; st.className = "sst bad"; st.textContent = "Falhou: " + e.message; return; }
  }
  const pg0 = sndPage;
  st.className = "sst";
  for (const [n, f] of files.entries()) {
    const pre = files.length > 1 ? `(${n + 1}/${files.length}) ` : "";
    try {
      if ((DECK.pages[pg0].buttons || []).length >= 48) throw new Error("a página já tem 48 botões");
      st.textContent = `${pre}Abrindo ${f.name}…`;
      let wav;
      if (files.length === 1) {   // um arquivo: escolhe o trecho no cortador
        const cut = await sbTrim(await sbDecode(f), f.name);
        if (!cut) { st.textContent = "Cancelado."; continue; }
        wav = cut.wav;
      } else wav = (await sbConvert(f)).wav;
      st.textContent = `${pre}Enviando ${f.name}…`;
      const r = await send("snd.add", { data: sbB64(wav) }, 90000);
      const pg = DECK.pages[pg0]; (pg.buttons = pg.buttons || []).push({ label: sbName(f), type: "sound", value: r.id, vol: 100 });
      await saveDeckNow(); done.push(sbName(f));
    } catch (err) { fail.push(`${f.name}: ${sndErr(err)}`); }
  }
  sndBusy = false;
  if (!done.length && !fail.length) { sndBusy = false; return; }
  st.className = fail.length ? "sst bad" : "sst";
  st.textContent = [done.length ? `${done.length} som(ns) adicionado(s) na página "${DECK.pages[pg0]?.name}".` : "", ...fail.map((x) => "Falhou: " + x)].filter(Boolean).join("\n");
}

// salva já (sem esperar os 300 ms) e só volta depois: quem adiciona botão no meio de um envio não perde nada
async function saveDeckNow() {
  clearTimeout(deckT); status("saving", "Salvando botões…");
  DECK = (await send("deck.save", { deck: DECK })).deck; renderDeck(); status("ok", "Conectado · tudo salvo");
}

// ------------------------------------------------------------ prévias (o próprio app em iframes)
const PV = { portrait: [412, 860, 0.52], landscape: [1104, 405, 0.5] };
function mountPreviews() {
  for (const [o, [w, h, sc]] of Object.entries(PV)) {
    const box = $("fr-" + o); if (box.firstChild) continue;
    box.style.width = w * sc + "px"; box.style.height = h * sc + "px";
    const f = document.createElement("iframe");
    f.src = `/?preview=1#t=${encodeURIComponent(TOKEN)}`; f.width = w; f.height = h; f.style.transform = `scale(${sc})`;
    f.title = "Prévia " + o; box.appendChild(f);
  }
}
function preview(view) {
  document.querySelectorAll(".frame iframe").forEach((f) => { try { f.contentWindow.postMessage({ pcc: "view", view }, location.origin); } catch {} });
}

connect();

// ------------------------------------------------------------ Jogador (1.18): o mesmo da seção Jogador do app
let CQ = null;
const CQ_HM = (s) => (s < 3600 ? `${Math.round(s / 60)} min` : `${Math.floor(s / 3600)}h${String(Math.round((s % 3600) / 60)).padStart(2, "0")}`);
const CQ_FMT = (unit, v) => (unit === "dur" ? CQ_HM(v) : unit === "min" ? CQ_HM(v * 60) : String(Math.round(v)));
function themeLock(skin, v) {
  const r = CQ?.rewards?.find((x) => x.id === `${skin}:${v}`);
  return r && !r.got ? (r.req ? `nível ${r.req}` : `conquista ${r.conq}`) : "";
}
async function loadConq() { try { CQ = await send("conq.get"); renderConq(); renderThemes(); } catch {} }
function renderConq() {
  const box = $("jg-body"); if (!box || !CQ) return;
  const d = CQ, eq = d.equip || {}, nm = (id) => d.rewards.find((r) => r.id === id)?.name || "";
  const pct = Math.max(0, Math.min(100, ((d.xp - d.lvl_lo) / Math.max(1, d.lvl_hi - d.lvl_lo)) * 100));
  const got = d.rewards.filter((r) => r.got).length;
  box.innerHTML = `<div class="jg-top">${badge(d.level, eq.frame, "big", eq.avatar)}
      <div style="flex:1;min-width:0">${fxName(nm(eq.title) || "Novato", eq.effect, "div", "jg-title")}
        <div class="hint" style="margin:2px 0">${d.xp - d.lvl_lo} / ${d.lvl_hi - d.lvl_lo} XP para o nível ${d.level + 1} · sequência ${d.streak} dia${d.streak === 1 ? "" : "s"}
          · <b>${d.credits?.bal ?? 0}</b> créditos · ${got} de ${d.rewards.length} itens</div>
        <div class="jg-bar"><i style="width:${pct}%"></i></div></div>
      <button class="pri" id="jg-open">Abrir a página Jogador</button></div>
    <div class="row" style="margin-top:12px"><label class="chk"><input type="checkbox" id="jg-ov"${d.pc_overlay !== false ? " checked" : ""}> Troféu no canto da tela do PC</label></div>
    <p class="hint" style="margin:10px 0 0">Perfil, troféus, vitrine, inventário, loja, evento, desafios, liga, amigos e duelos: tudo dá para ver e editar na página <b>Jogador</b>
      (também no menu do ícone perto do relógio).</p>`;
  $("jg-open").onclick = () => window.open("/jogador", "_blank");
  $("jg-ov").onchange = async () => { try { CQ = await send("conq.cfg", { overlay: $("jg-ov").checked }); } catch (e) { status("bad", e.message); } };
}
