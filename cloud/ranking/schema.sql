-- Ranking público do Companion PC (Cloudflare D1). Banco novo: este arquivo. Banco da 1.17: migrations/0002_social.sql
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,            -- público (aparece só para o próprio PC)
  key_hash TEXT NOT NULL,         -- sha256 da chave secreta; a chave fica só no PC
  nick TEXT NOT NULL,
  nick_lc TEXT NOT NULL UNIQUE,   -- apelido normalizado (único sem diferenciar maiúsculas/acentos)
  created INTEGER NOT NULL,
  last_submit INTEGER NOT NULL DEFAULT 0,
  nick_changed INTEGER NOT NULL DEFAULT 0,
  xp INTEGER NOT NULL DEFAULT 0,
  level INTEGER NOT NULL DEFAULT 1,
  streak INTEGER NOT NULL DEFAULT 0,
  best_streak INTEGER NOT NULL DEFAULT 0,
  unlocked INTEGER NOT NULL DEFAULT 0,
  strikes INTEGER NOT NULL DEFAULT 0, -- envios recusados (números impossíveis)
  hidden INTEGER NOT NULL DEFAULT 0,  -- 1 = fora do ranking (moderação ou strikes demais)
  title TEXT NOT NULL DEFAULT '',     -- 1.18: ids do título, da moldura e da vitrine (até 3, separados por vírgula)
  frame TEXT NOT NULL DEFAULT '',
  show TEXT NOT NULL DEFAULT '',
  league INTEGER NOT NULL DEFAULT 0,  -- liga atual (0 Bronze ... 5 Diamante)
  league_res TEXT NOT NULL DEFAULT '',-- resultado da última semana fechada: up, down, stay
  league_week TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS users_xp ON users (hidden, xp DESC);
CREATE INDEX IF NOT EXISTS users_streak ON users (hidden, streak DESC);

CREATE TABLE IF NOT EXISTS weeks (
  user_id TEXT NOT NULL,
  week TEXT NOT NULL,             -- semana ISO, ex.: 2026-W48
  xp INTEGER NOT NULL,
  PRIMARY KEY (user_id, week)
);
CREATE INDEX IF NOT EXISTS weeks_board ON weeks (week, xp DESC);

-- limite de cadastros por IP (guardado só como hash) e por dia
CREATE TABLE IF NOT EXISTS regs (ip_hash TEXT NOT NULL, day TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (ip_hash, day));

-- ligas: em que grupo cada um ficou em cada semana (o XP vem de weeks)
CREATE TABLE IF NOT EXISTS league_members (
  week TEXT NOT NULL,
  user_id TEXT NOT NULL,
  league INTEGER NOT NULL,        -- 0 Bronze ... 5 Diamante
  grp INTEGER NOT NULL,           -- grupo de até 20 dentro da liga
  PRIMARY KEY (week, user_id)
);
CREATE INDEX IF NOT EXISTS league_groups ON league_members (week, league, grp);
CREATE INDEX IF NOT EXISTS league_user ON league_members (user_id, week);

-- quem segue quem (amigos)
CREATE TABLE IF NOT EXISTS follows (user_id TEXT NOT NULL, friend_id TEXT NOT NULL, created INTEGER NOT NULL, PRIMARY KEY (user_id, friend_id));
CREATE INDEX IF NOT EXISTS follows_back ON follows (friend_id);

-- duelos de XP da semana: a desafia b; a0/b0 = XP da semana de cada um quando b aceitou
CREATE TABLE IF NOT EXISTS duels (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  week TEXT NOT NULL,
  a TEXT NOT NULL,
  b TEXT NOT NULL,
  status TEXT NOT NULL,           -- pending, active, declined, cancelled
  a0 INTEGER NOT NULL DEFAULT 0,
  b0 INTEGER NOT NULL DEFAULT 0,
  created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS duels_a ON duels (a, week);
CREATE INDEX IF NOT EXISTS duels_b ON duels (b, week);
