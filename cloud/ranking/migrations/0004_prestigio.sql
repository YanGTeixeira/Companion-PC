-- 1.21: prestígio (1 a 10, e 11 = Mestre) e o XP total na hora do último (o nível conta a partir dele).
-- Rodar uma vez no banco que já existia: npx wrangler d1 execute companion-ranking --remote --file=migrations/0004_prestigio.sql
ALTER TABLE users ADD COLUMN prestige INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN pxp INTEGER NOT NULL DEFAULT 0;
-- o nível agora vai até o 30 (curva 17·N·(N−1)): recalcula de quem já está no banco
UPDATE users SET level = MIN(30, level) WHERE level > 30;
