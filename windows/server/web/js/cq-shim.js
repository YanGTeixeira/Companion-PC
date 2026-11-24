// Navegadores sem container queries (Chrome < 105, ex.: Chrome 96 do Android antigo):
// reescreve cada "@container (min-width/min-height)" como classes .cq-wN/.cq-hN nas abas
// (.tab), ligadas por ResizeObserver, e as unidades cqw/cqh como variáveis --cqw/--cqh.
(function cqShim() {
  const force = /[?&]cqshim\b/.test(location.search);
  if (CSS.supports("container-type: size") && !force) return;
  // o CSS fica em arquivos (css/*.css): lê o texto de cada um (síncrono, para valer antes do corpo
  // da página) e troca os <link> por uma <style> só, na mesma ordem
  const links = [...document.querySelectorAll('link[rel="stylesheet"]')];
  const read = (href) => { const x = new XMLHttpRequest(); x.open("GET", href, false); x.send(); return x.status === 200 ? x.responseText : ""; };
  // url(../fonts/x) é relativo ao arquivo css/; numa <style> passa a ser relativo à página
  const texts = links.map((l) => { try { return read(l.href); } catch { return ""; } });
  if (texts.some((t) => !t)) return;   // não leu algum: fica sem o adaptador, mas com o estilo
  let css = texts.join("\n").replace(/url\(\.\.\//g, "url(").replace(/\/\*[\s\S]*?\*\//g, "");
  const st = document.createElement("style");
  links[links.length - 1].after(st);
  links.forEach((l) => l.remove());
  const ws = new Set(), hs = new Set();
  const block = (str, open) => { let d = 0; for (let k = open; k < str.length; k++) { if (str[k] === "{") d++; else if (str[k] === "}" && !--d) return k; } return str.length - 1; };
  const splitSel = (sel) => { const out = []; let d = 0, cur = ""; for (const c of sel) { if (c === "(") d++; if (c === ")") d--; if (c === "," && !d) { out.push(cur); cur = ""; } else cur += c; } out.push(cur); return out.map((x) => x.trim()).filter(Boolean); };
  let res = "", pos = 0, m;
  const re = /@container\s*([^{]*)\{/g;
  while ((m = re.exec(css))) {
    const open = m.index + m[0].length - 1, close = block(css, open);
    const w = /min-width:\s*(\d+)px/.exec(m[1]), h = /min-height:\s*(\d+)px/.exec(m[1]);
    const pre = (w ? ".cq-w" + w[1] : "") + (h ? ".cq-h" + h[1] : "");
    const w0 = ":where(" + pre + ")";  // sem especificidade extra: a cascata fica igual à do navegador novo
    if (w) ws.add(+w[1]); if (h) hs.add(+h[1]);
    let body = css.slice(open + 1, close), conv = "", p = 0;
    while (true) {
      const b = body.indexOf("{", p); if (b < 0) break;
      const e = block(body, b);
      // "#t-sys .cols": a própria aba é o container, então a classe vai nela também
      conv += splitSel(body.slice(p, b)).flatMap((x) => /^#t-[\w-]+\s/.test(x) ? [w0 + " " + x, x.replace(/^(#t-[\w-]+)/, "$1" + w0)] : [w0 + " " + x]).join(", ") + body.slice(b, e + 1) + "\n";
      p = e + 1;
    }
    res += css.slice(pos, m.index) + conv; pos = close + 1; re.lastIndex = pos;
  }
  res += css.slice(pos);
  res = res.replace(/(-?[\d.]+)cq(w|h)\b/g, "calc($1 * var(--cq$2, 1v$2))");
  st.textContent = res;
  const fit = (el, r) => {
    for (const n of ws) el.classList.toggle("cq-w" + n, r.width >= n);
    for (const n of hs) el.classList.toggle("cq-h" + n, r.height >= n);
    el.style.setProperty("--cqw", r.width / 100 + "px"); el.style.setProperty("--cqh", r.height / 100 + "px");
  };
  const ro = new ResizeObserver((es) => es.forEach((e) => fit(e.target, e.contentRect)));
  const go = () => document.querySelectorAll(".tab").forEach((t) => ro.observe(t));
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go); else go();
  window.CQ_SHIM = { ws: [...ws], hs: [...hs] };
})();
