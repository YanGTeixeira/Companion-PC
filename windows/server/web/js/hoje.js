"use strict";
// ---------------------------------------------------------------- Hoje: clima, agenda e foco
const hm = (iso) => iso.slice(11, 16);
const evDate = (iso) => new Date(iso.length === 16 ? iso + ":00" : iso);
function upcoming() {
  const now = Date.now();
  return (state.daily?.events || []).filter((e) => !e.all_day && evDate(e.end) > now);
}
function renderToday() {
  const d = state.daily || {}, w = d.weather;
  // card Sistema e modo base
  $("sys-wx").classList.toggle("hidden", !w);
  if (w) $("sys-wx-v").textContent = `${w.temp}° ${w.desc} · ${w.max}°/${w.min}°${w.rain ? ` · chuva às ${w.rain.at}` : ""}`;
  const next = upcoming()[0];
  $("sys-ag").classList.toggle("hidden", !next);
  if (next) $("sys-ag-v").textContent = `${hm(next.start)} ${next.title}`;
  // aba Hoje
  const wx = $("td-weather");
  if (!d.city) wx.innerHTML = `<h3><span>Clima</span></h3><div class="sub" style="white-space:normal">Escolha a cidade no editor do PC (ícone da bandeja &gt; Personalizar &gt; Hoje).</div>`;
  else if (!w) wx.innerHTML = `<h3><span>Clima</span><span>${esc(d.city)}</span></h3><div class="sub" style="white-space:normal">${d.err?.weather ? "Erro: " + esc(d.err.weather) : "Carregando…"}</div>`;
  else wx.innerHTML = `<h3><span>Clima</span><span>${esc(w.city)}${w.region ? ", " + esc(w.region) : ""}</span></h3>
    <div class="wxnow"><b>${w.temp}°</b><span>${esc(w.desc)} · sensação ${w.feels}°</span></div>
    <div class="row"><span>Hoje</span><span>máx ${w.max}° · mín ${w.min}° · chuva ${w.rain_pct ?? 0}%</span></div>
    ${w.rain ? `<div class="row"><span>Chuva</span><span>${w.rain.pct}% às ${w.rain.at}</span></div>` : ""}
    <div class="wxh">${(w.hours || []).map((h) => `<div><b>${h.t}°</b>${h.h}h${h.p >= 30 ? `<br>${h.p}%` : ""}</div>`).join("")}</div>
    ${w.tomorrow ? `<div class="row"><span>Amanhã</span><span>${esc(w.tomorrow.desc)} · ${w.tomorrow.max}°/${w.tomorrow.min}° · chuva ${w.tomorrow.rain_pct ?? 0}%</span></div>` : ""}`;
  const ag = $("td-agenda");
  if (!d.has_ics) ag.innerHTML = `<h3><span>Agenda</span></h3><div class="sub" style="white-space:normal">Cole o endereço secreto iCal do Google Agenda no editor do PC (Personalizar &gt; Hoje).</div>`;
  else {
    const now = Date.now(), today = new Date().toISOString().slice(0, 10), evs = d.events || [];
    const dayStr = (e) => { const x = evDate(e.start); return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`; };
    const localToday = (() => { const x = new Date(); return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`; })();
    const row = (e) => {
      const st = evDate(e.start), en = evDate(e.end), on = st <= now && en > now, soon = !on && st - now < 15 * 60000 && st > now;
      const rel = e.all_day ? "o dia todo" : on ? "agora" : st > now ? (st - now < 3600000 ? `em ${Math.round((st - now) / 60000)} min` : "") : "";
      return `<div class="agev${on || soon ? " now" : ""}${!e.all_day && en <= now ? " past" : ""}"><span class="at">${e.all_day ? "dia" : hm(e.start)}</span>
        <span class="ti">${esc(e.title)}<small>${[rel, e.all_day ? "" : `até ${hm(e.end)}`, e.where ? esc(e.where) : ""].filter(Boolean).join(" · ")}</small></span>
        ${e.link && !e.all_day && en > now ? `<button class="btn sm${on || soon ? " primary" : ""}" data-join="${esc(e.link)}">Entrar</button>` : "<span></span>"}</div>`;
    };
    const tday = evs.filter((e) => dayStr(e) === localToday), tom = evs.filter((e) => dayStr(e) > localToday);
    ag.innerHTML = `<h3><span>Agenda</span><span>${d.err?.calendar ? "erro ao atualizar" : tday.filter((e) => !e.all_day).length + " hoje"}</span></h3>
      ${d.busy_only ? '<div class="sub" style="white-space:normal">A agenda chega só como livre/ocupado (sem títulos nem links do Meet). No editor do PC, troque pelo endereço secreto iCal.</div>' : ""}
      ${tday.length ? tday.map(row).join("") : '<div class="empty">Nada hoje</div>'}
      ${tom.length ? `<div class="agday">Amanhã</div>${tom.slice(0, 5).map(row).join("")}` : ""}`;
  }
  renderDockDaily();
}
function renderDockDaily() {
  const w = state.daily?.weather, next = upcoming()[0], now = Date.now();
  $("dk-wx").textContent = w ? `${w.temp}° ${w.desc} · ${w.max}°/${w.min}°${w.rain ? ` · chuva ${w.rain.pct}% às ${w.rain.at}` : ""}` : "";
  if (next) {
    const st = evDate(next.start), on = st <= now, mins = Math.round((st - now) / 60000);
    $("dk-ag").textContent = `${hm(next.start)} ${next.title}${on ? " · agora" : mins < 120 ? ` · em ${mins} min` : ""}`;
    const join = !!next.link && (on || mins <= 15);
    $("dk-join").classList.toggle("hidden", !join); $("dk-join").dataset.join = next.link || "";
  } else { $("dk-ag").textContent = ""; $("dk-join").classList.add("hidden"); }
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-join]"); if (!b || !b.dataset.join) return;
  e.stopPropagation(); act("daily.open", { link: b.dataset.join }, "Abrindo a reunião no PC");
}, true);
// lembrete 5 min antes de cada compromisso com horário (o de 1 min vem do PC)
const remindDone = new Set();
setInterval(() => {
  if (PREVIEW) return;
  const now = Date.now();
  for (const e of upcoming()) {
    const st = evDate(e.start), key = e.start + e.title;
    if (!e.all_day && st - now <= 5 * 60000 && st - now > 90000 && !remindDone.has(key)) { remindDone.add(key); alarm(`${e.link ? "Reunião" : "Compromisso"} em ${Math.max(1, Math.round((st - now) / 60000))} min: ${e.title}`); }
  }
  if (vis("today") && state.daily) renderToday();
}, 20000);
// foco
let focusEnd = null;
function onFocus(f) {
  state.focus = f;
  focusEnd = f?.on ? Date.now() + f.left * 1000 : null;
  if (f?.done) { alarm("Foco concluído"); }
  renderFocus();
}
function renderFocus() {
  const f = state.focus, on = !!(f && f.on && focusEnd);
  const left = on ? Math.max(0, (focusEnd - Date.now()) / 1000) : 0;
  $("fo-on").classList.toggle("hidden", !on); $("fo-off").classList.toggle("hidden", on);
  if (on) $("fo-left").textContent = fmtTime(left);
  $("fo-today").textContent = f?.today ? `hoje: ${humanDur(f.today * 60)}` : "";
  for (const id of ["fo-chip", "fo-chip2"]) { const c = $(id); c.classList.toggle("hidden", !on); c.classList.toggle("on", on); c.textContent = id === "fo-chip" ? "FOCO " + fmtTime(left) : "FOCO"; }
}
setInterval(() => { if (focusEnd) renderFocus(); }, 1000);
document.querySelectorAll("[data-fmin]").forEach((b) => (b.onclick = () => act("focus.start", { minutes: +b.dataset.fmin }, `Foco: ${b.dataset.fmin} min`)));
$("fo-stop").onclick = () => act("focus.stop", {}, "Foco parado");
$("fo-chip").onclick = $("fo-chip2").onclick = () => { buzz(8); showView("today"); };
// perfis de áudio
function renderProfiles(list) {
  $("ap-list").innerHTML = list?.length ? list.map((p) => `<div class="approw"><button class="btn" data-ap="${esc(p.name)}">${esc(p.name)} <small>${esc(p.out_name || "")}${p.level != null ? " · " + Math.round(p.level) + "%" : ""}${p.mic_muted ? " · mic mudo" : ""}</small></button><button class="btn sm" data-apdel="${esc(p.name)}" aria-label="apagar">x</button></div>`).join("")
    : '<div class="empty">Deixe o som do jeito que quer (saída, volume, apps, microfone) e toque em Salvar o atual.</div>';
}
function loadProfiles() { send("audio.profiles").then(renderProfiles).catch(() => {}); }
$("ap-save").onclick = async () => {
  const name = prompt("Nome do perfil (ex.: Fone + Discord):"); if (!name) return;
  const r = await act("audio.profile_save", { name }, "Perfil salvo"); if (r) renderProfiles(r);
};
$("ap-list").addEventListener("click", async (e) => {
  const a = e.target.closest("[data-ap]"), del = e.target.closest("[data-apdel]");
  if (del) { if (!confirm(`Apagar o perfil ${del.dataset.apdel}?`)) return; const r = await act("audio.profile_del", { name: del.dataset.apdel }); if (r) renderProfiles(r); return; }
  if (a) { const r = await act("audio.profile_apply", { name: a.dataset.ap }, `Perfil: ${a.dataset.ap}`); if (r?.warn?.length) toast(r.warn.join(" · "), "warn"); pollMixer?.(); }
});

