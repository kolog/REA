"""Battle brain (M2): reads game state, picks FIGHT / RUN, drives the menus."""
import time

MENU = "DrawBattleMenuNormal"
ATTACKS = "DrawAttacksMenu"
ATK_CURR = "class:com.pkmngen.game.DrawAttacksMenu#curr"
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


def decide(s):
    """Returns ('fight', move_index) or ('run', None)."""
    party = s["player"]["party"]
    me = party[s["player"]["curr"]] if 0 <= s["player"]["curr"] < len(party) else party[0]
    opp = s["battle"]["opp"]
    cur, mx = hp(me)
    mi, dmg = best_move(me, opp)
    t = threat(opp, me)
    ohp = opp["stats"]["hp"]
    turns_to_kill = ohp / dmg if dmg > 0 else 99
    turns_to_die = cur / t if t > 0 else 99
    if opp["lvl"] > me["lvl"] + 6 or (turns_to_die < 2 and turns_to_kill > 1.2) or cur < 0.25 * mx:
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


def run_battle(g, log=print, max_seconds=300):
    """Plays one battle to the end. Returns summary dict."""
    Data.load(g)
    t0 = time.time()
    s = g.state()
    turns, decided, idle = 0, None, 0
    while in_battle(s) and time.time() - t0 < max_seconds:
        acts = s["actions"]
        if MENU in acts:
            decided, mi = decide(s)
            me = s["player"]["party"][max(0, s["player"]["curr"])]
            opp = s["battle"]["opp"]
            log("turn %d: %s L%d (%d/%d) vs %s L%d (%d/%d) -> %s %s" % (
                turns + 1, me["specie"], me["lvl"], *hp(me), opp["specie"], opp["lvl"],
                opp["stats"]["hp"], opp["max"]["hp"], decided, me["moves"][mi] if mi is not None else ""))
            turns += 1
            if decided == "run":
                _cell_move(g, MENU, "br")
                g.tap("a", 2, 10)
            else:
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
            g.tap("a", 2, 10)          # forced switch: take the highlighted mon
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
