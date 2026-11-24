"use strict";
// ---------------------------------------------------------------- Reunião automática
let meetSoon = null;
function onMeetSoon(e) {
  if (PREVIEW) return;
  meetSoon = e;
  $("ms-title").textContent = e.link ? "Reunião em 1 min" : "Compromisso em 1 min";
  $("ms-sub").textContent = [e.title, e.profile ? `perfil de áudio: ${e.profile}` : "", e.opened ? "aberta no PC" : ""].filter(Boolean).join(" · ");
  $("ms-join").classList.toggle("hidden", !!e.opened || !e.link);
  $("meetsoon").classList.remove("hidden");
  alarm(`${e.link ? "Reunião" : "Compromisso"} em 1 min: ${e.title}`);
  setTimeout(() => $("meetsoon").classList.add("hidden"), 3 * 60000);
}
$("ms-close").onclick = () => $("meetsoon").classList.add("hidden");
$("ms-join").onclick = () => { $("meetsoon").classList.add("hidden"); if (meetSoon?.link) act("daily.open", { link: meetSoon.link }, "Abrindo a reunião no PC"); };

// ---------------------------------------------------------------- Seu dia
let dayT = 0;
async function loadDay(force) {
  if (!ws || ws.readyState !== 1 || (!force && Date.now() - dayT < 60000)) return;
  dayT = Date.now();
  let r; try { r = await send("day.summary"); } catch { return; }
  state.day = r; renderDay();
}
function renderDay() {
  const r = state.day; if (!r) return;
  const m = r.matches, mt = r.meetings;
  const box = (v, l) => `<div><b>${v}</b><small>${l}</small></div>`;
  const vsAvg = r.prev_avg ? ` (${r.screen > r.prev_avg ? "+" : "-"}${humanDur(Math.abs(r.screen - r.prev_avg))} da média)` : "";
  $("day-when").textContent = new Date().toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" });
  $("day-body").innerHTML = `<div class="dayg">
    ${box(humanDur(r.screen || 0), "tela" + vsAvg)}
    ${box(humanDur((r.focus_min || 0) * 60), "foco")}
    ${box(humanDur(r.game_s || 0), r.games?.[0] ? "jogando · " + esc(r.games[0].name) : "jogando")}
    ${box(m.n ? `${m.w}V ${m.l}D` : "-", m.n ? `${m.n} partida${m.n > 1 ? "s" : ""}` : "nenhuma partida")}
    ${box(mt.n ? humanDur(mt.min * 60) : "-", mt.n ? `${mt.n} reuni${mt.n > 1 ? "ões" : "ão"}` : "sem reuniões")}
    ${box(r.apps?.[0] ? esc(r.apps[0].name) : "-", "app mais usado")}</div>`;
  const h = new Date().getHours();
  $("dk-day").textContent = h >= 21 || h < 4 ? `Hoje: tela ${humanDur(r.screen || 0)} · foco ${humanDur((r.focus_min || 0) * 60)} · jogo ${humanDur(r.game_s || 0)}${m.n ? ` · ${m.w}V ${m.l}D` : ""}` : "";
}
setInterval(() => { if (vis("today") || (new Date().getHours() >= 21 && !$("dock").classList.contains("hidden"))) loadDay(); }, 30000);

