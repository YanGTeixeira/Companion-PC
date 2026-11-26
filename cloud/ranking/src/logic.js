// Regras do ranking (sem nada da Cloudflare: dá para testar com o Node puro, veja test/logic.test.mjs).
export const DAY_CAP = 2500;          // XP máximo plausível num dia (foco 300 + metas 200 + muitas partidas)
export const CONQ_XP = 4050;          // XP de todas as conquistas juntas (podem cair no mesmo dia)
export const FIRST_MAX = 60000;       // 1º envio traz o histórico: até ~nível 35
export const MIN_SUBMIT_S = 240;      // intervalo mínimo entre envios do mesmo PC
export const REGS_PER_DAY = 5;        // cadastros por IP por dia
export const MAX_STRIKES = 10;        // envios impossíveis até sair do ranking

// ------------------------------------------------------------------ utilidades
export function levelOf(xp) {          // igual ao conquistas.py: o nível N começa em 50·N·(N−1)
  let n = 1;
  while (50 * (n + 1) * n <= xp) n++;
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
  if (s.unlocked > 100) return "conquistas demais";
  return null;
}

