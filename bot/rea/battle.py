"""Battle brain (M2): reads game state, picks FIGHT / RUN, drives the menus."""
import time

from . import items as _items

BALLS = ["master ball", "ultra ball", "great ball", "poké ball", "heavy ball", "fast ball", "love ball",
         "level ball", "moon ball", "lure ball", "friend ball", "net ball", "dive ball", "quick ball",
         "heal ball", "nest ball", "dusk ball", "dream ball", "timer ball"]
OWNED = set()          # species we already have (party + farm + caught); kept up to date by the Brain
MENU = "DrawBattleMenuNormal"
ATTACKS = "DrawAttacksMenu"
ATK_CURR = "class:com.pkmngen.game.DrawAttacksMenu#curr"
PM_CURR = "class:com.pkmngen.game.DrawPokemonMenu#currIndex"
CELL_XY = {"tl": (0, 0), "tr": (1, 0), "bl": (0, 1), "br": (1, 1)}


class Data:
    """Static game tables, read once from the running game."""
    attacks = None
    chart = None

    @classmethod
    def load(cls, g):
        if cls.attacks is None:
            cls.attacks = g.get("game.battle.attacks", 2)
            cls.chart = g.get("game.battle.gen2TypeEffectiveness", 3)
        return cls


def in_battle(s):
    return "DrawBattle" in s["actions"]


def type_mult(atk_type, def_types):
    m, seen = 1.0, set()
    for t in def_types:
        t = t.lower()
        if t in seen:
            continue
        seen.add(t)
        m *= Data.chart.get(atk_type, {}).get(t, 1.0)
    return m


def expected_damage(src, move_name, dst):
    """Mean damage of `move_name` from src to dst (dicts from the snapshot), accuracy-weighted."""
    a = Data.attacks.get(move_name) if move_name else None
    if not a or not a.get("power"):
        return 0.0
    phys = a["isPhysical"]
    atk = src["stats"]["attack" if phys else "specialAtk"]
    dfn = max(1, dst["stats"]["defense" if phys else "specialDef"])
    base = ((2 * src["lvl"] // 5 + 2) * atk * a["power"] // dfn) // 50 + 2 + 2
    if a["type"].upper() in src["types"]:
        base *= 1.5
    return base * type_mult(a["type"], dst["types"]) * (a["accuracy"] / 100.0) * 0.85


def best_move(src, dst):
    best, bi = -1.0, 0
    for i, m in enumerate(src["moves"]):
        if not m:
            continue
        d = expected_damage(src, m, dst)
        if d > best:
            best, bi = d, i
    return bi, best


def threat(opp, me):
    """Highest expected damage the opponent can deal per turn."""
    return max([expected_damage(opp, m, me) for m in opp["moves"] if m] or [0.0])


def hp(p):
    return p["stats"]["hp"], p["max"]["hp"]


def matchup(me, opp):
    """(damage we deal per turn as a share of the opponent's hp, damage we take per turn as a share of our hp)."""
    mi, dmg = best_move(me, opp)
    t = threat(opp, me)
    off = dmg / max(1, opp["stats"]["hp"])
    risk = t / max(1, me["stats"]["hp"])
    return mi, off, risk


def value(me, opp):
    """Higher is better: how decisively `me` beats `opp` (0 when fainted)."""
    if me["stats"]["hp"] <= 0 or me.get("egg"):
        return 0.0
    _, off, risk = matchup(me, opp)
    return off / max(risk, 0.04)


BALL_COST = {"master ball": 9, "ultra ball": 4, "great ball": 3, "poké ball": 2}   # everything else: 1 apricorn
MOON_MONS = ("clefairy", "jigglypuff", "nidorina", "nidorino")


def ball_multiplier(ball, me, opp, turn, night=False):
    """Catch-rate multiplier of `ball` in this situation (rules read from Battle.java)."""
    rate = max(1, opp["stats"].get("catchRate", 100))
    b = ball
    if b == "master ball":
        return 99.0
    if b in ("great ball", "park ball"):
        return 1.5
    if b == "ultra ball":
        return 2.0
    if b == "dusk ball":
        return 3.5 if night else 1.0
    if b == "fast ball":
        return 4.0 if opp.get("base", {}).get("speed", 0) >= 100 else 1.0
    if b == "quick ball":
        return 5.0 if turn == 1 else 1.0
    if b == "net ball":
        return min(1.0 + turn * 0.3, 4.0) if set(opp["types"]) & {"WATER", "BUG"} else 1.0
    if b == "dive ball":
        return 1.0
    if b == "nest ball":
        return (41.0 - opp["lvl"]) / 10.0 if opp["lvl"] <= 29 else 1.0
    if b == "dream ball":
        return 4.0 if opp.get("status") == "sleep" else 1.0
    if b == "heavy ball":
        w = opp.get("wt", 0)
        delta = 30 if w >= 300 else 20 if w >= 200 else 0 if w >= 100 else -20
        return max(0.1, (rate + delta) / rate)
    if b == "level ball":
        l = me["lvl"]
        return 8.0 if l / 4 > opp["lvl"] else 4.0 if l / 2 > opp["lvl"] else 2.0 if l > opp["lvl"] else 1.0
    if b == "love ball":
        same = me["specie"] == opp["specie"]
        opposite = {me.get("gender"), opp.get("gender")} == {"male", "female"}
        return 8.0 if same and opposite else 1.0
    if b == "moon ball":
        return 4.0 if opp["specie"] in MOON_MONS else 1.0
    return 1.0


A_LOOKUP = [1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40, 50, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 254, 255]
B_LOOKUP = [63, 75, 84, 90, 95, 103, 113, 126, 134, 149, 160, 169, 177, 191, 201, 211, 220, 227, 234, 240, 246, 251, 253, 255]


def catch_probability(opp, mult):
    """P(caught) for one throw: (a+1)/256 immediately, otherwise three shake checks against b (Battle.java)."""
    rate = min(255, int(max(1, opp["stats"].get("catchRate", 100)) * mult))
    m = 3 * opp["max"]["hp"]
    h = 2 * opp["stats"]["hp"]
    if m > 255:
        m //= 4
        h //= 4
    a = max(1, (m - h) * rate // max(1, m))
    if opp.get("status") in ("sleep", "freeze"):
        a += 10
    a = min(255, a)
    if mult >= 99:
        return 1.0
    p1 = min(1.0, (a + 1) / 256.0)
    i = 0
    prev = -1
    for val in A_LOOKUP:
        if a > prev and a <= val:
            break
        prev = val
        i += 1
    b = B_LOOKUP[min(i, len(B_LOOKUP) - 1)]
    return p1 + (1 - p1) * (b / 256.0) ** 3


def best_ball(s):
    """(ball, probability) with the best chance among the balls we hold; cheap balls win near-ties."""
    have = s["player"]["items"]
    opp = s["battle"].get("opp")
    party = s["player"]["party"]
    me = party[s["player"]["curr"]] if 0 <= s["player"]["curr"] < len(party) else party[0]
    turn = s["battle"].get("turn", 1)
    best, bp, bscore = None, 0.0, -1.0
    for b in BALLS:
        if have.get(b, 0) <= 0:
            continue
        p = catch_probability(opp, ball_multiplier(b, me, opp, turn)) if opp else 0.0
        score = p - 0.03 * BALL_COST.get(b, 1)
        if score > bscore:
            best, bp, bscore = b, p, score
    return (best, bp) if best else (None, 0.0)


def want_catch(s):
    """Catch new species when there is room, a ball, and the target is not wildly out of our league."""
    party = s["player"]["party"]
    opp = s["battle"].get("opp")
    if not opp or len(party) >= 6 or best_ball(s)[0] is None:
        return False
    if opp["specie"] in {m["specie"] for m in party} or opp["specie"] in OWNED:
        return False
    return opp["lvl"] <= max(m["lvl"] for m in party) + 10


def decide(s, switched_recently=False, allow_ball=True):
    """Returns ('fight', move_index) | ('switch', party_index) | ('run', None)."""
    party = s["player"]["party"]
    cur_i = s["player"]["curr"] if 0 <= s["player"]["curr"] < len(party) else 0
    me = party[cur_i]
    opp = s["battle"]["opp"]
    mi, off, risk = matchup(me, opp)
    cur_v = value(me, opp)
    best_i, best_v = cur_i, cur_v
    for i, m in enumerate(party):
        if i != cur_i and value(m, opp) > best_v:
            best_i, best_v = i, value(m, opp)
    hpf = me["stats"]["hp"] / max(1, me["max"]["hp"])
    turns_to_die = 1.0 / risk if risk > 0 else 99
    turns_to_kill = 1.0 / off if off > 0 else 99
    losing = turns_to_die < 2 and turns_to_kill > 1.2
    ohp = opp["stats"]["hp"] / max(1, opp["max"]["hp"])
    if allow_ball and want_catch(s) and hpf > 0.25:
        ball, p = best_ball(s)
        # a good ball for this level can be thrown at full hp; otherwise weaken it first
        if p >= 0.5 or (p >= 0.12 and (ohp <= 0.5 or opp["status"] not in ("", None))):
            return "ball", ball
    # a clearly better mon is waiting: swap, unless we just did (avoid ping-pong) or we are about to win anyway
    if best_i != cur_i and not switched_recently and best_v > max(1.6 * cur_v, 0.8) and turns_to_kill > 1.5:
        return "switch", best_i
    if best_i != cur_i and not switched_recently and (losing or hpf < 0.25) and best_v > 0.6:
        return "switch", best_i
    if opp["lvl"] > me["lvl"] + 8 or losing or hpf < 0.2:
        return "run", None
    return "fight", mi


def _cell_move(g, name, target):
    for _ in range(4):
        cur = g.act(name)["curr"]
        if cur == target:
            return
        cx, cy = CELL_XY[cur]
        tx, ty = CELL_XY[target]
        if cy != ty:
            g.tap("down" if ty > cy else "up", 2, 4)
        elif cx != tx:
            g.tap("right" if tx > cx else "left", 2, 4)


def throw_ball(g, ball):
    """From the battle main menu: ITEM -> ball -> USE."""
    _cell_move(g, MENU, "bl")
    g.tap("a", 2, 14)
    for _ in range(80):
        m = g.act("DrawItemMenuGen2", 1)
        if m is not None and not m.get("disabled"):
            break
        g.wait(4)
    else:
        return False
    g.wait(10)
    if not _items.select_item(g, ball):
        g.tap("b", 2, 14)
        return False
    for _ in range(40):
        if "DrawUseTossMenu" in g.state()["actions"]:
            break
        g.wait(4)
    else:
        return False
    g.wait(10)
    g.tap("a", 2, 14)                 # USE
    return True


def switch_to(g, idx):
    """From the battle main menu: POKeMON -> member idx -> SWITCH. Returns True if the menu flow completed."""
    _cell_move(g, MENU, "tr")
    g.tap("a", 2, 14)
    for _ in range(60):
        m = g.act("DrawPokemonMenu", 1)
        if m is not None and not m.get("disabled"):
            break
        g.wait(4)
    else:
        return False
    g.wait(16)
    for _ in range(8):
        cur = g.get(PM_CURR)
        if cur == idx:
            break
        g.tap("down" if idx > cur else "up", 2, 8)
    g.tap("a", 2, 12)
    sel = None
    for _ in range(40):
        sel = g.act("DrawPokemonMenu$SelectedMenu", 2)
        if sel is not None:
            break
        g.wait(4)
    if sel is None or "SWITCH" not in sel["words"]:
        g.tap("b", 2, 12)
        return False
    target = sel["words"].index("SWITCH")
    for _ in range(6):
        cur = g.act("DrawPokemonMenu$SelectedMenu", 1)["curr"]
        if cur == target:
            break
        g.tap("down" if target > cur else "up", 2, 8)
    g.tap("a", 2, 14)
    return True


def run_battle(g, log=print, max_seconds=300):
    """Plays one battle to the end. Returns summary dict."""
    Data.load(g)
    t0 = time.time()
    s = g.state()
    turns, decided, idle, last_switch, banned_ball = 0, None, 0, -10, False
    while in_battle(s) and time.time() - t0 < max_seconds:
        acts = s["actions"]
        if MENU in acts:
            decided, arg = decide(s, switched_recently=(turns - last_switch) < 3, allow_ball=not banned_ball)
            me = s["player"]["party"][max(0, s["player"]["curr"])]
            opp = s["battle"]["opp"]
            what = (me["moves"][arg] if decided == "fight" else
                    s["player"]["party"][arg]["specie"] if decided == "switch" else arg if decided == "ball" else "")
            log("turn %d: %s L%d (%d/%d) vs %s L%d (%d/%d) -> %s %s" % (
                turns + 1, me["specie"], me["lvl"], *hp(me), opp["specie"], opp["lvl"],
                opp["stats"]["hp"], opp["max"]["hp"], decided, what))
            turns += 1
            if decided == "ball":
                if not throw_ball(g, arg):
                    g.tap("b", 2, 12)
                    banned_ball = True
            elif decided == "switch":
                last_switch = turns
                if not switch_to(g, arg):
                    last_switch = turns + 10          # menu flow failed: do not try again this fight
                    g.tap("b", 2, 12)
            elif decided == "run":
                _cell_move(g, MENU, "br")
                g.tap("a", 2, 10)
            else:
                mi = arg
                _cell_move(g, MENU, "tl")
                g.tap("a", 2, 14)
                for _ in range(40):  # wait for the attack list
                    s = g.state()
                    if ATTACKS in s["actions"]:
                        break
                    g.wait(2)
                else:
                    s = g.wait(4)
                    continue
                for _ in range(4):
                    cur = g.get(ATK_CURR)
                    if cur == mi:
                        break
                    g.tap("down" if mi > cur else "up", 2, 4)
                g.tap("a", 2, 10)
            g.wait(20)
        elif "DrawYesNoMenu" in acts:
            g.tap("b", 2, 10)          # "No" to switch / learn prompts
        elif "DrawPokemonMenu" in acts:
            # forced switch (our mon fainted): send the best remaining one
            opp = s.get("battle", {}).get("opp")
            party = s["player"]["party"]
            alive = [i for i, m in enumerate(party) if m["stats"]["hp"] > 0 and not m.get("egg")]
            if not alive:
                g.tap("a", 2, 10)
            else:
                idx = max(alive, key=lambda i: value(party[i], opp)) if opp else alive[0]
                for _ in range(8):
                    cur = g.get(PM_CURR)
                    if cur == idx:
                        break
                    g.tap("down" if idx > cur else "up", 2, 8)
                g.tap("a", 2, 12)
                sel = g.act("DrawPokemonMenu$SelectedMenu", 2)
                if sel is not None and "SWITCH" in sel["words"]:
                    for _ in range(4):
                        c = g.act("DrawPokemonMenu$SelectedMenu", 1)["curr"]
                        if c == sel["words"].index("SWITCH"):
                            break
                        g.tap("down", 2, 8)
                    g.tap("a", 2, 12)
        elif "DisplayText" in acts or any("ShowLevelUpStats" in a or "Evolution" in a for a in acts):
            g.tap("a", 2, 8)
            idle = 0
        else:
            idle += 1
            if idle >= 6:      # something unknown is waiting for input (stat screens, etc.)
                g.tap("a", 2, 8)
                idle = 0
            else:
                g.wait(6)
        s = g.state()
    return {"turns": turns, "last": decided, "seconds": round(time.time() - t0, 1)}
