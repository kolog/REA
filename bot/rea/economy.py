"""Resource gathering, building and crafting (M3). Yields come from Tile.items() in the decompiled game."""
from . import field, nav, recruit, travel

# nameUpper -> (field move needed, items it yields). Apricorns are random (50 %), listed as "apricorn".
YIELD = {
    "bush2_color": ("CUT", {"log": 1, "apricorn": 0.5}),
    "tree2": ("CUT", {"log": 2, "apricorn": 1.0}),
    "tree4": ("CUT", {"log": 2, "apricorn": 1.0}),
    "tree5": ("CUT", {"log": 2}),
    "tree6": ("CUT", {"log": 2}),
    "tree_large1": ("CUT", {"log": 4}),
    "tree_savanna1": ("CUT", {"log": 4}),
    "bush_savanna1": ("CUT", {"log": 1, "grass": 1}),
    "grass_savanna1": ("CUT", {"grass": 4}),
    "grass_savanna2": ("CUT", {"grass": 2}),
    "grass2": ("CUT", {"grass": 1}),
    "grass3": ("CUT", {"grass": 1}),
    "grass4": ("CUT", {"grass": 2}),
    "aloe_large1": ("CUT", {"log": 1, "grass": 4}),
    "rock1": ("SMASH", {"hard stone": 1}),
    "rock1_color": ("SMASH", {"hard stone": 1}),
    "rock_volcano1": ("SMASH", {"hard stone": 1}),
}
APRICORNS = ("black apricorn", "blue apricorn", "green apricorn", "pink apricorn",
             "red apricorn", "white apricorn", "yellow apricorn")


def party_with(s, move):
    """Index of the first party member that offers field move `move`, or None."""
    for i, m in enumerate(s["player"]["party"]):
        if move in m.get("hms", []):
            return i
    return None


def score(kind, wants):
    """How much a resource tile helps with what we still need."""
    mv, y = YIELD[kind]
    v = 0.0
    for item, n in y.items():
        if item == "apricorn":
            v += n * wants.get("apricorn", 0)
        else:
            v += min(n, wants.get(item, 0))
    return v


def nearest_resource(world, here, objs, wants, move, skip=()):
    dist = world.dist_map(here)
    best, best_cost = None, 1e18
    for o in objs:
        kind = o[2]
        if kind not in YIELD or YIELD[kind][0] != move or (o[0], o[1]) in skip:
            continue
        v = score(kind, wants)
        if v <= 0:
            continue
        near = [dist[(o[0] + dx, o[1] + dy)] for dx, dy in nav.DIRS.values() if (o[0] + dx, o[1] + dy) in dist]
        if not near:
            continue
        cost = min(near) / v
        if cost < best_cost:
            best, best_cost = o, cost
    return best


def inv(s):
    """Inventory with a synthetic 'apricorn' total."""
    it = dict(s["player"]["items"])
    it["apricorn"] = sum(it.get(a, 0) for a in APRICORNS)
    return it


def missing(items, need):
    return {k: v - items.get(k, 0) for k, v in need.items() if items.get(k, 0) < v}


def gather(g, world, need, move="CUT", log=print, max_trips=40):
    """Collect resources until `need` ({item: amount}) is met. Returns True when it is."""
    skip = set()
    for _ in range(max_trips):
        s = g.state()
        lack = missing(inv(s), need)
        if not lack:
            return True
        idx = party_with(s, move)
        if idx is None:
            log("no party member can %s" % move)
            return False
        if s["player"]["field"] != move or s["player"]["hm"] != idx:
            if not field.select(g, idx, move, log):
                return False
        here = nav.tile_of(s["player"])
        o = nearest_resource(world, here, g.objects(), dict(lack), move, skip)
        if o is None:
            log("no %s resource left for %s" % (move, lack))
            return False
        tile = (o[0], o[1])
        r = travel.go_near(g, world, tile, dist=1, max_level=None)
        if r == "battle":
            return False
        d = recruit.approach(g, tile)
        if d is None:
            skip.add(tile)
            continue
        recruit.face(g, d)
        before = dict(g.state()["player"]["items"])
        g.tap("a", 2, 40)
        for _ in range(8):
            s = g.state()
            if "DisplayText" in s["actions"]:
                g.tap("a", 2, 14)
            elif "CutTreeAnim" in s["actions"] or "DrawItemPickup" in s["actions"]:
                g.wait(20)
            else:
                break
        after = g.state()["player"]["items"]
        got = {k: after.get(k, 0) - before.get(k, 0) for k in set(after) | set(before) if after.get(k, 0) != before.get(k, 0)}
        skip.add(tile)
        if got:
            log("gathered %s from %s" % (got, o[2]))
    return not missing(inv(g.state()), need)
