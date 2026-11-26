-- 1.18: perfil (título, moldura, vitrine), ligas semanais, amigos e duelos.
-- Rodar uma vez no banco que já existia: npx wrangler d1 execute companion-ranking --remote --file=migrations/0002_social.sql
ALTER TABLE users ADD COLUMN title TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN frame TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN show TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN league INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN league_res TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN league_week TEXT NOT NULL DEFAULT '';

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
