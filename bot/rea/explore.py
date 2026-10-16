"""Frontier-style exploration on top of nav.goto (M1)."""
import random
from . import nav, rest


class Explorer:
    def __init__(self, g, radius=20):
        self.g = g
        self.radius = radius
        self.seen = set()          # tiles we have stood next to or on
        self.failed = {}           # goal -> times it failed
        self.danger = set()        # tiles around places where we had to run away
        self.log = print

    def policy(self, s):
        party = s["player"]["party"]
        top = max((m["lvl"] for m in party), default=5)
        frac = rest.party_hp_frac(s)
        # Cap the route level, but never below the level of the ground we stand on or of the
        # lowest route nearby, otherwise a high-level spawn would leave no legal tile at all.
        cap = top + 6
        return {"max_level": cap, "avoid_grass": frac < 0.6, "blocked": self.danger}

    def mark_danger(self, tile, r=8):
        """Called after fleeing a battle: don't come back to this neighbourhood."""
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                self.danger.add((tile[0] + dx, tile[1] + dy))

    def _mark(self, here):
        for dx in range(-6, 7):
            for dy in range(-6, 7):
                self.seen.add((here[0] + dx, here[1] + dy))

    def pick_goal(self, s):
        here = nav.tile_of(s["player"])
        self.pol = self.policy(s)
        grid = nav.Grid(self.g.grid(self.radius), s["map"]["mons"], **self.pol)
        self._mark(here)
        best, best_score = None, -1
        cands = [p for p in grid.tiles if grid.passable(p) and (not grid.get(p).get("grass") or random.random() < 0.1)]
        random.shuffle(cands)
        cap = self.pol["max_level"]
        lv = lambda p: grid.get(p).get("rl", 0)
        safe = [p for p in cands if lv(p) <= cap]
        if not safe and cands:                    # nothing safe in view: head for the weakest ground
            low = min(lv(p) for p in cands)
            safe = [p for p in cands if lv(p) == low]
        for p in safe[:400]:
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
        if rest.party_hp_frac(s) < 0.5:          # hurt: heal before wandering
            if rest.rest(self.g, log=self.log):
                return self.g.state()
        goal = self.pick_goal(s)
        if goal is None:
            self.seen.clear()
            self.danger.clear()
            self.g.wait(30)       # never spin without letting the game advance
            return self.g.state()
        ok, s = nav.goto(self.g, goal, self.radius, policy=self.pol)
        if not ok:
            self.failed[goal] = self.failed.get(goal, 0) + 1
            if not nav.is_free(s) and on_interrupt:
                on_interrupt(s)
        return self.g.state()
