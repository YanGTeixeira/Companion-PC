"use strict";
// ---------------------------------------------------------------- Botões (deck)
let deckData = null, deckEdit = false;
prefs.deckPage = store.get("deckPage", 0);
const DECK_COLORS = ["", "#58a6ff", "#50c878", "#f0b446", "#eb5757", "#aa82ff", "#5865f2", "#ff7ab6", "#3dd6d0"];
const clone = (o) => JSON.parse(JSON.stringify(o));
// ícone só em texto: emoji colorido é removido; sem ícone, usa as iniciais do nome
const NO_EMOJI = /[\p{Extended_Pictographic}\u{FE0F}\u{200D}\u{20E3}]/gu;
const deckIcon = (b) => (b.icon || "").replace(NO_EMOJI, "").trim()
  || (b.label || "?").replace(NO_EMOJI, "").split(/[\s:/]+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
async function loadDeck() { try { deckData = await send("deck.get"); renderDeck(); } catch {} }
const deckPages = () => deckData?.deck?.pages || [];
function pageButtons(pg) {
  if (pg.auto === "shortcuts") return (welcome.shortcuts || []).map((x) => ({ label: x.name, type: "shortcut", value: x.id }));
  return pg.buttons || [];
}
function renderDeck() {
  const pages = deckPages(); if (!pages.length) return;
  prefs.deckPage = Math.max(0, Math.min(prefs.deckPage, pages.length - 1));
  $("deck-pages").innerHTML = pages.map((pg, i) => `<button class="chip2${i === prefs.deckPage ? " on" : ""}" data-page="${i}">${esc(pg.name)}</button>`).join("")
    + (deckEdit ? '<button class="chip2 add" data-page="new">+ Página</button>' : "");
  const pg = pages[prefs.deckPage], btns = pageButtons(pg);
  let html = btns.map((b, i) => `<button class="dbtn${b.confirm ? " warn" : ""}" data-i="${i}"${b.color ? ` style="--c:${b.color}"` : ""}>
    <span class="di">${esc(deckIcon(b))}</span><span class="dl">${esc(b.label)}</span></button>`).join("");
  if (deckEdit && !pg.auto) html += '<button class="dbtn add" data-i="new"><span class="di">+</span><span class="dl">Novo botão</span></button>';
  if (deckEdit && pg.auto) html += '<div class="empty full">Esta página mostra os programas do config.json do PC — edite lá.</div>';
  if (!btns.length && !deckEdit) html = `<div class="empty full">${pg.auto ? "Nenhum programa no config.json do PC" : "Página vazia. Toque em Editar para adicionar botões."}</div>`;
  $("deck-grid").innerHTML = html;
  $("deck-grid").classList.toggle("editing", deckEdit);
  $("deck-edit").textContent = deckEdit ? "Pronto" : "Editar";
  $("deck-editbar").classList.toggle("hidden", !deckEdit);
}
$("deck-pages").onclick = (e) => {
  const b = e.target.closest("[data-page]"); if (!b) return; buzz(8);
  if (b.dataset.page === "new") return editPage(-1);
  const i = +b.dataset.page;
  if (deckEdit && i === prefs.deckPage) return editPage(i);
  prefs.deckPage = i; store.set("deckPage", i); renderDeck();
};
$("deck-edit").onclick = () => { if (!deckData) return; deckEdit = !deckEdit; buzz(8); renderDeck(); };
$("deck-reset").onclick = () => confirmAsk("Voltar aos botões padrão?", async () => {
  try { deckData = await send("deck.reset"); prefs.deckPage = 0; renderDeck(); toast("Botões restaurados", "ok"); } catch (e) { toast(e.message, "bad"); }
});
$("deck-grid").onclick = (e) => {
  const el = e.target.closest(".dbtn"); if (!el) return;
  const pg = deckPages()[prefs.deckPage];
  if (deckEdit) { if (!pg.auto) editButton(el.dataset.i === "new" ? -1 : +el.dataset.i); return; }
  const i = +el.dataset.i, b = pageButtons(pg)[i];
  el.classList.add("hit"); setTimeout(() => el.classList.remove("hit"), 160);
  const run = () => (pg.auto ? act("app.launch", { id: b.value }, "Abrindo " + b.label)
    : act("deck.press", { page: prefs.deckPage, index: i }, b.type === "action" || b.type === "shortcut" ? b.label : null));
  b.confirm ? confirmAsk(b.label + "?", run) : run();
};
async function saveDeck(deck) {
  try { deckData = await send("deck.save", { deck }); renderDeck(); return true; } catch (e) { toast(e.message, "bad"); return false; }
}
let bedIdx = -1, bedColor = "";
function editButton(i) {
  const pg = deckPages()[prefs.deckPage], b = i >= 0 ? pg.buttons[i] : { label: "", type: "keys", value: "" };
  bedIdx = i;
  $("bed-title").textContent = i >= 0 ? "Editar botão" : "Novo botão";
  $("bed-label").value = b.label || ""; $("bed-icon").value = b.icon || "";
  $("bed-type").value = b.type;
  $("bed-keys").value = b.type === "keys" ? b.value : ""; $("bed-text").value = b.type === "text" ? b.value : "";
  $("bed-action").innerHTML = Object.entries(deckData.actions).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("bed-shortcut").innerHTML = (welcome.shortcuts || []).map((x) => `<option value="${esc(x.id)}">${esc(x.name)}</option>`).join("");
  if (b.type === "action") $("bed-action").value = b.value;
  if (b.type === "shortcut") $("bed-shortcut").value = b.value;
  $("bed-macro").value = b.type === "macro" ? b.value : "";
  $("bed-macro-progs").textContent = "Programas: " + (welcome.shortcuts || []).map((x) => x.id).join(", ");
  $("bed-confirm").checked = !!b.confirm; bedColor = b.color || ""; renderColors();
  ["bed-del", "bed-left", "bed-right"].forEach((id) => $(id).classList.toggle("hidden", i < 0));
  bedType(); $("bed").classList.remove("hidden");
}
function bedType() { const t = $("bed-type").value; for (const k of ["keys", "text", "action", "shortcut", "macro"]) $("bed-v-" + k).classList.toggle("hidden", k !== t); }
$("bed-type").onchange = bedType;
function renderColors() {
  $("bed-colors").innerHTML = DECK_COLORS.map((c) => `<button type="button" class="sw${c === bedColor ? " on" : ""}" data-c="${c}" style="background:${c || "var(--bg)"}" aria-label="${c || "sem cor"}"></button>`).join("");
}
$("bed-colors").onclick = (e) => { const x = e.target.closest(".sw"); if (x) { bedColor = x.dataset.c; renderColors(); } };
$("bed-cancel").onclick = () => $("bed").classList.add("hidden");
$("bed-form").onsubmit = async (e) => {
  e.preventDefault();
  const t = $("bed-type").value;
  const v = { keys: $("bed-keys").value.trim().toLowerCase().replace(/\s+/g, ""), text: $("bed-text").value, action: $("bed-action").value, shortcut: $("bed-shortcut").value, macro: $("bed-macro").value.trim() }[t];
  if (!v) return toast("Preencha o que o botão faz", "bad");
  if (t === "keys") { const bad = v.split("+").filter((k) => !deckData.keys.includes(k)); if (bad.length) return toast("Tecla desconhecida: " + bad.join(", "), "bad"); }
  let label = $("bed-label").value.trim();
  if (!label) label = t === "action" ? deckData.actions[v] : t === "shortcut" ? $("bed-shortcut").selectedOptions[0]?.text || v : t === "macro" ? "Macro" : v.slice(0, 24);
  const b = { label, type: t, value: v };
  const ic = $("bed-icon").value.replace(NO_EMOJI, "").trim(); if (ic) b.icon = ic;
  if (bedColor) b.color = bedColor;
  if ($("bed-confirm").checked) b.confirm = true;
  const deck = clone(deckData.deck), pg = deck.pages[prefs.deckPage];
  pg.buttons = pg.buttons || [];
  bedIdx >= 0 ? (pg.buttons[bedIdx] = b) : pg.buttons.push(b);
  if (await saveDeck(deck)) { $("bed").classList.add("hidden"); buzz(); }
};
$("bed-del").onclick = () => confirmAsk("Excluir este botão?", async () => {
  const deck = clone(deckData.deck); deck.pages[prefs.deckPage].buttons.splice(bedIdx, 1);
  if (await saveDeck(deck)) $("bed").classList.add("hidden");
});
async function moveBtn(d) {
  const deck = clone(deckData.deck), arr = deck.pages[prefs.deckPage].buttons, j = bedIdx + d;
  if (j < 0 || j >= arr.length) return;
  [arr[bedIdx], arr[j]] = [arr[j], arr[bedIdx]];
  if (await saveDeck(deck)) { bedIdx = j; buzz(8); }
}
$("bed-left").onclick = () => moveBtn(-1); $("bed-right").onclick = () => moveBtn(1);
let pedIdx = -1;
const parseApps = (t) => t.toLowerCase().split(/[,;\s]+/).map((a) => a.trim()).filter(Boolean)
  .map((a) => (a === "@jogo" || a.endsWith(".exe") ? a : a + ".exe"));
$("ped-cur").onclick = () => {
  const s = state.stats; if (!s?.app) return toast("Nenhum programa em foco no PC", "bad");
  const a = s.app_game ? "@jogo" : s.app, cur = parseApps($("ped-apps").value);
  if (!cur.includes(a)) cur.push(a);
  $("ped-apps").value = cur.join(", "); buzz(8);
};
function editPage(i) {
  pedIdx = i;
  $("ped-apps").value = i >= 0 ? (deckPages()[i].apps || []).join(", ") : "";
  $("ped-title").textContent = i >= 0 ? "Página" : "Nova página";
  $("ped-name").value = i >= 0 ? deckPages()[i].name : "";
  ["ped-del", "ped-left", "ped-right"].forEach((id) => $(id).classList.toggle("hidden", i < 0));
  $("ped").classList.remove("hidden"); setTimeout(() => $("ped-name").focus(), 50);
}
$("ped-cancel").onclick = () => $("ped").classList.add("hidden");
$("ped-form").onsubmit = async (e) => {
  e.preventDefault();
  const name = $("ped-name").value.trim() || "Página", deck = clone(deckData.deck);
  const apps = parseApps($("ped-apps").value);
  if (pedIdx >= 0) { deck.pages[pedIdx].name = name; deck.pages[pedIdx].apps = apps; }
  else { deck.pages.push({ name, buttons: [], apps }); prefs.deckPage = deck.pages.length - 1; store.set("deckPage", prefs.deckPage); }
  if (await saveDeck(deck)) $("ped").classList.add("hidden");
};
$("ped-del").onclick = () => {
  if (deckPages().length <= 1) return toast("Precisa ter pelo menos uma página", "bad");
  confirmAsk(`Excluir a página "${deckPages()[pedIdx].name}"?`, async () => {
    const deck = clone(deckData.deck); deck.pages.splice(pedIdx, 1); prefs.deckPage = 0;
    if (await saveDeck(deck)) $("ped").classList.add("hidden");
  });
};
async function movePage(d) {
  const deck = clone(deckData.deck), j = pedIdx + d;
  if (j < 0 || j >= deck.pages.length) return;
  [deck.pages[pedIdx], deck.pages[j]] = [deck.pages[j], deck.pages[pedIdx]];
  if (await saveDeck(deck)) { pedIdx = j; prefs.deckPage = j; store.set("deckPage", j); renderDeck(); buzz(8); }
}
$("ped-left").onclick = () => movePage(-1); $("ped-right").onclick = () => movePage(1);

// ---------------------------------------------------------------- página que segue o programa em foco
prefs.deckAuto = store.get("deckAuto", true);
let lastApp = null;
function deckFollow(s) {
  if (!deckData) return;          // espera os botões carregarem
  const key = (s.app || "") + (s.app_game ? "@" : "");
  if (key === lastApp) return;   // só troca quando o foco muda: escolher outra página na mão continua valendo
  lastApp = key;
  if (!prefs.deckAuto || deckEdit || !deckData || !s.app) return;
  const pages = deckPages();
  let i = pages.findIndex((p) => (p.apps || []).includes(s.app));
  if (i < 0 && s.app_game) i = pages.findIndex((p) => (p.apps || []).includes("@jogo"));
  if (i >= 0 && i !== prefs.deckPage) { prefs.deckPage = i; renderDeck(); }
}

