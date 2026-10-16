"""Whole-island terrain model and global path planning."""
import heapq
from collections import deque

DIRS = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}
WALK_COST = {".": 1.0, "t": 1.1, "g": 3.0}      # ledges, water, walls, doors are never planned through


class World:
    def __init__(self, resp):
        self.x0, self.y1, self.w, self.h = resp["x0"], resp["y1"], resp["w"], resp["h"]
        self.rows = resp["rows"]
        self.lv = resp["lv"]

    def ch(self, p):
        c, r = p[0] - self.x0, self.y1 - p[1]
        if 0 <= c < self.w and 0 <= r < self.h:
            return self.rows[r][c]
        return " "

    def level(self, p):
        c, r = p[0] - self.x0, self.y1 - p[1]
        if 0 <= c < self.w and 0 <= r < self.h:
            return int(self.lv[r][2 * c:2 * c + 2])
        return 0

    def walkable(self, p):
        return self.ch(p) in WALK_COST

    def path(self, start, goal_fn, blocked=(), max_level=None, avoid_grass=False, limit=200000):
        """Cheapest list of directions from start to the nearest tile with goal_fn(tile) true."""
        best = {start: 0.0}
        prev = {}
        pq = [(0.0, start)]
        n = 0
        while pq:
            g, cur = heapq.heappop(pq)
            if g > best.get(cur, 1e18):
                continue
            if cur != start and goal_fn(cur):
                out = []
                while cur in prev:
                    cur, d = prev[cur]
                    out.append(d)
                return out[::-1]
            n += 1
            if n > limit:
                return None
            for d, (dx, dy) in DIRS.items():
                nx = (cur[0] + dx, cur[1] + dy)
                ch = self.ch(nx)
                if ch not in WALK_COST or nx in blocked:
                    continue
                c = WALK_COST[ch]
                if ch == "g" and avoid_grass:
                    c += 40
                if max_level is not None and self.level(nx) > max_level:
                    c += 25
                ng = g + c
                if ng < best.get(nx, 1e18):
                    best[nx] = ng
                    prev[nx] = (cur, d)
                    heapq.heappush(pq, (ng, nx))
        return None

    def dist_map(self, start, limit=200000):
        """Walking distance (in steps) from start to every reachable tile."""
        dist = {start: 0}
        q = deque([start])
        while q and len(dist) < limit:
            cur = q.popleft()
            for dx, dy in DIRS.values():
                nx = (cur[0] + dx, cur[1] + dy)
                if nx not in dist and self.walkable(nx):
                    dist[nx] = dist[cur] + 1
                    q.append(nx)
        return dist
