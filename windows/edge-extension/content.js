// Lê o estado do Google Meet e aperta os botões dele quando o Companion PC pede.
// Os botões são achados pelo texto de acessibilidade (português ou inglês), que muda menos que as classes.
(() => {
  const RX = {
    mic: /microfone|microphone/i,
    cam: /c[âa]mera|camera/i,
    leave: /sair da chamada|leave call|desligar|hang up/i,
    hand: /(levantar|abaixar) a m[ãa]o|(raise|lower) hand/i,
    share: /apresentar agora|compartilhar (a )?tela|present now|share (your )?screen|apresentar|present/i,
    stopShare: /parar (de )?apresentar|interromper apresenta|stop present|stop sharing/i,
    captions: /legendas|captions/i,
    join: /^(participar agora|pedir para participar|join now|ask to join|participar)$/i,
    people: /mostrar todos|participantes|show everyone|people/i,
    chat: /chat|mensagens|conversar/i,
  };
  const label = (el) => (el.getAttribute("aria-label") || el.getAttribute("data-tooltip") || el.textContent || "").trim();
  function buttons() { return [...document.querySelectorAll('button, [role="button"]')].filter((b) => b.offsetParent !== null || b.getClientRects().length); }
  function find(rx, list = buttons()) { return list.find((b) => rx.test(label(b))); }
  function muteBtn(rx) {
    // botões de microfone/câmera têm data-is-muted
    return [...document.querySelectorAll("[data-is-muted]")].find((b) => rx.test(label(b))) || null;
  }
  function state() {
    const list = buttons();
    const leave = find(RX.leave, list), mic = muteBtn(RX.mic), cam = muteBtn(RX.cam);
    const hand = find(RX.hand, list), stop = find(RX.stopShare, list);
    const join = list.find((b) => RX.join.test(b.textContent.trim()));
    const ppl = find(RX.people, list);
    let count = null;
    if (ppl) { const n = (ppl.textContent.match(/\d+/) || ppl.parentElement?.textContent.match(/\d+/) || [])[0]; if (n) count = +n; }
    const title = document.title.replace(/^Meet\s*[-–:]\s*/, "").trim();
    return {
      app: "Meet", inCall: !!leave, lobby: !leave && !!join, title: title && title !== "Meet" && title !== "Google Meet" ? title : (location.pathname.slice(1) || ""),
      code: location.pathname.slice(1), mic: mic ? mic.getAttribute("data-is-muted") !== "true" : null,
      cam: cam ? cam.getAttribute("data-is-muted") !== "true" : null,
      hand: hand ? /abaixar|lower/i.test(label(hand)) : null, sharing: !!stop, people: count,
      can: { mic: !!mic, cam: !!cam, hand: !!hand, share: !!(stop || find(RX.share, list)), leave: !!leave, join: !!join, captions: !!find(RX.captions, list) },
    };
  }
  function click(el) { if (!el) return false; el.click(); return true; }
  function run(cmd, arg) {
    const list = buttons();
    switch (cmd) {
      case "mic": { const b = muteBtn(RX.mic); const on = b && b.getAttribute("data-is-muted") !== "true"; if (b && (arg == null || arg !== on)) click(b); break; }
      case "cam": { const b = muteBtn(RX.cam); const on = b && b.getAttribute("data-is-muted") !== "true"; if (b && (arg == null || arg !== on)) click(b); break; }
      case "hand": click(find(RX.hand, list)); break;
      case "share": click(find(RX.stopShare, list) || find(RX.share, list)); break;
      case "sharePrep": { const b = find(RX.share, list); if (b) { window.focus(); b.focus(); } return; }
      case "captions": click(find(RX.captions, list)); break;
      case "leave": click(find(RX.leave, list)); break;
      case "join": click(list.find((b) => RX.join.test(b.textContent.trim()))); break;
      case "chat": click(find(RX.chat, list)); break;
    }
    setTimeout(report, 300); setTimeout(report, 1200);
  }
  let port = null, last = "";
  function connect() {
    port = chrome.runtime.connect({ name: "meet" });
    port.onMessage.addListener((m) => m.cmd && run(m.cmd, m.arg));
    port.onDisconnect.addListener(() => { port = null; last = ""; setTimeout(connect, 1000); });
    report();
  }
  function report() {
    if (!port) return;
    const s = JSON.stringify(state());
    if (s !== last) { last = s; try { port.postMessage({ state: JSON.parse(s) }); } catch { port = null; } }
  }
  connect();
  setInterval(report, 1000);
  new MutationObserver(() => { clearTimeout(report.t); report.t = setTimeout(report, 150); })
    .observe(document.body, { subtree: true, attributes: true, attributeFilter: ["data-is-muted", "aria-label", "aria-pressed"] });
})();
