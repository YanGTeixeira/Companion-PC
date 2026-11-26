// Regras do ranking. Rodar: node --test test/
import assert from "node:assert/strict";
import { test } from "node:test";
import { CONQ_XP, DAY_CAP, FIRST_MAX, checkNick, checkSubmit, cleanProfile, duelView, isoWeek, leagueAfter, leagueZones, levelOf, nickKey, weekDay } from "../src/logic.js";

test("nível igual ao conquistas.py", () => {
  assert.equal(levelOf(0), 1);
  assert.equal(levelOf(99), 1);
  assert.equal(levelOf(100), 2);
  assert.equal(levelOf(4500), 10);
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
const ok = (o = {}) => ({ xp: 500, week: "2026-W48", week_xp: 300, streak: 2, best_streak: 3, unlocked: 4, ...o });
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
  assert.deepEqual(cleanProfile({ title: "coruja", frame: "f_ouro", show: ["foco1", "foco1", "imortal", "x", "y"] }),
    { title: "coruja", frame: "f_ouro", show: "foco1,imortal,x" });
  assert.deepEqual(cleanProfile({ title: "<b>oi</b>", frame: 3, show: "foco1" }), { title: "", frame: "", show: "" });
  assert.deepEqual(cleanProfile(null), { title: "", frame: "", show: "" });
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
