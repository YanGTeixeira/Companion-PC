// Ranking público do Companion PC (Cloudflare Worker + D1).
//
// O PC envia só um resumo: nível/XP, XP da semana, sequência e quantos troféus (nada de tempo de tela ou apps),
// (1.18) os ids do título, da moldura e da vitrine e (1.19) o perfil: fundo, avatar, efeito, cor, ordem dos blocos
// e uma frase curta (filtrada), com até 6 troféus na vitrine.
// Sem e-mail nem senha: no cadastro o servidor devolve um id e uma chave secreta; guarda só o sha256 da chave.
// Como os números vêm do PC de cada um, o servidor recusa o que é impossível (XP que diminui, XP demais por
// dia, semana errada) e recalcula o nível ele mesmo.
//
// Rotas (JSON):
//   POST   /v1/register  {nick}                 -> {id, key, nick}
//   POST   /v1/submit    {xp, week, week_xp, streak, best_streak, unlocked, title, frame, show, profile}  (Authorization: Bearer id.key)
//   POST   /v1/nick      {nick}                 (troca o apelido; 1 vez por dia)
//   GET    /v1/me                               -> posições do próprio usuário
//   DELETE /v1/me                               -> apaga a conta e os dados
//   GET    /v1/board?kind=week|level|streak     -> top 50 (cache de 60 s)
//   GET    /v1/profile?nick=                    -> perfil público (nível, título, moldura, vitrine, liga)
//   1.18 (com a chave):
//   GET    /v1/league                           -> o seu grupo da liga nesta semana
//   GET    /v1/friends | POST {nick} | DELETE ?nick=   -> quem você segue
//   GET    /v1/duels | POST {nick} | POST /v1/duels/answer {id, accept}

import {
  DUELS_INBOX, DUELS_OPEN, FRIENDS_MAX, GROUP_SIZE, LEAGUES, MIN_SUBMIT_S, MAX_STRIKES, REGS_PER_DAY, SOFT,
  checkNick, checkSubmit, cleanProfile, pfMini, readProfile, duelView, isoWeek, leagueAfter, leagueZones, levelOf, nickKey, normNick, weekDay,
} from "./logic.js";

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
const nowS = () => Math.floor(Date.now() / 1000);
const show = (s) => (s ? String(s).split(",").filter(Boolean) : []);

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
const byNick = (env, nick) => env.DB.prepare("SELECT * FROM users WHERE nick_lc = ? AND hidden = 0").bind(nickKey(nick)).first();
const weekXp = async (env, id, week) => (await env.DB.prepare("SELECT xp FROM weeks WHERE user_id = ? AND week = ?").bind(id, week).first())?.xp || 0;

// ------------------------------------------------------------------ rotas
async function register(req, env) {
  const b = await body(req);
  const bad = checkNick(b.nick);
  if (bad) return fail(400, bad);
  const ip = await sha256((req.headers.get("cf-connecting-ip") || "?") + env.IP_SALT);
  const day = new Date().toISOString().slice(0, 10);
  const r = await env.DB.prepare("SELECT n FROM regs WHERE ip_hash = ? AND day = ?").bind(ip, day).first();
  if (r && r.n >= REGS_PER_DAY) return fail(429, "cadastros demais hoje a partir desta rede");
  const nick = normNick(b.nick), id = rand(9), key = rand(32), now = nowS();
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
  const now = nowS();
  if (now - u.last_submit < +(env.MIN_SUBMIT_S ?? MIN_SUBMIT_S)) return fail(429, "cedo demais");
  const b = await body(req);
  const s = { xp: int(b.xp), week: String(b.week || ""), week_xp: int(b.week_xp), streak: int(b.streak),
    best_streak: int(b.best_streak), unlocked: int(b.unlocked), prestige: int(b.prestige ?? 0), pxp: int(b.pxp ?? 0) };
  const p = cleanProfile(b);
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
    env.DB.prepare("UPDATE users SET xp = ?, level = ?, streak = ?, best_streak = ?, unlocked = ?, last_submit = ?, title = ?, frame = ?, show = ?, profile = ?, prestige = ?, pxp = ? WHERE id = ?")
      .bind(s.xp, levelOf(s.xp - s.pxp), s.streak, s.best_streak, s.unlocked, now, p.title, p.frame, p.show, p.profile, s.prestige, s.pxp, u.id),
    env.DB.prepare("INSERT INTO weeks VALUES (?, ?, ?) ON CONFLICT(user_id, week) DO UPDATE SET xp = excluded.xp").bind(u.id, s.week, s.week_xp),
  ]);
  const lg = u.hidden ? null : await leagueEnsure(env, u, weeks.cur);
  return json({ ok: true, level: levelOf(s.xp - s.pxp), prestige: s.prestige, league: lg?.league ?? u.league });
}

async function changeNick(req, env, u) {
  const now = nowS();
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

const COLS = "u.nick, u.level, u.prestige, u.streak, u.unlocked, u.title, u.frame, u.league, u.profile";
// linha de lista: troca o perfil inteiro (JSON) pelo avatar e o efeito no nome
const slim = (r) => { const { profile: pf, ...rest } = r; return { ...rest, ...pfMini(pf) }; };
const BOARDS = {
  week: (week) => [`SELECT ${COLS}, w.xp AS value FROM weeks w JOIN users u ON u.id = w.user_id ` +
    "WHERE w.week = ? AND u.hidden = 0 AND w.xp > 0 ORDER BY w.xp DESC, u.created LIMIT ?", [week, BOARD_LIMIT]],
  // 1.21: prestígio primeiro (★2 nível 12 fica acima de ★1 nível 30), depois o nível e o XP
  level: () => [`SELECT ${COLS}, u.xp AS value FROM users u WHERE hidden = 0 AND xp > 0 ORDER BY prestige DESC, level DESC, xp DESC, created LIMIT ?`, [BOARD_LIMIT]],
  streak: () => [`SELECT ${COLS}, u.streak AS value FROM users u WHERE hidden = 0 AND streak > 0 ORDER BY streak DESC, xp DESC LIMIT ?`, [BOARD_LIMIT]],
};

async function board(req, env, ctx, url) {
  const kind = url.searchParams.get("kind") || "week";
  if (!BOARDS[kind]) return fail(400, "ranking inválido");
  const cache = caches.default, key = new Request(`https://board.cache/v4/${kind}/${isoWeek()}`);
  const hit = await cache.match(key);
  if (hit) return hit;
  const week = isoWeek();
  const [sql, args] = BOARDS[kind](week);
  const { results } = await env.DB.prepare(sql).bind(...args).all();
  const total = await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE hidden = 0 AND xp > 0").first();
  const res = json({ kind, week, players: total?.n || 0, rows: results.map((r, i) => ({ rank: i + 1, ...slim(r) })) }, 200,
    { "cache-control": "public, max-age=60" });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

async function me(env, u) {
  const week = isoWeek();
  const wxp = await weekXp(env, u.id, week);
  const q = (sql, ...a) => env.DB.prepare(sql).bind(...a).first().then((r) => (r?.n || 0) + 1);
  const ranks = {
    week: wxp ? await q("SELECT COUNT(*) AS n FROM weeks w JOIN users u ON u.id = w.user_id WHERE w.week = ? AND u.hidden = 0 AND w.xp > ?", week, wxp) : null,
    level: u.xp ? await q("SELECT COUNT(*) AS n FROM users WHERE hidden = 0 AND (prestige > ? OR (prestige = ? AND (level > ? OR (level = ? AND xp > ?))))",
      u.prestige, u.prestige, u.level, u.level, u.xp) : null,
    streak: u.streak ? await q("SELECT COUNT(*) AS n FROM users WHERE hidden = 0 AND streak > ?", u.streak) : null,
  };
  return json({ nick: u.nick, hidden: !!u.hidden, xp: u.xp, level: u.level, prestige: u.prestige, streak: u.streak, week, week_xp: wxp, ranks,
    league: u.league, title: u.title, frame: u.frame, ...pfMini(u.profile) });
}

async function remove(env, u) {
  await env.DB.batch([
    env.DB.prepare("DELETE FROM weeks WHERE user_id = ?").bind(u.id),
    env.DB.prepare("DELETE FROM league_members WHERE user_id = ?").bind(u.id),
    env.DB.prepare("DELETE FROM follows WHERE user_id = ? OR friend_id = ?").bind(u.id, u.id),
    env.DB.prepare("DELETE FROM duels WHERE a = ? OR b = ?").bind(u.id, u.id),
    env.DB.prepare("DELETE FROM users WHERE id = ?").bind(u.id),
  ]);
  return json({ ok: true });
}

async function profile(env, url) {
  const u = await byNick(env, url.searchParams.get("nick") || "");
  if (!u) return fail(404, "ninguém com esse apelido");
  return json({ nick: u.nick, level: u.level, prestige: u.prestige, xp: u.xp, streak: u.streak, best_streak: u.best_streak, unlocked: u.unlocked,
    title: u.title, frame: u.frame, show: show(u.show), league: u.league, week_xp: await weekXp(env, u.id, isoWeek()),
    pf: readProfile(u.profile) },
  200, { "cache-control": "public, max-age=60" });
}

// ------------------------------------------------------------------ ligas
const GROUP_SQL = "SELECT u.id, u.nick, u.level, u.prestige, u.title, u.frame, u.streak, u.profile, COALESCE(w.xp, 0) AS xp FROM league_members m " +
  "JOIN users u ON u.id = m.user_id LEFT JOIN weeks w ON w.user_id = m.user_id AND w.week = m.week " +
  "WHERE m.week = ? AND m.league = ? AND m.grp = ? AND u.hidden = 0 ORDER BY xp DESC, u.created";

// Entra num grupo da semana (uma vez por semana). Antes, fecha a semana anterior em que participou: sobe, desce ou fica.
async function leagueEnsure(env, u, week) {
  const cur = await env.DB.prepare("SELECT league, grp FROM league_members WHERE week = ? AND user_id = ?").bind(week, u.id).first();
  if (cur) return cur;
  let league = u.league || 0, res = "";
  const last = await env.DB.prepare("SELECT week, league, grp FROM league_members WHERE user_id = ? AND week < ? ORDER BY week DESC LIMIT 1")
    .bind(u.id, week).first();
  if (last) {
    const { results } = await env.DB.prepare(GROUP_SQL).bind(last.week, last.league, last.grp).all();
    const i = results.findIndex((r) => r.id === u.id);
    const after = leagueAfter(last.league, i + 1, results.length, i >= 0 ? results[i].xp : 0);
    league = after.league; res = after.res;
  }
  const open = await env.DB.prepare("SELECT grp, COUNT(*) AS n FROM league_members WHERE week = ? AND league = ? GROUP BY grp HAVING n < ? ORDER BY grp LIMIT 1")
    .bind(week, league, GROUP_SIZE).first();
  const grp = open ? open.grp
    : ((await env.DB.prepare("SELECT MAX(grp) AS m FROM league_members WHERE week = ? AND league = ?").bind(week, league).first())?.m ?? -1) + 1;
  await env.DB.batch([
    env.DB.prepare("INSERT OR IGNORE INTO league_members VALUES (?, ?, ?, ?)").bind(week, u.id, league, grp),
    env.DB.prepare("UPDATE users SET league = ?, league_res = ?, league_week = ? WHERE id = ?").bind(league, res, last?.week || "", u.id),
  ]);
  return { league, grp };
}

async function league(env, u) {
  const week = isoWeek();
  const m = await env.DB.prepare("SELECT league, grp FROM league_members WHERE week = ? AND user_id = ?").bind(week, u.id).first();
  const base = { week, leagues: LEAGUES, league: m?.league ?? u.league ?? 0, res: u.league_res || "", res_week: u.league_week || "" };
  if (!m) return json({ ...base, joined: false, rows: [] });
  const { results } = await env.DB.prepare(GROUP_SQL).bind(week, m.league, m.grp).all();
  const z = leagueZones(results.length);
  return json({ ...base, joined: true, up: z.up, down: m.league > 0 ? z.down : 0,
    rows: results.map((r, i) => ({ rank: i + 1, nick: r.nick, level: r.level, prestige: r.prestige, title: r.title, frame: r.frame, streak: r.streak, xp: r.xp, me: r.id === u.id, ...pfMini(r.profile) })) });
}

// ------------------------------------------------------------------ amigos (quem você segue)
async function friends(env, u) {
  const week = isoWeek();
  const { results } = await env.DB.prepare(
    "SELECT u.nick, u.level, u.prestige, u.title, u.frame, u.streak, u.league, u.unlocked, u.profile, COALESCE(w.xp, 0) AS week_xp, " +
    "EXISTS(SELECT 1 FROM follows b WHERE b.user_id = u.id AND b.friend_id = ?) AS mutual " +
    "FROM follows f JOIN users u ON u.id = f.friend_id LEFT JOIN weeks w ON w.user_id = u.id AND w.week = ? " +
    "WHERE f.user_id = ? AND u.hidden = 0 ORDER BY week_xp DESC, u.xp DESC").bind(u.id, week, u.id).all();
  const followers = await env.DB.prepare("SELECT COUNT(*) AS n FROM follows WHERE friend_id = ?").bind(u.id).first();
  return json({ week, me: { nick: u.nick, level: u.level, prestige: u.prestige, title: u.title, frame: u.frame, streak: u.streak, league: u.league,
    week_xp: await weekXp(env, u.id, week), ...pfMini(u.profile) }, rows: results.map((r) => ({ ...slim(r), mutual: !!r.mutual })), followers: followers?.n || 0 });
}

async function friendAdd(req, env, u) {
  const b = await body(req);
  const f = await byNick(env, String(b.nick || ""));
  if (!f) return fail(404, "ninguém com esse apelido");
  if (f.id === u.id) return fail(400, "esse é você");
  const n = await env.DB.prepare("SELECT COUNT(*) AS n FROM follows WHERE user_id = ?").bind(u.id).first();
  if ((n?.n || 0) >= FRIENDS_MAX) return fail(429, `dá para seguir até ${FRIENDS_MAX} pessoas`);
  await env.DB.prepare("INSERT OR IGNORE INTO follows VALUES (?, ?, ?)").bind(u.id, f.id, nowS()).run();
  return friends(env, u);
}

async function friendDel(env, u, url) {
  const f = await env.DB.prepare("SELECT id FROM users WHERE nick_lc = ?").bind(nickKey(url.searchParams.get("nick") || "")).first();
  if (f) await env.DB.prepare("DELETE FROM follows WHERE user_id = ? AND friend_id = ?").bind(u.id, f.id).run();
  return friends(env, u);
}

// ------------------------------------------------------------------ duelos de XP da semana
async function duels(env, u) {
  const week = isoWeek(), old = isoWeek(new Date(Date.now() - 21 * 86400000));
  const { results } = await env.DB.prepare(
    "SELECT d.*, ua.nick AS na, ub.nick AS nb, ua.title AS ta, ub.title AS tb, ua.frame AS fa, ub.frame AS fb, " +
    "COALESCE(wa.xp, 0) AS xa, COALESCE(wb.xp, 0) AS xb FROM duels d JOIN users ua ON ua.id = d.a JOIN users ub ON ub.id = d.b " +
    "LEFT JOIN weeks wa ON wa.user_id = d.a AND wa.week = d.week LEFT JOIN weeks wb ON wb.user_id = d.b AND wb.week = d.week " +
    "WHERE (d.a = ? OR d.b = ?) AND d.week >= ? ORDER BY d.week DESC, d.created DESC LIMIT 30").bind(u.id, u.id, old).all();
  return json({ week, rows: results.map((d) => {
    const mine = d.a === u.id;
    return { ...duelView(d, u.id, d.xa, d.xb, week), nick: mine ? d.nb : d.na, title: mine ? d.tb : d.ta, frame: mine ? d.fb : d.fa };
  }) });
}

async function duelNew(req, env, u) {
  const b = await body(req), week = isoWeek();
  const f = await byNick(env, String(b.nick || ""));
  if (!f) return fail(404, "ninguém com esse apelido");
  if (f.id === u.id) return fail(400, "esse é você");
  const follows = await env.DB.prepare("SELECT 1 AS x FROM follows WHERE user_id = ? AND friend_id = ?").bind(u.id, f.id).first();
  if (!follows) return fail(400, "siga essa pessoa antes de desafiar");
  const pair = await env.DB.prepare("SELECT id FROM duels WHERE week = ? AND status IN ('pending', 'active') AND ((a = ? AND b = ?) OR (a = ? AND b = ?))")
    .bind(week, u.id, f.id, f.id, u.id).first();
  if (pair) return fail(409, "vocês já têm um duelo nesta semana");
  const mine = await env.DB.prepare("SELECT COUNT(*) AS n FROM duels WHERE week = ? AND status IN ('pending', 'active') AND (a = ? OR b = ?)")
    .bind(week, u.id, u.id).first();
  if ((mine?.n || 0) >= DUELS_OPEN) return fail(429, `no máximo ${DUELS_OPEN} duelos por semana`);
  const inbox = await env.DB.prepare("SELECT COUNT(*) AS n FROM duels WHERE week = ? AND status = 'pending' AND b = ?").bind(week, f.id).first();
  if ((inbox?.n || 0) >= DUELS_INBOX) return fail(429, "essa pessoa já tem convites demais");
  await env.DB.prepare("INSERT INTO duels (week, a, b, status, a0, b0, created) VALUES (?, ?, ?, 'pending', 0, 0, ?)").bind(week, u.id, f.id, nowS()).run();
  return duels(env, u);
}

async function duelAnswer(req, env, u) {
  const b = await body(req), week = isoWeek();
  const d = await env.DB.prepare("SELECT * FROM duels WHERE id = ?").bind(int(b.id)).first();
  if (!d || (d.a !== u.id && d.b !== u.id)) return fail(404, "duelo não encontrado");
  if (d.status !== "pending" || d.week !== week) return fail(409, "esse duelo não está mais aberto");
  if (d.a === u.id) {               // quem desafiou só pode cancelar
    await env.DB.prepare("UPDATE duels SET status = 'cancelled' WHERE id = ?").bind(d.id).run();
  } else if (b.accept) {
    const mine = await env.DB.prepare("SELECT COUNT(*) AS n FROM duels WHERE week = ? AND status = 'active' AND (a = ? OR b = ?)")
      .bind(week, u.id, u.id).first();
    if ((mine?.n || 0) >= DUELS_OPEN) return fail(429, `no máximo ${DUELS_OPEN} duelos por semana`);
    await env.DB.prepare("UPDATE duels SET status = 'active', a0 = ?, b0 = ? WHERE id = ?")
      .bind(await weekXp(env, d.a, week), await weekXp(env, d.b, week), d.id).run();
  } else {
    await env.DB.prepare("UPDATE duels SET status = 'declined' WHERE id = ?").bind(d.id).run();
  }
  return duels(env, u);
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url), p = url.pathname, m = req.method;
    if (m === "OPTIONS") return new Response(null, { headers: CORS });
    try {
      if (p === "/v1/board" && m === "GET") return await board(req, env, ctx, url);
      if (p === "/v1/profile" && m === "GET") return await profile(env, url);
      if (p === "/v1/register" && m === "POST") return await register(req, env);
      if (["/v1/submit", "/v1/nick", "/v1/me", "/v1/league", "/v1/friends", "/v1/duels", "/v1/duels/answer"].includes(p)) {
        const u = await auth(req, env);
        if (!u) return fail(401, "chave inválida");
        if (p === "/v1/submit" && m === "POST") return await submit(req, env, u);
        if (p === "/v1/nick" && m === "POST") return await changeNick(req, env, u);
        if (p === "/v1/me" && m === "GET") return await me(env, u);
        if (p === "/v1/me" && m === "DELETE") return await remove(env, u);
        if (p === "/v1/league" && m === "GET") return await league(env, u);
        if (p === "/v1/friends" && m === "GET") return await friends(env, u);
        if (p === "/v1/friends" && m === "POST") return await friendAdd(req, env, u);
        if (p === "/v1/friends" && m === "DELETE") return await friendDel(env, u, url);
        if (p === "/v1/duels" && m === "GET") return await duels(env, u);
        if (p === "/v1/duels" && m === "POST") return await duelNew(req, env, u);
        if (p === "/v1/duels/answer" && m === "POST") return await duelAnswer(req, env, u);
      }
      if (p === "/") return json({ name: "Companion PC ranking", week: isoWeek() });
      return fail(404, "não encontrado");
    } catch (e) {
      console.error(e);
      return fail(500, "erro no servidor");
    }
  },
};
