"""Home base around the campfire: a shelter (>=3 roof + >=2 fence tiles within 3 tiles of the farm pokemon doubles
their production, Pokemon.checkHabitat) and the farm itself."""
from . import economy, field, nav, travel
from .world import World

ROOF = "house5_roof_middle1"
FENCE = "fence1"
NEED_ROOF, NEED_FENCE = 3, 2


def count_pieces(objs, center, r=3):
    roof = fence = 0
    for o in objs:
        if abs(o[0] - center[0]) <= r and abs(o[1] - center[1]) <= r:
            if "roof" in o[2]:
                roof += 1
            elif "fence" in o[2]:
                fence += 1
    return roof, fence


def free_tiles_near(world, objs, center, r=2):
    taken = {(o[0], o[1]) for o in objs}
    out = []
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            p = (center[0] + dx, center[1] + dy)
            if p != center and p not in taken and world.ch(p) == "." and max(abs(dx), abs(dy)) >= 1:
                out.append(p)
    out.sort(key=lambda p: abs(p[0] - center[0]) + abs(p[1] - center[1]))
    return out


def shelter_missing(objs, center):
    roof, fence = count_pieces(objs, center)
    return max(0, NEED_ROOF - roof), max(0, NEED_FENCE - fence)


def build_shelter(g, world, objs, center, log=print, avoid=()):
    """Build the missing roof/fence pieces on free tiles around `center`. Returns number of pieces placed."""
    roofs, fences = shelter_missing(objs, center)
    plan = [ROOF] * roofs + [FENCE] * fences
    if not plan:
        return 0
    s = g.state()
    items = economy.inv(s)
    if items.get("log", 0) < len(plan) or items.get("grass", 0) < len(plan):
        need = {"log": len(plan), "grass": len(plan)}
        economy.gather(g, world, need, "CUT", log=log, max_trips=25)
        field.clear(g)
        s = g.state()
        items = economy.inv(s)
        if items.get("log", 0) < len(plan) or items.get("grass", 0) < len(plan):
            return 0
    spots = free_tiles_near(world, objs, center)
    if len(spots) < len(plan) + 2:              # not enough clear ground: cut the vegetation around the camp first
        economy.clear_area(g, world, center, r=3, log=log, avoid=avoid)
        objs = g.objects()
        world = World(g.world())                # terrain changed: refresh
        spots = free_tiles_near(world, objs, center)
    placed = 0
    for piece in plan:
        for p in list(spots):
            r = travel.go_near(g, world, p, dist=1, avoid_grass=True, max_legs=40, avoid=avoid)
            if r != "arrived":
                continue
            if economy.build_at(g, piece, p, log=log):
                placed += 1
                spots.remove(p)
                break
            spots.remove(p)
    field.clear(g)
    return placed
