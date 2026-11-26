-- 1.19: perfil personalizado (fundo, avatar, efeito no nome, cor, ordem dos blocos e frase), vitrine com até 6.
-- Rodar uma vez no banco que já existia: npx wrangler d1 execute companion-ranking --remote --file=migrations/0003_perfil.sql
ALTER TABLE users ADD COLUMN profile TEXT NOT NULL DEFAULT '';
