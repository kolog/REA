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


# ---------------------------------------------------------------- the house
HOUSE_W, HOUSE_H = 5, 3          # wall row (with the door) + two roof rows => 5x3 interior floor


def find_site(world, objs, mons, camp, w=HOUSE_W, h=HOUSE_H, margin=1, radius=30):
    """Best origin (south-west corner) for a w x h building: a flat, empty, grass-free rectangle (plus a free margin
    so every outside piece can be built from a free tile), close to the camp and away from strong aggressive mons."""
    taken = {(o[0], o[1]) for o in objs}
    danger = [(m[3], m[4]) for m in mons if m[2] == "aggro"]
    dist = world.dist_map(camp)
    best = None
    for (cx, cy), d in dist.items():
        if d > radius:
            continue
        for ox in range(cx - w, cx + 1):
            oy = cy
            key = (ox, oy)
            ok = True
            for x in range(ox - margin, ox + w + margin):
                for y in range(oy - margin, oy + h + margin):
                    p = (x, y)
                    if world.ch(p) != "." or p in taken:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                continue
            nearest_agg = min([abs(ox - a[0]) + abs(oy - a[1]) for a in danger] or [99])
            if nearest_agg < 12:
                continue
            score = abs(ox + w // 2 - camp[0]) + abs(oy + h // 2 - camp[1])
            if best is None or score < best[0]:
                best = (score, key)
    return best[1] if best else None


def house_plan(origin, w=HOUSE_W, h=HOUSE_H):
    """Pieces in a build order that always leaves a free outside tile next to the piece being placed."""
    x0, y0 = origin
    plan = []
    for i in range(w):                                   # wall row, door in the middle
        plan.append(("house5_door1" if i == w // 2 else "house5_middle1", (x0 + i, y0)))
    for j in range(1, h):                                # roof rows, south to north
        for i in range(w):
            plan.append(("house5_roof_middle1", (x0 + i, y0 + j)))
    return plan


def build_house(g, world, objs, origin, log=print, avoid=()):
    """Place every missing piece. Gathers all materials first, then builds. Returns (placed, total)."""
    plan = house_plan(origin)
    have = {(o[0], o[1]): o[2] for o in objs}
    todo = [(n, t) for n, t in plan if t not in have]
    if not todo:
        return 0, len(plan)
    need = {"log": len(todo), "grass": len(todo)}
    s = g.state()
    if economy.missing(economy.inv(s), need):
        economy.gather(g, world, need, "CUT", log=log, max_trips=40)
        field.clear(g)
        if economy.missing(economy.inv(g.state()), need):
            return 0, len(plan)
    placed = 0
    for name, tile in todo:
        s = nav.ensure_free(g)
        if "DrawBattle" in s["actions"]:
            break
        if economy.build_at(g, name, tile, log=log):
            placed += 1
    field.clear(g)
    return placed, len(plan)
