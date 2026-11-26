// Regras do ranking (sem nada da Cloudflare: dá para testar com o Node puro, veja test/logic.test.mjs).
export const DAY_CAP = 4500;          // XP máximo plausível num dia (foco, metas e partidas x sequência x dia em dobro + desafios e chefão)
export const CONQ_XP = 8000;          // XP de todas as conquistas juntas (podem cair no mesmo dia; 7350 na 1.18)
export const FIRST_MAX = 60000;       // 1º envio traz o histórico: até ~nível 35
export const MIN_SUBMIT_S = 240;      // intervalo mínimo entre envios do mesmo PC
export const REGS_PER_DAY = 5;        // cadastros por IP por dia
export const MAX_STRIKES = 10;        // envios impossíveis até sair do ranking

// ------------------------------------------------------------------ utilidades
// 1.21: igual ao colecao.py: o nível N começa em 17·N·(N−1) e vai até o 30; depois, prestígio (1 a 10, e 11 = Mestre)
export const LEVEL_K = 17, LEVEL_MAX = 30, PRESTIGE_MAX = 11;
export const XP_MAX_LEVEL = LEVEL_K * LEVEL_MAX * (LEVEL_MAX - 1);
export function levelOf(xp) {
  let n = 1;
  while (n < LEVEL_MAX && LEVEL_K * (n + 1) * n <= xp) n++;
  return n;
}

export function isoWeek(d = new Date()) {   // "2026-W48" (semana ISO, segunda a domingo, em UTC)
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  const w = Math.ceil(((t - y0) / 86400000 + 1) / 7);
  return `${t.getUTCFullYear()}-W${String(w).padStart(2, "0")}`;
}

export function weekDay(d = new Date()) {   // 1 = segunda ... 7 = domingo (UTC)
  return d.getUTCDay() || 7;
}

// apelido: 3-20 letras/números/espaço/_.-; sem palavrão nem nome reservado
const BANNED = ["porra", "caralh", "buceta", "bucet", "puta", "viado", "cuzao", "merda", "foder", "fodas", "arrombad",
  "piroca", "xoxota", "bosta", "retardad", "estupr", "pedof", "nazi", "hitler", "fuck", "shit", "bitch", "nigg",
  "fagg", "cunt", "whore", "rapist", "admin", "moderador", "companion", "anthropic", "suporte", "oficial"];
const LEET = { 0: "o", 1: "i", 3: "e", 4: "a", 5: "s", 7: "t", "@": "a", $: "s", "!": "i" };
// a frase do perfil: os mesmos palavrões, sem os nomes reservados (que só valem para o apelido)
const BANNED_BIO = BANNED.filter((w) => !["admin", "moderador", "companion", "anthropic", "suporte", "oficial"].includes(w));

export function normNick(nick) {
  return String(nick || "").trim().replace(/\s+/g, " ");
}
export function nickKey(nick) {        // para comparar: minúsculas, sem acento, sem espaços/símbolos
  return normNick(nick).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]/g, "");
}
export function checkNick(nick) {
  const n = normNick(nick);
  if (!/^[\p{L}\p{N}_.\- ]{3,20}$/u.test(n)) return "o apelido precisa ter de 3 a 20 letras, números, espaço, _ . ou -";
  const flat = n.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[0-9@$!]/g, (c) => LEET[c] ?? c).replace(/[^a-z]/g, "");
  if (BANNED.some((w) => flat.includes(w))) return "escolha outro apelido";
  if (nickKey(n).length < 3) return "o apelido precisa ter pelo menos 3 letras ou números";
  return null;
}

// ------------------------------------------------------------------ validação do envio
// Devolve null se o envio é plausível, senão o motivo. now: segundos (epoch). weeks: {cur, prev, next} (UTC).
// A semana do PC é a do fuso dele: perto da virada, aceita a anterior (segunda em UTC) ou a seguinte (domingo em UTC).
export const SOFT = new Set(["semana errada", "semana já fechou"]);   // problema de relógio/fuso: não conta strike
export function checkSubmit(u, s, now, weekRow, weeks, wday) {
  for (const k of ["xp", "week_xp", "streak", "best_streak", "unlocked"]) if (Number.isNaN(s[k])) return `campo inválido: ${k}`;
  const ok = s.week === weeks.cur || (s.week === weeks.prev && wday === 1) || (s.week === weeks.next && wday === 7);
  if (!ok) return s.week === weeks.prev ? "semana já fechou" : "semana errada";
  if (s.xp < u.xp) return "XP não pode diminuir";
  const first = !u.last_submit;
  const days = Math.max(1, Math.ceil((now - (u.last_submit || now)) / 86400));
  if (first ? s.xp > FIRST_MAX : s.xp - u.xp > days * DAY_CAP + CONQ_XP) return "XP demais de uma vez";
  if (s.week_xp > s.xp) return "XP da semana maior que o total";
  const wdays = s.week === weeks.cur ? wday : s.week === weeks.next ? 1 : 7;
  if (s.week_xp > wdays * DAY_CAP + CONQ_XP) return "XP da semana demais";
  if (weekRow && s.week_xp < weekRow.xp) return "XP da semana não pode diminuir";
  if (s.streak > 1000 || s.best_streak > 1000 || s.streak > s.best_streak) return "sequência inválida";
  if (s.unlocked > 200) return "conquistas demais";
  // 1.21: prestígio. pxp = o XP total na hora do último prestígio; cada um exige um nível 30 inteiro
  const up = u.prestige || 0, upxp = u.pxp || 0;
  if (Number.isNaN(s.prestige) || Number.isNaN(s.pxp) || s.prestige > PRESTIGE_MAX) return "prestígio inválido";
  if (s.pxp > s.xp || s.pxp < s.prestige * XP_MAX_LEVEL || (!s.prestige && s.pxp)) return "prestígio inválido";
  if (s.prestige < up || (s.prestige === up && s.pxp !== upxp)) return "prestígio não pode voltar";
  if (s.prestige > up + 1 && !first) return "prestígio demais de uma vez";
  return null;
}


// ------------------------------------------------------------------ perfil (1.18): título, moldura e vitrine
// 1.19: fundo, avatar, efeito no nome, cor de destaque, ordem dos blocos e uma frase curta. Ids só do catálogo
// (o mesmo do windows/server/colecao.py; um teste do PC confere); a frase passa pelo filtro de palavrões.
export const ID_RE = /^[a-z0-9_]{1,20}$/;
export const SHOW_MAX = 6;
export const BIO_MAX = 60;
export const PROFILE_IDS = {
  bg: ["b_nenhum", "b_grade", "b_cidade", "b_montanhas", "b_espaco", "b_sol", "b_circuito", "b_aurora", "b_castelo", "b_lava",
    "b_oceano", "b_floresta", "b_chuva", "b_natal", "b_halloween", "b_vortice"],
  avatar: ["av_nivel", "av_robo", "av_gato", "av_controle", "av_fantasma", "av_alien", "av_caveira", "av_ninja", "av_coroa",
    "av_dragao", "av_coruja", "av_espada", "av_foguete", "av_slime", "av_cogumelo", "av_pinguim", "av_mago", "av_neve",
    "av_abobora", "av_mascara", "av_estrela", "av_fenix"],
  effect: ["e_nenhum", "e_brilho", "e_gradiente", "e_fogo", "e_arco", "e_glitch", "e_gelo", "e_neon", "e_ouro", "e_confete", "e_cintilante", "e_mestre", "e_prisma"],
  accent: ["a_tema", "a_livre", "a_holo", "a_arco", "a_brasa", "a_plasma", "a_ouro"],
};
export const LAY_BLOCKS = ["bio", "stats", "show", "recent", "league"];

export function cleanBio(v) {
  const s = String(typeof v === "string" ? v : "").replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2066-\u2069]/g, "")
    .replace(/\s+/g, " ").trim().slice(0, BIO_MAX);
  if (!s) return "";
  const flat = s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[0-9@$!]/g, (c) => LEET[c] ?? c).replace(/[^a-z]/g, "");
  return BANNED_BIO.some((w) => flat.includes(w)) ? "" : s;
}

export function cleanProfile(b) {
  const id = (v) => (typeof v === "string" && ID_RE.test(v) ? v : "");
  const show = Array.isArray(b?.show) ? [...new Set(b.show.filter((v) => typeof v === "string" && ID_RE.test(v)))].slice(0, SHOW_MAX) : [];
  const p = b?.profile && typeof b.profile === "object" ? b.profile : {};
  const pick = (k, v) => (PROFILE_IDS[k].includes(v) ? v : PROFILE_IDS[k][0]);
  const pf = { bg: pick("bg", p.bg), av: pick("avatar", p.avatar), fx: pick("effect", p.effect), acc: pick("accent", p.accent),
    bio: cleanBio(p.bio), lay: Array.isArray(p.lay) ? [...new Set(p.lay.filter((x) => LAY_BLOCKS.includes(x)))] : ["bio", "stats", "show"] };
  if (pf.acc === "a_livre" && typeof p.color === "string" && /^#[0-9a-f]{6}$/i.test(p.color)) pf.col = p.color.toLowerCase();
  else if (pf.acc === "a_livre") pf.acc = "a_tema";
  return { title: id(b?.title), frame: id(b?.frame), show: show.join(","), profile: JSON.stringify(pf) };
}

// o que as listas (ranking, liga, amigos, duelos) mostram de cada um: avatar e efeito no nome
export function readProfile(s) {
  try { const p = JSON.parse(s || "{}"); return p && typeof p === "object" ? p : {}; } catch { return {}; }
}
export function pfMini(s) {
  const p = readProfile(s);
  return { av: p.av || "av_nivel", fx: p.fx || "e_nenhum" };
}

// ------------------------------------------------------------------ ligas semanais (1.18)
// Grupos de até GROUP_SIZE pessoas da mesma liga, formados na 1ª vez que alguém envia na semana. Na semana
// seguinte, quem ficou no topo do grupo sobe (com um mínimo de XP) e quem ficou no fim (ou zerou) desce.
export const LEAGUES = ["Bronze", "Prata", "Ouro", "Safira", "Rubi", "Diamante"];
export const GROUP_SIZE = 20;
export const PROMOTE_MIN_XP = 200;
export function leagueZones(n) {
  return { up: Math.max(1, Math.floor(n / 4)), down: n >= 5 ? Math.max(1, Math.floor(n / 5)) : 0 };
}
export function leagueAfter(league, rank, n, xp) {
  const { up, down } = leagueZones(n);
  if (rank <= up && xp >= PROMOTE_MIN_XP && league < LEAGUES.length - 1) return { league: league + 1, res: "up" };
  if (league > 0 && (xp <= 0 || rank > n - down)) return { league: league - 1, res: "down" };
  return { league, res: "stay" };
}

// ------------------------------------------------------------------ duelos (1.18)
// Duelo de XP da semana: conta o que cada um ganhou desde que o duelo foi aceito até o fim da semana.
export const DUELS_OPEN = 3;          // duelos seus (pendentes + valendo) por semana
export const DUELS_INBOX = 5;         // convites pendentes que alguém pode receber
export const FRIENDS_MAX = 50;
export function duelView(d, me, xpA, xpB, curWeek) {
  const mine = d.a === me;
  const sa = Math.max(0, xpA - (d.a0 || 0)), sb = Math.max(0, xpB - (d.b0 || 0));
  const my = mine ? sa : sb, their = mine ? sb : sa;
  let status = d.status;
  if (d.week < curWeek) status = d.status === "active" ? "done" : d.status === "pending" ? "expired" : d.status;
  const res = status === "done" ? (my > their ? "won" : my < their ? "lost" : "tie") : null;
  return { id: d.id, week: d.week, dir: mine ? "out" : "in", status, res,
    my: status === "active" || status === "done" ? my : null, their: status === "active" || status === "done" ? their : null };
}
