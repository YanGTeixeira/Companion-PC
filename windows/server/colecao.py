"""Coleção (1.19): o catálogo de tudo o que dá para liberar, os créditos, a loja da semana e os eventos sazonais.

Cada item tem um tipo, uma raridade e uma forma de liberar:
    nível (int) · conquista (id de CONQ) · "shop" (só na loja, comprado com créditos) · "ev:<id>" (evento sazonal)
O visual de cada item (fundos, avatares, efeitos, temas) fica no app (web/js/catalogo.js); aqui só ids e regras.

Créditos: calculados do histórico, como o XP (sempre dão o mesmo resultado); só as compras ficam gravadas.
"""
import random
from datetime import date, timedelta

RARITY = ("comum", "raro", "epico", "lendario")
PRICE = {"comum": 60, "raro": 150, "epico": 350, "lendario": 800}
SHOP_N = 4

# tipos: title (título), frame (moldura), sound (som dos avisos), theme ("skin:variante"), accent (cor de destaque),
# bg (fundo do cartão do jogador), avatar, effect (efeito no nome)
KINDS = ("title", "frame", "sound", "theme", "accent", "bg", "avatar", "effect")
EQUIP_KINDS = ("title", "frame", "sound", "accent", "bg", "avatar", "effect")   # tema fica no layout (vale por aparelho)

C, R, E, L = RARITY
SHOP = "shop"

# (id, tipo, nome, raridade, requisito)
ITEMS = [
    # ---- títulos
    ("novato", "title", "Novato", C, 1), ("aprendiz", "title", "Aprendiz", C, 3), ("focado", "title", "Focado", C, 5),
    ("explorador", "title", "Explorador", C, 7), ("veterano", "title", "Veterano", R, 10), ("mestre", "title", "Mestre", R, 20),
    ("lenda", "title", "Lenda", E, 25), ("campeao", "title", "Campeão", E, 35), ("imperador", "title", "Imperador", E, 45),
    ("mito", "title", "Mito", L, 50), ("eterno", "title", "Eterno", L, 60),
    ("coruja", "title", "Coruja", C, "coruja"), ("madrugador", "title", "Madrugador", C, "cedo"), ("monge", "title", "Monge", E, "foco100"),
    ("imortal", "title", "Imortal", E, "imortal"), ("imparavel", "title", "Imparável", E, "vit10"),
    ("cacador", "title", "Caçador de chefões", R, "boss5"), ("desafiante", "title", "Desafiante", R, "des10"),
    ("tagarela", "title", "Tagarela", C, "fala"), ("duelista", "title", "Duelista", R, "duelo1"),
    ("colecionador", "title", "Colecionador", R, "col25"), ("fenix", "title", "Fênix", E, "fenix"),
    ("zen", "title", "Zen", C, SHOP), ("lobo", "title", "Lobo solitário", R, SHOP), ("estrategista", "title", "Estrategista", R, SHOP),
    ("arcanista", "title", "Arcanista", E, SHOP), ("soberano", "title", "Soberano", L, SHOP),
    ("noel", "title", "Espírito natalino", R, "ev:natal"), ("assombrado", "title", "Assombrado", R, "ev:halloween"),
    ("foliao", "title", "Folião", R, "ev:carnaval"), ("visionario", "title", "Visionário", R, "ev:anonovo"),
    # ---- molduras
    ("f_simples", "frame", "Simples", C, 1), ("f_bronze", "frame", "Bronze", C, 4), ("f_prata", "frame", "Prata", R, 8),
    ("f_neon", "frame", "Neon", E, 12), ("f_ouro", "frame", "Ouro", R, 15), ("f_esmeralda", "frame", "Esmeralda", R, 24),
    ("f_cristal", "frame", "Cristal", E, 30), ("f_obsidiana", "frame", "Obsidiana", E, 40), ("f_arco", "frame", "Arco-íris", L, 50),
    ("f_chamas", "frame", "Chamas", E, "seq30"),
    ("f_pixel", "frame", "Pixel", R, SHOP), ("f_gelo", "frame", "Gelo", R, SHOP), ("f_galaxia", "frame", "Galáxia", L, SHOP),
    ("f_natal", "frame", "Guirlanda", R, "ev:natal"), ("f_abobora", "frame", "Abóbora", R, "ev:halloween"),
    # ---- sons das conquistas
    ("s_bipe", "sound", "Bipe", C, 1), ("s_fanfarra", "sound", "Fanfarra", C, 4), ("s_moeda", "sound", "Moeda", C, 7),
    ("s_arcade", "sound", "Arcade", R, 11), ("s_sino", "sound", "Sino", R, 16), ("s_vitoria", "sound", "Vitória", E, 22),
    ("s_powerup", "sound", "Power-up", R, 27),
    ("s_laser", "sound", "Laser", R, SHOP), ("s_harpa", "sound", "Harpa", E, SHOP), ("s_natal", "sound", "Sinos de Natal", R, "ev:natal"),
    # ---- temas: variantes de cor dos temas de sempre
    ("minimal:mint", "theme", "Minimal Menta", C, 5), ("fallout:red", "theme", "Fallout Vermelho", R, 6),
    ("minimal:purple", "theme", "Minimal Roxo", R, 9), ("lcd:ice", "theme", "LCD Gelo", R, 11),
    ("fallout:violet", "theme", "Fallout Violeta", R, 13), ("synth:gold", "theme", "Synthwave Ouro", E, 14),
    ("synth:mint", "theme", "Synthwave Menta", R, 17), ("paper:sepia", "theme", "Papel Sépia", R, 19),
    ("rpg:emerald", "theme", "Fantasia Esmeralda", E, 20), ("hud:alert", "theme", "Cockpit Alerta", R, 21),
    ("minimal:sand", "theme", "Minimal Areia", R, 24), ("code:dracula", "theme", "Código Drácula", E, 26),
    ("tac:desert", "theme", "Tático Deserto", R, 28), ("rpg:frost", "theme", "Fantasia Gelo", E, 33),
    ("exec:bordeaux", "theme", "Executivo Bordô", E, 38),
    ("fallout:toxic", "theme", "Fallout Tóxico", R, SHOP), ("minimal:rose", "theme", "Minimal Rosé", R, SHOP),
    ("pocket:pink", "theme", "Portátil Rosa", R, SHOP), ("code:solar", "theme", "Código Solarizado", R, SHOP),
    ("paper:night", "theme", "Papel Noturno", E, SHOP), ("jp:matcha", "theme", "Japão Matcha", E, SHOP),
    ("synth:blood", "theme", "Synthwave Sangue", E, SHOP),
    # ---- temas inteiros novos (todas as variantes têm cadeado)
    ("abismo:deep", "theme", "Abismo", R, 18), ("abismo:coral", "theme", "Abismo Coral", E, SHOP),
    ("masmorra:torch", "theme", "Masmorra", E, "boss5"), ("masmorra:crypt", "theme", "Masmorra Cripta", E, "boss20"),
    ("cosmos:nebula", "theme", "Cosmos", E, 30), ("cosmos:galaxy", "theme", "Cosmos Galáxia", L, SHOP),
    ("dunas:day", "theme", "Dunas", R, SHOP), ("dunas:night", "theme", "Dunas Noite", E, SHOP),
    ("matrix:green", "theme", "Chuva Digital", E, "des10"), ("matrix:red", "theme", "Chuva Digital Vermelha", E, SHOP),
    ("aurora:boreal", "theme", "Aurora", L, 45), ("aurora:austral", "theme", "Aurora Austral", L, 55),
    # ---- temas de evento
    ("natal:pinheiro", "theme", "Natal", E, "ev:natal"), ("natal:neve", "theme", "Natal Nevado", E, "ev:natal"),
    ("halloween:abobora", "theme", "Halloween", E, "ev:halloween"), ("carnaval:confete", "theme", "Carnaval", E, "ev:carnaval"),
    ("anonovo:fogos", "theme", "Ano Novo", E, "ev:anonovo"),
    # ---- cor de destaque (por cima de qualquer tema)
    ("a_tema", "accent", "A do tema", C, 1), ("a_livre", "accent", "Cor livre", E, 35), ("a_holo", "accent", "Holográfica", E, 42),
    ("a_arco", "accent", "Arco-íris", L, 55), ("a_brasa", "accent", "Brasa", E, "vit10"),
    ("a_plasma", "accent", "Plasma", E, SHOP), ("a_ouro", "accent", "Ouro vivo", L, SHOP),
    # ---- fundos do cartão do jogador
    ("b_nenhum", "bg", "Liso", C, 1), ("b_grade", "bg", "Grade", C, 2), ("b_cidade", "bg", "Cidade pixel", R, 6),
    ("b_montanhas", "bg", "Montanhas", R, 10), ("b_espaco", "bg", "Espaço", R, 16), ("b_sol", "bg", "Sol neon", E, 23),
    ("b_circuito", "bg", "Circuito", R, 27), ("b_aurora", "bg", "Aurora", L, 48),
    ("b_castelo", "bg", "Castelo", E, "boss20"), ("b_lava", "bg", "Lava", E, "seq30"),
    ("b_oceano", "bg", "Oceano", R, SHOP), ("b_floresta", "bg", "Floresta", R, SHOP), ("b_chuva", "bg", "Chuva digital", E, SHOP),
    ("b_natal", "bg", "Noite de Natal", R, "ev:natal"), ("b_halloween", "bg", "Lua cheia", R, "ev:halloween"),
    # ---- avatares (pixel art no lugar do número do nível)
    ("av_nivel", "avatar", "Número do nível", C, 1), ("av_robo", "avatar", "Robô", C, 2), ("av_gato", "avatar", "Gato", C, 3),
    ("av_controle", "avatar", "Controle", C, 5), ("av_fantasma", "avatar", "Fantasma", R, 8), ("av_alien", "avatar", "Alien", R, 13),
    ("av_caveira", "avatar", "Caveira", R, 19), ("av_ninja", "avatar", "Ninja", E, 25), ("av_coroa", "avatar", "Coroa", E, 40),
    ("av_dragao", "avatar", "Dragão", L, 50),
    ("av_coruja", "avatar", "Coruja", R, "coruja"), ("av_espada", "avatar", "Espada", R, "boss1"), ("av_foguete", "avatar", "Foguete", R, "foco3h"),
    ("av_slime", "avatar", "Slime", C, SHOP), ("av_cogumelo", "avatar", "Cogumelo", R, SHOP), ("av_pinguim", "avatar", "Pinguim", R, SHOP),
    ("av_mago", "avatar", "Mago", E, SHOP),
    ("av_neve", "avatar", "Boneco de neve", R, "ev:natal"), ("av_abobora", "avatar", "Abóbora", R, "ev:halloween"),
    ("av_mascara", "avatar", "Máscara", R, "ev:carnaval"), ("av_estrela", "avatar", "Estrela", R, "ev:anonovo"),
    # ---- efeitos no nome e no título
    ("e_nenhum", "effect", "Nenhum", C, 1), ("e_brilho", "effect", "Brilho", C, 5), ("e_gradiente", "effect", "Degradê", R, 12),
    ("e_fogo", "effect", "Fogo", E, 32), ("e_arco", "effect", "Arco-íris", L, 52), ("e_glitch", "effect", "Glitch", E, "vit10"),
    ("e_gelo", "effect", "Gelo", R, SHOP), ("e_neon", "effect", "Neon pulsante", E, SHOP), ("e_ouro", "effect", "Ouro reluzente", L, SHOP),
    ("e_confete", "effect", "Confete", R, "ev:carnaval"), ("e_cintilante", "effect", "Cintilante", R, "ev:anonovo"),
]
BY_ID = {i[0]: i for i in ITEMS}
ANIMATED = {"matrix:green", "matrix:red", "aurora:boreal", "aurora:austral", "natal:neve", "anonovo:fogos",
            "a_holo", "a_arco", "a_brasa", "a_plasma", "a_ouro", "b_aurora", "b_chuva", "b_lava", "b_natal",
            "e_fogo", "e_arco", "e_glitch", "e_neon", "e_ouro", "e_cintilante", "f_galaxia"}

EQUIP_DEFAULT = {"title": "novato", "frame": "f_simples", "sound": "s_bipe", "accent": "a_tema", "bg": "b_nenhum",
                 "avatar": "av_nivel", "effect": "e_nenhum", "color": "#4c8dff", "bio": "", "lay": ["bio", "stats", "show"], "show": []}
LAY_BLOCKS = ("bio", "stats", "show", "recent", "league")
BIO_MAX = 60
SHOW_SLOTS = [(50, 6), (30, 5), (15, 4)]   # nível -> lugares na vitrine (3 até o 15)


def show_max(level):
    return next((n for lv, n in SHOW_SLOTS if level >= lv), 3)


def item_got(item, level, unlocked, bought):
    _id, _k, _n, _r, req = item
    if isinstance(req, int):
        return req <= level
    if req == SHOP:
        return _id in bought
    if req.startswith("ev:"):
        return "ev_" + req[3:] in unlocked
    return req in unlocked


def got_ids(level, unlocked, bought):
    return {i[0] for i in ITEMS if item_got(i, level, unlocked, bought)}


def clean_color(v):
    v = str(v or "").strip().lower()
    return v if len(v) == 7 and v[0] == "#" and all(c in "0123456789abcdef" for c in v[1:]) else None


def clean_bio(v):
    s = " ".join("".join(ch for ch in str(v or "") if ch.isprintable()).split())
    return s[:BIO_MAX]


def clean_lay(v):
    out = []
    for b in v if isinstance(v, list) else []:
        if b in LAY_BLOCKS and b not in out:
            out.append(b)
    return out


# ---------------------------------------------------------------- créditos
CR_META, CR_ALL_METAS = 2, 3            # por meta do dia, e o bônus das 3
CR_QUEST, CR_ALL_QUESTS, CR_BOSS = 10, 10, 25
CR_LEVEL = 20                           # por nível acima do 1
CR_CONQ = {"bronze": 5, "prata": 15, "ouro": 40}
CR_STREAK7 = 15                         # a cada 7 dias seguidos
CR_EVENT = 50


def credits_by_day(days, weeks, sim_per, conq_days, level, events_done):
    """Créditos ganhos por dia. days: [(dia, facts, metas)]; weeks: eval_week de cada semana; sim_per: streak_sim()["per"];
    conq_days: [(dia, tier)] das conquistas; events_done: {id: dia}. O dos níveis entra no dia de hoje (o último)."""
    out = {}
    add = lambda k, v: out.__setitem__(k, out.get(k, 0) + v)  # noqa: E731
    for k, _f, metas in days:
        done = sum(1 for m in metas if m["status"] == "done")
        add(k, CR_META * done + (CR_ALL_METAS if metas and done == len(metas) == 3 else 0))
        before = (sim_per.get(k) or (0, False))[0]
        if done >= 2 and (before + 1) % 7 == 0:
            add(k, CR_STREAK7)
    for w in weeks:
        for q in w["quests"]:
            if q["day"]:
                add(q["day"], CR_QUEST)
        if w["all"]:
            add(max(q["day"] for q in w["quests"]), CR_ALL_QUESTS)
        if w["boss"]["dead"]:
            add(w["boss"]["dead"], CR_BOSS)
    for d, tier in conq_days:
        add(d, CR_CONQ.get(tier, 0))
    for d in events_done.values():
        add(d, CR_EVENT)
    if days:
        add(days[-1][0], CR_LEVEL * (level - 1))
    return out


# ---------------------------------------------------------------- loja da semana
def shop_pick(week, owned_before):
    """Os SHOP_N itens da semana (sorteados pela semana: iguais em todo aparelho e não mudam ao recarregar).
    owned_before: o que já era seu antes da semana começar. Sempre vem pelo menos um raro ou melhor."""
    pool = [i[0] for i in ITEMS if i[4] == SHOP and i[0] not in owned_before]
    rng = random.Random("shop:" + week)
    rare = [i for i in pool if BY_ID[i][3] != C]
    picks = [rng.choice(rare)] if rare else []
    rest = [i for i in pool if i not in picks]
    picks += rng.sample(rest, min(SHOP_N - len(picks), len(rest)))
    return sorted(picks, key=lambda i: (RARITY.index(BY_ID[i][3]), i))


# ---------------------------------------------------------------- eventos sazonais
def easter(y):
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    return date(y, month, day)


# (id, nome, ícone, janela(ano) -> (início, fim), tipo da meta, alvo, texto)
EVENTS = [
    ("natal", "Natal", "🎄", lambda y: (date(y, 12, 1), date(y, 12, 31)), "metas", 20, "Cumpra 20 metas do dia em dezembro"),
    ("anonovo", "Ano Novo", "🎆", lambda y: (date(y, 1, 1), date(y, 1, 15)), "dias", 7, "7 dias com 2 metas cumpridas até 15/01"),
    ("carnaval", "Carnaval", "🎭", lambda y: (easter(y) - timedelta(days=58), easter(y) - timedelta(days=46)), "foco", 300,
     "5 h de foco durante o Carnaval"),
    ("halloween", "Halloween", "🎃", lambda y: (date(y, 10, 15), date(y, 11, 2)), "boss", 1, "Derrote um chefão da semana no Halloween"),
]


def event_value(kind, days, weeks, start, end):
    s, e = start.isoformat(), end.isoformat()
    inside = [(k, f, m) for k, f, m in days if s <= k <= e]
    if kind == "metas":
        return sum(sum(1 for x in m if x["status"] == "done") for _k, _f, m in inside)
    if kind == "dias":
        return sum(1 for _k, _f, m in inside if sum(1 for x in m if x["status"] == "done") >= 2)
    if kind == "foco":
        return sum(f.get("foc", 0) for _k, f, _m in inside)
    if kind == "boss":
        return sum(1 for w in weeks if w["boss"]["dead"] and s <= w["boss"]["dead"] <= e)
    return 0


def events_eval(days, weeks, today, since):
    """Eventos: o que já foi completado (dia) e o atual ou o próximo, com o progresso.
    Só contam dias a partir de since (a 1ª vez que a 1.19 rodou): evento que já passou não vale."""
    t = date.fromisoformat(today)
    first = date.fromisoformat(since)
    done, cur = {}, None
    items = {}
    for it in ITEMS:
        if isinstance(it[4], str) and it[4].startswith("ev:"):
            items.setdefault(it[4][3:], []).append(it[0])
    for eid, name, icon, win, kind, target, text in EVENTS:
        for y in range(first.year, t.year + 1):
            start, end = win(y)
            if end < first or start > t:
                continue
            s2 = max(start, first)
            # o dia em que bateu a meta
            for k in sorted({k for k, _f, _m in days if s2.isoformat() <= k <= min(end, t).isoformat()}):
                if event_value(kind, days, weeks, s2, date.fromisoformat(k)) >= target:
                    done.setdefault(eid, k)
                    break
    # atual (dentro da janela) ou o próximo a começar
    best = None
    for eid, name, icon, win, kind, target, text in EVENTS:
        for y in (t.year, t.year + 1):
            start, end = win(y)
            if end < t:
                continue
            if best is None or start < best[0]:
                best = (start, end, eid, name, icon, kind, target, text)
            break
    if best:
        start, end, eid, name, icon, kind, target, text = best
        live = start <= t <= end
        val = event_value(kind, days, weeks, max(start, first), min(end, t)) if live else 0
        cur = {"id": eid, "name": name, "icon": icon, "start": start.isoformat(), "end": end.isoformat(), "live": live,
               "text": text, "kind": kind, "target": target, "value": min(val, target) if kind != "foco" else min(val, target),
               "done": eid in done, "items": items.get(eid, [])}
    return done, cur
