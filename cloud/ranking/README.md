# Ranking público do Companion PC

Um Cloudflare Worker com banco D1 (grátis até 100 mil acessos/dia). O PC de cada pessoa envia só um resumo:
apelido, XP total e da semana, sequência, quantos troféus e os ids do título, da moldura e da vitrine (nada de
tempo de tela, apps ou horários). Desde a 1.18 também tem ligas semanais, amigos (quem você segue) e duelos. Sem e-mail
nem senha: no cadastro o servidor devolve uma chave secreta, que fica no `config.json` do PC; aqui fica só o hash.

O servidor recusa números impossíveis (XP que diminui, XP demais por dia, semana errada), recalcula o nível e
limita cadastros (5 por rede por dia) e envios (1 a cada 4 min). Quem manda números impossíveis 10 vezes sai do
ranking sozinho. Regras e limites: `src/logic.js`.

## Publicar (uma vez)

Precisa do Node.js 18 ou mais novo.

```sh
cd cloud/ranking
npm install
npx wrangler login                         # abre o navegador para entrar na conta da Cloudflare
npx wrangler d1 create companion-ranking   # copie o "database_id" que aparecer para o wrangler.toml
npx wrangler d1 execute companion-ranking --remote --file=schema.sql
npx wrangler deploy                        # mostra o endereço: https://companion-ranking.<sua-conta>.workers.dev
```

Depois, coloque esse endereço em `URL` no `windows/server/ranking.py` e lance uma versão nova.
Publicado em https://companion-ranking.yancubot.workers.dev (desde a 1.17).

## Atualizar

`npx wrangler deploy` de novo. Mudanças no banco ficam em `migrations/` (rode cada uma uma vez, antes do deploy):

```sh
npx wrangler d1 execute companion-ranking --remote --file=migrations/0002_social.sql   # 1.18: perfil, ligas, amigos, duelos
```

Um banco novo usa só o `schema.sql` (já tem tudo).

## Testar

```sh
npm test                                   # regras (Node puro)
npx wrangler d1 execute companion-ranking --local --file=schema.sql
npx wrangler dev --local --var MIN_SUBMIT_S:0   # servidor local em http://127.0.0.1:8787
```

## Moderar

```sh
# tirar alguém do ranking (apelido ofensivo, números estranhos)
npx wrangler d1 execute companion-ranking --remote --command "UPDATE users SET hidden = 1 WHERE nick = 'Apelido'"
# ver quem tem mais envios recusados
npx wrangler d1 execute companion-ranking --remote --command "SELECT nick, xp, strikes, hidden FROM users ORDER BY strikes DESC LIMIT 20"
```
A lista de palavras proibidas em apelidos fica em `BANNED`, no `src/logic.js`.
