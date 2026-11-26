"use strict";
// ---------------------------------------------------------------- Retrospectiva do mês (stories + cartão para compartilhar)
// Os números vêm do PC (retro.py). Toque à direita avança, à esquerda volta; o último slide gera a imagem.
let retroData = null, retroI = 0, retroSlides = [];
const rpct = (a, b) => (b ? Math.round(((a - b) / b) * 100) : null);
const rday = (d) => new Date(d + "T12:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
const GAME_NAME = { dota2: "Dota 2", cs2: "CS2" };
const rcap = (s) => s.charAt(0).toUpperCase() + s.slice(1);   // "novembro de 2026" -> "Novembro de 2026"
const rdur = (s) => (s ? humanDur(s) : "-");

async function openRetro(month) {
  $("retro").classList.remove("hidden"); $("retro-body").innerHTML = '<div class="rslide on"><div class="empty">Montando o seu mês…</div></div>';
  try { retroData = await send("retro.get", month ? { month } : {}, true, 30000); }
  catch (e) { $("retro").classList.add("hidden"); return toast(e.message, "bad"); }
  retroSlides = retroBuild(retroData); retroI = 0; retroShow();
}
function closeRetro() { $("retro").classList.add("hidden"); }

function retroBuild(r) {
  const s = [], sc = r.screen, g = r.games, f = r.focus;
  const big = (v, small = "") => `<div class="rbig">${v}</div>${small ? `<div class="rsub">${small}</div>` : ""}`;
  s.push(`<div class="rk">SUA RETROSPECTIVA</div><div class="rtitle">${esc(rcap(r.label))}</div>
    <div class="rsub">${r.days_used} dia${r.days_used === 1 ? "" : "s"} com o PC ligado${r.partial ? " (o mês ainda não acabou)" : ""}</div>
    <div class="rhint">toque para continuar ›</div>`);
  if (!sc.total) { s.push(`<div class="rk">HMM…</div>${big("Quase nada", "o PC quase não foi usado neste mês")}`); return s; }
  const cmp = rpct(sc.total, sc.prev_total);
  const peak = Math.max(...sc.hours, 1);
  s.push(`<div class="rk">TEMPO DE TELA</div>${big(humanDur(sc.total), `média de ${humanDur(sc.avg)} por dia`)}
    ${cmp !== null ? `<div class="rpill">${cmp >= 0 ? "+" : ""}${cmp}% que o mês passado${r.partial ? " (até o mesmo dia)" : ""}</div>` : ""}
    <div class="rhours">${sc.hours.map((h, i) => `<i style="height:${Math.max(2, (h / peak) * 100)}%" class="${i === sc.peak_hour ? "pk" : ""}"></i>`).join("")}</div>
    <div class="rsub">seu horário: <b>${sc.peak_hour}h</b> · dia favorito: <b>${esc(sc.weekday)}</b></div>
    ${sc.best_day ? `<div class="rsub">dia mais longo: <b>${rday(sc.best_day.day)}</b> (${humanDur(sc.best_day.secs)})</div>` : ""}`);
  if (r.apps.length) s.push(`<div class="rk">ONDE O TEMPO FOI</div>
    <div class="rlist">${r.cats.slice(0, 5).map((c) => `<div><span>${esc(c.cat)}</span><b>${c.pct}%</b><i style="width:${c.pct}%"></i></div>`).join("")}</div>
    <div class="rk2">APPS MAIS USADOS</div>
    <ol class="rapps">${r.apps.map((a) => `<li><span>${esc(a.name)}</span><small>${humanDur(a.secs)}</small></li>`).join("")}</ol>`);
  if (f.min || f.metas_done) s.push(`<div class="rk">FOCO</div>${big(humanDur(f.min * 60), "de foco no mês")}
    ${f.best_day ? `<div class="rsub">melhor dia: <b>${rday(f.best_day.day)}</b> (${humanDur(f.best_day.min * 60)})</div>` : ""}
    <div class="rgrid"><div><b>${f.metas_done}</b><small>de ${f.metas_total} metas</small></div><div><b>${f.perfect}</b><small>dias perfeitos</small></div>
    <div><b>${f.best_streak}</b><small>dias seguidos</small></div></div>`);
  if (g.secs || g.matches) {
    const favs = Object.entries(g.fav).map(([k, v]) => `<div class="rsub">${GAME_NAME[k]}: <b>${esc(v.title)}</b> · ${v.n} partida${v.n > 1 ? "s" : ""}, ${v.w} vitória${v.w === 1 ? "" : "s"}</div>`).join("");
    s.push(`<div class="rk">JOGOS</div>${big(humanDur(g.secs), g.top[0] ? `jogando · mais jogado: ${esc(g.top[0].name)}` : "jogando")}
      ${g.matches ? `<div class="rgrid"><div><b>${g.matches}</b><small>partidas</small></div><div><b>${g.wins}V ${g.losses}D</b><small>placar</small></div>
        <div><b>${g.winrate ?? "-"}${g.winrate != null ? "%" : ""}</b><small>de vitórias</small></div></div>` : ""}
      ${favs}
      ${g.best ? `<div class="rpill">melhor partida: ${esc(g.best.title)} · ${g.best.k}/${g.best.d}/${g.best.a} (KDA ${g.best.kda}) em ${rday(g.best.day)}</div>` : ""}`);
  }
  if (r.talk.total >= 60) s.push(`<div class="rk">SUA VOZ</div>${big(humanDur(r.talk.total), "falando no microfone")}
    <div class="rsub">${[r.talk.meet >= 60 ? `${humanDur(r.talk.meet)} em reuniões` : "", r.talk.game >= 60 ? `${humanDur(r.talk.game)} em jogo` : ""].filter(Boolean).join(" · ")}</div>`);
  s.push(`<div class="rk">EVOLUÇÃO</div>${big("+" + r.xp.month + " XP")}
    <div class="rsub">${r.xp.level_end > r.xp.level_start ? `do nível <b>${r.xp.level_start}</b> para o <b>${r.xp.level_end}</b>` : `nível <b>${r.xp.level_end}</b>`}</div>
    ${r.conq.length ? `<div class="rk2">${r.conq.length} CONQUISTA${r.conq.length > 1 ? "S" : ""}</div><div class="rconq">${r.conq.map((c) => `<span class="${c.tier}">${esc(c.name)}</span>`).join("")}</div>` : ""}`);
  s.push(`<div class="rk">NESTE MÊS VOCÊ FOI</div><div class="rtitle rpersona">${esc(r.persona.name)}</div><div class="rsub">${esc(r.persona.why)}</div>`);
  s.push(`<div class="rk">PARA GUARDAR</div><img id="retro-img" class="rimg" alt="Cartão da retrospectiva">
    <div class="brow"><button class="btn" id="retro-share">Compartilhar</button><button class="btn" id="retro-close2">Fechar</button></div>`);
  return s;
}

function retroShow() {
  const n = retroSlides.length;
  $("retro-prog").innerHTML = retroSlides.map((_, i) => `<i class="${i < retroI ? "seen" : i === retroI ? "on" : ""}"></i>`).join("");
  $("retro-body").innerHTML = `<div class="rslide on">${retroSlides[retroI]}</div>`;
  retroFit();
  if (retroI === n - 1 && $("retro-img")) {
    retroCard(retroData).then((blob) => {
      if (!blob || !$("retro-img")) return;
      $("retro-img").src = URL.createObjectURL(blob);
      $("retro-share").onclick = (e) => { e.stopPropagation(); retroShare(blob); };
    });
    $("retro-close2").onclick = (e) => { e.stopPropagation(); closeRetro(); };
  }
}
// números e títulos grandes: diminui a fonte até a palavra mais longa caber (fontes largas, como a do Synthwave)
function retroFit() {
  document.querySelectorAll("#retro-body .rbig, #retro-body .rtitle").forEach((el) => {
    el.style.fontSize = "";
    let size = parseFloat(getComputedStyle(el).fontSize);
    while (el.scrollWidth > el.clientWidth + 1 && size > 20) { size -= 2; el.style.fontSize = size + "px"; }
  });
}
document.fonts?.ready.then(() => { if (!$("retro").classList.contains("hidden")) retroFit(); });
$("retro-body").onclick = (e) => {
  if (e.target.closest("button, img")) return;
  const left = e.clientX < innerWidth / 3;
  if (left) { if (retroI > 0) { retroI--; retroShow(); } }
  else if (retroI < retroSlides.length - 1) { retroI++; buzz(6); retroShow(); }
};
$("retro-x").onclick = closeRetro;
document.addEventListener("keydown", (e) => {
  if ($("retro").classList.contains("hidden")) return;
  if (e.key === "Escape") closeRetro();
  if (e.key === "ArrowRight" && retroI < retroSlides.length - 1) { retroI++; retroShow(); }
  if (e.key === "ArrowLeft" && retroI > 0) { retroI--; retroShow(); }
});

// cartão 1080x1350 com as cores do tema atual
async function retroCard(r) {
  try { await document.fonts.ready; } catch {}
  const cs = getComputedStyle(document.documentElement), v = (k, d) => cs.getPropertyValue(k).trim() || d;
  const P = v("--p", "#5cff8a"), P2 = v("--p2", "#33cf68"), P3 = v("--p3", "#1c7a3d"), BG = v("--bg", "#040d07"), FONT = v("--display", "monospace");
  const c = document.createElement("canvas"); c.width = 1080; c.height = 1350;
  const x = c.getContext("2d");
  x.fillStyle = BG; x.fillRect(0, 0, c.width, c.height);
  x.strokeStyle = P3; x.lineWidth = 4; x.strokeRect(40, 40, 1000, 1270);
  const txt = (t, y, size, color = P, align = "left", xx = 90) => { x.font = `${size}px ${FONT}`; x.fillStyle = color; x.textAlign = align; x.fillText(t, align === "center" ? 540 : xx, y); };
  txt("MINHA RETROSPECTIVA", 140, 44, P2);
  txt(r.label.toUpperCase(), 215, 72);
  txt("NESTE MÊS EU FUI", 330, 40, P2);
  txt(r.persona.name.toUpperCase(), 420, 92);
  const rows = [["Tela", rdur(r.screen.total)], ["Foco", rdur(r.focus.min * 60)],
    ["Metas cumpridas", `${r.focus.metas_done}`], r.games.matches ? ["Partidas", `${r.games.matches} (${r.games.wins}V ${r.games.losses}D)`] : ["Jogando", rdur(r.games.secs)],
    ["App mais usado", r.apps[0]?.name || "-"], ["Nível", `${r.xp.level_end} (+${r.xp.month} XP)`], ["Conquistas", `${r.conq.length}`]];
  let y = 540;
  for (const [k, val] of rows) {
    txt(k, y, 44, P2); x.font = `52px ${FONT}`; x.fillStyle = P; x.textAlign = "right";
    let t = String(val); while (x.measureText(t).width > 560 && t.length > 4) t = t.slice(0, -2) + "…";
    x.fillText(t, 990, y);
    x.strokeStyle = P3; x.lineWidth = 2; x.beginPath(); x.moveTo(90, y + 26); x.lineTo(990, y + 26); x.stroke();
    y += 100;
  }
  txt("Companion PC", 1270, 36, P3, "center");
  return new Promise((res) => c.toBlob(res, "image/png"));
}
async function retroShare(blob) {
  const file = new File([blob], `retrospectiva-${retroData.month}.png`, { type: "image/png" });
  try {
    if (navigator.canShare?.({ files: [file] })) return await navigator.share({ files: [file], title: "Minha retrospectiva" });
  } catch (e) { if (e.name === "AbortError") return; }
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = file.name; a.click();
  toast("Imagem salva", "ok");
}

// cartão na aba Conquistas: escolher o mês e abrir
async function renderRetroCard() {
  const sel = $("retro-month"); if (!sel || sel.dataset.done) return;
  const now = new Date(), cur = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  let months = [cur];
  try { months = (await send("retro.get", { month: cur }, true, 30000)).months || months; } catch {}
  if (!months.includes(cur)) months.unshift(cur);
  sel.innerHTML = months.map((m) => {
    const [y, mo] = m.split("-"); const l = new Date(+y, +mo - 1, 1).toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
    return `<option value="${m}">${esc(l)}${m === cur ? " (até agora)" : ""}</option>`;
  }).join("");
  // nos primeiros dias do mês, o padrão é o mês que acabou
  if (now.getDate() <= 7 && months[1]) sel.value = months[1];
  sel.dataset.done = 1;
}
$("retro-open").onclick = () => { buzz(8); openRetro($("retro-month").value); };
function onRetroEvent(m) {
  if (PREVIEW) return;
  notify("Sua retrospectiva está pronta", `O mês ${m.label} em números: veja em Status › Conquistas`, "retro");
  $("retro-month").dataset.done = ""; $("td-retro")?.classList.add("new");
}
