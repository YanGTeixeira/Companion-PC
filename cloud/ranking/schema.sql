-- Ranking público do Companion PC (Cloudflare D1)
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
  hidden INTEGER NOT NULL DEFAULT 0   -- 1 = fora do ranking (moderação ou strikes demais)
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
