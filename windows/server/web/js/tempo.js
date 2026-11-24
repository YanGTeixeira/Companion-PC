"use strict";
// ---------------------------------------------------------------- Tempo de tela
// tons do tema para as categorias (sem cores fora da paleta)
const CAT_STYLE = ["var(--hl)", "var(--p2)", "var(--p3)", "repeating-linear-gradient(45deg, var(--p) 0 2px, transparent 2px 4px)",
  "repeating-linear-gradient(45deg, var(--p2) 0 2px, transparent 2px 4px)", "repeating-linear-gradient(90deg, var(--p) 0 2px, transparent 2px 4px)",
  "repeating-linear-gradient(90deg, var(--p3) 0 2px, transparent 2px 4px)", "var(--p4)"];
let uRange = store.get("urange", "day"), uRef = null, uData = null, uT = 0;
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const WD = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"], MON_N = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
function uShift(dir) {
  const d = uRef ? new Date(uRef + "T12:00") : new Date();
  if (uRange === "day") d.setDate(d.getDate() + dir);
  else if (uRange === "week") d.setDate(d.getDate() + 7 * dir);
  else d.setMonth(d.getMonth() + dir, 1);
  const today = isoDay(new Date());
  uRef = isoDay(d) >= today ? null : isoDay(d);
  loadUsage(true);
}
async function loadUsage(force) {
  if (!vis("usage") || !ws || ws.readyState !== 1 || !welcome.features?.usage) return;
  if (!force && Date.now() - uT < 15000) return;
  uT = Date.now();
  try { uData = await send("usage.get", { range: uRange, day: uRef }); renderUsage(); } catch { uT = 0; }
}
function catIdx(c) { return Math.max(0, (uData?.cat_list || []).indexOf(c)); }
function renderUsage() {
  const u = uData; if (!u) return;
  document.querySelectorAll("#u-range [data-r]").forEach((b) => b.classList.toggle("on", b.dataset.r === uRange));
  const st = new Date(u.start + "T12:00"), en = new Date(u.end + "T12:00");
  $("u-label").textContent = u.range === "day" ? (uRef ? `${WD[st.getDay()]} ${st.getDate()} ${MON_N[st.getMonth()]}` : "Hoje")
    : u.range === "week" ? `${st.getDate()} ${MON_N[st.getMonth()]} – ${en.getDate()} ${MON_N[en.getMonth()]}` : `${MON_N[st.getMonth()]} ${st.getFullYear()}`;
  $("u-next").disabled = !uRef;
  $("u-total").textContent = u.total ? humanDur(u.total) : "0m";
  if (u.range === "day") {
    const diff = u.prev_avg ? Math.round((u.total / u.prev_avg - 1) * 100) : null;
    $("u-cmp").textContent = diff == null ? "" : `${Math.abs(diff)}% ${diff >= 0 ? "acima" : "abaixo"} da média de 7 dias (${humanDur(u.prev_avg)})`;
  } else $("u-cmp").textContent = u.avg ? `média ${humanDur(u.avg)}/dia` : "";
  // gráfico
  let bars, labels;
  const hr = new Date().getHours(), today = isoDay(new Date());
  if (u.range === "day") {
    const max = Math.max(1800, ...u.hours);
    bars = u.hours.map((s, h) => `<div class="uc${!uRef && h === hr ? " now" : ""}" title="${h}h: ${humanDur(s)}"><i style="height:${(s / max) * 100}%"></i></div>`);
    labels = ["0h", "6h", "12h", "18h", "23h"];
  } else {
    const max = Math.max(3600, ...u.days.map((d) => d.secs));
    bars = u.days.map((d) => `<div class="uc${d.day === today ? " now" : ""}" title="${d.day}: ${humanDur(d.secs)}"><i style="height:${(d.secs / max) * 100}%"></i></div>`);
    labels = u.range === "week" ? ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"] : ["1", "8", "15", "22", String(u.days.length)];
  }
  $("u-chart").innerHTML = bars.join("");
  $("u-chart").nextElementSibling?.classList.contains("uaxis") || $("u-chart").insertAdjacentHTML("afterend", '<div class="uaxis" id="u-axis"></div>');
  $("u-axis").innerHTML = labels.map((l) => `<span>${l}</span>`).join("");
  // categorias
  const tot = u.total || 1;
  $("u-catbar").innerHTML = u.cats.map((c) => `<i style="flex:${c.secs} 1 0;background:${CAT_STYLE[catIdx(c.cat)]}" title="${esc(c.cat)}"></i>`).join("");
  $("u-legend").innerHTML = u.cats.map((c) => `<div><span class="usw" style="background:${CAT_STYLE[catIdx(c.cat)]}"></span><span>${esc(c.cat)}</span><span>${humanDur(c.secs)} · ${Math.round((c.secs / tot) * 100)}%</span></div>`).join("")
    || '<div class="empty">Nada registrado ainda</div>';
  // apps
  const top = u.apps[0]?.secs || 1;
  const opts = (sel) => u.cat_list.map((c) => `<option${c === sel ? " selected" : ""}>${esc(c)}</option>`).join("");
  $("u-apps").innerHTML = u.apps.length ? u.apps.map((a) => `<div class="uapp${a.app === u.current && !uRef ? " now" : ""}">
      <span class="un">${esc(a.name)}</span><select class="catsel" data-app="${esc(a.app)}" aria-label="Categoria de ${esc(a.name)}">${opts(a.cat)}</select><span class="ut">${humanDur(a.secs)}</span>
      <div class="bar"><i style="width:${(a.secs / top) * 100}%"></i></div></div>`).join("")
    : '<div class="empty">Nenhum uso registrado neste período. O tempo conta enquanto você usa o PC (para depois de 2 min parado, a não ser que algo esteja passando na tela).</div>';
}
$("u-range").onclick = (e) => { const b = e.target.closest("[data-r]"); if (!b) return; buzz(8); uRange = b.dataset.r; store.set("urange", uRange); uRef = null; loadUsage(true); };
$("u-prev").onclick = () => { buzz(8); uShift(-1); };
$("u-next").onclick = () => { buzz(8); uShift(1); };
$("u-apps").addEventListener("change", async (e) => {
  const sel = e.target.closest(".catsel"); if (!sel) return;
  buzz(8);
  try { await send("usage.cat", { app: sel.dataset.app, cat: sel.value }); uT = 0; loadUsage(true); } catch (err) { toast(err.message, "bad"); }
});
setInterval(() => { if (vis("usage") && !document.hidden) loadUsage(); }, 30000);

function renderLib() {
  $("g-lib").innerHTML = libData.length ? libData.map((g, i) => `<button class="lgame${g.running ? " run" : ""}" data-g="${i}">
    <div class="gart"${g.art ? ` style="background-image:url(data:image/jpeg;base64,${g.art})"` : ""}>${g.art ? "" : esc(g.name)}</div>
    <div class="ln"><span>${esc(g.name)}</span><span>${g.running ? "aberto" : g.ago != null ? humanAgo(g.ago) : esc(g.store)}</span></div></button>`).join("")
    : '<div class="empty full">Nenhum jogo da Steam, Epic ou GOG encontrado no PC</div>';
}
$("g-lib").onclick = (e) => {
  const b = e.target.closest("[data-g]"); if (!b) return;
  const g = libData[+b.dataset.g]; buzz();
  if (g.running) return toast(g.name + " já está aberto", "ok");
  confirmAsk(`Abrir ${g.name}?`, () => act("games.launch", { id: g.id }, "Abrindo " + g.name).then(() => { libT = 0; setTimeout(loadGamesExtra, 8000); }));
};
setInterval(() => { if (vis("games")) loadGamesExtra(); }, 15000);

