"use strict";
// ---------------------------------------------------------------- Sons no microfone (botões "Tocar som" do deck)
// O celular converte o áudio (qualquer formato que o navegador abre) em WAV mono 48 kHz, corta o silêncio
// e iguala o volume; o PC toca no cabo virtual (VB-CABLE) junto com o microfone, e o Discord ouve o cabo.
let sbState = null, sbSel = null, sbBusy = false;
async function sbLoad() { try { onSb(await send("snd.state")); } catch {} }
function onSb(d) { if (d) { sbState = d; sbMark(); sbChip(); if (!$("sbx").classList.contains("hidden")) sbLive(); } }
// chip no topo: NO AR (acende quando você fala) / MUDO (pisca). Toque = muta/desmuta só a sua voz no cabo.
function sbChip() {
  const d = sbState, on = !!(d && d.status === "on" && d.mic);
  for (const id of ["sb-chip", "sb-chip2"]) {
    const c = $(id); c.classList.toggle("hidden", !on); if (!on) continue;
    c.classList.toggle("on", !d.muted && d.talk); c.classList.toggle("muted", d.muted);
    c.textContent = d.muted ? "MUDO" : id === "sb-chip" ? (d.fx ? (d.fxs?.[d.fx] || "FX").toUpperCase() : "NO AR") : "AR";
  }
}
$("sb-chip").onclick = $("sb-chip2").onclick = () => { buzz(8); send("snd.set", { muted: "toggle" }).then(onSb).catch((e) => toast(e.message, "bad")); };
// partes da tela "Som" que mudam sozinhas (falando, mudo, efeito) sem refazer a lista de microfones
function sbLive() {
  const d = sbState; if (!d) return;
  $("sbx-mute").classList.toggle("on", d.muted);
  $("sbx-talk").textContent = d.muted ? "· no mudo" : d.talk ? "· falando" : "";
  $("sbx-fx").innerHTML = [["", "Nenhum"], ...Object.entries(d.fxs || {})]
    .map(([k, l]) => `<button class="chip2${(d.fx || "") === k ? " on" : ""}" data-fx="${k}">${esc(l)}</button>`).join("");
}
function onTalkWarn(m) {
  if (PREVIEW) return;
  notify("Você está no mudo", m.why === "meet" ? "Falando com o microfone do Meet desligado" : "Falando com o seu mic mutado na mesa de som", "talkwarn");
}
function sbMark() {
  const playing = new Set(sbState?.playing || []);
  document.querySelectorAll("#deck-grid .dbtn.sb").forEach((el) => el.classList.toggle("playing", playing.has(el.dataset.snd)));
  $("deck-stop").classList.toggle("hidden", !playing.size);
  $("deck-snd").classList.toggle("hidden", !welcome.features?.sounds);
}
$("deck-stop").onclick = () => { buzz(8); send("snd.stop").catch(() => {}); };

// ---------------------------------------------------------------- editar o botão
function sbEdit(b) {
  sbSel = b.type === "sound" ? { id: b.value, name: b.label } : null;
  $("bed-snd-vol").value = b.type === "sound" ? (b.vol ?? 100) : 100;
  $("bed-snd-vv").textContent = $("bed-snd-vol").value + "%";
  $("bed-snd-info").textContent = sbSel ? "áudio atual" : "nenhum";
  if (sbSel) send("snd.info", { id: sbSel.id }).then((r) => { if (sbSel?.id === r.id) $("bed-snd-info").textContent = `áudio atual · ${r.dur.toFixed(1)} s`; })
    .catch(() => { $("bed-snd-info").textContent = "áudio sumiu do PC: escolha de novo"; });
}
$("bed-snd-vol").oninput = () => { $("bed-snd-vv").textContent = $("bed-snd-vol").value + "%"; };
$("bed-snd-pick").onclick = () => $("bed-snd-file").click();
$("bed-snd-test").onclick = () => {
  if (!sbSel) return toast("Escolha um arquivo primeiro", "bad");
  buzz(8); send("snd.play", { id: sbSel.id, vol: +$("bed-snd-vol").value }).catch((e) => toast(e.message, "bad"));
};
// escolhe o trecho no cortador e manda para o PC (arquivo novo, ou o áudio atual para cortar mais)
async function sbPut(getX, name, whole) {
  const info = $("bed-snd-info"); sbBusy = true; info.textContent = "abrindo…";
  try {
    const cut = await sbTrim(await getX(), name, whole);
    if (!cut) { info.textContent = sbSel ? "áudio atual" : "nenhum"; return; }
    info.textContent = `enviando ${fmtBytes(cut.wav.byteLength)}…`;
    const r = await send("snd.add", { data: sbB64(cut.wav) }, true, 90000);
    sbSel = { id: r.id, name: sbSel?.name || name };
    if (!$("bed-label").value.trim()) $("bed-label").value = name;
    info.textContent = `${name} · ${cut.secs.toFixed(1)} s`; buzz(25);
  } catch (err) {
    info.textContent = "falhou"; toast(err.name === "EncodingError" ? "Não consegui abrir esse áudio" : err.message, "bad");
  } finally { sbBusy = false; }
}
$("bed-snd-file").onchange = (e) => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  sbPut(() => sbDecode(f), sbName(f));
};
$("bed-snd-cut").onclick = () => {
  if (!sbSel) return toast("Escolha um arquivo primeiro", "bad");
  const id = sbSel.id;
  sbPut(async () => sbDecode(sbUnB64((await send("snd.get", { id }, true, 30000)).data)), $("bed-label").value.trim() || sbSel.name, true);
};
// ---------------------------------------------------------------- ajustes (botão "Som")
$("deck-snd").onclick = async () => {
  buzz(8); $("sbx").classList.remove("hidden"); sbRender();
  try {
    const [st, mics] = await Promise.all([send("snd.state"), send("snd.mics")]);
    sbState = st; sbRender(mics);
  } catch (e) { toast(e.message, "bad"); }
};
$("sbx-close").onclick = () => $("sbx").classList.add("hidden");
let sbMics = [];
function sbRender(mics) {
  const d = sbState; if (!d) return;
  if (mics) sbMics = mics;
  const cab = d.status === "on";
  $("sbx-st").innerHTML = !d.available ? `<div class="warn">Faltam pacotes no PC: ${esc(d.error)}</div>`
    : cab ? `<div class="ok">Saindo no microfone pelo cabo <b>${esc(d.cable)}</b></div><div class="row"><span>Microfone junto</span><span class="ell">${esc(d.mic || "nenhum")}</span></div>`
    : d.status === "nocable" ? '<div class="warn">Sem cabo virtual no PC: por enquanto os sons tocam só para você.</div>'
    : `<div class="warn">${esc(d.error || "Mesa de som desligada")}</div>`;
  const opts = [["", "Padrão do Windows"], ...sbMics.map((m) => [m, m]), ["nenhum", "Nenhum (só os sons)"]];
  $("sbx-mic").innerHTML = opts.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join("");
  $("sbx-mic").value = opts.some(([v]) => v === d.pick) ? d.pick : "";
  $("sbx-monsw").classList.toggle("on", d.monitor); $("sbx-mon").textContent = d.monitor_dev || "";
  $("sbx-one").classList.toggle("on", !d.overlap);
  $("sbx-nr").classList.toggle("on", d.nr && d.nr_ok);
  $("sbx-nrl").classList.toggle("hidden", !cab || !d.mic || !d.nr_ok);
  $("sbx-mutel").classList.toggle("hidden", !cab || !d.mic);
  $("sbx-fxl").classList.toggle("hidden", !cab || !d.mic);
  sbLive();
  $("sbx-vol").value = d.vol; $("sbx-vv").textContent = d.vol + "%";
  $("sbx-mvol").value = d.mic_vol; $("sbx-mv").textContent = d.mic_vol + "%";
  $("sbx-mvl").classList.toggle("hidden", !cab);
  $("sbx-mic").parentElement.classList.toggle("hidden", !cab);
  $("sbx-help").innerHTML = cab
    ? `<b>No Discord:</b> Configurações &gt; Voz e vídeo &gt; Dispositivo de entrada: <b>CABLE Output</b>.
       Em <b>Supressão de ruído</b> escolha <b>Nenhuma</b> e desligue o <b>cancelamento de eco</b>: eles agem em tudo o que sai pelo cabo e cortam música e efeitos.
       ${d.nr_ok ? "O ruído do seu microfone é tirado aqui mesmo (opção acima), sem encostar nos sons." : "Para tirar o ruído só do microfone, atualize o servidor (instala o RNNoise) ou escolha acima um microfone já limpo, como o <b>NVIDIA Broadcast</b>."}`
    : `<b>Para sair no microfone (uma vez só):</b><ol><li>Instale o <b>VB-CABLE</b> (grátis, vb-audio.com/Cable): extraia o zip, rode <b>VBCABLE_Setup_x64</b> como administrador e reinicie o PC.</li>
       <li>Se o som do PC sumir depois, volte a saída padrão para o seu fone (aba Mixer).</li>
       <li>No Discord: Voz e vídeo &gt; Dispositivo de entrada: <b>CABLE Output</b>.</li></ol>`;
}
const sbSet = (p) => send("snd.set", p).then((d) => { sbState = d; sbRender(); }).catch((e) => toast(e.message, "bad"));
$("sbx-mic").onchange = () => { buzz(8); sbSet({ mic: $("sbx-mic").value }); };
$("sbx-monsw").onclick = () => { buzz(8); sbSet({ monitor: !sbState?.monitor }); };
$("sbx-one").onclick = () => { buzz(8); sbSet({ overlap: !sbState?.overlap }); };
$("sbx-nr").onclick = () => { buzz(8); sbSet({ nr: !sbState?.nr }); };
$("sbx-mute").onclick = () => { buzz(8); sbSet({ muted: !sbState?.muted }); };
$("sbx-fx").onclick = (e) => { const b = e.target.closest("[data-fx]"); if (b) { buzz(8); sbSet({ fx: b.dataset.fx }); } };
for (const [id, key, lab] of [["sbx-vol", "vol", "sbx-vv"], ["sbx-mvol", "mic_vol", "sbx-mv"]]) {
  $(id).oninput = () => { $(lab).textContent = $(id).value + "%"; };
  $(id).onchange = () => sbSet({ [key]: +$(id).value });
}
