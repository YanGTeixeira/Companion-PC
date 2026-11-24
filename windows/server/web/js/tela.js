"use strict";
// ---------------------------------------------------------------- Tela do PC
const scr = { on: false, busy: false, mon: 0, mons: 1, fast: store.get("scrFast", true), z: 1, tx: 0, ty: 0, iw: 0, ih: 0, fw: 0, fh: 0,
  sid: Math.random().toString(36).slice(2), timer: 0 };
const screenActive = () => vis("screen") && !docked && !document.hidden && ws && ws.readyState === 1 && welcome.host;
async function screenLoop() {
  if (scr.busy) return;
  clearTimeout(scr.timer);
  if (!screenActive()) { scr.on = false; return; }
  scr.on = true; scr.busy = true;
  const t0 = performance.now(), box = $("scr"), dpr = Math.min(devicePixelRatio || 1, 2);
  const want = Math.round(Math.min(scr.fast ? 1280 : 2560, box.clientWidth * dpr * Math.min(scr.z, 2.5) * (scr.fast ? 0.7 : 1.2)));
  try {
    const r = await send("screen.shot", { mon: scr.mon, w: Math.max(480, want), q: scr.fast ? 50 : 75, sid: scr.sid });
    scr.mons = r.mons; scr.mon = r.mon;
    $("scr-mon").textContent = `Monitor ${r.mon + 1}/${r.mons}`; $("scr-mon").classList.toggle("hidden", r.mons < 2);
    if (!r.same) $("scr-img").src = "data:image/jpeg;base64," + r.jpg;
    if (r.w !== scr.iw || r.h !== scr.ih) { scr.iw = r.w; scr.ih = r.h; layoutScreen(); }
    $("scr-msg").classList.add("hidden");
  } catch (e) {
    $("scr-msg").textContent = "Sem imagem: " + e.message; $("scr-msg").classList.remove("hidden");
  }
  scr.busy = false;
  scr.timer = setTimeout(screenLoop, Math.max(0, (scr.fast ? 90 : 350) - (performance.now() - t0)));
}
function layoutScreen() {
  const box = $("scr"), img = $("scr-img"); if (!scr.iw || !box.clientWidth) return;
  const bw = box.clientWidth, bh = box.clientHeight, k = Math.min(bw / scr.iw, bh / scr.ih);
  scr.fw = scr.iw * k; scr.fh = scr.ih * k;
  const mx = (scr.fw * (scr.z - 1)) / 2, my = (scr.fh * (scr.z - 1)) / 2;
  scr.tx = Math.max(-mx, Math.min(mx, scr.tx)); scr.ty = Math.max(-my, Math.min(my, scr.ty));
  Object.assign(img.style, { width: scr.fw + "px", height: scr.fh + "px", left: (bw - scr.fw) / 2 + "px", top: (bh - scr.fh) / 2 + "px",
    transform: `translate(${scr.tx}px, ${scr.ty}px) scale(${scr.z})` });
  $("scr-zoom").textContent = (Math.round(scr.z * 10) / 10) + "×";
}
addEventListener("resize", () => vis("screen") && layoutScreen());
function screenClick(cx, cy, button) {
  const r = $("scr-img").getBoundingClientRect(), x = (cx - r.left) / r.width, y = (cy - r.top) / r.height;
  if (!r.width || x < 0 || x > 1 || y < 0 || y > 1) return;
  buzz(button === "right" ? 30 : 10);
  const box = $("scr"), b = box.getBoundingClientRect(), rp = document.createElement("div");
  rp.className = "ripple" + (button === "right" ? " r" : ""); rp.style.left = cx - b.left + "px"; rp.style.top = cy - b.top + "px";
  box.appendChild(rp); setTimeout(() => rp.remove(), 500);
  send("screen.click", { mon: scr.mon, x, y, button }, false).catch(() => {});
  setTimeout(() => { if (scr.on && !scr.busy) screenLoop(); }, 120);  // mostra o resultado logo
}
(() => {
  const box = $("scr"), pts = new Map();
  let start = null, moved = false, lp = 0, longFired = false, pinch = null;
  box.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".scr-tools, .scr-scroll")) return;
    e.preventDefault(); box.setPointerCapture(e.pointerId);
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pts.size === 1) {
      start = { x: e.clientX, y: e.clientY, tx: scr.tx, ty: scr.ty }; moved = false; longFired = false;
      clearTimeout(lp); lp = setTimeout(() => { if (!moved && pts.size === 1) { longFired = true; screenClick(start.x, start.y, "right"); } }, 550);
    } else if (pts.size === 2) {
      clearTimeout(lp); moved = true;
      const [a, b] = [...pts.values()];
      pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, z: scr.z, cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2, tx: scr.tx, ty: scr.ty };
    }
  });
  box.addEventListener("pointermove", (e) => {
    const p = pts.get(e.pointerId); if (!p) return;
    p.x = e.clientX; p.y = e.clientY;
    if (pts.size >= 2 && pinch) {
      const [a, b] = [...pts.values()], d = Math.hypot(a.x - b.x, a.y - b.y);
      scr.z = Math.max(1, Math.min(5, (pinch.z * d) / pinch.d));
      scr.tx = pinch.tx + ((a.x + b.x) / 2 - pinch.cx); scr.ty = pinch.ty + ((a.y + b.y) / 2 - pinch.cy);
      layoutScreen(); return;
    }
    if (start && Math.hypot(e.clientX - start.x, e.clientY - start.y) > 10) { moved = true; clearTimeout(lp); }
    if (moved && start && scr.z > 1) { scr.tx = start.tx + e.clientX - start.x; scr.ty = start.ty + e.clientY - start.y; layoutScreen(); }
  });
  const up = (e) => {
    if (!pts.delete(e.pointerId)) return;
    clearTimeout(lp);
    if (!pts.size) {
      if (!moved && !longFired && start && e.type === "pointerup") screenClick(start.x, start.y, "left");
      start = null; pinch = null;
    } else if (pts.size === 1) { pinch = null; const q = [...pts.values()][0]; start = { x: q.x, y: q.y, tx: scr.tx, ty: scr.ty }; moved = true; }
  };
  box.addEventListener("pointerup", up); box.addEventListener("pointercancel", up);
  box.addEventListener("contextmenu", (e) => e.preventDefault());
  // faixa da direita: rolagem
  const sb = $("scr-scroll"); let sy = null, acc = 0;
  sb.addEventListener("pointerdown", (e) => { e.preventDefault(); sb.setPointerCapture(e.pointerId); sy = e.clientY; });
  sb.addEventListener("pointermove", (e) => {
    if (sy === null) return; acc += -(e.clientY - sy) * 8; sy = e.clientY;
    const n = Math.trunc(acc / 40) * 40; if (n) { acc -= n; send("mouse.scroll", { dy: n }, false).catch(() => {}); }
  });
  const sEnd = () => { sy = null; acc = 0; setTimeout(() => scr.on && !scr.busy && screenLoop(), 100); };
  sb.addEventListener("pointerup", sEnd); sb.addEventListener("pointercancel", sEnd);
})();
$("scr-mon").onclick = () => { buzz(8); scr.mon = (scr.mon + 1) % scr.mons; scr.z = 1; scr.tx = scr.ty = 0; scr.iw = 0; if (!scr.busy) screenLoop(); };
const setQ = () => { $("scr-q").textContent = scr.fast ? "Rápido" : "Nítido"; };
$("scr-q").onclick = () => { buzz(8); scr.fast = !scr.fast; store.set("scrFast", scr.fast); setQ(); };
setQ();
$("scr-zoom").onclick = () => { buzz(8); scr.z = scr.z > 1 ? 1 : 2; scr.tx = scr.ty = 0; layoutScreen(); };
$("scr-kb").addEventListener("pointerdown", (e) => e.preventDefault());
$("scr-kb").onclick = () => $("kb-btn").click();

