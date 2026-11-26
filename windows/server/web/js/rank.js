"use strict";
// ---------------------------------------------------------------- Ranking público (Jogador › Ranking)
// O PC envia só apelido, XP, sequência, quantos troféus e os ids de título/moldura/vitrine (ranking.py) e busca
// tudo no servidor (cloud/ranking). Abas: Liga (grupo da semana), Amigos (quem você segue), Duelos e Geral.
let rankSt = null, rankTab = "league", rankKind = "week", rankData = {}, rankEditing = false;
const RANK_TABS = [["league", "Liga"], ["friends", "Amigos"], ["duels", "Duelos"], ["board", "Geral"]];
const RANK_KINDS = [["week", "Semana"], ["level", "Nível"], ["streak", "Sequência"]];
const LEAGUES = ["Bronze", "Prata", "Ouro", "Safira", "Rubi", "Diamante"];
const LEAGUE_COLOR = ["#cd7f32", "#c9d1d9", "#ffd23f", "#3b82f6", "#e0245e", "#7df9ff"];
const RANK_ACT = { league: "rank.league", friends: "rank.friends", duels: "rank.duels" };

async function loadRank(force) {
  try { rankSt = await send("rank.state"); } catch { return; }
  renderRank();
  if (!rankSt.joined) return;
  if (force || !rankKey()) loadBoard(force);
  // amigos e duelos em segundo plano: o perfil sabe se você já segue, e a aba Duelos mostra os convites
  for (const k of ["friends", "duels"]) if (k !== rankTab && (force || !rankData[k]))
    send(RANK_ACT[k], {}, true, 20000).then((d) => { rankData[k] = d; if (k === "duels") renderRank(); }).catch(() => {});
}
const rankKey = () => (rankTab === "board" ? rankData["b:" + rankKind] : rankData[rankTab]);
// aviso do PC: só recarrega se a conta mudou (entrou, saiu, trocou o apelido, ou apareceu/sumiu um erro)
function onRank(d) {
  const changed = !rankSt || d.joined !== rankSt.joined || d.nick !== rankSt.nick || d.error !== rankSt.error;
  rankSt = d;
  if (!changed) return;
  rankData = {};
  if (vis("rank")) loadRank(true); else renderRank();
}
async function loadBoard(force) {
  const tab = rankTab, kind = rankKind, key = tab === "board" ? "b:" + kind : tab;
  try {
    rankData[key] = tab === "board" ? await send("rank.board", { kind }, true, 20000) : await send(RANK_ACT[tab], { force: !!force }, true, 20000);
  } catch (e) { rankData[key] = { error: e.message }; }
  if (tab === rankTab && kind === rankKind) renderRank();
}
// envia uma ação e põe a resposta no lugar do que a aba mostra
async function rankDo(act, p, tab, okMsg) {
  try { rankData[tab] = await send(act, p, true, 20000); if (okMsg) toast(okMsg, "ok"); renderRank(); return true; }
  catch (e) { toast(e.message, "bad"); return false; }
}

const rankVal = (kind, r) => (kind === "week" ? `${r.value} XP` : kind === "level" ? `nível ${r.level}` : `${r.value} dia${r.value === 1 ? "" : "s"}`);
const leagueTag = (n) => (n == null ? "" : `<span class="lgtag" style="--lg:${LEAGUE_COLOR[n] || "var(--p3)"}">${LEAGUES[n] || ""}</span>`);
const shield = (n, cls = "") => `<svg class="lgsh ${cls}" viewBox="0 0 40 46" aria-hidden="true"><path d="M20 2 37 8v14c0 11-7.5 18.5-17 22C10.5 40.5 3 33 3 22V8z" fill="${LEAGUE_COLOR[n] || "#888"}"/>
  <path d="M20 8 31 12v10c0 7.5-4.8 12.6-11 15-6.2-2.4-11-7.5-11-15V12z" fill="#000" fill-opacity=".22"/><text x="20" y="28" text-anchor="middle" font-size="14" font-family="sans-serif" font-weight="700" fill="#fff">${n + 1}</text></svg>`;
// linha de jogador (nick clicável abre o perfil)
function rankRow(r, right, cls = "") {
  const t = rewardName(r.title);
  return `<li class="${cls}${r.me || r.nick === rankSt?.nick ? " me" : ""}"><span class="rkpos">${r.pos ?? ""}</span>
    <button class="rknick" data-pf="${esc(r.nick)}">${badge(r.level, r.frame, "xs", r.av, r.prestige)}${fxName(r.nick, r.fx)}</button>
    <small>${t ? esc(t) + " · " : ""}nível ${r.level}${r.extra ? " · " + r.extra : ""}</small><b>${right}</b></li>`;
}

function renderRank() {
  const box = $("rk-body"); if (!box || !rankSt) return;
  $("rk-me").textContent = "";
  if (!rankSt.available) { box.innerHTML = '<div class="empty">O ranking online ainda não está no ar.</div>'; return; }
  if (!rankSt.joined) {
    box.innerHTML = `<div class="sub" style="white-space:normal;margin-bottom:10px">Compare o seu XP com o de outras pessoas, entre numa <b>liga</b> semanal,
      siga amigos e desafie para <b>duelos</b>. Do seu PC sai só: <b>apelido, nível, XP, sequência, quantos troféus e o seu perfil</b> (título, moldura, avatar, fundo, efeito, cor, vitrine e a frase que você escrever).
      Nada de apps, sites ou tempo de tela. Dá para sair e apagar tudo quando quiser.</div>
      <div class="brow rkjoin"><input class="fi" id="rk-nick" maxlength="20" placeholder="Seu apelido (3 a 20 letras)" autocomplete="off"><button class="btn" id="rk-join">Entrar</button></div>`;
    $("rk-join").onclick = async () => {
      const nick = $("rk-nick").value.trim(); if (nick.length < 3) return toast("O apelido precisa de pelo menos 3 letras", "bad");
      buzz(8); $("rk-join").disabled = true;
      try { rankSt = await send("rank.join", { nick }, true, 20000); rankData = {}; toast(`No ranking como ${rankSt.nick}`, "ok"); loadRank(true); }
      catch (e) { toast(e.message, "bad"); $("rk-join").disabled = false; }
    };
    return;
  }
  const tabs = `<div class="chips rkchips">${RANK_TABS.map(([k, l]) => `<button class="chip2${k === rankTab ? " on" : ""}" data-rt="${k}">${l}${k === "duels" && duelsIn() ? ` <i class="rkdot">${duelsIn()}</i>` : ""}</button>`).join("")}</div>`;
  const d = rankKey();
  let body;
  if (!d) body = '<div class="empty">Carregando…</div>';
  else if (d.error) body = `<div class="warn">${esc(d.error)}</div>`;
  else body = { league: rankLeague, friends: rankFriends, duels: rankDuels, board: rankBoard }[rankTab](d);
  const foot = rankEditing
    ? `<div class="brow rkjoin"><input class="fi" id="rk-nick" maxlength="20" value="${esc(rankSt.nick)}"><button class="btn" id="rk-save">Salvar</button></div>`
    : `<div class="rkfoot"><span>você: ${esc(rankSt.nick)}</span>
       <span><button class="btn sm" id="rk-edit">Apelido</button><button class="btn sm danger" id="rk-leave">Sair</button></span></div>`;
  const focus = document.activeElement?.id === "rk-fnick" ? $("rk-fnick").value : null;
  box.innerHTML = tabs + body + (rankSt.error ? `<div class="warn">${esc(rankSt.error)}</div>` : "") + foot;
  if (focus !== null && $("rk-fnick")) { $("rk-fnick").value = focus; $("rk-fnick").focus(); }
  box.querySelector(".rkchips").onclick = (e) => {
    const b = e.target.closest("[data-rt]"); if (!b) return;
    buzz(8); rankTab = b.dataset.rt; renderRank(); if (!rankKey()) loadBoard();
  };
  box.querySelector(".rkkinds")?.addEventListener("click", (e) => {
    const b = e.target.closest("[data-rk]"); if (!b) return;
    buzz(8); rankKind = b.dataset.rk; renderRank(); if (!rankKey()) loadBoard();
  });
  if (rankEditing) {
    $("rk-save").onclick = async () => {
      try { rankSt = await send("rank.nick", { nick: $("rk-nick").value.trim() }, true, 20000); rankEditing = false; rankData = {}; toast("Apelido trocado", "ok"); loadRank(true); }
      catch (e) { toast(e.message, "bad"); }
    };
  } else {
    $("rk-edit").onclick = () => { rankEditing = true; renderRank(); $("rk-nick").focus(); };
    $("rk-leave").onclick = async () => {
      if (!confirm("Sair do ranking? A sua conta, a liga, os amigos e os duelos são apagados do servidor.")) return;
      try { rankSt = await send("rank.leave", {}, true, 20000); rankData = {}; toast("Você saiu do ranking", "ok"); renderRank(); }
      catch (e) { toast(e.message, "bad"); }
    };
  }
}

// ---------------------------------------------------------------- Liga da semana
function rankLeague(d) {
  const n = d.league || 0, lname = LEAGUES[n];
  const res = d.res === "up" ? `<div class="lgres up">Você subiu para a liga ${lname}!</div>` : d.res === "down" ? `<div class="lgres down">Você caiu para a liga ${lname}. Bora voltar!</div>` : "";
  const head = `<div class="lghead">${shield(n)}<div><b style="color:${LEAGUE_COLOR[n]}">Liga ${lname}</b>
    <small>${d.joined ? `grupo de ${d.rows.length} · ${n < 5 ? `os ${d.up} primeiros sobem` : "a liga mais alta"}${d.down ? ` · os ${d.down} últimos descem` : ""}` : "ganhe XP nesta semana para entrar num grupo"}</small>
    <small>zera na segunda; quem ganhar pelo menos 200 XP e ficar no topo sobe</small></div></div>`;
  if (!d.joined) return res + head;
  const me = d.rows.find((r) => r.me);
  $("rk-me").textContent = me ? `você: #${me.rank}` : "";
  const nn = d.rows.length;
  return res + head + `<ol class="rklist lg">${d.rows.map((r) => {
    const zone = r.rank <= d.up && n < 5 ? "up" : d.down && r.rank > nn - d.down ? "down" : "";
    return rankRow({ ...r, pos: r.rank }, `${r.xp} XP`, zone);
  }).join("")}</ol>`;
}

// ---------------------------------------------------------------- Amigos (quem você segue)
function rankFriends(d) {
  const all = [...d.rows.map((r) => ({ ...r })), { ...d.me, me: true }].sort((a, b) => b.week_xp - a.week_xp);
  all.forEach((r, i) => (r.pos = i + 1));
  const myPos = all.find((r) => r.me)?.pos;
  if (d.rows.length) $("rk-me").textContent = `você: #${myPos} de ${all.length}`;
  const add = `<div class="brow rkjoin"><input class="fi" id="rk-fnick" maxlength="20" placeholder="Apelido de alguém para seguir" autocomplete="off"><button class="btn" id="rk-follow">Seguir</button></div>`;
  const list = d.rows.length ? `<ol class="rklist">${all.map((r) => rankRow({ ...r, extra: r.me ? "" : r.mutual ? "segue você" : "" },
    `${r.week_xp} XP`)).join("")}</ol><small class="rkweek" style="display:block;margin-top:6px">XP desta semana · ${d.followers} pessoa${d.followers === 1 ? "" : "s"} segue${d.followers === 1 ? "" : "m"} você</small>`
    : '<div class="empty">Siga alguém pelo apelido para comparar o XP da semana e desafiar para duelos.</div>';
  setTimeout(() => {
    const go = async () => {
      const nick = $("rk-fnick")?.value.trim(); if (!nick) return;
      buzz(8);
      if (await rankDo("rank.friend.add", { nick }, "friends", `Seguindo ${nick}`)) $("rk-fnick").value = "";
    };
    if ($("rk-follow")) { $("rk-follow").onclick = go; $("rk-fnick").onkeydown = (e) => e.key === "Enter" && go(); }
  });
  return add + list;
}

// ---------------------------------------------------------------- Duelos
const duelsIn = () => (rankData.duels?.rows || []).filter((x) => x.dir === "in" && x.status === "pending").length;
function rankDuels(d) {
  const rows = d.rows || [];
  const grp = { pending_in: [], active: [], pending_out: [], done: [] };
  for (const x of rows) {
    if (x.status === "pending") grp[x.dir === "in" ? "pending_in" : "pending_out"].push(x);
    else if (x.status === "active") grp.active.push(x);
    else if (x.status === "done") grp.done.push(x);
  }
  const who = (x) => `<button class="rknick" data-pf="${esc(x.nick)}">${esc(x.nick)}</button>`;
  const sec = (t, items, fn) => (items.length ? `<h4 class="dlh">${t}</h4>${items.map(fn).join("")}` : "");
  const html = sec("Convites para você", grp.pending_in, (x) => `<div class="duel">${who(x)} desafiou você
      <span class="dlbtn"><button class="btn sm" data-duel="${x.id}" data-acc="1">Aceitar</button><button class="btn sm danger" data-duel="${x.id}" data-acc="0">Recusar</button></span></div>`)
    + sec("Valendo nesta semana", grp.active, (x) => {
      const tot = Math.max(1, x.my + x.their), p = (x.my / tot) * 100;
      return `<div class="duel act"><div class="dlrow"><span>Você <b>${x.my}</b></span><span>${who(x)} <b>${x.their}</b></span></div>
        <div class="dlbar"><i style="width:${p}%"></i></div><small>XP ganho desde o aceite · acaba domingo</small></div>`;
    })
    + sec("Esperando resposta", grp.pending_out, (x) => `<div class="duel">Você desafiou ${who(x)}<span class="dlbtn"><button class="btn sm" data-duel="${x.id}" data-acc="0">Cancelar</button></span></div>`)
    + sec("Encerrados", grp.done, (x) => `<div class="duel ${x.res}"><span>${x.res === "won" ? "🏆 Venceu" : x.res === "lost" ? "Perdeu" : "Empate"} contra ${who(x)}</span><small>${x.my} × ${x.their} · ${x.week}</small></div>`);
  setTimeout(() => document.querySelectorAll("#rk-body [data-duel]").forEach((b) => (b.onclick = () => {
    buzz(8); rankDo("rank.duel.answer", { id: +b.dataset.duel, accept: b.dataset.acc === "1" }, "duels", b.dataset.acc === "1" ? "Duelo aceito: valendo até domingo" : "");
  })));
  return (html || '<div class="empty">Nenhum duelo ainda.</div>') +
    '<div class="sub" style="white-space:normal;margin-top:8px">Desafie alguém que você segue: abra o perfil (toque no apelido) e escolha <b>Desafiar</b>. Vence quem ganhar mais XP do aceite até domingo. Até 3 duelos por semana. Vencer libera a conquista <b>Duelista</b>.</div>';
}

// ---------------------------------------------------------------- Geral (o ranking de antes)
function rankBoard(d) {
  const me = d.me, myRank = me?.ranks?.[rankKind];
  $("rk-me").textContent = myRank ? `você: #${myRank}` : "";
  const kinds = `<div class="chips rkkinds">${RANK_KINDS.map(([k, l]) => `<button class="chip2${k === rankKind ? " on" : ""}" data-rk="${k}">${l}</button>`).join("")}${rankKind === "week" ? '<small class="rkweek">zera na segunda</small>' : ""}</div>`;
  if (!d.rows.length) return kinds + '<div class="empty">Ninguém pontuou ainda. Seja o primeiro!</div>';
  const medal = ["ouro", "prata", "bronze"];
  let list = `<ol class="rklist">${d.rows.map((r) => rankRow({ ...r, pos: r.rank <= 3 ? trophy(medal[r.rank - 1], true) : "#" + r.rank,
    extra: `${r.unlocked} troféu${r.unlocked === 1 ? "" : "s"}` }, rankVal(rankKind, r))).join("")}</ol>`;
  if (myRank && myRank > d.rows.length) {
    const val = rankKind === "week" ? `${me.week_xp} XP` : rankKind === "level" ? `nível ${me.level}` : `${me.streak} dias`;
    list += `<div class="rkyou">… você: <b>#${myRank}</b> · ${esc(val)}</div>`;
  } else if (!myRank && me) list += `<div class="rkyou">Você ainda não pontuou ${rankKind === "week" ? "nesta semana" : "aqui"}.</div>`;
  return kinds + list + (d.players ? `<small class="rkweek" style="display:block;margin-top:6px">${d.players} jogador${d.players > 1 ? "es" : ""}${me?.hidden ? " · você está fora do ranking" : ""}</small>` : "");
}

// ---------------------------------------------------------------- perfil de um jogador (toque no apelido)
document.addEventListener("click", async (e) => {
  const b = e.target.closest("#rk-body [data-pf]"); if (!b) return;
  buzz(8);
  const nick = b.dataset.pf, mine = nick === rankSt?.nick;
  $("pfm").classList.remove("hidden");
  $("pfm-body").innerHTML = '<div class="empty">Carregando…</div>';
  let p;
  try { p = await send("rank.profile", { nick }, true, 20000); } catch (err) { $("pfm-body").innerHTML = `<div class="warn">${esc(err.message)}</div>`; return; }
  const follows = (rankData.friends?.rows || []).some((r) => r.nick === p.nick);
  const conq = state.conq?.conq || [], pf = p.pf || {};
  const show = p.show.map((id) => conq.find((c) => c.id === id)).filter(Boolean);
  // a cor livre/animada do outro vale só dentro do cartão dele
  $("pfm-body").innerHTML = `<div id="pf-other">${profileCard({ nick: p.nick, level: p.level, prestige: p.prestige, title: rewardName(p.title) || "Novato", frame: p.frame,
      avatar: pf.av, effect: pf.fx, bg: pf.bg, bio: pf.bio, lay: pf.lay || ["stats", "show"], sub: p.streak ? `🔥 ${p.streak} dia${p.streak > 1 ? "s" : ""}` : "",
      stats: [[p.level, "nível"], [p.week_xp, "XP na semana"], [p.best_streak ?? p.streak, "recorde"], [p.unlocked, "troféus"]],
      show: show.length ? `<div class="shrow">${show.map((c) => `<div class="cqt got">${trophy(c.tier, true)}<span>${esc(c.name)}</span></div>`).join("")}</div>` : '<div class="empty">Nada na vitrine.</div>',
      league: leagueTag(p.league) })}</div>
    ${mine ? "" : `<div class="brow pfbtns">${follows ? '<button class="btn" id="pf-unf">Deixar de seguir</button><button class="btn" id="pf-duel">Desafiar para duelo</button>'
      : '<button class="btn" id="pf-fol">Seguir</button>'}</div>`}`;
  accentApply($("pf-other"), pf.acc, pf.col);
  const close = () => $("pfm").classList.add("hidden");
  if ($("pf-fol")) $("pf-fol").onclick = async () => { buzz(8); if (await rankDo("rank.friend.add", { nick: p.nick }, "friends", `Seguindo ${p.nick}`)) close(); };
  if ($("pf-unf")) $("pf-unf").onclick = async () => { buzz(8); if (await rankDo("rank.friend.del", { nick: p.nick }, "friends", `Deixou de seguir ${p.nick}`)) close(); };
  if ($("pf-duel")) $("pf-duel").onclick = async () => {
    buzz(8);
    if (await rankDo("rank.duel.new", { nick: p.nick }, "duels", `Duelo enviado para ${p.nick}`)) { close(); rankTab = "duels"; renderRank(); }
  };
});
$("pfm-x").onclick = () => $("pfm").classList.add("hidden");
$("pfm").onclick = (e) => { if (e.target === $("pfm")) $("pfm").classList.add("hidden"); };
