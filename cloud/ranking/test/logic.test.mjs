// Regras do ranking. Rodar: node --test test/
import assert from "node:assert/strict";
import { test } from "node:test";
import { XP_MAX_LEVEL } from "../src/logic.js";
import { CONQ_XP, DAY_CAP, FIRST_MAX, checkNick, checkSubmit, cleanProfile, duelView, pfMini, readProfile, isoWeek, leagueAfter, leagueZones, levelOf, nickKey, weekDay } from "../src/logic.js";

test("nível igual ao conquistas.py", () => {
  assert.equal(levelOf(0), 1);          // 1.21: 17·N·(N−1), até o 30
  assert.equal(levelOf(33), 1);
  assert.equal(levelOf(34), 2);
  assert.equal(levelOf(1530), 10);
  assert.equal(levelOf(XP_MAX_LEVEL - 1), 29);
  assert.equal(levelOf(XP_MAX_LEVEL), 30);
  assert.equal(levelOf(10 ** 7), 30);
});

test("semana ISO em UTC", () => {
  assert.equal(isoWeek(new Date("2026-11-26T12:00:00Z")), "2026-W48");
  assert.equal(isoWeek(new Date("2026-11-29T23:59:59Z")), "2026-W48");   // domingo
  assert.equal(isoWeek(new Date("2026-11-30T00:00:00Z")), "2026-W49");   // segunda
  assert.equal(isoWeek(new Date("2027-01-01T12:00:00Z")), "2026-W53");   // 2026 tem 53 semanas
  assert.equal(isoWeek(new Date("2027-01-04T12:00:00Z")), "2027-W01");
  assert.equal(weekDay(new Date("2026-11-29T12:00:00Z")), 7);
  assert.equal(weekDay(new Date("2026-11-30T12:00:00Z")), 1);
});

test("apelidos", () => {
  assert.equal(checkNick("Yan_123"), null);
  assert.equal(checkNick("  João  Silva "), null);
  assert.match(checkNick("ab"), /3 a 20/);
  assert.match(checkNick("a".repeat(21)), /3 a 20/);
  assert.match(checkNick("<script>"), /3 a 20/);
  assert.match(checkNick("..."), /pelo menos 3/);
  for (const bad of ["Caralho", "c4r4lh0", "FUCK you", "p u t a", "Admin", "companion pc"]) assert.equal(checkNick(bad), "escolha outro apelido", bad);
  assert.equal(nickKey("João Silva"), nickKey("joao-silva"));   // "iguais" para o UNIQUE
});

const W = { cur: "2026-W48", prev: "2026-W47", next: "2026-W49" };
const fresh = { xp: 0, last_submit: 0 };
const ok = (o = {}) => ({ xp: 500, week: "2026-W48", week_xp: 300, streak: 2, best_streak: 3, unlocked: 4, prestige: 0, pxp: 0, ...o });
const NOW = 1_800_000_000;

test("envio plausível passa", () => {
  assert.equal(checkSubmit(fresh, ok(), NOW, null, W, 4), null);
  assert.equal(checkSubmit({ xp: 500, last_submit: NOW - 3600 }, ok({ xp: 700, week_xp: 500 }), NOW, { xp: 300 }, W, 4), null);
});

test("números impossíveis são recusados", () => {
  const u = { xp: 1000, last_submit: NOW - 3600 };
  assert.equal(checkSubmit(u, ok({ xp: 900 }), NOW, null, W, 4), "XP não pode diminuir");
  assert.equal(checkSubmit(u, ok({ xp: 1000 + DAY_CAP + CONQ_XP + 1, week_xp: 100 }), NOW, null, W, 4), "XP demais de uma vez");
  assert.equal(checkSubmit({ xp: 1000, last_submit: NOW - 3 * 86400 }, ok({ xp: 1000 + 3 * DAY_CAP, week_xp: 100 }), NOW, null, W, 4), null);
  assert.equal(checkSubmit(fresh, ok({ xp: FIRST_MAX + 1, week_xp: 0 }), NOW, null, W, 4), "XP demais de uma vez");
  assert.equal(checkSubmit(fresh, ok({ week_xp: 600 }), NOW, null, W, 4), "XP da semana maior que o total");
  assert.equal(checkSubmit(fresh, ok({ xp: 50000, week_xp: 2 * DAY_CAP + CONQ_XP + 1 }), NOW, null, W, 2), "XP da semana demais");
  assert.equal(checkSubmit(u, ok({ xp: 1200, week_xp: 200 }), NOW, { xp: 300 }, W, 4), "XP da semana não pode diminuir");
  assert.equal(checkSubmit(fresh, ok({ streak: 5, best_streak: 3 }), NOW, null, W, 4), "sequência inválida");
  assert.equal(checkSubmit(fresh, ok({ unlocked: 201 }), NOW, null, W, 4), "conquistas demais");
  assert.equal(checkSubmit(fresh, ok({ xp: NaN }), NOW, null, W, 4), "campo inválido: xp");
});

test("virada da semana pelo fuso", () => {
  assert.equal(checkSubmit(fresh, ok({ week: "2026-W47" }), NOW, null, W, 1), null);           // Brasil: domingo à noite = segunda UTC
  assert.equal(checkSubmit(fresh, ok({ week: "2026-W47" }), NOW, null, W, 2), "semana já fechou");
  assert.equal(checkSubmit(fresh, ok({ week: "2026-W49" }), NOW, null, W, 7), null);           // Ásia: segunda local = domingo UTC
  assert.equal(checkSubmit(fresh, ok({ week: "2026-W49" }), NOW, null, W, 3), "semana errada");
  assert.equal(checkSubmit(fresh, ok({ week: "2026-W40" }), NOW, null, W, 3), "semana errada");
});

test("perfil: só ids curtos", () => {
  const r = cleanProfile({ title: "coruja", frame: "f_ouro", show: ["foco1", "foco1", "imortal", "x", "y", "z", "w", "v"] });
  assert.deepEqual([r.title, r.frame, r.show], ["coruja", "f_ouro", "foco1,imortal,x,y,z,w"]);   // até 6
  const bad = cleanProfile({ title: "<b>oi</b>", frame: 3, show: "foco1" });
  assert.deepEqual([bad.title, bad.frame, bad.show], ["", "", ""]);
  assert.equal(cleanProfile(null).show, "");
});

test("perfil 1.19: catálogo, cor livre e frase filtrada", () => {
  const p = (x) => JSON.parse(cleanProfile({ profile: x }).profile);
  assert.deepEqual(p({ bg: "b_espaco", avatar: "av_robo", effect: "e_fogo", accent: "a_holo", bio: "  oi   mundo ", lay: ["show", "bio", "show", "xx"] }),
    { bg: "b_espaco", av: "av_robo", fx: "e_fogo", acc: "a_holo", bio: "oi mundo", lay: ["show", "bio"] });
  const d = p({ bg: "<script>", avatar: "av_inventado", effect: 5 });
  assert.deepEqual([d.bg, d.av, d.fx, d.acc], ["b_nenhum", "av_nivel", "e_nenhum", "a_tema"]);
  assert.equal(p({ accent: "a_livre", color: "#FF00aa" }).col, "#ff00aa");
  assert.equal(p({ accent: "a_livre", color: "red" }).acc, "a_tema");       // cor livre sem cor válida
  assert.equal(p({ accent: "a_ouro", color: "#ff00aa" }).col, undefined);   // a cor só vai com a cor livre
  assert.equal(p({ bio: "x".repeat(200) }).bio.length, 60);
  assert.equal(p({ bio: "vai tomar no c* p0rr4" }).bio, "");
  assert.equal(p({ bio: "sou admin do clã" }).bio, "sou admin do clã");    // nome reservado só vale no apelido
  assert.equal(p({ bio: "a\u202eb\u0007c" }).bio, "abc");
  assert.deepEqual(pfMini('{"av":"av_gato","fx":"e_arco"}'), { av: "av_gato", fx: "e_arco" });
  assert.deepEqual(pfMini(""), { av: "av_nivel", fx: "e_nenhum" });
  assert.deepEqual(readProfile("{quebrado"), {});
});

test("ligas: sobe, desce, fica", () => {
  assert.deepEqual(leagueZones(20), { up: 5, down: 4 });
  assert.deepEqual(leagueZones(3), { up: 1, down: 0 });
  assert.deepEqual(leagueAfter(0, 1, 20, 900), { league: 1, res: "up" });
  assert.deepEqual(leagueAfter(0, 1, 20, 100), { league: 0, res: "stay" });     // pouco XP: não sobe
  assert.deepEqual(leagueAfter(2, 18, 20, 300), { league: 1, res: "down" });
  assert.deepEqual(leagueAfter(2, 10, 20, 0), { league: 1, res: "down" });      // zerou a semana
  assert.deepEqual(leagueAfter(0, 20, 20, 0), { league: 0, res: "stay" });      // Bronze não desce
  assert.deepEqual(leagueAfter(5, 1, 20, 9999), { league: 5, res: "stay" });    // Diamante é o topo
  assert.deepEqual(leagueAfter(1, 1, 1, 500), { league: 2, res: "up" });        // sozinho no grupo
});

test("duelos: placar desde o aceite e resultado no fim da semana", () => {
  const d = { id: 1, week: "2026-W48", a: "A", b: "B", status: "active", a0: 100, b0: 50 };
  assert.deepEqual(duelView(d, "A", 400, 300, "2026-W48"), { id: 1, week: "2026-W48", dir: "out", status: "active", res: null, my: 300, their: 250 });
  assert.equal(duelView(d, "B", 400, 300, "2026-W49").res, "lost");
  assert.equal(duelView(d, "A", 400, 300, "2026-W49").res, "won");
  assert.equal(duelView({ ...d, status: "pending" }, "B", 0, 0, "2026-W49").status, "expired");
  assert.equal(duelView({ ...d, status: "pending" }, "B", 0, 0, "2026-W48").my, null);
});

test("prestígio (1.21): só sobe, um por vez, e cada um custa um nível 30 inteiro", () => {
  const X = XP_MAX_LEVEL, u = { xp: X + 100, last_submit: NOW - 3600, prestige: 0, pxp: 0 };
  assert.equal(checkSubmit(u, ok({ xp: X + 200, prestige: 1, pxp: X + 150 }), NOW, null, W, 4), null);
  assert.equal(checkSubmit(u, ok({ xp: X + 200, prestige: 1, pxp: X - 1 }), NOW, null, W, 4), "prestígio inválido");
  assert.equal(checkSubmit(u, ok({ xp: X + 200, prestige: 1, pxp: X + 300 }), NOW, null, W, 4), "prestígio inválido");  // maior que o XP
  const u3 = { ...u, last_submit: NOW - 3 * 86400 };
  assert.equal(checkSubmit(u3, ok({ xp: 2 * X + 200, prestige: 2, pxp: 2 * X + 100 }), NOW, null, W, 4), "prestígio demais de uma vez");
  assert.equal(checkSubmit(u, ok({ xp: X + 200, prestige: 0, pxp: 50 }), NOW, null, W, 4), "prestígio inválido");
  assert.equal(checkSubmit(u, ok({ xp: X + 200, prestige: 12, pxp: X }), NOW, null, W, 4), "prestígio inválido");
  const p1 = { xp: X + 500, last_submit: NOW - 3600, prestige: 1, pxp: X + 150 };
  assert.equal(checkSubmit(p1, ok({ xp: X + 600, prestige: 1, pxp: X + 150 }), NOW, null, W, 4), null);
  assert.equal(checkSubmit(p1, ok({ xp: X + 600, prestige: 1, pxp: X + 160 }), NOW, null, W, 4), "prestígio não pode voltar");
  assert.equal(checkSubmit(p1, ok({ xp: X + 600, prestige: 0, pxp: 0 }), NOW, null, W, 4), "prestígio não pode voltar");
  // PC da 1.20 (não manda prestígio): continua passando
  assert.equal(checkSubmit({ xp: 100, last_submit: NOW - 3600 }, ok({ xp: 200, week_xp: 100 }), NOW, null, W, 4), null);
});
