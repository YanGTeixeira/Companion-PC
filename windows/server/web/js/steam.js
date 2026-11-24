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
// relatório do Dota (STRATZ/OpenDota): chega minutos depois do fim, por match_report
const LANE_RES = { stomp_win: ["Atropelou a lane", "up"], win: ["Ganhou a lane", "up"], tie: ["Lane empatada", ""], loss: ["Perdeu a lane", "dn"], stomp_loss: ["Atropelado na lane", "dn"] };
const LANE_NAME = { safe: "safe", mid: "mid", off: "off", jungle: "jungle", roam: "roaming" };
const fmtNw = (v) => v == null ? "–" : v >= 1000 ? (v / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(v);
const fmtImp = (v) => v == null ? "" : (v > 0 ? "+" : "") + v;
function onMatchReport(d) {
  if (!state.post || state.post.key !== d.key) { if (vis("games")) loadHist(); return; }
  const before = state.post.report;
  state.post.report = d.report; renderPost();
  if (vis("games")) loadHist();
  const me = d.report.me != null ? d.report.players[d.report.me] : null;
  // avisa uma vez, quando a nota sai (ou quando só o OpenDota tem a partida e não virá mais nada)
  if (!PREVIEW && me && d.report.complete && !before?.complete) {
    snd("note");
    notify("Relatório da partida", [me.imp != null ? `Nota ${fmtImp(me.imp)}` : "", me.award || "", me.lane_res ? LANE_RES[me.lane_res][0] : ""].filter(Boolean).join(" · ") || "Placar completo", "post");
  }
}
function reportHtml(pm) {
  const rp = pm.report;
  if (!rp) return '<div class="sub drep-wait">Placar dos 10 e nota chegam alguns minutos depois do fim…</div>';
  const me = rp.me != null ? rp.players[rp.me] : null;
  const chips = me ? [
    me.imp != null ? `<span class="chip3 ${me.imp >= 0 ? "up" : "dn"}" title="Desempenho vs. quem joga o mesmo herói no seu rank">Nota ${fmtImp(me.imp)}</span>` : "",
    me.award ? `<span class="chip3 up">${esc(me.award)}</span>` : "",
    me.pos || me.lane ? `<span class="chip3">${me.pos ? "Pos " + me.pos : ""}${me.pos && me.lane ? " · " : ""}${me.lane ? LANE_NAME[me.lane] : ""}</span>` : "",
    me.lane_res ? `<span class="chip3 ${LANE_RES[me.lane_res][1]}">${LANE_RES[me.lane_res][0]}</span>` : "",
  ].join("") : "";
  const note = [rp.outcome ? rp.outcome[0].toUpperCase() + rp.outcome.slice(1) : "", rp.src === "stratz" ? "STRATZ" : "OpenDota",
    rp.complete ? "" : rp.src === "opendota" ? "a nota chega quando o STRATZ analisar" : "análise do STRATZ em andamento"].filter(Boolean).join(" · ");
  const team = (rad) => {
    const won = rp.radiant_win === rad;
    return `<div class="dteam"><div class="dth"><span>${rad ? "Radiant" : "Dire"}</span><span class="${won ? "up" : "dn"}">${won ? "vitória" : "derrota"}</span></div>`
      + rp.players.filter((p) => p.r === rad).map((p) => `<div class="dpl${p.me ? " me" : ""}"><span class="dh">${esc(p.hero)}${p.pos ? ` <small>${p.pos}</small>` : ""}</span>`
        + `<span>${p.k}/${p.d}/${p.a}</span><span>${fmtNw(p.nw)}</span><span class="${p.imp == null ? "" : p.imp >= 0 ? "up" : "dn"}">${fmtImp(p.imp)}</span></div>`).join("") + "</div>";
  };
  return `<div class="drep">${chips ? `<div class="chips3">${chips}</div>` : ""}
    ${me && me.items.length ? `<div class="sub">${me.items.map(esc).join(" · ")}${me.neutral ? " · <i>" + esc(me.neutral) + "</i>" : ""}</div>` : ""}
    <div class="sub">${note}</div><div class="dteams">${team(true)}${team(false)}</div></div>`;
}
function renderPost() {
  const pm = state.post, now = Date.now() / 1000;
  // fica 30 min depois do fim, ou 30 min depois que o relatório chegou
  const show = pm && (now - pm.t < 1800 || (pm.report && now - pm.report.t < 1800));
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
    ${!refN ? '<div class="sub">Primeira partida salva: a comparação aparece a partir da próxima.</div>' : ""}
    ${cs ? "" : reportHtml(pm)}`;
  setBox("g-post", html); setBox("pl-post", html);
}
setInterval(() => { if (state.post) renderPost(); }, 60000);

