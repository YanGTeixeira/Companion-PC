"use strict";
// ---------------------------------------------------------------- Atalhos / Sistema
function renderPower() {
  $("tmr-sec").classList.toggle("hidden", !welcome.power);
  const items = [["lock", "Bloquear o PC", false]];
  if (welcome.power) items.push(["monitor_off", "Desligar monitor", false], ["sleep", "Suspender", true],
    ["restart", "Reiniciar", true], ["shutdown", "Desligar", true], ["cancel", "Cancelar desligamento", false]);
  $("power").innerHTML = items.map(([a, l, c]) => `<button class="tile${c ? " warn" : ""}" data-power="${a}" data-label="${l}"${c ? ' data-confirm="1"' : ""}>${l}</button>`).join("");
}
let confirmFn = null;
function confirmAsk(q, fn) { $("confirm-q").textContent = q; confirmFn = fn; $("confirm").classList.remove("hidden"); }
$("confirm-no").onclick = () => { $("confirm").classList.add("hidden"); confirmFn = null; };
$("confirm-yes").onclick = () => { $("confirm").classList.add("hidden"); const f = confirmFn; confirmFn = null; f && f(); };

document.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-launch],button[data-power],button[data-act],.tiles button[data-key]");
  if (!b) return;
  const label = b.dataset.label || b.textContent.trim();
  let run;
  if (b.dataset.launch) run = () => act("app.launch", { id: b.dataset.launch }, "Abrindo " + label);
  else if (b.dataset.power) run = () => act("power", { action: b.dataset.power }, label);
  else if (b.dataset.act) run = () => act(b.dataset.act, {}, label);
  else run = () => act("key.press", { keys: b.dataset.key }, label);
  b.dataset.confirm ? confirmAsk(label + "?", run) : run();
});

// ---------------------------------------------------------------- Mouse (touchpad)
(() => {
  const pad = $("pad"), sb = $("scrollbar");
  const pts = new Map();             // pointerId -> {x, y, x0, y0, t0}
  let mode = null;                   // "move" | "scroll" | "drag"
  let acc = { x: 0, y: 0 }, sacc = { x: 0, y: 0 }, moved = false, maxPts = 0, lastTapT = 0, raf = 0;
  const TAP_MS = 220, TAP_PX = 10;

  function flush() {
    raf = 0;
    const dx = Math.trunc(acc.x), dy = Math.trunc(acc.y);
    if (dx || dy) { acc.x -= dx; acc.y -= dy; send("mouse.move", { dx, dy }, false).catch(() => {}); }
    const sx = Math.trunc(sacc.x), sy = Math.trunc(sacc.y);
    if (sx || sy) { sacc.x -= sx; sacc.y -= sy; send("mouse.scroll", { dx: sx, dy: sy }, false).catch(() => {}); }
  }
  const schedule = () => { if (!raf) raf = requestAnimationFrame(flush); };
  const accel = (d, dt) => { const v = Math.abs(d) / Math.max(dt, 1); return d * prefs.sens * (1 + Math.min(v, 3) * 0.9); };

  function down(e) {
    e.preventDefault();
    pad.setPointerCapture(e.pointerId);
    const now = performance.now();
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, t: now, t0: now });
    maxPts = Math.max(maxPts, pts.size);
    if (pts.size === 1) {
      moved = false;
      // toque duplo e arraste = segurar o botão esquerdo
      if (now - lastTapT < 300) { lastTapT = 0; mode = "drag"; pad.classList.add("drag"); send("mouse.button", { button: "left", state: "down" }, false).catch(() => {}); buzz(20); }
      else mode = "move";
    } else if (pts.size === 2 && mode !== "drag") mode = "scroll";
  }
  function move(e) {
    const p = pts.get(e.pointerId); if (!p) return;
    e.preventDefault();
    const now = performance.now(), dx = e.clientX - p.x, dy = e.clientY - p.y, dt = now - p.t;
    p.x = e.clientX; p.y = e.clientY; p.t = now;
    if (Math.hypot(p.x - p.x0, p.y - p.y0) > TAP_PX) moved = true;
    if (mode === "scroll") {
      if (pts.size < 2) return;
      sacc.y += -dy * 6 / pts.size; sacc.x += dx * 6 / pts.size;   // média dos dois dedos; 120 = 1 "clique" da roda
    } else { acc.x += accel(dx, dt); acc.y += accel(dy, dt); }
    schedule();
  }
  function up(e) {
    const p = pts.get(e.pointerId); if (!p) return;
    pts.delete(e.pointerId);
    if (pts.size) return;
    const quick = performance.now() - p.t0 < TAP_MS + (maxPts > 1 ? 80 : 0);
    if (mode === "drag") {
      send("mouse.button", { button: "left", state: "up" }, false).catch(() => {});
      pad.classList.remove("drag");
    } else if (!moved && quick && e.type !== "pointercancel") {
      if (maxPts >= 2) { send("mouse.button", { button: "right" }, false).catch(() => {}); buzz(); }
      else {
        // clique já; um 2º toque logo depois vira arraste
        lastTapT = performance.now();
        send("mouse.button", { button: "left" }, false).catch(() => {}); buzz(8);
      }
    }
    mode = null; maxPts = 0;
  }
  pad.addEventListener("pointerdown", down);
  pad.addEventListener("pointermove", move);
  pad.addEventListener("pointerup", up);
  pad.addEventListener("pointercancel", up);
  pad.addEventListener("contextmenu", (e) => e.preventDefault());

  // faixa da direita = rolagem com um dedo
  let sy = null;
  sb.addEventListener("pointerdown", (e) => { e.stopPropagation(); e.preventDefault(); sb.setPointerCapture(e.pointerId); sy = e.clientY; });
  sb.addEventListener("pointermove", (e) => { if (sy === null) return; e.stopPropagation(); sacc.y += -(e.clientY - sy) * 8; sy = e.clientY; schedule(); });
  const sbEnd = (e) => { e.stopPropagation(); sy = null; };
  sb.addEventListener("pointerup", sbEnd); sb.addEventListener("pointercancel", sbEnd);

  // botões físicos: segurar = arrastar
  const hold = (id, button) => {
    const b = $(id);
    b.addEventListener("pointerdown", (e) => { e.preventDefault(); b.setPointerCapture(e.pointerId); b.classList.add("held"); buzz(8);
      send("mouse.button", { button, state: "down" }, false).catch(() => {}); });
    const rel = () => { if (!b.classList.contains("held")) return; b.classList.remove("held"); send("mouse.button", { button, state: "up" }, false).catch(() => {}); };
    b.addEventListener("pointerup", rel); b.addEventListener("pointercancel", rel);
    b.addEventListener("contextmenu", (e) => e.preventDefault());
  };
  hold("mb-left", "left"); hold("mb-mid", "middle"); hold("mb-right", "right");
})();

// ---------------------------------------------------------------- Teclado
const mods = new Set();
function withMods(key) { return mods.size ? [...mods, key].join("+") : key; }
function clearMods() { mods.clear(); document.querySelectorAll(".key.mod").forEach((b) => b.classList.remove("on")); }
document.querySelectorAll(".key.mod").forEach((b) => (b.onclick = () => {
  buzz(8); const m = b.dataset.mod; mods.has(m) ? mods.delete(m) : mods.add(m); b.classList.toggle("on", mods.has(m));
}));
document.querySelectorAll(".keys .key[data-key]").forEach((b) => {
  b.addEventListener("pointerdown", (e) => e.preventDefault()); // não tira o foco do teclado do Android
  b.onclick = () => { buzz(8); send("key.press", { keys: withMods(b.dataset.key) }, false).catch(() => toast("Sem conexão", "bad")); clearMods(); };
});
// Alt+Tab: segura Alt; cada toque avança; solta Alt 1,2 s depois do último toque
(() => {
  let t = null; const b = $("alttab");
  b.addEventListener("pointerdown", (e) => e.preventDefault());
  b.onclick = () => {
    buzz(8);
    if (!t) send("key.down", { key: "alt" }, false).catch(() => {});
    send("key.press", { keys: "tab" }, false).catch(() => {});
    clearTimeout(t); t = setTimeout(() => { send("key.up", { key: "alt" }, false).catch(() => {}); t = null; }, 1200);
  };
})();

// O texto digitado no teclado do Android é comparado com o anterior:
// apaga o que mudou e digita o novo (funciona com autocorretor/composição).
(() => {
  const kbd = $("kbd"), btn = $("kb-btn");
  let last = "";
  btn.addEventListener("pointerdown", (e) => e.preventDefault());
  btn.onclick = () => {
    if (document.activeElement === kbd) { kbd.blur(); return; }
    kbd.value = last = ""; kbd.focus(); buzz(8);
  };
  kbd.addEventListener("focus", () => btn.classList.add("on"));
  kbd.addEventListener("blur", () => btn.classList.remove("on"));
  kbd.addEventListener("keydown", (e) => {
    // teclas que não geram texto (Enter, Backspace com campo vazio, setas de teclado físico)
    const special = { Enter: "enter", Tab: "tab", Escape: "esc", ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down" };
    if (special[e.key]) { e.preventDefault(); send("key.press", { keys: withMods(special[e.key]) }, false).catch(() => {}); clearMods(); kbd.value = last = ""; return; }
    if (e.key === "Backspace" && !kbd.value) { e.preventDefault(); send("key.press", { keys: withMods("backspace") }, false).catch(() => {}); }
  });
  kbd.addEventListener("input", () => {
    const v = kbd.value;
    let i = 0; while (i < v.length && i < last.length && v[i] === last[i]) i++;
    const del = [...last.slice(i)].length, add = v.slice(i);
    last = v;
    if (mods.size && add.length === 1 && /[a-z0-9]/i.test(add) && !del) {
      send("key.press", { keys: withMods(add.toLowerCase()) }, false).catch(() => {}); clearMods();
      kbd.value = last = ""; return;
    }
    const text = "\b".repeat(del) + add;
    if (text) send("key.text", { text }, false).catch(() => toast("Sem conexão", "bad"));
    // limpa o campo no fim de cada palavra para ele não crescer sem parar
    if (/\s$/.test(v) && v.length > 40) kbd.value = last = "";
  });
})();

