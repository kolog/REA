"""Farm: drop non-essential pokemon where their habitat is satisfied and harvest what they produce.

Rules come from Pokemon.checkHabitat / Specie.initHabitatValues: within +-3 tiles of the pokemon every habitat
group of the species needs one tile whose name/object contains one of its keywords; a species without habitat
groups (electric, psychic, fighting, fairy, poison) produces anywhere.
"""
from . import economy, field, nav, recruit, travel

# type -> habitat keyword group (any of them satisfies the group)
HABITAT = {
    "WATER": ("water",),
    "ROCK": ("rock", "statue", "gym"),
    "FIRE": ("campfire", "lava", "soot", "volcano"),
    "GRASS": ("grass",),
    "FLYING": ("tree", "bush"),
}
PRODUCE = {"BUG": "silky thread", "WATER": "hard shell", "FLYING": "soft feather", "ROCK": "hard stone",
           "FIRE": "charcoal", "GRASS": "miracle seed", "POISON": "poison barb", "GROUND": "soft sand",
           "STEEL": "metal coat", "PSYCHIC": "psi energy", "DARK": "dark energy", "GHOST": "life force",
           "FIGHTING": "binding band", "FAIRY": "stardust", "ICE": "nevermeltice", "ELECTRIC": "magnet",
           "DRAGON": "dragon scale"}
UNSUPPORTED = {"BUG", "GROUND", "STEEL", "GHOST", "ICE", "DRAGON"}      # habitat tiles not modelled yet
VALUE = {"magnet": 5, "hard shell": 5, "life force": 3, "metal coat": 3, "stardust": 2, "hard stone": 2,
         "charcoal": 2, "miracle seed": 2, "soft feather": 1, "poison barb": 1, "psi energy": 1,
         "binding band": 1, "dark energy": 1}
NEEDED_MOVES = {"BUILD", "CUT", "SMASH", "DIG", "HEADBUTT", "SURF", "FLY"}


def produce_value(types):
    return max([VALUE.get(PRODUCE.get(t, ""), 0) for t in set(types)] or [0])


def groups_for(types):
    return [HABITAT[t] for t in set(types) if t in HABITAT]


def farmable(types):
    return not (set(types) & UNSUPPORTED)


class HabitatMap:
    """Tag sets built from the world export (ground chars) and the object list."""

    def __init__(self, world, objs):
        self.world = world
        self.tags = {k: set() for k in ("water", "rock", "tree", "fire", "grass")}
        for r in range(world.h):
            row = world.rows[r]
            y = world.y1 - r
            for c, ch in enumerate(row):
                if ch == "w":
                    self.tags["water"].add((c + world.x0, y))
                elif ch == "g":
                    self.tags["grass"].add((c + world.x0, y))
        for o in objs:
            n = o[2]
            p = (o[0], o[1])
            if any(k in n for k in ("rock", "statue", "gym")):
                self.tags["rock"].add(p)
            if any(k in n for k in ("tree", "bush")):
                self.tags["tree"].add(p)
            if any(k in n for k in ("campfire", "lava", "soot", "volcano")):
                self.tags["fire"].add(p)
            if "grass" in n:
                self.tags["grass"].add(p)

    def satisfied(self, q, groups, r=3):
        for grp in groups:
            ok = False
            for kw in grp:
                key = {"water": "water", "rock": "rock", "statue": "rock", "gym": "rock", "tree": "tree",
                       "bush": "tree", "campfire": "fire", "lava": "fire", "soot": "fire", "volcano": "fire",
                       "grass": "grass"}[kw]
                tiles = self.tags[key]
                if any((q[0] + dx, q[1] + dy) in tiles for dx in range(-r, r + 1) for dy in range(-r, r + 1)):
                    ok = True
                    break
            if not ok:
                return False
        return True


def find_drop_spot(world, objs, types, origin, limit=60, hab=None):
    """Nearest walkable tile (by walking distance from origin) from which a pokemon dropped on the next tile is in
    its habitat. Returns (stand_tile, drop_tile) or None."""
    hab = hab or HabitatMap(world, objs)
    groups = groups_for(types)
    dist = world.dist_map(origin)
    blocked = {(o[0], o[1]) for o in objs}
    cands = sorted((p for p, d in dist.items() if d <= limit and world.ch(p) == "." and p not in blocked),
                   key=lambda p: dist[p])
    for p in cands:
        for dx, dy in nav.DIRS.values():
            q = (p[0] + dx, p[1] + dy)
            if world.ch(q) == "." and q not in blocked and hab.satisfied(q, groups):
                return p, q
    return None


def deployable(s):
    """Party index of a member that can leave the team for farming, or None."""
    party = s["player"]["party"]
    if len(party) < 5:
        return None
    by_level = sorted(range(len(party)), key=lambda i: -party[i]["lvl"])
    top = set(by_level[:3])
    best = None
    for i, m in enumerate(party):
        if i in top or not farmable(m["types"]):
            continue
        provides = set(m.get("hms", [])) & NEEDED_MOVES
        others = {h for j, o in enumerate(party) if j != i for h in o.get("hms", [])}
        if provides - others:                       # the only one that can use some needed field move
            continue
        v = produce_value(m["types"])
        if v > 0 and (best is None or v > best[0]):
            best = (v, i)
    return best[1] if best else None


def ready_items(mons):
    """Owned pokemon on the map that currently hold an item: [(specie, tile, item)]."""
    return [(m[0], (m[3], m[4]), m[5]) for m in mons if m[2] == "owned" and m[5]]


def collect(g, world, mons, log=print, avoid=()):
    """Walk to the nearest ready pokemon and take its item. Returns True if anything was attempted."""
    ready = ready_items(mons)
    if not ready:
        return False
    s = g.state()
    here = nav.tile_of(s["player"])
    ready.sort(key=lambda r: abs(r[1][0] - here[0]) + abs(r[1][1] - here[1]))
    specie, tile, item = ready[0]
    log("collect %s from %s at %s" % (item, specie, tile))
    r = travel.go_near(g, world, tile, dist=2, avoid_grass=True, max_legs=60, avoid=avoid)
    if r != "arrived":
        return True
    fresh = [m for m in g.allmons() if m[2] == "owned" and m[0] == specie and m[5]]
    if not fresh:
        return True
    fresh.sort(key=lambda m: abs(m[3] - here[0]) + abs(m[4] - here[1]))
    field.clear(g)
    recruit.pick_up(g, (fresh[0][3], fresh[0][4]), log=log)
    return True


def deploy(g, world, objs, idx, log=print, avoid=()):
    """Drop party member `idx` in a spot that satisfies its habitat. Returns True if it left the party."""
    s = g.state()
    m = s["player"]["party"][idx]
    here = nav.tile_of(s["player"])
    spot = find_drop_spot(world, objs, m["types"], here, limit=250)
    if spot is None:
        log("no habitat spot for %s" % m["specie"])
        return False
    stand, drop = spot
    log("deploying %s at %s (drop tile %s)" % (m["specie"], stand, drop))
    r = travel.go_near(g, world, stand, dist=0, avoid_grass=True, max_legs=80, avoid=avoid)
    if r == "battle":
        return "interrupted"             # not a failure: the caller fights and tries again
    if r != "arrived":
        return False
    # face the intended drop tile, then drop
    d = next(k for k, (dx, dy) in nav.DIRS.items() if (stand[0] + dx, stand[1] + dy) == drop)
    s = g.state()
    idx = next((i for i, x in enumerate(s["player"]["party"]) if x["specie"] == m["specie"]), idx)
    field.clear(g)
    recruit.face(g, d)
    before = len(g.state()["player"]["party"])
    if not field.party_action(g, idx, "DROP", log):
        return False
    for _ in range(30):
        s = g.state()
        if "DrawYesNoMenu" in s["actions"]:
            recruit.yes_no(g, True)
        elif "DisplayText" in s["actions"]:
            g.tap("a", 2, 14)
        elif "PlayerStanding" in s["actions"] and not any("Menu" in a for a in s["actions"]):
            break
        else:
            g.wait(8)
    return len(g.state()["player"]["party"]) < before


def recall(g, world, specie, log=print, avoid=()):
    """Take a dropped pokemon back into the party (only possible while the party has room)."""
    s = nav.ensure_free(g)
    if len(s["player"]["party"]) >= 6:
        return False
    mons = [m for m in g.allmons() if m[2] == "owned" and m[0] == specie]
    if not mons:
        return False
    here = nav.tile_of(s["player"])
    mons.sort(key=lambda m: abs(m[3] - here[0]) + abs(m[4] - here[1]))
    tile = (mons[0][3], mons[0][4])
    if travel.go_near(g, world, tile, dist=2, avoid_grass=True, max_legs=60, avoid=avoid) != "arrived":
        return False
    fresh = [m for m in g.allmons() if m[2] == "owned" and m[0] == specie]
    if not fresh:
        return False
    tile = (fresh[0][3], fresh[0][4])
    field.clear(g)
    d = recruit.approach(g, tile)
    if d is None:
        return False
    n = len(g.state()["player"]["party"])
    for _ in range(3):                      # first A may only hand over a held item
        recruit.face(g, d)
        g.tap("a", 2, 20)
        s = recruit.dismiss_text(g)
        if "DrawYesNoMenu" in s["actions"]:
            recruit.yes_no(g, True)
            recruit.dismiss_text(g)
            break
    ok = len(g.state()["player"]["party"]) > n
    if ok:
        log("recalled %s" % specie)
    return ok
