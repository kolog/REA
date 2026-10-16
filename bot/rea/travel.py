"""Long-distance walking on the global map, in short re-planned legs."""
from . import nav, battle


def go_near(g, world, target, dist=1, leg=6, max_legs=80, blocked=(), max_level=None, on_leg=None, avoid_grass=False, avoid=()):
    """Walk until within `dist` (manhattan) of `target`. Returns 'arrived' | 'battle' | 'nopath' | 'timeout'."""
    for _ in range(max_legs):
        s = g.state()
        if battle.in_battle(s):
            return "battle"
        if not nav.is_free(s):
            nav.ensure_free(g)
            continue
        here = nav.tile_of(s["player"])
        if abs(here[0] - target[0]) + abs(here[1] - target[1]) <= dist:
            return "arrived"
        mons = {(int(round(m["x"][0] / 16)), int(round(m["x"][1] / 16))) for m in s["map"]["mons"] if m.get("x")}
        path = world.path(here, lambda p: abs(p[0] - target[0]) + abs(p[1] - target[1]) <= dist,
                          blocked=set(blocked) | mons, max_level=max_level, avoid_grass=avoid_grass, avoid=avoid)
        if not path:
            return "nopath"
        s, res, done = g.walk(path[:leg])
        nav.settle(g)
        if on_leg:
            on_leg(g.state())
    return "timeout"
