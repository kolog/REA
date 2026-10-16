"""Resource gathering, building and crafting (M3). Yields come from Tile.items() in the decompiled game."""
from . import battle, field, nav, recruit, travel

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
        s = nav.ensure_free(g)
        if battle.in_battle(s):
            battle.run_battle(g, log=log)
            continue
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
            continue
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


def free_neighbor(g, avoid_grass=True):
    """Direction of an adjacent empty, walkable tile (nothing built/grown on it), or None."""
    s = g.state()
    here = nav.tile_of(s["player"])
    grid = nav.Grid(g.grid(2), s["map"]["mons"])
    for d, (dx, dy) in nav.DIRS.items():
        p = (here[0] + dx, here[1] + dy)
        t = grid.get(p)
        if t and grid.passable(p) and not t.get("u") and not t.get("item") and not (avoid_grass and t.get("grass")):
            return d
    return None


def build(g, tile_name, log=print):
    """Use BUILD (a FIGHTING-type member) to place `tile_name` (e.g. 'campfire1') on an adjacent free tile."""
    s = nav.ensure_free(g)
    idx = party_with(s, "BUILD")
    if idx is None:
        log("no BUILD pokemon")
        return False
    if not field.select(g, idx, "BUILD", log):
        return False
    for _ in range(40):
        if g.state()["player"]["building"] == tile_name:
            break
        g.tap("r", 2, 8)
    else:
        log("could not select build tile %s" % tile_name)
        return False
    d = free_neighbor(g)
    if d is None:
        log("no free tile next to me")
        return False
    recruit.face(g, d)
    before = dict(g.state()["player"]["items"])
    g.tap("a", 2, 40)
    for _ in range(8):
        s = g.state()
        if "DisplayText" in s["actions"]:
            g.tap("a", 2, 14)
        else:
            g.wait(15)
    after = g.state()["player"]["items"]
    spent = {k: before[k] - after.get(k, 0) for k in before if before[k] != after.get(k, 0)}
    log("built %s, spent %s" % (tile_name, spent))
    return bool(spent)


def open_crafts(g, camp):
    """Walk next to the campfire at tile `camp`, face it and open the crafting menu."""
    field.clear(g)
    d = recruit.approach(g, camp)
    if d is None:
        return False
    recruit.face(g, d)
    g.tap("a", 2, 30)
    for _ in range(40):
        if "DrawCraftsMenu" in g.state()["actions"]:
            g.wait(20)
            return True
        g.wait(8)
    return False


def craft(g, name, amount=1, log=print):
    """With the crafts menu open: make `amount` of `name`. Returns the amount gained."""
    for _ in range(40):                                  # wait until the list accepts input again
        m = g.act("DrawCraftsMenu", 1)
        if m is not None and not m.get("disabled"):
            break
        g.wait(6)
    g.wait(10)
    m = g.act("DrawCraftsMenu", 2)
    if m is None:
        return 0
    lst = m["craftsList"]
    if name not in lst:
        log("%s is not craftable here" % name)
        return 0
    t = lst.index(name)

    def where():
        c = g.act("DrawCraftsMenu", 1)["currCraft"]
        return lst.index(c) if c in lst else len(lst) - 1      # '' is the Cancel row
    for _ in range(60):
        cur = where()
        if cur == t:
            break
        g.tap("down" if t > cur else "up", 2, 10)
    else:
        log("could not reach %s in the craft list" % name)
        return 0
    before = dict(g.state()["player"]["items"])
    g.tap("a", 2, 20)
    for _ in range(30):                                  # SelectAmount menu
        if "DrawCraftsMenu$SelectAmount" in g.state()["actions"]:
            break
        g.wait(6)
    else:
        return 0
    for _ in range(amount - 1):
        g.tap("up", 2, 6)
    g.tap("a", 2, 20)
    for _ in range(30):                                  # CRAFT / CANCEL confirmation (cursor starts on CRAFT)
        if "DrawCraftsMenu$Selected" in g.state()["actions"]:
            break
        g.wait(6)
    g.wait(12)
    g.tap("a", 2, 20)
    for _ in range(40):                                  # "crafted" text and back to the list
        s = g.state()
        if "DisplayText" in s["actions"]:
            g.tap("a", 2, 14)
        elif "DrawCraftsMenu" in s["actions"] and not any(a in s["actions"] for a in ("DrawCraftsMenu$SelectAmount", "DrawCraftsMenu$Selected")):
            break
        else:
            g.wait(8)
    after = g.state()["player"]["items"]
    gained = after.get(name, 0) - before.get(name, 0)
    log("crafted %s x%d" % (name, gained))
    return gained


def close_crafts(g):
    for _ in range(6):
        s = g.state()
        if any(a.startswith("DrawCraftsMenu") for a in s["actions"]):
            g.tap("b", 2, 14)
        else:
            return
