"use strict";
// ---------------------------------------------------------------- Steam: downloads e amigos
const fmtRate = (b) => b ? (b >= 1048576 ? (b / 1048576).toFixed(1) + " MB/s" : Math.round(b / 1024) + " KB/s") : "";
const fmtGB = (b) => b >= 1073741824 ? (b / 1073741824).toFixed(1) + " GB" : Math.round(b / 1048576) + " MB";
let prevPlaying = null;
function onSteam(d) {
  const fr = d.friends || [];
  // aviso quando um amigo começa a jogar (não no primeiro carregamento)
  const now = new Map(fr.filter((f) => f.game).map((f) => [f.id, f.game]));
  if (prevPlaying && prefs.alerts.steam && !PREVIEW) for (const [id, g] of now) if (prevPlaying.get(id) !== g) {
    const f = fr.find((x) => x.id === id); toast(`${f.name} começou a jogar ${g}`);
  }
  if (d.friends) prevPlaying = now;
  state.steam = d; renderSteam();
}
function renderSteam() {
  const d = state.steam; if (!d) return;
  const dls = d.downloads || [], top = dls[0];
  const dl = $("g-dl"); dl.classList.toggle("hidden", !dls.length);
  dl.innerHTML = `<h3><span>Steam</span><span>${dls.length} ${dls.length > 1 ? "na fila" : "baixando"}</span></h3>` + dls.map((x) => `<div class="dlrow">
    <div class="row"><span>${esc(x.name)}</span><span>${x.state}${x.pct != null ? " " + Math.floor(x.pct) + "%" : ""}</span></div>
    ${x.total ? `<div class="bar"><i style="width:${x.pct || 0}%"></i></div><div class="sub">${fmtGB(x.done)} de ${fmtGB(x.total)}${x.speed ? " · " + fmtRate(x.speed) + (x.state === "baixando" && x.speed ? " · falta " + humanDur((x.total - x.done) / x.speed) : "") : ""}</div>` : ""}</div>`).join("");
  const chip = $("dl-chip"); chip.classList.toggle("hidden", !top || top.state !== "baixando");
  if (top) chip.textContent = `STEAM ${top.pct != null ? Math.floor(top.pct) + "%" : ""}`;
  const fc = $("g-friends");
  if (!d.has_key) { fc.innerHTML = `<h3><span>Amigos</span></h3><div class="sub" style="white-space:normal">Para ver os amigos da Steam: crie uma chave em steamcommunity.com/dev/apikey e cole no editor do PC (Personalizar &gt; Steam).</div>`; return; }
  if (d.err) { fc.innerHTML = `<h3><span>Amigos</span></h3><div class="sub" style="white-space:normal">Erro: ${esc(d.err)}</div>`; return; }
  const fr = d.friends || [], on = fr.filter((f) => f.on), playing = fr.filter((f) => f.game);
  const row = (f) => `<div class="frow${f.game ? " play" : ""}${f.on ? "" : " off"}">${f.avatar ? `<img src="${esc(f.avatar)}" alt="" loading="lazy">` : "<span></span>"}
    <span class="fn">${esc(f.name)}<small>${f.game ? "jogando " + esc(f.game) : f.state}</small></span><span></span></div>`;
  fc.innerHTML = `<h3><span>Amigos</span><span>${playing.length ? playing.length + " jogando · " : ""}${on.length} online</span></h3>
    ${on.length ? on.slice(0, 12).map(row).join("") : '<div class="empty">Ninguém online</div>'}`;
}
$("dl-chip").onclick = () => { buzz(8); showView("games"); };

// ---------------------------------------------------------------- Pós-partida
const CMP_LABEL = { k: "Abates", d: "Mortes", a: "Assist.", hs_pct: "HS %", adr: "ADR", mvp: "MVPs", gpm: "GPM", xpm: "XPM", lh: "Last hits", dur: "Duração" };
function onMatchEnd(pm) {
  const fresh = !state.post || state.post.t !== pm.t;
  state.post = pm; renderPost();
  if (fresh && !PREVIEW && Date.now() / 1000 - pm.t < 120) {
    snd("note"); notify(`${pm.win === true ? "Vitória" : pm.win === false ? "Derrota" : "Fim de partida"}: ${pm.title}`, postLine(pm), "post");
  }
}
function postLine(pm) {
  const d = pm.data || {};
  return pm.game === "cs2" ? `${d.k ?? 0}/${d.d ?? 0}/${d.a ?? 0} · ADR ${d.adr ?? "-"} · HS ${d.hs_pct ?? "-"}%` : `${d.k ?? 0}/${d.d ?? 0}/${d.a ?? 0} · GPM ${d.gpm ?? "-"} · XPM ${d.xpm ?? "-"}`;
}
function renderPost() {
  const pm = state.post;
  const show = pm && Date.now() / 1000 - pm.t < 1800;
  $("g-post").classList.toggle("hidden", !show);
  $("pl-post").classList.toggle("hidden", !show || $("pl-gsi").parentElement.classList.contains("match"));
  if (!show) return;
  const d = pm.data || {}, cs = pm.game === "cs2", ref = pm.n_same >= 2 ? pm.avg_same : pm.avg_all, refN = pm.n_same >= 2 ? pm.n_same : pm.n_all;
  const refLabel = pm.n_same >= 2 ? `média em ${esc(pm.title)} (${refN})` : refN ? `média geral (${refN})` : "";
  const fmt = (k, v) => v == null ? "-" : k === "dur" ? fmtTime(v) : Number.isInteger(v) ? v : v.toFixed(1);
  const rows = (pm.game === "cs2" ? ["k", "d", "a", "hs_pct", "adr", "mvp"] : ["k", "d", "a", "gpm", "xpm", "lh", "dur"]).filter((k) => d[k] != null).map((k) => {
    const v = d[k], a = ref?.[k], better = a == null || k === "dur" ? null : k === "d" ? v < a : v > a;
    const diff = a == null || k === "dur" ? "" : `${v - a >= 0 ? "+" : ""}${fmt(k, Math.round((v - a) * 10) / 10)}`;
    return `<span>${CMP_LABEL[k]}</span><b>${fmt(k, v)}</b><span class="${better == null ? "" : better ? "up" : "dn"}">${diff}</span>`;
  }).join("");
  const res = pm.win === true ? "VITÓRIA" : pm.win === false ? "DERROTA" : "FIM";
  const extra = [pm.streak >= 2 ? `${pm.streak} ${pm.win ? "vitórias" : "derrotas"} seguidas` : "", pm.winrate_same != null && pm.n_same >= 2 ? `${pm.winrate_same}% de vitórias em ${esc(pm.title)}` : "", cs && d.rounds ? `${d.rounds} rounds` : ""].filter(Boolean).join(" · ");
  const html = `<h3><span>Fim de partida · ${cs ? "CS2" : "Dota 2"}</span><span>${humanAgo(Date.now() / 1000 - pm.t)}</span></h3>
    <div class="res${pm.win === false ? " l" : ""}">${res}</div><div class="sub">${esc(pm.title)}${extra ? " · " + extra : ""}</div>
    ${rows ? `<div class="cmp"><span class="h"></span><span class="h">agora</span><span class="h">${refLabel ? "vs " + refLabel : ""}</span>${rows}</div>` : ""}
    ${!refN ? '<div class="sub">Primeira partida salva: a comparação aparece a partir da próxima.</div>' : ""}`;
  setBox("g-post", html); setBox("pl-post", html);
}
setInterval(() => { if (state.post) renderPost(); }, 60000);

