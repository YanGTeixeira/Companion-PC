"use strict";
// ---------------------------------------------------------------- Games
const STORE_COLORS = { Steam: "#66c0f4", Epic: "#dcdcdc", Riot: "#eb5757", GOG: "#aa82ff", EA: "#f07850", Ubisoft: "#58a6ff" };
function renderGames() {
  const d = state.games; if (!d) return;
  const g = d.game, since = (performance.now() - state.gamesT) / 1000;
  const art = g?.art && state.gameart[g.art];
  $("g-art").style.backgroundImage = art ? `url(${art})` : "";
  $("g-art").classList.toggle("hidden", !art);
  if (g) {
    $("g-head").innerHTML = `<span class="chip">${esc(g.store)}</span><span class="playing">jogando</span><div class="gname">${esc(g.name)}</div>`;
    $("g-time").textContent = humanDur(g.elapsed + since);
    $("g-extra").textContent = [`Hoje: ${humanDur(g.today_s + since)}`, g.total_h ? `Total: ${Math.round(g.total_h)} h` : ""].filter(Boolean).join(" · ");
  } else {
    $("g-head").innerHTML = `<div class="gname">Nenhum jogo aberto</div>`;
    $("g-time").textContent = "";
    $("g-extra").textContent = d.today_s ? `Hoje: ${humanDur(d.today_s)} jogando` : "Steam, Epic, GOG, Riot, EA, Ubisoft";
  }
  const r = d.recent || [];
  $("g-recent").innerHTML = r.length ? r.map((x) => `<div class="row"><span>${esc(x.name)}</span><span>${humanDur(x.dur)} · ${humanAgo(x.ago + since)}</span></div>`).join("")
    : '<div class="empty">Nenhuma sessão ainda</div>';
}

// ---------------------------------------------------------------- Jogos: semana e biblioteca
let libT = 0, libData = [];
async function loadGamesExtra() {
  if (!ws || ws.readyState !== 1 || !welcome.features?.library || Date.now() - libT < 60000) return;
  libT = Date.now();
  try {
    const [lib, h] = await Promise.all([send("games.library"), send("games.history")]);
    libData = lib || []; renderLib(); renderWeek(h);
  } catch { libT = 0; }
}
function renderWeek(h) {
  if (!h) return;
  const max = Math.max(3600, ...h.days.map((d) => d.s));
  $("gh-total").textContent = h.week_s ? humanDur(h.week_s) : "";
  $("gh-days").innerHTML = h.days.map((d, i) => `<div class="wk${i === h.days.length - 1 ? " today" : ""}" title="${humanDur(d.s)}">
    <small>${d.s >= 3600 ? Math.round(d.s / 360) / 10 + "h" : d.s >= 60 ? Math.round(d.s / 60) + "m" : ""}</small>
    <i style="height:${Math.round((d.s / max) * 62)}px"></i>${d.d}</div>`).join("");
  const top = h.top[0]?.s || 1;
  $("gh-top").innerHTML = h.top.length ? h.top.map((g) => `<div class="toprow"><div class="row"><span>${esc(g.name)}</span><span>${humanDur(g.s)}</span></div>
    <div class="bar"><i style="width:${(g.s / top) * 100}%"></i></div></div>`).join("") : '<div class="empty">Nenhum jogo nos últimos 7 dias</div>';
}
// ---------------------------------------------------------------- Jogando (aba que aparece com um jogo aberto)
let playSeen = null;
function onGameState() {
  const g = state.games?.game, key = g ? g.name : null;
  setLive("play", "Jogando", !!g);
  if (typeof autoTheme === "function") autoTheme();
  if (g && playSeen !== key) {
    playSeen = key;
    // o jogo vira a tela principal (a não ser que esteja numa reunião agora)
    if (!vis("play") && !(state.meet?.inCall)) showView("play", true);
  }
  if (!g) playSeen = null;
  dotaPlace(dotaRunning());
  renderPlay();
}
function renderPlay() {
  const g = state.games?.game; if (!g) return;
  const since = (performance.now() - state.gamesT) / 1000, art = g.art && state.gameart[g.art];
  $("pl-art").style.backgroundImage = art ? `url(${art})` : "";
  $("pl-store").textContent = g.store; $("pl-name").textContent = g.name;
  $("pl-time").textContent = humanClock(g.elapsed + since);
  $("pl-extra").textContent = [`Hoje: ${humanDur(g.today_s + since)}`, g.total_h ? `Total: ${Math.round(g.total_h)} h` : ""].filter(Boolean).join(" · ");
  const dc = state.games?.discord || {};
  document.querySelector('[data-pa="dmute"]').classList.toggle("hidden", !dc.running);
  document.querySelector('[data-pa="ddeaf"]').classList.toggle("hidden", !dc.running);
  renderGsi();
}
function renderPlayPerf(s) {
  if (!vis("play")) return;
  const f = s.fps?.fps != null ? s.fps : null, g = s.gpu, sen = s.sensors;
  $("pl-fps").textContent = f ? f.fps : "–";
  $("pl-low").textContent = f?.low ? `1% baixo: ${f.low}` : "";
  $("pl-gpu").textContent = g ? `${Math.round(g.util)}% · ${Math.round(g.temp)}°C · ${fmtBytes(g.mem_used)}` : "–";
  $("pl-cpu").textContent = `${Math.round(s.cpu)}%${sen?.cpu_temp != null ? " · " + Math.round(sen.cpu_temp) + "°C" : ""}`;
  $("pl-ram").textContent = `${Math.round(s.ram_pct)}% · ${fmtBytes(s.ram_used)}`;
  $("pl-ping").textContent = !s.ping ? "–" : s.ping.ok ? s.ping.ms + " ms" : "sem internet";
  const ferr = s.fps?.error;
  $("pl-fps-hint").classList.toggle("hidden", !ferr);
  if (ferr) $("pl-fps-hint").textContent = ferr === "perm" ? "FPS: o PC precisa liberar o PresentMon uma vez (veja o README)." : "FPS: instale o PresentMon Console no PC.";
  drawSpark("sp-fps", [{ data: hist.fps, color: "--p", fill: true }]);
  const m = s.mic; document.querySelector('[data-pa="mic"]').classList.toggle("on", !!m?.muted);
  document.querySelector('[data-pa="mic"]').textContent = m?.muted ? "MIC mudo" : "MIC";
}
const clock = (s) => { if (s == null) return "–"; const neg = s < 0; s = Math.abs(Math.floor(s)); return (neg ? "-" : "") + Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
// ---------------------------------------------------------------- partida (Game State Integration de CS2 e Dota 2)
const GSI_BOX = ["pl-gsi", "pl-tact", "pl-graph"];
function gsiFresh() {
  const g = state.games?.game, d = state.gsi, name = (g?.name || "").toLowerCase();
  const isCs = /counter-strike/.test(name), isDota = /dota 2/.test(name);
  const fresh = d && Date.now() - state.gsiT < 30000 && ((d.g === "cs2" && isCs) || (d.g === "dota2" && isDota));
  return { d: fresh ? d : null, isCs, isDota };
}
function setBox(id, h) {
  const box = $(id); box.classList.toggle("hidden", !h);
  if (box.innerHTML !== h) box.innerHTML = h;
}
function renderGsi() {
  const { d, isCs, isDota } = gsiFresh();
  let h = ["", "", ""];
  if (d && d.g === "cs2") h = d.menu ? [`<h3><span>CS2</span><span>menu</span></h3><div class="sub">Esperando uma partida…</div>`, "", ""] : [gsiCs(d), csTact(d), csRounds(d)];
  else if (d && d.g === "dota2") h = d.menu || !d.hero ? [`<h3><span>Dota 2</span><span>${esc(d.state || "menu")}</span></h3><div class="sub">Esperando uma partida…</div>`, "", ""] : [gsiDota(d), dotaTimers(d), dotaGraph(d)];
  else if (isDota) h[0] = `<h3><span>Partida</span></h3><div class="sub" style="white-space:normal">Para ver a partida aqui: na Steam, clique com o botão direito em Dota 2 > Propriedades > Opções de inicialização e escreva <b>-gamestateintegration</b>. Depois reabra o jogo.</div>`;
  else if (isCs) h[0] = `<h3><span>Partida</span></h3><div class="sub" style="white-space:normal">Entre numa partida para ver placar, economia e rounds aqui.</div>`;
  GSI_BOX.forEach((id, i) => setBox(id, h[i]));
  const play = $("pl-gsi").parentElement;
  play.classList.toggle("has-gsi", !!h[0]);
  play.classList.toggle("match", !!(h[1] || h[2]));
  if (state.post) $("pl-post").classList.toggle("hidden", play.classList.contains("match") || Date.now() / 1000 - state.post.t > 1800);
  if (d && d.g === "dota2" && !d.menu) dotaAlerts(d);
  dotaPlace(isDota);
  if (d && d.g === "dota2") dotaGsi(d);
}

// ---- histórico (aba Jogos)
let histGame = store.get("histGame", "cs2");
async function loadHist() {
  document.querySelectorAll("#hist-g [data-hg]").forEach((b) => b.classList.toggle("on", b.dataset.hg === histGame));
  let r; try { r = await send("matches.get", { game: histGame }); } catch { return; }
  if (!r || r.game !== histGame) return;
  const cs = histGame === "cs2";
  if (!r.total) { $("hist").innerHTML = `<div class="empty">Nenhuma partida de ${cs ? "CS2" : "Dota 2"} salva ainda. Elas entram aqui sozinhas quando terminam.</div>`; return; }
  const when = (t) => { const d = new Date(t * 1000); return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); };
  $("hist").innerHTML = `<div class="row"><span>${r.total} partida${r.total > 1 ? "s" : ""}</span><span>${r.winrate ?? "–"}% de vitórias</span></div>
    <table><tr><th>${cs ? "Mapa" : "Herói"}</th><th>jogos</th><th>vit.</th><th>K/D/A</th><th>${cs ? "HS%" : "GPM"}</th><th>${cs ? "ADR" : "XPM"}</th></tr>
    ${r.groups.map((g) => `<tr><td>${esc(g.name)}</td><td>${g.n}</td><td>${g.winrate}%</td><td>${g.k}/${g.d}/${g.a}</td><td>${g.x ?? "–"}</td><td>${g.y ?? "–"}</td></tr>`).join("")}</table>
    <div style="margin-top:8px">${r.recent.map((m) => `<div class="hrow"><span class="wl ${m.win === false ? "l" : ""}">${m.win === true ? "V" : m.win === false ? "D" : "E"}</span>
      <span>${esc(m.title)}${cs ? ` <small>${m.mine}x${m.theirs}</small>` : ` <small>nível ${m.lvl ?? "–"} · ${clock(m.dur)}</small>`}<br><small>${when(m.ended)}${m.rp?.imp != null ? ` · <b class="${m.rp.imp >= 0 ? "up" : "dn"}">nota ${fmtImp(m.rp.imp)}</b>` : ""}${m.rp?.award ? " · " + esc(m.rp.award) : ""}</small></span>
      <span>${m.k ?? 0}/${m.d ?? 0}/${m.a ?? 0}<br><small>${cs ? `HS ${m.hs_pct ?? "–"}% · ADR ${m.adr ?? "–"}` : `${m.gpm ?? "–"} GPM · ${m.lh ?? 0} LH`}</small></span></div>`).join("")}</div>`;
}
$("hist-g").addEventListener("click", (e) => { const b = e.target.closest("[data-hg]"); if (!b) return; buzz(8); histGame = b.dataset.hg; store.set("histGame", histGame); loadHist(); });

// ---- CS2
const CS_FULL = { CT: 5000, T: 4300 }, CS_WIN = 3250;
function gsiCs(d) {
  const mine = d.team === "CT" ? d.ct : d.t, theirs = d.team === "CT" ? d.t : d.ct;
  const w = d.weapon, phase = { live: "ao vivo", freezetime: "compra", over: "fim do round" }[d.rphase] || d.rphase || "";
  return `<h3><span>${esc(d.map || "CS2")} · round ${d.round || "–"}</span><span>${esc(phase)}</span></h3>
    <div class="gsc"><div><b>${mine ?? "–"}</b> <span class="vs">${esc(d.team || "")}</span></div><span class="vs">x</span><div><span class="vs">${d.team === "CT" ? "T" : "CT"}</span> <b>${theirs ?? "–"}</b></div></div>
    ${d.spectating ? '<div class="dead">Morto · assistindo</div>' : `<div class="row"><span>Vida</span><span>${d.hp ?? "–"}</span></div><div class="bar hpbar ${d.hp <= 30 ? "bad" : ""}"><i style="width:${d.hp || 0}%"></i></div>
    <div class="row"><span>Colete</span><span>${d.armor ?? "–"}${d.helmet ? " + capacete" : ""}</span></div>
    ${w ? `<div class="row"><span>${esc(w.name)}</span><span class="big2">${w.clip ?? "–"}<small style="font-size:14px;color:var(--p3)"> / ${w.reserve ?? "–"}</small></span></div>` : ""}`}
    <div class="kda k5"><div><b>${d.k ?? 0}</b><small>abates</small></div><div><b>${d.d ?? 0}</b><small>mortes</small></div><div><b>${d.a ?? 0}</b><small>assist.</small></div>
      <div><b>${d.hs_pct ?? "–"}</b><small>HS %</small></div><div><b>${d.adr ?? "–"}</b><small>ADR</small></div></div>
    <div class="row"><span>Neste round</span><span>${d.rk ?? 0} abates${d.rhs ? ` (${d.rhs} HS)` : ""} · ${d.dmg ?? 0} de dano</span></div>`;
}
function bombLeft(d) { return d.cd ? d.cd.ends - (Date.now() - state.gsiT) / 1000 : null; }
function csTact(d) {
  const ph = d.cd?.phase;
  if (ph === "bomb" || ph === "defuse" || d.bomb === "planted") {
    const left = Math.max(0, bombLeft(d) ?? 0), defusing = ph === "defuse";
    const ct = d.team === "CT";
    const hint = defusing ? "Desarmando" : !d.cd ? "Bomba plantada" : left > 10 ? "Dá para desarmar sem kit (10 s)" : left > 5 ? "Só com kit (5 s)" : "Não dá mais para desarmar";
    return `<h3><span>${defusing ? "Desarmando" : "Bomba plantada"}</span><span>${ct ? "defenda / desarme" : "segure o bomb"}</span></h3>
      <div class="bomb${defusing ? " ok" : ""}"><b id="cs-bomb">${d.cd ? left.toFixed(1) : "!"}</b><div class="sub" id="cs-bomb-h">${hint}</div></div>
      <div class="bar ${left <= 10 ? "bad" : ""}"><i id="cs-bomb-bar" style="width:${Math.min(100, (left / 40) * 100)}%"></i></div>`;
  }
  const side = d.team === "T" ? "T" : "CT", money = d.money ?? 0, full = CS_FULL[side];
  const losses = Math.max(0, Math.min(4, d.losses ?? 0)), bonus = 1400 + 500 * losses;
  let buy, cls = "";
  if (money >= full) buy = "Compra completa";
  else if (money + bonus >= full) { buy = "Eco: guarde, compra completa no próximo"; cls = "eco"; }
  else if (money >= 2000) buy = "Force: SMG ou pistola + colete";
  else { buy = "Eco: só pistola"; cls = "eco"; }
  return `<h3><span>Economia</span><span>${side} · ${losses ? losses + " derrota" + (losses > 1 ? "s" : "") + " seguida" + (losses > 1 ? "s" : "") : "sem sequência"}</span></h3>
    <div class="row"><span>Dinheiro</span><span class="big2">$${money}</span></div>
    <div class="row"><span>Equipamento</span><span>$${d.equip ?? 0}</span></div>
    <div class="buy ${cls}">${buy}</div>
    <div class="row"><span>Compra completa (${side})</span><span>~$${full}</span></div>
    <div class="row"><span>Se perder o round</span><span>+$${bonus} → $${money + bonus}</span></div>
    <div class="row"><span>Se ganhar</span><span>+$${CS_WIN}+ → $${money + CS_WIN}</span></div>`;
}
const CS_RN = { E: "eliminação", B: "bomba", D: "desarme", T: "tempo", R: "refém", S: "desistência" };
function csRounds(d) {
  const rs = d.rounds || [];
  if (!rs.length) return `<h3><span>Rounds</span></h3><div class="sub">O primeiro round ainda não acabou.</div>`;
  const wins = rs.filter((r) => r.win === true).length, losses = rs.filter((r) => r.win === false).length;
  const last = rs[rs.length - 1];
  return `<h3><span>Rounds</span><span>${wins} ganhos · ${losses} perdidos</span></h3>
    <div class="rnds">${rs.map((r) => `<span class="${r.win === true ? "w" : r.win === false ? "l" : ""}${r.n === 13 || (r.n > 24 && (r.n - 25) % 3 === 0) ? " half" : ""}" title="Round ${r.n}: ${r.side || ""} por ${CS_RN[r.r] || r.r}">${r.r}</span>`).join("")}</div>
    <div class="clg"><span>E eliminação</span><span>B bomba</span><span>D desarme</span><span>T tempo</span></div>
    <div class="row" style="margin-top:6px"><span>Último (${last.n})</span><span>${last.win === true ? "ganhou" : last.win === false ? "perdeu" : esc(last.side || "")} por ${CS_RN[last.r] || "?"}</span></div>
    ${last.k != null ? `<div class="row"><span>Você</span><span>${last.k} abates${last.hs ? ` (${last.hs} HS)` : ""} · ${last.dmg} de dano</span></div>` : ""}
    ${rs.slice(-6, -1).filter((r) => r.k != null).reverse().map((r) => `<div class="row"><span>Round ${r.n}</span><span>${r.win ? "G" : "P"} · ${r.k} abates · ${r.dmg} dano</span></div>`).join("")}`;
}

// ---- Dota 2
// Tempos do patch 7.3x (relógio da partida, em segundos). Se o patch mudar, é só ajustar aqui.
const DOTA_TIMERS = [
  { id: "bounty", name: "Runa de recompensa", first: 0, every: 180 },
  { id: "power", name: "Runa de poder", first: 360, every: 120 },
  { id: "water", name: "Runa de água", at: [120, 240] },
  { id: "wisdom", name: "Runa de sabedoria", first: 420, every: 420 },
  { id: "lotus", name: "Lótus", first: 180, every: 180 },
  { id: "neutral", name: "Itens neutros", at: [420, 1020, 1620, 2220, 3600], tier: true },
  { id: "stack", name: "Stack (puxe agora)", every: 60, offset: 53, lead: 3 },
];
const DOTA_BELL_DEFAULT = ["power", "wisdom", "neutral", "rosh", "torm", "aegis"];
prefs.dotaBell = new Set(store.get("dotaBell", DOTA_BELL_DEFAULT));
prefs.dotaAlerts = store.get("dotaAlerts", true);
function dotaClock(d) { return d.clock == null ? null : d.clock + (d.paused ? 0 : Math.floor((Date.now() - state.gsiT) / 1000)); }
function nextOf(t, c) {
  if (t.at) { const i = t.at.findIndex((x) => x > c); return i < 0 ? null : { at: t.at[i], label: t.tier ? `tier ${i + 1}` : "" }; }
  if (t.offset != null) { let n = Math.floor(c / 60) * 60 + t.offset; if (n <= c) n += 60; return c < 60 ? null : { at: n }; }
  if (c < t.first) return { at: t.first };
  return { at: t.first + Math.ceil((c - t.first + 0.001) / t.every) * t.every };
}
function dotaRows(d) {
  const c = dotaClock(d); if (c == null) return [];
  const rows = [];
  for (const t of DOTA_TIMERS) { const n = nextOf(t, c); if (n) rows.push({ id: t.id, name: t.name + (n.label ? " " + n.label : ""), at: n.at, left: n.at - c, span: t.every || 180, lead: t.lead || 15 }); }
  rows.push({ id: "day", name: d.day === false ? "Dia" : "Noite", at: Math.ceil((c + 0.001) / 300) * 300, left: Math.ceil((c + 0.001) / 300) * 300 - c, span: 300, lead: 0 });
  const m = d.marks || {};
  if (m.aegis != null && m.aegis + 300 > c) rows.push({ id: "aegis", name: "Aegis acaba", left: m.aegis + 300 - c, span: 300, lead: 20 });
  if (m.rosh != null) {
    if (c < m.rosh + 480) rows.push({ id: "rosh", name: "Roshan pode voltar", left: m.rosh + 480 - c, span: 480, lead: 30 });
    else if (c < m.rosh + 660) rows.push({ id: "rosh2", name: "Roshan com certeza vivo", left: m.rosh + 660 - c, span: 180, lead: 0, soon: true });
  }
  const tormAt = m.torm != null ? m.torm + 600 : 1200;
  if (tormAt > c) rows.push({ id: "torm", name: "Tormentor" + (m.torm != null ? " volta" : " aparece"), left: tormAt - c, span: m.torm != null ? 600 : 1200, lead: 20 });
  return rows.sort((a, b) => a.left - b.left);
}
function dotaTimers(d) {
  const rows = dotaRows(d).slice(0, 8);
  return `<h3><span>Timers · ${clock(dotaClock(d))}</span><button class="btn sm" data-dt="alerts" style="padding:0 8px">${prefs.dotaAlerts ? "avisos: sim" : "avisos: não"}</button></h3>
    <div id="dt-rows">${rows.map((r) => ttRow(r)).join("")}</div>
    <div class="tbtns"><button class="btn sm" data-dt="rosh">Roshan morreu</button><button class="btn sm" data-dt="torm">Tormentor morreu</button>${d.marks?.rosh != null || d.marks?.torm != null ? '<button class="btn sm" data-dt="clear">Limpar</button>' : ""}</div>`;
}
function ttRow(r) {
  const on = prefs.dotaBell.has(r.id.replace(/2$/, ""));
  return `<div class="ttrow${r.soon || (r.lead && r.left <= r.lead) ? " soon" : ""}"><button class="bell${on ? " on" : ""}" data-bell="${r.id}" aria-label="aviso">${on ? "●" : "○"}</button><span>${esc(r.name)}</span><span class="tt">${clock(r.left)}</span>
    <div class="bar"><i style="width:${Math.max(0, Math.min(100, 100 - (r.left / r.span) * 100))}%"></i></div></div>`;
}
function svgChart(lines, xmax, ymax) {
  const W = 300, H = 70, x = (v) => ((v / Math.max(1, xmax)) * W).toFixed(1), y = (v) => (H - (v / Math.max(1, ymax)) * H).toFixed(1);
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><line class="ax" x1="0" y1="${H}" x2="${W}" y2="${H}"/>${lines.map(([pts, cls]) =>
    pts.length ? `<polyline class="${cls}" points="${pts.map(([a, b]) => x(a) + "," + y(b)).join(" ")}"/>` : "").join("")}</svg>`;
}
const LH_GOAL = 7;
function dotaGraph(d) {
  const s = d.series || [], c = dotaClock(d) || 0, m = Math.max(1, c / 60);
  if (s.length < 2) return `<h3><span>Ritmo</span></h3><div class="sub" style="white-space:normal">Os gráficos aparecem depois de alguns minutos de partida.</div>`;
  const xmax = Math.max(10, s[s.length - 1].m + 1);
  const lh = s.map((p) => [p.m, p.lh || 0]), goal = [[0, 0], [xmax, LH_GOAL * xmax]];
  const gp = s.map((p) => [p.m, p.gpm || 0]), xp = s.map((p) => [p.m, p.xpm || 0]);
  const rate = (d.lh || 0) / m, gmax = Math.max(600, ...gp.map((p) => p[1]), ...xp.map((p) => p[1]));
  const prev = s.length > 5 ? s[s.length - 6] : s[0], last = s[s.length - 1];
  const recent = last.m > prev.m ? ((last.lh - prev.lh) / (last.m - prev.m)).toFixed(1) : "–";
  return `<h3><span>Last hits</span><span>${rate.toFixed(1)}/min · últ. 5 min ${recent}</span></h3>
    ${svgChart([[goal, "l2"], [lh, "l1"]], xmax, Math.max(LH_GOAL * xmax, ...lh.map((p) => p[1])))}
    <div class="clg"><span><i></i>seus last hits (${d.lh ?? 0})</span><span><i class="d"></i>meta ${LH_GOAL}/min (${Math.round(LH_GOAL * m)})</span></div>
    <h3 style="margin-top:10px"><span>GPM e XPM</span><span>${d.gpm ?? "–"} / ${d.xpm ?? "–"}</span></h3>
    ${svgChart([[gp, "l1"], [xp, "l3"]], xmax, gmax)}
    <div class="clg"><span><i></i>GPM</span><span><i class="h"></i>XPM</span><span>ouro agora: ${d.gold ?? "–"}</span></div>`;
}
function gsiDota(d) {
  const hp = d.hpmax ? Math.round((d.hp / d.hpmax) * 100) : 0, mp = d.manamax ? Math.round((d.mana / d.manamax) * 100) : 0;
  const ult = (d.abilities || []).find((a) => a.ult);
  return `<h3><span>${esc(d.hero)} · nível ${d.level ?? "–"}</span><span>${clock(dotaClock(d))} ${d.day === false ? "noite" : "dia"}${d.paused ? " · pausado" : ""}</span></h3>
    <div class="gsc"><div><b>${d.rad ?? "–"}</b> <span class="vs">Radiant</span></div><span class="vs">${esc(d.state || "")}</span><div><span class="vs">Dire</span> <b>${d.dire ?? "–"}</b></div></div>
    ${d.alive === false ? `<div class="dead">Morto · volta em ${d.respawn ?? "?"} s</div><div class="sub">Buyback: ${d.buyback ?? "–"} de ouro${d.bbcd ? ` · recarga ${d.bbcd}s` : (d.gold ?? 0) >= (d.buyback ?? 1e9) ? " · disponível" : " · falta ouro"}</div>`
      : `<div class="row"><span>Vida</span><span>${d.hp ?? "–"} / ${d.hpmax ?? "–"}</span></div><div class="bar hpbar ${hp <= 30 ? "bad" : ""}"><i style="width:${hp}%"></i></div>
    <div class="row"><span>Mana</span><span>${d.mana ?? "–"} / ${d.manamax ?? "–"}</span></div><div class="bar hpbar"><i style="width:${mp}%"></i></div>`}
    <div class="kda"><div><b>${d.k ?? 0}</b><small>abates</small></div><div><b>${d.d ?? 0}</b><small>mortes</small></div><div><b>${d.a ?? 0}</b><small>assist.</small></div><div><b>${d.lh ?? 0}<small style="font-size:14px">/${d.dn ?? 0}</small></b><small>LH / DN</small></div></div>
    <div class="row"><span>Ouro</span><span>${d.gold ?? "–"} · ${d.gpm ?? "–"} GPM · ${d.xpm ?? "–"} XPM</span></div>
    ${ult ? `<div class="row"><span>Ultimate</span><span>${!ult.lvl ? "não aprendida" : ult.cd ? ult.cd + " s" : "pronta"}</span></div>` : ""}
    ${d.alive !== false && d.buyback ? `<div class="row"><span>Buyback</span><span>${d.bbcd ? "recarga " + clock(d.bbcd) : (d.gold ?? 0) >= d.buyback ? "tem ouro (" + d.buyback + ")" : "falta " + (d.buyback - (d.gold ?? 0))}</span></div>` : ""}
    ${d.items?.length ? `<div class="items">${d.items.map((it) => `<div class="${it.cd ? "cd" : ""}">${esc(it.name)}${it.cd ? ` ${it.cd}s` : it.charges ? ` x${it.charges}` : ""}</div>`).join("")}</div>` : ""}`;
}
// avisos: bipe + vibração + aviso na tela, uma vez por acontecimento
let dotaPrev = null; const dotaFired = new Set();
function alarm(msg) { toast(msg, "warn"); snd("alarm"); if (prefs.vib && navigator.vibrate && !PREVIEW) try { navigator.vibrate([120, 60, 120]); } catch {} }
function dotaAlerts(d) {
  if (!prefs.dotaAlerts || PREVIEW) { dotaPrev = d; return; }
  const p = dotaPrev; dotaPrev = d;
  for (const r of dotaRows(d)) {
    const base = r.id.replace(/2$/, "");
    if (!prefs.dotaBell.has(base) || !r.lead || r.left > r.lead || r.left < 0) continue;
    const key = r.id + ":" + Math.round((dotaClock(d) + r.left) / 5);
    if (dotaFired.has(key)) continue;
    dotaFired.add(key); alarm(`${r.name} em ${r.left} s`);
  }
  if (!p || p.hero !== d.hero) return;
  const ult = (d.abilities || []).find((a) => a.ult), pu = (p.abilities || []).find((a) => a.ult);
  if (ult && pu && pu.cd > 0 && !ult.cd && ult.lvl) alarm("Ultimate pronta");
  const bkb = (d.items || []).find((i) => /black king bar/i.test(i.name)), pb = (p.items || []).find((i) => /black king bar/i.test(i.name));
  if (bkb && pb && pb.cd > 0 && !bkb.cd) alarm("BKB pronta");
  const canBB = (x) => x.alive === false && !x.bbcd && x.buyback && (x.gold ?? 0) >= x.buyback;
  if (canBB(d) && !canBB(p)) alarm("Buyback disponível");
  const low = (x) => x.alive !== false && x.hpmax && x.hp / x.hpmax < 0.25;
  if (low(d) && !low(p)) alarm("Vida baixa");
}
document.querySelector(".play").addEventListener("click", (e) => {
  const bell = e.target.closest("[data-bell]");
  if (bell) {
    const id = bell.dataset.bell.replace(/2$/, "");
    prefs.dotaBell.has(id) ? prefs.dotaBell.delete(id) : prefs.dotaBell.add(id);
    store.set("dotaBell", [...prefs.dotaBell]); buzz(8); renderGsi(); return;
  }
  const b = e.target.closest("[data-dt]"); if (!b) return;
  const k = b.dataset.dt;
  if (k === "alerts") { prefs.dotaAlerts = !prefs.dotaAlerts; store.set("dotaAlerts", prefs.dotaAlerts); buzz(8); renderGsi(); }
  else if (k === "clear") { act("dota.mark", { what: "rosh", clear: true }); act("dota.mark", { what: "torm", clear: true }); act("dota.mark", { what: "aegis", clear: true }); }
  else act("dota.mark", { what: k }, k === "rosh" ? "Roshan: marcado" : "Tormentor: marcado");
});
// relógio da partida e contagem da bomba andam no celular entre um dado e outro
setInterval(() => {
  if (!vis("play")) return;
  const { d } = gsiFresh(); if (!d) return;
  if (d.g === "dota2" && !d.menu) { const rows = dotaRows(d).slice(0, 8), el = $("dt-rows"); if (el) el.innerHTML = rows.map(ttRow).join(""); dotaAlerts(d); }
}, 1000);
setInterval(() => {
  if (!vis("play")) return;
  const { d } = gsiFresh(); const n = $("cs-bomb");
  if (!d || d.g !== "cs2" || !n || !d.cd) return;
  const left = Math.max(0, bombLeft(d)); n.textContent = left.toFixed(1);
  $("cs-bomb-bar").style.width = Math.min(100, (left / 40) * 100) + "%";
  if (d.cd.phase === "bomb") $("cs-bomb-h").textContent = left > 10 ? "Dá para desarmar sem kit (10 s)" : left > 5 ? "Só com kit (5 s)" : "Não dá mais para desarmar";
}, 100);
document.querySelector(".pacts").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-pa]"); if (!b) return;
  const k = b.dataset.pa;
  if (k === "mic") act("mic.set", { muted: "toggle" });
  else if (k === "dmute") act("discord.mute", null, "Discord: mudo");
  else if (k === "ddeaf") act("discord.deafen", null, "Discord: surdo");
  else if (k === "shot") act("key.press", { keys: "f12" }, "Print (F12 da Steam)");
  else if (k === "clip") act("key.press", { keys: "win+alt+g" }, "Clipe: últimos 30 s (Game Bar)");
});
setInterval(() => { if (vis("play") && state.games?.game) { $("pl-time").textContent = humanClock(state.games.game.elapsed + (performance.now() - state.gamesT) / 1000); } }, 1000);

