"""Tile grid, A* and a step-by-step walker (M1)."""
import heapq

DIRS = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}
OPP = {"up": "down", "down": "up", "left": "right", "right": "left"}


class Grid:
    """Local tile window around the player, indexed by integer tile coords (tx, ty); y grows upward."""

    def __init__(self, resp, mons=(), max_level=None, avoid_grass=False, blocked=()):
        self.blocked = set(blocked)       # tiles we learned to stay away from
        self.max_level = max_level        # refuse tiles of routes above this level
        self.avoid_grass = avoid_grass    # treat grass (wild encounters) as a wall
        self.r = resp["r"]
        self.cx = int(round(resp["px"] / 16))
        self.cy = int(round(resp["py"] / 16))
        self.tiles = {}
        i = 0
        for dy in range(self.r, -self.r - 1, -1):
            for dx in range(-self.r, self.r + 1):
                self.tiles[(self.cx + dx, self.cy + dy)] = resp["tiles"][i]
                i += 1
        self.mons = {(int(round(m["x"][0] / 16)), int(round(m["x"][1] / 16)))
                     for m in mons if m.get("x")}

    def get(self, p):
        return self.tiles.get(p)

    def passable(self, p, move_dir=None):
        t = self.tiles.get(p)
        if t is None or p in self.mons or p in self.blocked:
            return False
        if self.avoid_grass and t.get("grass") and not t.get("tidal"):
            return False
        if t.get("solid") or t.get("water") or t.get("lava") or t.get("ledge") or t.get("waterfall"):
            return False
        return True

    def cost(self, p):
        t = self.tiles[p]
        c = 1.0 if t.get("tidal") else (6.0 if t.get("grass") else 1.0)
        if self.max_level is not None and t.get("rl", 0) > self.max_level:
            c += 10.0         # too dangerous: allowed only as a way out
        return c

    def astar(self, start, goal_fn, h=None):
        """Path of directions from start to the nearest tile satisfying goal_fn (or None)."""
        openq = [(0, 0, start)]
        best = {start: 0}
        prev = {}
        while openq:
            _, g, cur = heapq.heappop(openq)
            if g > best.get(cur, 1e9):
                continue
            if goal_fn(cur):
                path = []
                while cur in prev:
                    cur, d = prev[cur]
                    path.append(d)
                return path[::-1]
            for d, (dx, dy) in DIRS.items():
                n = (cur[0] + dx, cur[1] + dy)
                if not self.passable(n, d) and not goal_fn(n):
                    continue
                if n not in self.tiles:
                    continue
                if not self.passable(n, d) and goal_fn(n) and n in self.mons:
                    continue
                ng = g + (self.cost(n) if self.passable(n) else 1)
                if ng < best.get(n, 1e9):
                    best[n] = ng
                    prev[n] = (cur, d)
                    hh = h(n) if h else 0
                    heapq.heappush(openq, (ng + hh, ng, n))
        return None


def tile_of(p):
    return int(round(p["x"] / 16)), int(round(p["y"] / 16))


def is_free(s):
    """True when the player stands on a tile and the overworld is accepting input."""
    return "PlayerStanding" in s["actions"] and not any(
        a in s["actions"] for a in ("DisplayText", "DrawBattle", "DrawAttacksMenu", "DrawPlayerMenu"))


def ensure_free(g, tries=25):
    """Close leftover text boxes / menus until the overworld accepts input again. Returns the state."""
    s = g.state()
    for _ in range(tries):
        if is_free(s) or "DrawBattle" in s["actions"]:
            return s
        acts = s["actions"]
        if "DrawYesNoMenu" in acts:
            g.tap("b", 2, 12)
        elif "DisplayText" in acts:
            g.tap("a", 2, 14)
        elif any(a.startswith("Draw") and "Menu" in a for a in acts):
            g.tap("b", 2, 14)
        else:
            g.wait(8)
        s = g.state()
    return s


def walk_step(g, d, max_frames=60):
    """Try to move one tile in direction d. Returns (state, moved)."""
    s = g.state()
    start = (s["player"]["x"], s["player"]["y"])
    for _ in range(max_frames):
        s = g.hold(d, 2)
        p = s["player"]
        if (p["x"], p["y"]) != start:
            break
        if not is_free(s):
            return s, False
    else:
        return s, False
    for _ in range(60):  # let the move finish
        s = g.wait(2)
        if is_free(s) and s["player"]["x"] % 16 == 0 and s["player"]["y"] % 16 == 0:
            break
    return s, True


def settle(g, frames=60):
    """Wait until the player is standing on a tile again."""
    s = g.wait(1)
    for _ in range(frames // 2):
        if is_free(s) and s["player"]["x"] % 16 == 0 and s["player"]["y"] % 16 == 0:
            break
        s = g.wait(2)
    return s


def goto(g, goal, radius=20, max_replans=60, leg=6, policy=None):
    """Walk to tile `goal` (tx, ty). Returns (arrived, last_state)."""
    s = ensure_free(g)
    for _ in range(max_replans):
        if not is_free(s):
            return False, s
        here = tile_of(s["player"])
        if here == goal:
            return True, s
        grid = Grid(g.grid(radius), s["map"]["mons"], **(policy or {}))
        path = grid.astar(here, lambda p: p == goal,
                          h=lambda p: abs(p[0] - goal[0]) + abs(p[1] - goal[1]))
        if not path:
            return False, s
        s, res, done = g.walk(path[:leg])  # short legs: re-read map between them
        s = settle(g)
        if res == "interrupted":
            return False, s
    return False, s
