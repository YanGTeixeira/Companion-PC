// Ranking público do Companion PC (Cloudflare Worker + D1).
//
// O PC envia só um resumo: nível/XP, XP da semana, sequência e quantos troféus (nada de tempo de tela ou apps).
// Sem e-mail nem senha: no cadastro o servidor devolve um id e uma chave secreta; guarda só o sha256 da chave.
// Como os números vêm do PC de cada um, o servidor recusa o que é impossível (XP que diminui, XP demais por
// dia, semana errada) e recalcula o nível ele mesmo.
//
// Rotas (JSON):
//   POST   /v1/register  {nick}                 -> {id, key, nick}
//   POST   /v1/submit    {xp, week, week_xp, streak, best_streak, unlocked}   (Authorization: Bearer id.key)
//   POST   /v1/nick      {nick}                 (troca o apelido; 1 vez por dia)
//   GET    /v1/me                               -> posições do próprio usuário
//   DELETE /v1/me                               -> apaga a conta e os dados
//   GET    /v1/board?kind=week|level|streak     -> top 50 (cache de 60 s)

import { MIN_SUBMIT_S, MAX_STRIKES, REGS_PER_DAY, SOFT, checkNick, checkSubmit, isoWeek, levelOf, nickKey, normNick, weekDay } from "./logic.js";

const BOARD_LIMIT = 50;

async function sha256(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function rand(bytes) {
  const a = crypto.getRandomValues(new Uint8Array(bytes));
  return btoa(String.fromCharCode(...a)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS" };
function json(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", ...CORS, ...extra } });
}
const fail = (status, error) => json({ error }, status);
const int = (v) => (Number.isFinite(+v) ? Math.max(0, Math.floor(+v)) : NaN);

async function auth(req, env) {
  const m = /^Bearer ([A-Za-z0-9_-]{8,32})\.([A-Za-z0-9_-]{20,64})$/.exec(req.headers.get("authorization") || "");
  if (!m) return null;
  const u = await env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(m[1]).first();
  if (!u || u.key_hash !== (await sha256(m[2]))) return null;
  return u;
}
async function body(req) {
  try { return await req.json(); } catch { return {}; }
}

// ------------------------------------------------------------------ rotas
async function register(req, env) {
  const b = await body(req);
  const bad = checkNick(b.nick);
  if (bad) return fail(400, bad);
  const ip = await sha256((req.headers.get("cf-connecting-ip") || "?") + env.IP_SALT);
  const day = new Date().toISOString().slice(0, 10);
  const r = await env.DB.prepare("SELECT n FROM regs WHERE ip_hash = ? AND day = ?").bind(ip, day).first();
  if (r && r.n >= REGS_PER_DAY) return fail(429, "cadastros demais hoje a partir desta rede");
  const nick = normNick(b.nick), id = rand(9), key = rand(32), now = Math.floor(Date.now() / 1000);
  try {
    await env.DB.batch([
      env.DB.prepare("INSERT INTO users (id, key_hash, nick, nick_lc, created) VALUES (?, ?, ?, ?, ?)").bind(id, await sha256(key), nick, nickKey(nick), now),
      env.DB.prepare("INSERT INTO regs VALUES (?, ?, 1) ON CONFLICT(ip_hash, day) DO UPDATE SET n = n + 1").bind(ip, day),
    ]);
  } catch (e) {
    if (/UNIQUE/i.test(String(e))) return fail(409, "esse apelido já está em uso");
    throw e;
  }
  return json({ id, key, nick });
}

async function submit(req, env, u) {
  const now = Math.floor(Date.now() / 1000);
  if (now - u.last_submit < +(env.MIN_SUBMIT_S ?? MIN_SUBMIT_S)) return fail(429, "cedo demais");
  const b = await body(req);
  const s = { xp: int(b.xp), week: String(b.week || ""), week_xp: int(b.week_xp), streak: int(b.streak),
    best_streak: int(b.best_streak), unlocked: int(b.unlocked) };
  const d = new Date(now * 1000);
  const weeks = { cur: isoWeek(d), prev: isoWeek(new Date((now - 7 * 86400) * 1000)), next: isoWeek(new Date((now + 7 * 86400) * 1000)) };
  const weekRow = await env.DB.prepare("SELECT xp FROM weeks WHERE user_id = ? AND week = ?").bind(u.id, s.week).first();
  const bad = checkSubmit(u, s, now, weekRow, weeks, weekDay(d));
  if (bad && SOFT.has(bad)) return fail(422, bad);
  if (bad) {
    await env.DB.prepare("UPDATE users SET strikes = strikes + 1, hidden = CASE WHEN strikes + 1 >= ? THEN 1 ELSE hidden END WHERE id = ?")
      .bind(MAX_STRIKES, u.id).run();
    return fail(422, bad);
  }
  await env.DB.batch([
    env.DB.prepare("UPDATE users SET xp = ?, level = ?, streak = ?, best_streak = ?, unlocked = ?, last_submit = ? WHERE id = ?")
      .bind(s.xp, levelOf(s.xp), s.streak, s.best_streak, s.unlocked, now, u.id),
    env.DB.prepare("INSERT INTO weeks VALUES (?, ?, ?) ON CONFLICT(user_id, week) DO UPDATE SET xp = excluded.xp").bind(u.id, s.week, s.week_xp),
  ]);
  return json({ ok: true, level: levelOf(s.xp) });
}

async function changeNick(req, env, u) {
  const now = Math.floor(Date.now() / 1000);
  if (now - u.nick_changed < 86400) return fail(429, "dá para trocar o apelido uma vez por dia");
  const b = await body(req);
  const bad = checkNick(b.nick);
  if (bad) return fail(400, bad);
  const nick = normNick(b.nick);
  try {
    await env.DB.prepare("UPDATE users SET nick = ?, nick_lc = ?, nick_changed = ? WHERE id = ?").bind(nick, nickKey(nick), now, u.id).run();
  } catch (e) {
    if (/UNIQUE/i.test(String(e))) return fail(409, "esse apelido já está em uso");
    throw e;
  }
  return json({ nick });
}

const BOARDS = {
  week: (week) => ["SELECT u.nick, w.xp AS value, u.level, u.streak, u.unlocked FROM weeks w JOIN users u ON u.id = w.user_id " +
    "WHERE w.week = ? AND u.hidden = 0 AND w.xp > 0 ORDER BY w.xp DESC, u.created LIMIT ?", [week, BOARD_LIMIT]],
  level: () => ["SELECT nick, xp AS value, level, streak, unlocked FROM users WHERE hidden = 0 AND xp > 0 ORDER BY xp DESC, created LIMIT ?", [BOARD_LIMIT]],
  streak: () => ["SELECT nick, streak AS value, level, streak, unlocked FROM users WHERE hidden = 0 AND streak > 0 ORDER BY streak DESC, xp DESC LIMIT ?", [BOARD_LIMIT]],
};

async function board(req, env, ctx, url) {
  const kind = url.searchParams.get("kind") || "week";
  if (!BOARDS[kind]) return fail(400, "ranking inválido");
  const cache = caches.default, key = new Request(`https://board.cache/${kind}/${isoWeek()}`);
  const hit = await cache.match(key);
  if (hit) return hit;
  const week = isoWeek();
  const [sql, args] = BOARDS[kind](week);
  const { results } = await env.DB.prepare(sql).bind(...args).all();
  const total = await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE hidden = 0 AND xp > 0").first();
  const res = json({ kind, week, players: total?.n || 0, rows: results.map((r, i) => ({ rank: i + 1, ...r })) }, 200,
    { "cache-control": "public, max-age=60" });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

async function me(env, u) {
  const week = isoWeek();
  const w = await env.DB.prepare("SELECT xp FROM weeks WHERE user_id = ? AND week = ?").bind(u.id, week).first();
  const wxp = w?.xp || 0;
  const q = (sql, ...a) => env.DB.prepare(sql).bind(...a).first().then((r) => (r?.n || 0) + 1);
  const ranks = {
    week: wxp ? await q("SELECT COUNT(*) AS n FROM weeks w JOIN users u ON u.id = w.user_id WHERE w.week = ? AND u.hidden = 0 AND w.xp > ?", week, wxp) : null,
    level: u.xp ? await q("SELECT COUNT(*) AS n FROM users WHERE hidden = 0 AND xp > ?", u.xp) : null,
    streak: u.streak ? await q("SELECT COUNT(*) AS n FROM users WHERE hidden = 0 AND streak > ?", u.streak) : null,
  };
  return json({ nick: u.nick, hidden: !!u.hidden, xp: u.xp, level: u.level, streak: u.streak, week, week_xp: wxp, ranks });
}

async function remove(env, u) {
  await env.DB.batch([
    env.DB.prepare("DELETE FROM weeks WHERE user_id = ?").bind(u.id),
    env.DB.prepare("DELETE FROM users WHERE id = ?").bind(u.id),
  ]);
  return json({ ok: true });
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url), p = url.pathname, m = req.method;
    if (m === "OPTIONS") return new Response(null, { headers: CORS });
    try {
      if (p === "/v1/board" && m === "GET") return await board(req, env, ctx, url);
      if (p === "/v1/register" && m === "POST") return await register(req, env);
      if (["/v1/submit", "/v1/nick", "/v1/me"].includes(p)) {
        const u = await auth(req, env);
        if (!u) return fail(401, "chave inválida");
        if (p === "/v1/submit" && m === "POST") return await submit(req, env, u);
        if (p === "/v1/nick" && m === "POST") return await changeNick(req, env, u);
        if (p === "/v1/me" && m === "GET") return await me(env, u);
        if (p === "/v1/me" && m === "DELETE") return await remove(env, u);
      }
      if (p === "/") return json({ name: "Companion PC ranking", week: isoWeek() });
      return fail(404, "não encontrado");
    } catch (e) {
      console.error(e);
      return fail(500, "erro no servidor");
    }
  },
};
