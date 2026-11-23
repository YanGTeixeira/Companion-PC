// Ponte entre as abas do Meet e o servidor do Companion PC (ws://127.0.0.1:8770).
// O servidor só aceita esta conexão sem token porque vem de uma extensão no próprio PC.
const URL_WS = "ws://127.0.0.1:8770/";
let ws = null, wsTimer = null;
const tabs = new Map(); // tabId -> { port, state }

function best() {
  // aba em chamada tem prioridade; depois a que mudou por último
  let pick = null;
  for (const [id, t] of tabs) {
    if (!t.state) continue;
    if (!pick || (t.state.inCall && !pick.t.state.inCall) || (t.state.inCall === pick.t.state.inCall && t.at > pick.t.at)) pick = { id, t };
  }
  return pick;
}
function push() {
  if (!ws || ws.readyState !== 1) return;
  const p = best();
  ws.send(JSON.stringify({ t: "meet", d: p ? { ...p.t.state, tab: p.id } : null }));
}
function connect() {
  clearTimeout(wsTimer);
  if (!tabs.size) return; // sem Meet aberto: não fica conectado à toa
  if (ws && ws.readyState <= 1) return;
  try { ws = new WebSocket(URL_WS); } catch { wsTimer = setTimeout(connect, 5000); return; }
  ws.onopen = () => { ws.send(JSON.stringify({ t: "hello", kind: "meet" })); push(); };
  ws.onmessage = (e) => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    if (m.t === "meet.cmd") {
      const p = best();
      if (p) p.t.port.postMessage({ cmd: m.cmd, arg: m.arg });
      if (p && m.cmd === "focus") { chrome.tabs.update(p.id, { active: true }); chrome.windows.update(p.t.port.sender.tab.windowId, { focused: true }); }
    } else if (m.t === "ping") ws.send(JSON.stringify({ t: "pong" }));
  };
  ws.onclose = () => { ws = null; if (tabs.size) wsTimer = setTimeout(connect, 3000); };
  ws.onerror = () => {};
}
chrome.runtime.onConnect.addListener((port) => {
  const id = port.sender?.tab?.id; if (id == null) return;
  tabs.set(id, { port, state: null, at: Date.now() });
  connect();
  port.onMessage.addListener((m) => {
    const t = tabs.get(id); if (!t) return;
    if (m.state) { t.state = m.state; t.at = Date.now(); push(); connect(); }
  });
  port.onDisconnect.addListener(() => {
    tabs.delete(id); push();
    if (!tabs.size && ws) { try { ws.close(); } catch {} }
  });
});
// mantém o service worker vivo enquanto há Meet aberto (o Chrome/Edge o encerra após 30 s parado)
setInterval(() => { if (ws && ws.readyState === 1) ws.send(JSON.stringify({ t: "keep" })); }, 20000);
