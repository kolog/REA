"""Healing by sleeping in the bag (restores the party; also sets the white-out spawn)."""
from . import nav, items

BAD_TERRAIN = ("stairs", "mountain", "snow", "desert")


def party_hp_frac(s):
    ms = [m for m in s["player"]["party"] if m["max"].get("hp")]
    return min((m["stats"]["hp"] / m["max"]["hp"] for m in ms), default=1.0)


def sleep_ok(grid, p):
    t = grid.get(p)
    r = grid.get((p[0] + 1, p[1]))
    if not t or not r or t.get("grass") or t.get("tidal") or "dungeon" in t.get("rn", ""):
        return False
    if any(b in t["n"] for b in BAD_TERRAIN) or any(b in r["n"] for b in BAD_TERRAIN):
        return False
    return grid.passable(p) and grid.passable((p[0] + 1, p[1]))


def find_spot(g, s, radius=20, max_level=99):
    here = nav.tile_of(s["player"])
    grid = nav.Grid(g.grid(radius), s["map"]["mons"])
    cands = [p for p in grid.tiles if sleep_ok(grid, p) and grid.tiles[p].get("rl", 0) <= max_level]
    cands.sort(key=lambda p: abs(p[0] - here[0]) + abs(p[1] - here[1]))
    return cands[:1] and cands[0]


def rest(g, until=0.95, log=print, max_seconds=240):
    """Walk to a safe tile, use the sleeping bag, wait until healed, wake up. Returns True if healed."""
    import time
    s = g.state()
    if "sleeping bag" not in s["player"]["items"]:
        return False
    spot = find_spot(g, s)
    if not spot:
        return False
    ok, s = nav.goto(g, spot)
    if not ok:
        return False
    if not items.use_item(g, "sleeping bag"):
        items.close_menus(g)
        return False
    t0 = time.time()
    while time.time() - t0 < max_seconds:
        s = g.wait(120)
        if not s["player"]["isSleeping"] or party_hp_frac(s) >= until:
            break
    log("rested: hp frac %.2f" % party_hp_frac(s))
    for _ in range(6):  # wake up
        if not g.state()["player"]["isSleeping"]:
            break
        g.tap("b", 2, 30)
        g.tap("a", 2, 30)
    return party_hp_frac(g.state()) >= until
