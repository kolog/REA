"""Flying travel (M5). While FLY is active no wild pokemon aggro or touch the player and any terrain can be crossed."""
from . import field, nav


def active(s):
    return s["player"]["field"] == "FLY"


def take_off(g, log=print):
    """Use FLY from the party menu with a pokemon that knows it. Returns True when flying."""
    s = nav.ensure_free(g)
    if active(s):
        return True
    idx = next((i for i, m in enumerate(s["player"]["party"]) if "FLY" in m.get("hms", [])), None)
    if idx is None:
        log("no pokemon knows FLY")
        return False
    if not field.party_action(g, idx, "FLY", log):
        return False
    for _ in range(40):                              # take-off animation
        s = g.wait(20)
        if active(s) and "Flying" in " ".join(s["actions"]) or active(s):
            g.wait(40)
            break
    return active(g.state())


def goto(g, target_tile, log=print, max_calls=60):
    """Fly in straight lines (x then y) until within half a tile of target_tile (tile coords)."""
    tx, ty = target_tile[0] * 16, target_tile[1] * 16
    for _ in range(max_calls):
        s = g.state()
        if not active(s):
            return False
        x, y = s["player"]["x"], s["player"]["y"]
        dx, dy = tx - x, ty - y
        if abs(dx) <= 8 and abs(dy) <= 8:
            return True
        if abs(dx) > 8:
            d, dist = ("right", dx) if dx > 0 else ("left", -dx)
        else:
            d, dist = ("up", dy) if dy > 0 else ("down", -dy)
        frames = int(max(2, min(150, (abs(dist) - 4) / 2.0)))
        g.hold(d, frames)
    return False


def land(g, log=print):
    """Press B on a tile that is free; if it refuses, drift one tile and retry. True when on the ground."""
    for i in range(8):
        s = g.state()
        if not active(s):
            return True
        g.tap("b", 2, 40)
        s = g.wait(60)
        if not active(s):
            return True
        g.hold(("right", "up", "left", "down")[i % 4], 8)   # the tile below us was solid/occupied: shift and retry
    return not active(g.state())


def trip(g, world, tile, log=print):
    """Take off, fly to a free walkable tile next to `tile` and land there. Returns the landing tile or None."""
    spots = [(tile[0] + dx, tile[1] + dy) for dx, dy in nav.DIRS.values()
             if world.ch((tile[0] + dx, tile[1] + dy)) in (".", "t")]
    if not spots:
        return None
    spot = spots[0]
    if not take_off(g, log):
        return None
    ok = goto(g, spot, log)
    landed = land(g, log)
    here = nav.tile_of(g.state()["player"])
    log("flew to %s, landed at %s (%s)" % (spot, here, "ok" if ok and landed else "check"))
    return here if landed else None
