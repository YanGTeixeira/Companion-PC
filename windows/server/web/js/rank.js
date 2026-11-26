"use strict";
// ---------------------------------------------------------------- Ranking público (aba Conquistas)
// O PC envia só apelido, XP, sequência e quantos troféus (ranking.py) e busca o ranking no servidor (cloud/ranking).
let rankSt = null, rankKind = "week", rankData = {}, rankEditing = false;
const RANK_KINDS = [["week", "Semana"], ["level", "Nível"], ["streak", "Sequência"]];
async function loadRank(force) {
  try { rankSt = await send("rank.state"); } catch { return; }
  renderRank();
  if (rankSt.joined && (force || !rankData[rankKind])) loadBoard();
}
function onRank(d) { rankSt = d; rankData = {}; if (vis("conq")) loadRank(true); }
async function loadBoard() {
  const kind = rankKind;
  try { rankData[kind] = await send("rank.board", { kind }, true, 20000); }
  catch (e) { rankData[kind] = { error: e.message }; }
  if (kind === rankKind) renderRank();
}
const rankVal = (kind, r) => (kind === "week" ? `${r.value} XP` : kind === "level" ? `nível ${r.level}` : `${r.value} dia${r.value === 1 ? "" : "s"}`);
function renderRank() {
  const box = $("rk-body"); if (!box || !rankSt) return;
  $("rk-me").textContent = "";
  if (!rankSt.available) { box.innerHTML = '<div class="empty">O ranking online ainda não está no ar.</div>'; return; }
  if (!rankSt.joined) {
    box.innerHTML = `<div class="sub" style="white-space:normal;margin-bottom:10px">Compare o seu XP com o de outras pessoas. Do seu PC sai só:
      <b>apelido, nível, XP, sequência e quantos troféus</b>. Nada de apps, sites ou tempo de tela. Dá para sair e apagar tudo quando quiser.</div>
      <div class="brow rkjoin"><input class="fi" id="rk-nick" maxlength="20" placeholder="Seu apelido (3 a 20 letras)" autocomplete="off"><button class="btn" id="rk-join">Entrar</button></div>`;
    $("rk-join").onclick = async () => {
      const nick = $("rk-nick").value.trim(); if (nick.length < 3) return toast("O apelido precisa de pelo menos 3 letras", "bad");
      buzz(8); $("rk-join").disabled = true;
      try { rankSt = await send("rank.join", { nick }, true, 20000); rankData = {}; toast(`No ranking como ${rankSt.nick}`, "ok"); loadRank(true); }
      catch (e) { toast(e.message, "bad"); $("rk-join").disabled = false; }
    };
    return;
  }
  const d = rankData[rankKind], me = d?.me, myRank = me?.ranks?.[rankKind];
  $("rk-me").textContent = myRank ? `você: #${myRank}` : "";
  const tabs = `<div class="chips rkchips">${RANK_KINDS.map(([k, l]) => `<button class="chip2${k === rankKind ? " on" : ""}" data-rk="${k}">${l}</button>`).join("")}</div>`;
  let list;
  if (!d) list = '<div class="empty">Carregando…</div>';
  else if (d.error) list = `<div class="warn">${esc(d.error)}</div>`;
  else if (!d.rows.length) list = '<div class="empty">Ninguém pontuou ainda. Seja o primeiro!</div>';
  else {
    const medal = ["ouro", "prata", "bronze"];
    list = `<ol class="rklist">${d.rows.map((r) => `<li class="${r.nick === rankSt.nick ? "me" : ""}"><span class="rkpos">${r.rank <= 3 ? trophy(medal[r.rank - 1], true) : "#" + r.rank}</span>
      <span class="rknick">${esc(r.nick)}</span><small>nível ${r.level} · ${r.unlocked} troféu${r.unlocked === 1 ? "" : "s"}</small><b>${rankVal(rankKind, r)}</b></li>`).join("")}</ol>`;
    if (myRank && myRank > d.rows.length) {
      const val = rankKind === "week" ? `${me.week_xp} XP` : rankKind === "level" ? `nível ${me.level}` : `${me.streak} dias`;
      list += `<div class="rkyou">… você: <b>#${myRank}</b> · ${esc(val)}</div>`;
    } else if (!myRank && me) list += `<div class="rkyou">Você ainda não pontuou ${rankKind === "week" ? "nesta semana" : "aqui"}.</div>`;
  }
  const foot = rankEditing
    ? `<div class="brow rkjoin"><input class="fi" id="rk-nick" maxlength="20" value="${esc(rankSt.nick)}"><button class="btn" id="rk-save">Salvar</button></div>`
    : `<div class="rkfoot"><span>${d?.players ? `${d.players} jogador${d.players > 1 ? "es" : ""} · ` : ""}você: ${esc(rankSt.nick)}${me?.hidden ? " (fora do ranking)" : ""}</span>
       <span><button class="btn sm" id="rk-edit">Apelido</button><button class="btn sm danger" id="rk-leave">Sair</button></span></div>`;
  box.innerHTML = tabs + list + (rankSt.error ? `<div class="warn">${esc(rankSt.error)}</div>` : "") + foot;
  if (rankKind === "week" && d?.week) box.querySelector(".rkchips").insertAdjacentHTML("beforeend", `<small class="rkweek">zera na segunda</small>`);
  box.querySelector(".rkchips").onclick = (e) => {
    const b = e.target.closest("[data-rk]"); if (!b) return;
    buzz(8); rankKind = b.dataset.rk; renderRank(); if (!rankData[rankKind]) loadBoard();
  };
  if (rankEditing) {
    $("rk-save").onclick = async () => {
      try { rankSt = await send("rank.nick", { nick: $("rk-nick").value.trim() }, true, 20000); rankEditing = false; rankData = {}; toast("Apelido trocado", "ok"); loadRank(true); }
      catch (e) { toast(e.message, "bad"); }
    };
  } else {
    $("rk-edit").onclick = () => { rankEditing = true; renderRank(); $("rk-nick").focus(); };
    $("rk-leave").onclick = async () => {
      if (!confirm("Sair do ranking? A sua conta e os seus números são apagados do servidor.")) return;
      try { rankSt = await send("rank.leave", {}, true, 20000); rankData = {}; toast("Você saiu do ranking", "ok"); renderRank(); }
      catch (e) { toast(e.message, "bad"); }
    };
  }
}
