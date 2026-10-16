"""Frontier-style exploration on top of nav.goto (M1)."""
import random
from . import nav


class Explorer:
    def __init__(self, g, radius=20):
        self.g = g
        self.radius = radius
        self.seen = set()          # tiles we have stood next to or on
        self.failed = {}           # goal -> times it failed

    def _mark(self, here):
        for dx in range(-6, 7):
            for dy in range(-6, 7):
                self.seen.add((here[0] + dx, here[1] + dy))

    def pick_goal(self, s):
        here = nav.tile_of(s["player"])
        grid = nav.Grid(self.g.grid(self.radius), s["map"]["mons"])
        self._mark(here)
        best, best_score = None, -1
        cands = [p for p in grid.tiles if grid.passable(p) and not grid.get(p).get("grass") or random.random() < 0.1]
        random.shuffle(cands)
        for p in cands[:400]:
            if not grid.passable(p) or self.failed.get(p, 0) > 1:
                continue
            d = abs(p[0] - here[0]) + abs(p[1] - here[1])
            if d < 8:
                continue
            unseen = sum((p[0] + dx, p[1] + dy) not in self.seen
                         for dx in range(-6, 7, 3) for dy in range(-6, 7, 3))
            score = unseen * 4 - d * 0.3
            if score > best_score:
                best, best_score = p, score
        return best

    def step(self, on_interrupt=None):
        """One exploration leg. Returns the final state."""
        s = self.g.state()
        if not nav.is_free(s):
            if on_interrupt:
                on_interrupt(s)
            return self.g.state()
        goal = self.pick_goal(s)
        if goal is None:
            self.seen.clear()
            return s
        ok, s = nav.goto(self.g, goal, self.radius)
        if not ok:
            self.failed[goal] = self.failed.get(goal, 0) + 1
            if not nav.is_free(s) and on_interrupt:
                on_interrupt(s)
        return self.g.state()
