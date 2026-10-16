"""Interacting with pokemon and items on the overworld (M3).

A on a *friendly* wild pokemon asks "Add X to your party?" and Yes recruits it for free.
Aggressive ones warn once and attack on the second A, skittish ones start a battle: both are left alone.
A on a tile with `hasItem` (pokeball1 etc.) picks the item up.
"""
from . import nav

FACE = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}


def yes_no(g, yes=True, tries=6):
    """Answer the on-screen YES/NO menu."""
    for _ in range(tries):
        m = g.act("DrawYesNoMenu", 1)
        if m is None:
            g.wait(4)
            continue
        want = 0 if yes else 1
        if m["curr"] == want:
            g.tap("a", 2, 10)
            return True
        g.tap("up" if want < m["curr"] else "down", 2, 6)
    return False


def dismiss_text(g, limit=12):
    """Advance DisplayText boxes. Stops when a YES/NO menu shows up or text is gone."""
    for _ in range(limit):
        s = g.state()
        if "DrawYesNoMenu" in s["actions"] or "DisplayText" not in s["actions"]:
            return s
        g.tap("a", 2, 14)
    return g.state()


def mon_tile(m):
    return int(round(m["x"][0] / 16)), int(round(m["x"][1] / 16))


def face(g, d):
    """Turn towards direction d without stepping: the game only walks after the key was held for >3 frames,
    so a 2-frame tap just changes the facing (also works when the target tile is walkable, e.g. grass)."""
    g.hold(d, 2)
    return g.wait(8)


def approach(g, target, radius=12, policy=None):
    """Walk to a free tile next to `target`. Returns the direction that faces target, or None."""
    s = g.state()
    here = nav.tile_of(s["player"])
    grid = nav.Grid(g.grid(radius), s["map"]["mons"], **(policy or {}))
    best = None
    for d, (dx, dy) in FACE.items():
        # standing at target - (dx,dy) we look towards `d` to face the target
        stand = (target[0] - dx, target[1] - dy)
        if stand == here:
            return d
        if grid.passable(stand):
            path = grid.astar(here, lambda p, st=stand: p == st)
            if path is not None and (best is None or len(path) < best[0]):
                best = (len(path), stand, d)
    if best is None:
        return None
    ok, s = nav.goto(g, best[1], radius, policy=policy)
    return best[2] if ok else None


def recruit(g, specie=None, log=print, attempts=6):
    """Recruit the nearest friendly wild pokemon in view (optionally of a given species). True if it joined."""
    for _ in range(attempts):
        s = g.state()
        party = len(s["player"]["party"])
        if party >= 6 or not nav.is_free(s):
            return False
        here = nav.tile_of(s["player"])
        cands = [m for m in s["map"]["mons"] if m["temper"] == "friendly" and m.get("x")
                 and (specie is None or m["specie"] == specie)]
        if not cands:
            return False
        cands.sort(key=lambda m: abs(mon_tile(m)[0] - here[0]) + abs(mon_tile(m)[1] - here[1]))
        m = cands[0]
        d = approach(g, mon_tile(m))
        if d is None:
            continue
        s = g.state()
        # the pokemon may have wandered off meanwhile; make sure it is still where we face
        t = nav.tile_of(s["player"])
        dx, dy = FACE[d]
        faced = (t[0] + dx, t[1] + dy)
        if not any(mon_tile(x) == faced for x in s["map"]["mons"] if x.get("x")):
            continue
        face(g, d)
        g.tap("a", 2, 20)
        s = dismiss_text(g)
        if "DrawYesNoMenu" in s["actions"]:
            yes_no(g, True)
            dismiss_text(g)
            if len(g.state()["player"]["party"]) > party:
                log("recruited %s" % m["specie"])
                return True
        else:
            dismiss_text(g)
    return False


def pick_up(g, tile, log=print):
    """Walk next to `tile` (which holds an item), face it and press A."""
    d = approach(g, tile)
    if d is None:
        return False
    face(g, d)
    before = dict(g.state()["player"]["items"])
    g.tap("a", 2, 20)
    dismiss_text(g)
    after = g.state()["player"]["items"]
    got = {k: v - before.get(k, 0) for k, v in after.items() if v != before.get(k, 0)}
    if got:
        log("picked up %s" % got)
    return bool(got)


def provoke(g, tile, log=print):
    """Talk to an aggressive pokemon twice: the first A only warns, the second starts the battle."""
    d = approach(g, tile)
    if d is None:
        return False
    for _ in range(3):
        face(g, d)
        g.tap("a", 2, 20)
        s = dismiss_text(g)
        if "DrawBattle" in s["actions"]:
            return True
    return "DrawBattle" in g.state()["actions"]
