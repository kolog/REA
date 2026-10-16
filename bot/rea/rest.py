"""Healing by sleeping in the bag (restores the party; also sets the white-out spawn)."""
from . import nav, items, field

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


def world_spot_fn(world, bad):
    """Candidate sleeping tiles from the global map: plain ground (not grass/tidal) with free ground to the right."""
    def ok(p):
        return p not in bad and world.ch(p) == "." and world.ch((p[0] + 1, p[1])) == "."
    return ok


def rest(g, until=0.95, log=print, max_seconds=240, attempts=12):
    """Leave the grass by the cheapest route, sleep in the bag, wait until healed."""
    import time
    from . import battle, travel
    from .world import World
    s = nav.ensure_free(g)
    if "sleeping bag" not in s["player"]["items"]:
        return False
    world = World(g.world())
    bad = set()
    arrived = False
    for _ in range(attempts):
        s = nav.ensure_free(g)
        if battle.in_battle(s):
            battle.run_battle(g, log=log)
            continue
        here = nav.tile_of(s["player"])
        ok_fn = world_spot_fn(world, bad)
        path = world.path(here, lambda p: ok_fn(p), avoid_grass=True)
        if not path:
            return False
        # walk the whole route in short legs; grass tiles cost 43 so this leaves grass as fast as possible
        goal = here
        for d in path:
            goal = (goal[0] + nav.DIRS[d][0], goal[1] + nav.DIRS[d][1])
        r = travel.go_near(g, world, goal, dist=0, avoid_grass=True, max_legs=60)
        s = nav.ensure_free(g)
        if battle.in_battle(s):
            continue
        if r != "arrived":
            bad.add(goal)
            continue
        grid = nav.Grid(g.grid(3), s["map"]["mons"])
        if sleep_ok(grid, nav.tile_of(s["player"])):
            arrived = True
            break
        bad.add(goal)             # terrain name rules out sleeping here (desert, mountain ...)
    if not arrived:
        return False
    field.clear(g)                       # the bag refuses to work while a field move is active
    if not items.use_item(g, "sleeping bag"):
        items.close_menus(g)
        return False
    for _ in range(40):                      # the lying-down animation takes a few seconds
        s = g.wait(15)
        if s["player"]["isSleeping"]:
            break
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


def home_door(objs):
    """Tile of the house door nearest to the camp, or None."""
    doors = [(o[0], o[1]) for o in objs if "door" in o[2] and o[2].startswith("house")]
    camp = next(((o[0], o[1]) for o in objs if "campfire" in o[2]), None)
    if not doors:
        return None
    if camp is None:
        return doors[0]
    return min(doors, key=lambda d: abs(d[0] - camp[0]) + abs(d[1] - camp[1]))


def rest_home(g, door, until=0.95, log=print, max_seconds=240, attempts=12):
    """Sleep inside the house (twice the healing, and the interior becomes the safe place). True if healed."""
    import time
    from . import battle, travel
    from .world import World
    s = nav.ensure_free(g)
    if "sleeping bag" not in s["player"]["items"]:
        return False
    world = World(g.world())
    front = (door[0], door[1] - 1)
    inside = False
    for _ in range(attempts):
        s = nav.ensure_free(g, allow_interior=True)
        if battle.in_battle(s):
            battle.run_battle(g, log=log)
            continue
        if s["map"]["interior"]:
            inside = True
            break
        r = travel.go_near(g, world, front, dist=0, avoid_grass=True, max_legs=80)
        if r != "arrived":
            continue
        g.walk(["up"])                      # through the door
        for _ in range(12):
            g.wait(15)
            if g.state()["map"]["interior"]:
                break
    if not inside and not g.state()["map"]["interior"]:
        return False
    field.clear(g)
    if not items.use_item(g, "sleeping bag"):
        items.close_menus(g)
        return False
    for _ in range(40):
        s = g.wait(15)
        if s["player"]["isSleeping"]:
            break
    t0 = time.time()
    while time.time() - t0 < max_seconds:
        s = g.wait(120)
        if not s["player"]["isSleeping"] or party_hp_frac(s) >= until:
            break
    log("rested at home: hp frac %.2f" % party_hp_frac(s))
    for _ in range(6):
        if not g.state()["player"]["isSleeping"]:
            break
        g.tap("b", 2, 30)
        g.tap("a", 2, 30)
    nav.ensure_outside(g)
    return party_hp_frac(g.state()) >= until
