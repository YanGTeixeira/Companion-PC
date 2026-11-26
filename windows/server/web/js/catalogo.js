"use strict";
// ---------------------------------------------------------------- Coleção (1.19): o visual de tudo o que dá para liberar
// Temas, fundos do cartão, avatares em pixel art, efeitos no nome e cores de destaque. Usado pelo app (index.html),
// pelo Personalizar (editor.html) e pela página Jogador do PC (jogador.html). Quem libera o quê fica no PC (colecao.py).

// temas: [id da variante, nome, amostra, fundo, texto, destaque]
const THEMES = [
  { id: "fallout", name: "Fallout", desc: "Terminal de fósforo", font: "VT323", crt: true, variants: [
    ["green", "Verde", "#5cff8a", "#040d07", "#5cff8a", "#1c7a3d"], ["amber", "Âmbar", "#ffbf47", "#0c0703", "#ffbf47", "#8a5a17"],
    ["cyan", "Ciano", "#7cf4ff", "#030b0d", "#7cf4ff", "#1b6f7a"], ["blue", "Azul", "#8fd3ff", "#030a10", "#8fd3ff", "#23597a"],
    ["white", "Branco", "#e8f0f2", "#07090a", "#e8f0f2", "#5e6a6e"], ["red", "Vermelho", "#ff5a4f", "#0d0403", "#ff6b5e", "#82271f"],
    ["violet", "Violeta", "#c39bff", "#0a0612", "#c39bff", "#5b3a8c"], ["toxic", "Tóxico", "#d4ff3a", "#080c02", "#d4ff3a", "#6a8a12"]] },
  { id: "synth", name: "Synthwave", desc: "Neon rosa e ciano", font: "Orbitron", crt: true, variants: [
    ["neon", "Neon", "#ff4fd8", "#0d0518", "#ff4fd8", "#3ef0ff"], ["sunset", "Pôr do sol", "#ffb347", "#140818", "#ff6b9d", "#ffb347"],
    ["ice", "Gelo", "#7df9ff", "#050b1a", "#4d7cff", "#7df9ff"], ["gold", "Ouro", "#ffc94d", "#120b02", "#ffc94d", "#ff7a1a"],
    ["mint", "Menta", "#5effc8", "#04120e", "#5effc8", "#b48cff"], ["blood", "Sangue", "#ff2a4d", "#14030a", "#ff2a4d", "#ff9a3c"]] },
  { id: "minimal", name: "Minimal", desc: "Limpo e moderno", font: "Inter", variants: [
    ["dark", "Escuro", "#171a20", "#171a20", "#eef1f5", "#4c8dff"], ["light", "Claro", "#f3f5f8", "#f3f5f8", "#15181d", "#2563eb"],
    ["amoled", "Preto (AMOLED)", "#000000", "#000000", "#f1f1f1", "#4c8dff"], ["purple", "Roxo", "#8b5cf6", "#110e1a", "#efeaff", "#8b5cf6"],
    ["mint", "Menta", "#2ec4a6", "#0d1615", "#e8f5f2", "#2ec4a6"], ["sand", "Areia", "#efe6d6", "#f4ede1", "#2a241c", "#c2703d"],
    ["rose", "Rosé", "#f472b6", "#1a1016", "#fbeaf3", "#f472b6"]] },
  { id: "hud", name: "Cockpit", desc: "HUD laranja e branco", font: "Rajdhani", variants: [
    ["orange", "Laranja", "#ff8a1f", "#0a0e12", "#eef3f7", "#ff8a1f"], ["aviation", "Aviônica", "#3fd3ff", "#04080a", "#ffb000", "#3fd3ff"],
    ["alert", "Alerta", "#ff3b3b", "#0c0606", "#f7eaea", "#ff3b3b"]] },
  { id: "lcd", name: "LCD 8-bit", desc: "Tela de pixel verde", font: "Press Start 2P", variants: [
    ["olive", "Oliva", "#a4b465", "#a4b465", "#1f2a10", "#5b6c32"], ["ice", "Gelo", "#9fc6d6", "#9fc6d6", "#10232c", "#3d6676"]] },
  { id: "paper", name: "Papel", desc: "E-ink, preto no creme", font: "Playfair Display", variants: [
    ["cream", "Creme", "#f2ede2", "#f2ede2", "#161514", "#8a857a"], ["sepia", "Sépia", "#e9d8b8", "#eadbbd", "#3b2a17", "#8a6a3c"],
    ["night", "Noturno", "#1b1a17", "#1b1a17", "#ece4d2", "#a89f8a"]] },
  { id: "pocket", name: "Portátil", desc: "4 tons, tela de bolso", font: "Pixelify Sans", variants: [
    ["dmg", "Verde", "#9bbc0f", "#9bbc0f", "#0f380f", "#306230"], ["gray", "Cinza", "#c4c4b2", "#c4c4b2", "#22221e", "#6e6e63"],
    ["pink", "Rosa", "#f4b6c8", "#f4b6c8", "#4a1830", "#a24a70"]] },
  { id: "code", name: "Código", desc: "Editor escuro, cores de sintaxe", font: "JetBrains Mono", variants: [
    ["dark", "Escuro", "#1e1e1e", "#1e1e1e", "#4ec9b0", "#c586c0"], ["mocha", "Mocha", "#1e1e2e", "#1e1e2e", "#94e2d5", "#cba6f7"],
    ["dracula", "Drácula", "#bd93f9", "#282a36", "#50fa7b", "#ff79c6"], ["solar", "Solarizado", "#002b36", "#002b36", "#2aa198", "#b58900"]] },
  { id: "rpg", name: "Fantasia", desc: "Pedra, ouro e moldura", font: "Cinzel", variants: [
    ["stone", "Pedra", "#d9ad4f", "#13100d", "#d9ad4f", "#b3302a"], ["crimson", "Carmim", "#c23b32", "#120a0b", "#e8c06a", "#c23b32"],
    ["emerald", "Esmeralda", "#2fbf71", "#0a110d", "#d9ad4f", "#2fbf71"], ["frost", "Gelo", "#9fd8ff", "#0b1118", "#dfeefa", "#9fd8ff"]] },
  { id: "tac", name: "Tático", desc: "Mapa de missão", font: "Chakra Petch", variants: [
    ["olive", "Oliva", "#ff7a1a", "#171a14", "#dadccf", "#ff7a1a"], ["urban", "Urbano", "#ffb020", "#121519", "#dfe3e8", "#ffb020"],
    ["desert", "Deserto", "#d9a35b", "#1d1812", "#ece3d2", "#d9a35b"]] },
  { id: "jp", name: "Japão", desc: "Washi, sakura e carimbo", font: "Zen Maru Gothic", variants: [
    ["sakura", "Sakura", "#f7f1e8", "#f7f1e8", "#d94f78", "#c8372d"], ["night", "Noite em Tóquio", "#17193a", "#0e0f24", "#6ee7ff", "#ff5c8a"],
    ["matcha", "Matcha", "#8fb573", "#f1f3e6", "#3d5a2a", "#8fb573"]] },
  { id: "exec", name: "Executivo", desc: "Marinho e champanhe", font: "Cormorant Garamond", variants: [
    ["navy", "Marinho", "#111a2c", "#0b1220", "#eef0f4", "#c9a961"], ["ivory", "Marfim", "#f6f3ec", "#f6f3ec", "#1c1f26", "#9c7b3c"],
    ["black", "Preto", "#131313", "#0a0a0a", "#f2f2f2", "#c9a961"], ["bordeaux", "Bordô", "#6b1d2e", "#160a0e", "#f3e7ea", "#c9a961"]] },
  // ---- 1.19: temas inteiros que se liberam (todas as variantes com cadeado)
  { id: "abismo", name: "Abismo", desc: "Fundo do mar, luz que brilha", font: "Exo 2", variants: [
    ["deep", "Profundo", "#2de2e6", "#020b14", "#bff6ff", "#2de2e6"], ["coral", "Coral", "#ff7f6e", "#0c0a14", "#ffe3dc", "#ff7f6e"]] },
  { id: "masmorra", name: "Masmorra", desc: "Pedra, tocha e pergaminho", font: "Cinzel", variants: [
    ["torch", "Tocha", "#ff9a2e", "#0f0b08", "#f1dfc0", "#ff9a2e"], ["crypt", "Cripta", "#8bd17c", "#080b0a", "#d7e6d0", "#8bd17c"]] },
  { id: "cosmos", name: "Cosmos", desc: "Estrelas e nebulosa", font: "Orbitron", variants: [
    ["nebula", "Nebulosa", "#b388ff", "#06040f", "#ece6ff", "#b388ff"], ["galaxy", "Galáxia", "#5ad1ff", "#03060f", "#e3f4ff", "#ffd36e"]] },
  { id: "dunas", name: "Dunas", desc: "Areia, sol e sombra", font: "Cormorant Garamond", variants: [
    ["day", "Dia", "#e9c58f", "#f3e3c6", "#3a2614", "#c2622d"], ["night", "Noite", "#33264a", "#120f1e", "#f0e2c8", "#e9b45f"]] },
  { id: "matrix", name: "Chuva Digital", desc: "Código caindo (animado)", font: "Share Tech Mono", anim: true, variants: [
    ["green", "Verde", "#00ff6a", "#000502", "#7dffb0", "#00ff6a"], ["red", "Vermelha", "#ff3355", "#050002", "#ffb0bd", "#ff3355"]] },
  { id: "aurora", name: "Aurora", desc: "Céu polar que se mexe (animado)", font: "Exo 2", anim: true, variants: [
    ["boreal", "Boreal", "#45f0a0", "#020812", "#e6fff4", "#45f0a0"], ["austral", "Austral", "#ff6ad5", "#0a0414", "#ffe8f8", "#8f7bff"]] },
  // ---- temas de prestígio (1.21: só saem prestigiando)
  { id: "insignia", name: "Insígnia", desc: "Prestígio 1: azul-marinho e ouro", font: "Rajdhani", variants: [
    ["naval", "Naval", "#d4af37", "#0a1428", "#f3ead2", "#d4af37"]] },
  { id: "fenix", name: "Fênix", desc: "Prestígio 3: brasas subindo (animado)", font: "Chakra Petch", anim: true, variants: [
    ["chama", "Chama", "#ff6a1f", "#0f0503", "#ffe7d6", "#ffb000"]] },
  { id: "prisma", name: "Prisma", desc: "Prestígio 7: cristal que muda de cor (animado)", font: "Exo 2", anim: true, variants: [
    ["cristal", "Cristal", "#9ef0ff", "#05070f", "#eef9ff", "#c49bff"]] },
  { id: "ascensao", name: "Ascensão", desc: "Prestígio 10: raios de luz dourada (animado)", font: "Cinzel", anim: true, variants: [
    ["ouro", "Ouro", "#ffd76a", "#0b0904", "#fff6dc", "#ffd76a"]] },
  // ---- temas de evento (liberam no evento e ficam)
  { id: "natal", name: "Natal", desc: "Evento de dezembro", font: "Cinzel", variants: [
    ["pinheiro", "Pinheiro", "#2f9e44", "#07130c", "#f3ead7", "#e03131"], ["neve", "Nevado (animado)", "#dbe8f5", "#0c1624", "#f1f6fb", "#e03131"]] },
  { id: "halloween", name: "Halloween", desc: "Evento de outubro", font: "Pixelify Sans", variants: [
    ["abobora", "Abóbora", "#ff7a1a", "#0d0712", "#f5e6ff", "#ff7a1a"]] },
  { id: "carnaval", name: "Carnaval", desc: "Evento de fevereiro", font: "Chakra Petch", variants: [
    ["confete", "Confete", "#ff3fa4", "#140724", "#fff3fb", "#ffd23f"]] },
  { id: "anonovo", name: "Ano Novo", desc: "Evento de janeiro (animado)", font: "Cormorant Garamond", variants: [
    ["fogos", "Fogos", "#ffd36e", "#05060d", "#f6f1e4", "#ffd36e"]] },
];
const VAR_NAME = Object.fromEntries(THEMES.flatMap((t) => t.variants.map((v) => [t.id + ":" + v[0], v[1]])));

const RARITY = { comum: "Comum", raro: "Raro", epico: "Épico", lendario: "Lendário" };
const KIND_LABEL = { title: "título", frame: "moldura", sound: "som", theme: "tema", accent: "cor", bg: "fundo", avatar: "avatar", effect: "efeito" };
const KIND_PLURAL = { title: "Títulos", frame: "Molduras", sound: "Sons das conquistas", theme: "Temas", accent: "Cor de destaque",
  bg: "Fundos do cartão", avatar: "Avatares", effect: "Efeito no nome" };
const LAY_LABEL = { bio: "Frase", stats: "Números", show: "Vitrine", recent: "Últimas conquistas", league: "Liga" };
const cEsc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// ---------------------------------------------------------------- avatares (pixel art 12×12; "." = vazio)
const AVATARS = {
  av_robo: { r: "#ff4d4d", g: "#7b8794", G: "#c7d0d9", c: "#3ef0ff", k: "#38404a", px: [
    ".....r......", ".....g......", "..gggggggg..", ".gGGGGGGGGg.", ".gGccGGccGg.", ".gGccGGccGg.",
    ".gGGGGGGGGg.", ".gGGkkkkGGg.", ".gGGGGGGGGg.", "..gggggggg..", "...g....g...", "..gg....gg.."] },
  av_gato: { o: "#ff9f43", e: "#2b2b2b", p: "#ff7aa2", w: "#ffd8a8", px: [
    ".o........o.", ".oo......oo.", ".ooo....ooo.", ".oooooooooo.", "oooooooooooo", "ooeeooooeeoo",
    "ooeeooooeeoo", "oooooppooooo", "owwoooooowwo", ".oooooooooo.", "..oooooooo..", "............"] },
  av_controle: { k: "#1d1f24", g: "#5a6270", w: "#e8e8e8", r: "#ff4d4d", b: "#3b82f6", y: "#ffd23f", a: "#2fbf71", px: [
    "............", "............", "..kkkkkkkk..", ".kggggggggk.", "kggwgggggrgk", "kgwwwgggbgyk",
    "kggwgggggagk", ".kggggggggk.", ".kgk....kgk.", "..k......k..", "............", "............"] },
  av_fantasma: { w: "#eef2ff", k: "#2a2a40", b: "#c5cdf5", px: [
    "....wwww....", "..wwwwwwww..", ".wwwwwwwwww.", ".wwkkwwkkww.", ".wwkkwwkkww.", "wwwwwwwwwwww",
    "wwwwwkkwwwww", "wwwwwkkwwwww", "wwwwwwwwwwww", "bwwwwwwwwwwb", "bwwbwwbwwbww", "w..w..w..w.."] },
  av_alien: { g: "#7cff6b", k: "#101820", d: "#3fa63a", px: [
    "....gggg....", "..gggggggg..", ".gggggggggg.", "gggggggggggg", "gkkkggggkkkg", "gkkkkggkkkkg",
    ".gkkkggkkkg.", ".gggggggggg.", "..gggddggg..", "...gggggg...", "....gddg....", ".....gg....."] },
  av_caveira: { w: "#f1f3f5", k: "#1a1a1a", px: [
    "...wwwwww...", "..wwwwwwww..", ".wwwwwwwwww.", ".wwwwwwwwww.", ".wkkkwwkkkw.", ".wkkkwwkkkw.",
    ".wwwwkkwwww.", "..wwwwwwww..", "...wkwkwkw..", "...wwwwwww..", "............", "............"] },
  av_ninja: { k: "#1b1e24", r: "#e03131", s: "#f2c9a0", e: "#111111", px: [
    "...kkkkkk...", "..kkkkkkkk..", ".kkkkkkkkkk.", ".rrrrrrrrrrr", ".kkkkkkkkkkr", ".kssssssssk.",
    ".kseesseesk.", ".kkkkkkkkkk.", ".kkkkkkkkkk.", "..kkkkkkkk..", "...kkkkkk...", "............"] },
  av_coroa: { y: "#ffd23f", Y: "#c8901a", r: "#ff3b6b", b: "#3ef0ff", px: [
    "............", "y....yy....y", "yy..yyyy..yy", "yyy.yyyy.yyy", "yyyyyyyyyyyy", "yyryyybyyyry",
    "yyyyyyyyyyyy", "YYYYYYYYYYYY", "yyyyyyyyyyyy", "............", "............", "............"] },
  av_dragao: { h: "#f5e6c8", r: "#e0483e", y: "#ffd23f", d: "#7a1f12", w: "#ffffff", o: "#ffb000", px: [
    "..h......h..", "..hh....hh..", "...rrrrrr...", "..rrrrrrrr..", ".rryrrrryrr.", ".rrrrrrrrrr.",
    "rrrrrrrrrrrr", "rrdrrrrrrdrr", ".rrrrrrrrrr.", "..rwrwrwrr..", "...rrrrrr...", "....oooo...."] },
  av_fenix: { r: "#e0483e", o: "#ff8a2a", y: "#ffd23f", k: "#1d1d1d", px: [
    "....y..y....", ".....yy.....", "....oyko....", "y...oooo...y", "oy.roooor.yo", "rooyrooryoor",
    ".roorooroor.", "..rrooooorr.", "....rooor...", "...ryoyoyr..", "..ry.y.y.yr.", ".y...y.y...y"] },
  av_coruja: { b: "#7a5230", B: "#c9a074", w: "#fff4d6", k: "#1d1d1d", y: "#ffb000", px: [
    ".b........b.", ".bb......bb.", ".bbbbbbbbbb.", "bwwwbbbbwwwb", "bwkwbbbbwkwb", "bwwwbyybwwwb",
    ".bbbbyybbbb.", ".bBBBBBBBBb.", ".bBbBbBbBBb.", ".bBBBBBBBBb.", "..bbbbbbbb..", "...y....y..."] },
  av_espada: { w: "#e6edf3", W: "#9fb0bf", g: "#ffd23f", h: "#7a5230", px: [
    "..........ww", ".........wWw", "........wWw.", ".......wWw..", "......wWw...", "..g..wWw....",
    "..ggwWw.....", "...gWw......", "...hgg......", "..hh.gg.....", ".hh.........", "hh.........."] },
  av_foguete: { w: "#e8ecf2", b: "#3b82f6", r: "#e0483e", o: "#ff7a1a", y: "#ffd23f", px: [
    ".....ww.....", "....wwww....", "....wbbw....", "....wbbw....", "....wwww....", "...rwwwwr...",
    "...rwwwwr...", "..rrwwwwrr..", "..rr.oo.rr..", ".....oo.....", "....oyyo....", ".....yy....."] },
  av_slime: { g: "#2f9e44", G: "#69db7c", w: "#ffffff", k: "#111111", px: [
    "............", "............", ".....gg.....", "....gGGg....", "...gGGGGg...", "..gGwGGwGg..",
    "..gGkGGkGg..", ".gGGGGGGGGg.", ".gGGGGGGGGg.", "gggggggggggg", "............", "............"] },
  av_cogumelo: { r: "#e03131", w: "#ffffff", s: "#f8e1c0", k: "#222222", px: [
    "....rrrr....", "..rrwwrrrr..", ".rrrwwrrwwr.", ".rrrrrrrwwr.", "rwwrrrrrrrrr", "rwwrrrrwwrrr",
    "rrrrrrrwwrrr", "...ssssss...", "...skssks...", "...ssssss...", "...ssssss...", "....ssss...."] },
  av_pinguim: { k: "#1f2933", w: "#f1f5f9", o: "#ffa94d", e: "#ffffff", px: [
    "....kkkk....", "...kkkkkk...", "..kkekkekk..", "..kkkookkk..", "..kwwwwwwk..", ".kkwwwwwwkk.",
    ".kkwwwwwwkk.", ".kkwwwwwwkk.", "..kwwwwwwk..", "..kkwwwwkk..", "...oo..oo...", "............"] },
  av_mago: { p: "#6741d9", y: "#ffd23f", s: "#f8d9b0", k: "#222222", w: "#e9ecef", px: [
    ".....pp.....", "....pppy....", "....pppp....", "...pppppp...", "..pppppppp..", ".yyyyyyyyyy.",
    "..ssssssss..", "..skssssks..", "..wwwsswww..", "..wwwwwwww..", "...wwwwww...", "....wwww...."] },
  av_neve: { w: "#f8f9fa", k: "#212529", o: "#ff922b", r: "#e03131", px: [
    "...kkkkkk...", "....kkkk....", "....kkkk....", "...wwwwww...", "...wkwwkw...", "...wwwowww..",
    "...rrrrrr...", "...wwwwwww..", "..wwwkwwww..", "..wwwwwwww..", "..wwwkwwww..", "...wwwwww..."] },
  av_abobora: { o: "#ff7a1a", O: "#d9480f", g: "#2f9e44", y: "#ffd43b", px: [
    ".....g......", ".....gg.....", "..oOoooOoo..", ".oooOooOooo.", "ooyooooooyoo", "oyyyooooyyyo",
    "ooooooyooooo", "oyoyoyoyoyoo", ".oyyyyyyyyo.", "..oooOoooo..", "............", "............"] },
  av_mascara: { p: "#ae3ec9", k: "#111111", y: "#ffd43b", c: "#3bc9db", px: [
    "............", "y..........y", ".y........y.", "..cppppppc..", ".pppppppppp.", "ppkkppppkkpp",
    "ppkkppppkkpp", ".pppp..pppp.", "..pp....pp..", "............", "............", "............"] },
  av_estrela: { y: "#ffd43b", Y: "#f59f00", k: "#3b2a00", px: [
    ".....yy.....", ".....yy.....", "....yyyy....", "....yyyy....", "yyyyyyyyyyyy", ".yyyyyyyyyy.",
    "..ykyyyyky..", "...yyyyyy...", "...yyYYyy...", "..yyy..yyy..", "..yy....yy..", ".yy......yy."] },
};
function avatarSvg(id) {
  const a = AVATARS[id]; if (!a) return "";
  let r = "";
  a.px.forEach((row, y) => { for (let x = 0; x < row.length; x++) { const c = a[row[x]]; if (c) r += `<rect x="${x}" y="${y}" width="1.02" height="1.02" fill="${c}"/>`; } });
  return `<svg class="avsvg" viewBox="0 0 12 12" shape-rendering="crispEdges" aria-hidden="true">${r}</svg>`;
}

// selo do nível com a moldura; com avatar, o desenho fica no miolo e o nível vai num selinho embaixo
function badge(level, frame, size = "", av = "", prest = 0) {
  const f = /^f_[a-z0-9]+$/.test(frame || "") ? frame : "f_simples";
  const art = av && av !== "av_nivel" ? avatarSvg(av) : "";
  const ps = +prest > 0 ? `<i class="bps${+prest >= 11 ? " m" : ""}" title="${cEsc(prestLabel(+prest))}">${+prest >= 11 ? "M" : "★" + +prest}</i>` : "";
  return `<span class="badge ${f}${size ? " " + size : ""}${art ? " hasav" : ""}"><b>${art || (+level || 1)}</b>${art ? `<i class="blv">${+level || 1}</i>` : ""}${ps}</span>`;
}
// ---------------------------------------------------------------- prestígio (1.21)
const PRESTIGE_MAX = 11;
const prestLabel = (p) => (p >= PRESTIGE_MAX ? "Mestre" : p > 0 ? "★" + p : "");
const prestName = (p) => (p >= PRESTIGE_MAX ? "Mestre do Prestígio" : `Prestígio ${p}`);
// barra de XP: até o próximo nível, ou (no 30) até os próximos créditos do XP extra
function xpLine(d) {
  if (d.extra) {
    return { pct: (d.extra.xp / d.extra.per) * 100,
      text: `Nível máximo · ${d.extra.xp}/${d.extra.per} XP para +${d.credits?.rules?.level ?? 20} créditos` };
  }
  return { pct: Math.max(0, Math.min(100, ((d.xp - d.lvl_lo) / Math.max(1, d.lvl_hi - d.lvl_lo)) * 100)),
    text: `${d.xp - d.lvl_lo} / ${d.lvl_hi - d.lvl_lo} XP para o nível ${d.level + 1}` };
}
// como liberar um item (texto da janela do item, no celular e no PC)
function howText(r, d) {
  if (r.got) return "Já é seu.";
  const inShop = r.shop && d.shop.items.includes(r.id);
  if (r.prestige) return `${r.prestige >= PRESTIGE_MAX ? "Chegue ao Mestre do Prestígio" : `Chegue ao prestígio ${r.prestige}`}${d.prestige ? ` (você está no ${prestLabel(d.prestige)})` : ""}. Dá para prestigiar no nível ${d.level_max || 30}.`;
  if (r.req) return `Chegue ao nível ${r.req}${d.prestige ? "" : ` (você está no ${d.level})`}.`;
  if (r.shop) return `Loja da semana: ${r.price} créditos.${r.shop_p ? ` Só aparece para quem tem prestígio ${prestLabel(r.shop_p)} ou mais.` : ""}${inShop ? "" : " Não está na loja agora; ela muda toda segunda."}`;
  if (r.event) return `Complete o evento ${EVENT_NAME[r.event] || r.event}.`;
  if (r.set) return `Complete o conjunto ${SET_NAME[r.set] || r.set}.`;
  return `Ganhe a conquista ${r.conq}.`;
}
// quadro do prestígio: onde você está, o que o próximo libera e o botão (id "pr-go"; a página liga o clique)
function prestigeBox(d) {
  if (!d || d.prestige_max == null) return "";
  const p = d.prestige, nx = (d.prestige_next || []).map((id) => d.rewards.find((r) => r.id === id)).filter(Boolean);
  const head = p ? `<b class="prl">${cEsc(prestName(p))}</b>` : "<b class=\"prl\">Sem prestígio ainda</b>";
  const hist = (d.prestiges || []).length ? `<small>${d.prestiges.map((x) => `${prestLabel(x.n)} em ${new Date(x.day + "T12:00").toLocaleDateString("pt-BR")}`).join(" · ")}</small>` : "";
  const how = p >= PRESTIGE_MAX ? "Você chegou ao topo. O XP extra no nível 30 continua rendendo créditos."
    : d.can_prestige ? `Você está no nível ${d.level_max}: dá para prestigiar. O nível volta a 1 e tudo o que já liberou continua seu.`
    : `Chegue ao nível ${d.level_max} para prestigiar (está no ${d.level}). Não é obrigatório: no 30, o XP extra vira créditos.`;
  return `<div class="prbox">${head}${hist}<p>${how}</p>
    ${nx.length ? `<small class="prnx">${p + 1 >= PRESTIGE_MAX ? "O MESTRE LIBERA" : `O ${prestLabel(p + 1)} LIBERA`}</small><div class="prits">${nx.map((r) => `<div class="ivit rar-${r.rarity}">${itemPreview(r, d.level, d.equip)}<span>${cEsc(r.name)}</span></div>`).join("")}</div>` : ""}
    ${d.can_prestige ? `<button class="prgo" id="pr-go">${p + 1 >= PRESTIGE_MAX ? "Virar Mestre do Prestígio" : `Prestigiar (${prestLabel(p + 1)})`}</button>` : ""}</div>`;
}

// troféu em SVG; a cor vem do degradê da raridade (TROPHY_DEFS, no index.html e na página Jogador), ou apagado se ainda não ganhou
function trophy(tier, got) {
  const f = got ? `url(#tg-${tier})` : "var(--p4)";
  return `<svg class="tro ${got ? tier : "off"}" viewBox="0 0 64 64" aria-hidden="true">
    <path d="M18 14h-7v3a10 10 0 0 0 10 10M46 14h7v3a10 10 0 0 1-10 10" fill="none" stroke="${f}" stroke-width="4" stroke-linecap="round"/>
    <path d="M18 7h28v15a14 14 0 0 1-28 0z" fill="${f}"/>
    <path d="M29 35h6v8h-6z" fill="${f}"/><path d="M23 50l3-7h12l3 7z" fill="${f}"/><rect x="18" y="50" width="28" height="7" rx="1.5" fill="${f}"/>
    ${got ? '<path d="M24 11v9a8 8 0 0 0 4 7" fill="none" stroke="#fff" stroke-opacity=".45" stroke-width="2.5" stroke-linecap="round"/>'
      : '<text x="32" y="25" text-anchor="middle" font-size="14" font-family="sans-serif" fill="var(--bg)">?</text>'}</svg>`;
}
const TROPHY_DEFS = `<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <linearGradient id="tg-bronze" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f0a868"/><stop offset=".5" stop-color="#cd7f32"/><stop offset="1" stop-color="#7a4518"/></linearGradient>
  <linearGradient id="tg-prata" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".5" stop-color="#c9ced3"/><stop offset="1" stop-color="#7d858c"/></linearGradient>
  <linearGradient id="tg-ouro" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff3b0"/><stop offset=".45" stop-color="#ffd23f"/><stop offset="1" stop-color="#b8860b"/></linearGradient></defs></svg>`;

// ---------------------------------------------------------------- nome com efeito
function fxName(text, fx, tag = "span", cls = "") {
  const f = /^e_[a-z]+$/.test(fx || "") && fx !== "e_nenhum" ? fx : "";
  return `<${tag} class="${cls}${f ? ` fx ${f} an` : ""}" data-t="${cEsc(text)}">${cEsc(text)}</${tag}>`;
}

// ---------------------------------------------------------------- fundos do cartão do jogador (SVG, 320×120)
const rnd = (seed) => () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
function stars(n, seed, h = 120, color = "#fff") {
  const r = rnd(seed); let s = "";
  for (let i = 0; i < n; i++) s += `<circle cx="${(r() * 320).toFixed(1)}" cy="${(r() * h).toFixed(1)}" r="${(r() * 0.9 + 0.3).toFixed(2)}" fill="${color}" opacity="${(r() * 0.6 + 0.3).toFixed(2)}"/>`;
  return s;
}
const BGS = {
  b_nenhum: () => "",
  b_grade: () => `<defs><pattern id="bgg" width="16" height="16" patternUnits="userSpaceOnUse"><path d="M16 0H0V16" fill="none" stroke="currentColor" stroke-opacity=".18"/></pattern>
    <linearGradient id="bggf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".12"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>
    <rect width="320" height="120" fill="url(#bgg)"/><rect width="320" height="120" fill="url(#bggf)"/>`,
  b_cidade: () => {
    const r = rnd(7); let b = "", x = 0;
    while (x < 320) {
      const w = 14 + Math.floor(r() * 22), h = 30 + Math.floor(r() * 60);
      b += `<rect x="${x}" y="${120 - h}" width="${w}" height="${h}" fill="#141a2e"/>`;
      for (let wy = 124 - h; wy < 116; wy += 7) for (let wx = x + 3; wx < x + w - 3; wx += 6) if (r() > 0.55) b += `<rect x="${wx}" y="${wy}" width="2.5" height="3" fill="#ffd36e" opacity="${(0.5 + r() * 0.5).toFixed(2)}"/>`;
      x += w + 2;
    }
    return `<defs><linearGradient id="bcs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2b1b4d"/><stop offset="1" stop-color="#ff7a59"/></linearGradient></defs>
      <rect width="320" height="120" fill="url(#bcs)"/>${stars(25, 3, 50)}<circle cx="250" cy="30" r="12" fill="#ffe8b0"/>${b}`;
  },
  b_montanhas: () => `<defs><linearGradient id="bms" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7fb2ff"/><stop offset="1" stop-color="#ffd8a8"/></linearGradient></defs>
    <rect width="320" height="120" fill="url(#bms)"/><circle cx="80" cy="44" r="16" fill="#fff4d6"/>
    <path d="M0 120V70l40-30 30 22 45-40 40 34 30-18 50 40 35-26 50 30v38z" fill="#6c7fa8"/>
    <path d="M115 22l-14 14 8-2 6 6 6-8 6 2z" fill="#fff" opacity=".85"/>
    <path d="M0 120V92l50-22 40 18 55-30 50 28 45-20 80 30v24z" fill="#3d4f74"/><path d="M0 120v-12l70-12 60 10 80-14 110 16v12z" fill="#22304a"/>`,
  b_espaco: () => `<rect width="320" height="120" fill="#05040f"/>${stars(90, 11)}
    <defs><radialGradient id="bep" cx=".35" cy=".35"><stop offset="0" stop-color="#ffb38a"/><stop offset=".7" stop-color="#c2410c"/><stop offset="1" stop-color="#431407"/></radialGradient>
    <radialGradient id="ben"><stop offset="0" stop-color="#8b5cf6" stop-opacity=".45"/><stop offset="1" stop-color="#8b5cf6" stop-opacity="0"/></radialGradient></defs>
    <ellipse cx="90" cy="70" rx="120" ry="50" fill="url(#ben)"/><circle cx="250" cy="72" r="30" fill="url(#bep)"/>
    <ellipse cx="250" cy="72" rx="48" ry="9" fill="none" stroke="#ffd8a8" stroke-opacity=".7" stroke-width="2.5" transform="rotate(-14 250 72)"/>`,
  b_sol: () => {
    let g = "";
    for (let i = 0; i < 9; i++) g += `<line x1="${-200 + i * 90}" y1="120" x2="${100 + i * 15}" y2="72" stroke="#ff4fd8" stroke-opacity=".6"/>`;
    for (let i = 0; i < 6; i++) { const y = 72 + Math.pow(i + 1, 1.6) * 2.2; g += `<line x1="0" y1="${y.toFixed(1)}" x2="320" y2="${y.toFixed(1)}" stroke="#ff4fd8" stroke-opacity=".6"/>`; }
    return `<defs><linearGradient id="bss" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe066"/><stop offset="1" stop-color="#ff3fa4"/></linearGradient>
      <linearGradient id="bsk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#12002b"/><stop offset="1" stop-color="#4a0a5c"/></linearGradient>
      <clipPath id="bsc"><rect x="0" y="0" width="320" height="72"/></clipPath></defs>
      <rect width="320" height="120" fill="url(#bsk)"/>${stars(30, 5, 60)}
      <g clip-path="url(#bsc)"><circle cx="160" cy="72" r="40" fill="url(#bss)"/>${[52, 58, 63, 67, 70].map((y, i) => `<rect x="110" y="${y}" width="100" height="${1.2 + i * 0.6}" fill="#4a0a5c"/>`).join("")}</g>
      <rect y="72" width="320" height="48" fill="#12002b"/>${g}`;
  },
  b_circuito: () => {
    const r = rnd(19); let p = "";
    for (let i = 0; i < 26; i++) {
      let x = Math.floor(r() * 20) * 16, y = Math.floor(r() * 8) * 16; const pts = [[x, y]];
      for (let k = 0; k < 3; k++) { if (r() > 0.5) x += (r() > 0.5 ? 1 : -1) * 32; else y += (r() > 0.5 ? 1 : -1) * 16; pts.push([x, y]); }
      p += `<polyline points="${pts.map((q) => q.join(",")).join(" ")}" fill="none" stroke="currentColor" stroke-opacity=".35" stroke-width="1.5"/><circle cx="${x}" cy="${y}" r="2.5" fill="currentColor" fill-opacity=".7"/>`;
    }
    return `<rect width="320" height="120" fill="#06100d"/>${p}`;
  },
  b_aurora: () => `<rect width="320" height="120" fill="#020812"/>${stars(50, 23, 70)}
    <defs><linearGradient id="bau" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#45f0a0" stop-opacity="0"/><stop offset=".5" stop-color="#45f0a0" stop-opacity=".55"/><stop offset="1" stop-color="#8f7bff" stop-opacity="0"/></linearGradient></defs>
    <g class="an bga-wave"><path d="M-80 60 C 0 10, 80 90, 160 40 S 320 10, 400 50 V 100 C 320 60, 240 110, 160 80 S 0 60, -80 100z" fill="url(#bau)"/>
    <path d="M-80 40 C 20 0, 100 70, 180 30 S 330 0, 400 30 V 60 C 320 40, 240 80, 170 55 S 0 40, -80 70z" fill="url(#bau)" opacity=".6"/></g>
    <path d="M0 120V104l40-10 40 8 50-14 60 12 50-10 80 14v16z" fill="#03101c"/>`,
  b_castelo: () => `<defs><linearGradient id="bck" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1a1033"/><stop offset="1" stop-color="#5b2a5e"/></linearGradient></defs>
    <rect width="320" height="120" fill="url(#bck)"/>${stars(30, 29, 60)}<circle cx="70" cy="36" r="18" fill="#fff1c1"/>
    <path d="M150 120V60h8v-8h6v8h8V40h6v-8h6v8h6v20h8v-8h6v8h8v60z M176 120v-24a8 8 0 0 1 16 0v24z" fill="#0c0718"/>
    <path d="M0 120V100l60-8 50 10 40-6v24z M210 120v-18l50-10 60 14v14z" fill="#0c0718"/>
    <rect x="183" y="70" width="3" height="6" fill="#ffd36e"/><rect x="158" y="72" width="3" height="5" fill="#ffd36e"/>`,
  b_vortice: () => `<rect width="320" height="120" fill="#07031a"/>
    <defs><radialGradient id="bvx"><stop offset="0" stop-color="#ffffff"/><stop offset=".12" stop-color="#c49bff"/><stop offset=".5" stop-color="#5a2dd6" stop-opacity=".45"/><stop offset="1" stop-color="#07031a" stop-opacity="0"/></radialGradient></defs>
    <circle cx="160" cy="60" r="160" fill="url(#bvx)" opacity=".7"/>${stars(30, 61, 120, "#c49bff")}
    <g class="an bgv-spin">${[22, 40, 60, 84, 110, 140].map((r, i) => `<circle cx="160" cy="60" r="${r}" fill="none" stroke="${i % 2 ? "#ff9ed8" : "#9ef0ff"}" stroke-opacity="${(0.75 - i * 0.1).toFixed(2)}" stroke-width="${(3 - i * 0.35).toFixed(2)}" stroke-dasharray="${Math.round(r * 0.9)} ${Math.round(r * 0.55)}"/>`).join("")}</g>
    <g class="an bgv-spin2">${[30, 72, 125].map((r) => `<circle cx="160" cy="60" r="${r}" fill="none" stroke="#ffffff" stroke-opacity=".25" stroke-width="1" stroke-dasharray="2 ${Math.round(r / 3)}"/>`).join("")}</g>`,
  b_lava: () => `<rect width="320" height="120" fill="#140403"/>
    <defs><radialGradient id="blv"><stop offset="0" stop-color="#ffb000"/><stop offset=".45" stop-color="#ff3b1f" stop-opacity=".8"/><stop offset="1" stop-color="#ff3b1f" stop-opacity="0"/></radialGradient></defs>
    <g class="an bgl-pulse"><ellipse cx="60" cy="118" rx="80" ry="26" fill="url(#blv)"/><ellipse cx="220" cy="122" rx="110" ry="30" fill="url(#blv)"/></g>
    <g class="an bgl-pulse2"><circle cx="140" cy="100" r="16" fill="url(#blv)"/><circle cx="290" cy="92" r="12" fill="url(#blv)"/><circle cx="30" cy="80" r="8" fill="url(#blv)"/></g>
    <path d="M0 70l40 10 30-14 50 18 40-10 50 16 60-12 50 10V0H0z" fill="#1f0806"/>`,
  b_oceano: () => `<defs><linearGradient id="bos" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9fe3ff"/><stop offset="1" stop-color="#3aa0d8"/></linearGradient></defs>
    <rect width="320" height="120" fill="url(#bos)"/><circle cx="260" cy="28" r="14" fill="#fffbe0"/>
    <path d="M0 64 q20 -8 40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 V120 H0z" fill="#1c7ed6"/>
    <path d="M0 80 q20 -8 40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 V120 H0z" fill="#1864ab"/>
    <path d="M0 98 q20 -8 40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 V120 H0z" fill="#0b4a80"/>`,
  b_floresta: () => {
    const tree = (x, y, s, c) => `<path d="M${x} ${y - 40 * s}l${12 * s} ${18 * s}h${-6 * s}l${10 * s} ${14 * s}h${-7 * s}l${9 * s} ${12 * s}h${-36 * s}l${9 * s} ${-12 * s}h${-7 * s}l${10 * s} ${-14 * s}h${-6 * s}z" fill="${c}"/>`;
    const r = rnd(31); let t = "";
    for (let i = 0; i < 14; i++) t += tree(10 + i * 24 + r() * 8, 104, 0.7 + r() * 0.3, "#2b5a3c");
    for (let i = 0; i < 11; i++) t += tree(i * 32 + r() * 10, 124, 0.9 + r() * 0.4, "#173a26");
    return `<defs><linearGradient id="bfs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#cfe8d5"/><stop offset="1" stop-color="#7fb28d"/></linearGradient></defs>
      <rect width="320" height="120" fill="url(#bfs)"/>${t}`;
  },
  b_chuva: () => {
    const r = rnd(41); let c = "";
    for (let i = 0; i < 22; i++) {
      const x = i * 15 + 4, d = (2 + r() * 3).toFixed(1), del = (-r() * 4).toFixed(1);
      let col = ""; for (let k = 0; k < 9; k++) col += `<text x="${x}" y="${k * 13}" fill="#00ff6a" fill-opacity="${(0.15 + k / 10).toFixed(2)}">${"01アイウエカキ"[Math.floor(r() * 8)]}</text>`;
      c += `<g class="an bgc-fall" style="animation-duration:${d}s;animation-delay:${del}s">${col}</g>`;
    }
    return `<rect width="320" height="120" fill="#000502"/><g font-family="monospace" font-size="11">${c}</g>`;
  },
  b_natal: () => {
    const r = rnd(53); let f = "";
    for (let i = 0; i < 40; i++) f += `<circle cx="${(r() * 320).toFixed(0)}" cy="${(r() * 120).toFixed(0)}" r="${(r() * 1.4 + 0.6).toFixed(1)}" fill="#fff" opacity="${(0.5 + r() * 0.5).toFixed(2)}"/>`;
    return `<defs><linearGradient id="bnt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b1a33"/><stop offset="1" stop-color="#23406b"/></linearGradient></defs>
      <rect width="320" height="120" fill="url(#bnt)"/><g class="an bgn-snow">${f}<g transform="translate(0 -120)">${f}</g></g>
      <path d="M0 120v-14q80-14 160 0t160 0v14z" fill="#eef4fb"/>
      <path d="M250 104l-22 0 10-14h-6l10-14h-5l13-18 13 18h-5l10 14h-6l10 14z" fill="#1b5e3a"/><circle cx="250" cy="56" r="3" fill="#ffd43b"/>
      <circle cx="244" cy="84" r="2" fill="#e03131"/><circle cx="257" cy="94" r="2" fill="#ffd43b"/><circle cx="252" cy="72" r="2" fill="#4dabf7"/>`;
  },
  b_halloween: () => `<defs><linearGradient id="bhw" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1b0b2e"/><stop offset="1" stop-color="#4b1d52"/></linearGradient></defs>
    <rect width="320" height="120" fill="url(#bhw)"/>${stars(20, 61, 60)}<circle cx="230" cy="44" r="28" fill="#ffe8a3"/><circle cx="240" cy="38" r="5" fill="#f2d07a" opacity=".6"/>
    <path d="M90 30q6-6 12 0q4-6 8 0q6-6 12 0q-8 0-10 6q-2-4-6 0q-2-6-6 0q-2-6-10-6z M150 50q5-5 10 0q3-5 6 0q5-5 10 0q-7 0-8 5q-2-3-5 0q-2-5-5 0q-2-5-8-5z" fill="#0d0614"/>
    <path d="M0 120V96q60-24 120-4t110-6t90 10v24z" fill="#0d0614"/><path d="M60 92v-22h4v22z M54 80h16v3H54z" fill="#0d0614"/>`,
};
function bgSvg(id) {
  const f = BGS[id]; if (!f || id === "b_nenhum") return "";
  if (!bgSvg.cache[id]) bgSvg.cache[id] = f();
  return `<svg class="bgart ${id}" viewBox="0 0 320 120" preserveAspectRatio="xMidYMid slice" aria-hidden="true">${bgSvg.cache[id]}</svg>`;
}
bgSvg.cache = {};

// ---------------------------------------------------------------- cor de destaque (por cima do tema)
const ACC_ANIM = ["a_holo", "a_arco", "a_brasa", "a_plasma", "a_ouro"];
function hexLum(hex) {
  const n = parseInt(String(hex).slice(1), 16), c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
const ACC_VARS = ["--hl", "--on", "--onfg", "--bar2"];
function accentApply(el, id, color) {
  ACC_VARS.forEach((p) => el.style.removeProperty(p));
  el.classList.remove("acc-anim", "an", ...ACC_ANIM.map((a) => "acc-" + a));
  if (id === "a_livre" && /^#[0-9a-f]{6}$/i.test(color || "")) {
    el.style.setProperty("--hl", color); el.style.setProperty("--on", color); el.style.setProperty("--bar2", color);
    el.style.setProperty("--onfg", hexLum(color) > 0.35 ? "#0b0b0f" : "#ffffff");
  } else if (ACC_ANIM.includes(id)) el.classList.add("acc-anim", "an", "acc-" + id);
}
const ACC_SWATCH = { a_tema: "var(--hl, var(--p))", a_livre: "conic-gradient(#ff4d4d, #ffd23f, #4dff88, #4dd2ff, #8a4dff, #ff4dd2, #ff4d4d)",
  a_holo: "linear-gradient(135deg, #7df9ff, #b388ff, #ff9de2)", a_arco: "linear-gradient(90deg, #ff4d4d, #ffd23f, #4dff88, #4dd2ff, #b388ff)",
  a_brasa: "linear-gradient(135deg, #ff3b1f, #ffb000)", a_plasma: "linear-gradient(135deg, #ff4fd8, #3ef0ff)", a_ouro: "linear-gradient(135deg, #fff1a8, #c8901a, #ffd23f)" };

// ---------------------------------------------------------------- prévia de um item (inventário e loja)
function themeVariant(id) {
  const [skin, v] = String(id).split(":"), t = THEMES.find((x) => x.id === skin);
  return t && t.variants.find((x) => x[0] === v);
}
function itemPreview(r, level, eq) {
  const k = r.kind;
  if (k === "title") return fxName(r.name, eq?.effect, "span", "ivtitle");
  if (k === "frame") return badge(level, r.id, "sm", eq?.avatar);
  if (k === "sound") return '<span class="ivplay" aria-hidden="true">▶</span>';
  if (k === "theme") { const v = themeVariant(r.id) || []; return `<span class="ivsw" style="background:linear-gradient(135deg, ${v[3]} 55%, ${v[5]} 55%)"><i style="background:${v[4]}"></i></span>`; }
  if (k === "accent") return `<span class="ivacc${ACC_ANIM.includes(r.id) ? " an acc-sw-" + r.id : ""}" style="background:${ACC_SWATCH[r.id] || "var(--p)"}"></span>`;
  if (k === "bg") return `<span class="ivbg">${bgSvg(r.id) || '<i class="ivbg0"></i>'}</span>`;
  if (k === "avatar") return r.id === "av_nivel" ? badge(level, eq?.frame, "sm") : `<span class="ivav">${avatarSvg(r.id)}</span>`;
  if (k === "effect") return fxName("Nome", r.id, "span", "ivfx");
  return "";
}
const reqText = (r) => (r.prestige ? `prestígio ${prestLabel(r.prestige)}` : r.req ? `nível ${r.req}` : r.shop ? `loja${r.shop_p ? " " + prestLabel(r.shop_p) + "+" : ""} · ${r.price} créditos` : r.event ? `evento ${EVENT_NAME[r.event] || r.event}`
  : r.set ? `conjunto ${SET_NAME[r.set] || r.set}` : `conquista ${r.conq}`);
const SET_NAME = { cosmos: "Cosmos", masmorra: "Masmorra", abismo: "Abismo", digital: "Chuva digital", dunas: "Deserto", fogo: "Fogo",
  retro: "Fliperama", natal: "Natal", halloween: "Halloween", carnaval: "Carnaval", anonovo: "Ano Novo", lendario: "Lendário" };
// 1.20: um conjunto da coleção (celular e PC). attr: o data-* que a página usa para abrir o item ao tocar
function setCard(s, d, attr) {
  const R = (id) => d.rewards.find((x) => x.id === id), rw = R(s.reward);
  const pct = (s.have / s.items.length) * 100;
  return `<div class="setc${s.done ? " done" : ""}"><div class="seth"><span class="seti">${s.icon}</span><div><b>${cEsc(s.name)}</b>
      <small>${s.done ? "Completo!" : `${s.have} de ${s.items.length}`} · +${s.credits} créditos</small></div>
      ${rw ? `<button class="ivit setrw rar-${rw.rarity}${rw.got ? "" : " lock"}" ${attr}="${cEsc(rw.id)}" title="Prêmio do conjunto">${itemPreview(rw, d.level, d.equip)}<small>${rw.got ? "prêmio ✓" : "prêmio"}</small></button>` : ""}</div>
    <div class="setbar"><i style="width:${pct}%"></i></div>
    <div class="setms">${s.items.map((id) => { const r = R(id); return r ? `<button class="ivit setmem${r.got ? " got" : " lock"}" ${attr}="${cEsc(id)}" title="${cEsc(r.got ? "Liberado" : reqText(r))}">${r.got ? "✓" : "🔒"} ${cEsc(r.name)}</button>` : ""; }).join("")}</div></div>`;
}
const EVENT_NAME = { natal: "de Natal", anonovo: "de Ano Novo", carnaval: "de Carnaval", halloween: "de Halloween" };

// ---------------------------------------------------------------- cartão do jogador (perfil)
// p: {nick, level, title (nome), frame, avatar, effect, bg, bio, lay, stats: [[valor, rótulo]], show: [html], recent: [html], league: html}
function profileCard(p) {
  const blocks = (p.lay || ["bio", "stats", "show"]).map((b) => {
    if (b === "bio") return p.bio ? `<div class="pfbio">“${cEsc(p.bio)}”</div>` : "";
    if (b === "stats") return p.stats?.length ? `<div class="pfstats">${p.stats.map(([v, l]) => `<div><b>${cEsc(v)}</b><small>${cEsc(l)}</small></div>`).join("")}</div>` : "";
    if (b === "show") return p.show ? `<div class="pfshow">${p.show}</div>` : "";
    if (b === "recent") return p.recent ? `<div class="pfrecent"><small>ÚLTIMAS CONQUISTAS</small>${p.recent}</div>` : "";
    if (b === "league") return p.league ? `<div class="pflg">${p.league}</div>` : "";
    return "";
  }).join("");
  return `<div class="pfcard${p.bg && p.bg !== "b_nenhum" ? " hasbg" : ""}">
    <div class="pfban">${bgSvg(p.bg)}<div class="pfid">${badge(p.level, p.frame, "big", p.avatar, p.prestige)}
      <div class="pfnm">${fxName(p.title || "Novato", p.effect, "div", "pftitle")}${p.nick ? fxName(p.nick, p.effect, "div", "pfnick") : ""}
        <small>${+p.prestige ? cEsc(prestLabel(+p.prestige)) + " · " : ""}nível ${+p.level || 1}${p.sub ? " · " + cEsc(p.sub) : ""}</small></div></div></div>
    ${blocks ? `<div class="pfblocks">${blocks}</div>` : ""}</div>`;
}

// ---------------------------------------------------------------- animações: param com "reduzir movimento", bateria fraca ou o interruptor
const ANIM = { pref: true, low: false };
function animSync() {
  const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.documentElement.classList.toggle("noanim", !ANIM.pref || reduce || ANIM.low);
}
try {
  if (navigator.getBattery) navigator.getBattery().then((b) => {
    const upd = () => { ANIM.low = !b.charging && b.level <= 0.2; animSync(); };
    b.addEventListener("levelchange", upd); b.addEventListener("chargingchange", upd); upd();
  }).catch(() => {});
  matchMedia("(prefers-reduced-motion: reduce)").addEventListener?.("change", animSync);
} catch {}
