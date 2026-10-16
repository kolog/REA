"""Goal-driven behaviour: heal when hurt, otherwise train the lead Pokemon in suitable grass.

Why this does not wander in circles: every cycle has an explicit goal (a grind zone picked on the
global map), progress is measured (battles / exp), and a zone that yields nothing or scares us off
is blacklisted for a while.
"""
import json
import os
import random
import time
from collections import deque

from . import battle, evo, field, nav, rest
from .world import World

MEMORY = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "memory.json")


class Trainer:
    def __init__(self, g, log=print):
        self.g = g
        self.log = log
        self.world = None
        self.zone = None                 # (tile in the zone, route level)
        self.zone_since = 0.0
        self.zone_battles = 0
        self.bad_zones = {}              # 8x8 cell origin -> unix time until which we avoid it
        self.learned_blocked = set()     # tiles that bumped us although the map said walkable
        self.bump_count = {}
        self.visited = set()
        self.hist = deque(maxlen=400)    # (time, tile)
        self.last_save = time.time()
        self.stats = {"battles": 0, "wins": 0, "runs": 0, "rests": 0, "relocations": 0}
        self._load_memory()

    # ---------------------------------------------------------------- persistence
    def _load_memory(self):
        try:
            with open(MEMORY) as f:
                m = json.load(f)
            self.visited = {tuple(t) for t in m.get("visited", [])}
            self.learned_blocked = {tuple(t) for t in m.get("blocked", [])}
            self.bad_zones = {tuple(map(int, k.split(","))): v for k, v in m.get("bad_zones", {}).items()}
        except (OSError, ValueError):
            pass

    def _save_memory(self):
        os.makedirs(os.path.dirname(MEMORY), exist_ok=True)
        with open(MEMORY, "w") as f:
            json.dump({"visited": sorted(self.visited), "blocked": sorted(self.learned_blocked),
                       "bad_zones": {"%d,%d" % k: v for k, v in self.bad_zones.items()}}, f)

    def checkpoint(self, force=False):
        if force or time.time() - self.last_save > 45:
            try:
                self.g.save()
                self._save_memory()
            finally:
                self.last_save = time.time()

    # ---------------------------------------------------------------- helpers
    def lead(self, s):
        party = s["player"]["party"]
        cur = s["player"]["curr"]
        return party[cur] if 0 <= cur < len(party) else party[0]

    def strongest(self, s):
        return max(m["lvl"] for m in s["player"]["party"])

    def ensure_lead(self, s):
        """Let the weakest worthwhile mon open the battles (the decision logic swaps in a stronger one when needed)."""
        i = evo.trainee(self.g, s)
        if i is None:
            if s["player"]["hm"] >= 0 and s["player"]["field"] == "":
                field.clear(self.g)
            return
        m = s["player"]["party"][i]
        if m["stats"]["hp"] < 0.6 * m["max"]["hp"]:
            return
        if s["player"]["hm"] != i or s["player"]["field"] != "":
            if field.set_lead(self.g, i, self.log):
                self.log("lead: %s L%d is training" % (m["specie"], m["lvl"]))

    def refresh_world(self):
        self.world = World(self.g.world())

    def note_position(self, s):
        t = nav.tile_of(s["player"])
        self.hist.append((time.time(), t))
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                self.visited.add((t[0] + dx, t[1] + dy))

    def stuck(self, secs=75, radius=2):
        now = time.time()
        pts = [t for ts, t in self.hist if now - ts <= secs]
        if len(pts) < 30 or now - self.hist[0][0] < secs:
            return False
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return max(xs) - min(xs) <= radius and max(ys) - min(ys) <= radius

    # ---------------------------------------------------------------- zone choice
    def choose_zone(self, s):
        here = nav.tile_of(s["player"])
        lvl = self.strongest(s)
        now = time.time()
        dist = self.world.dist_map(here)
        # a FLY-line trainee (natu -> xatu) needs exp fast: fight tougher routes, the strong mon covers it
        hungry = evo.trainee(self.g, s)
        hungry = hungry is not None and s["player"]["party"][hungry]["specie"] in evo.FLY_LINE
        want_lo, want_hi = max(2, lvl - 4), lvl + (8 if hungry else 4)
        target = lvl + (6 if hungry else 1)
        best, best_score = None, 1e18
        seen_cells = set()
        for p in dist:
            if self.world.ch(p) != "g":
                continue
            cell = (p[0] // 8 * 8, p[1] // 8 * 8)
            if cell in seen_cells:
                continue
            L = self.world.level(p)
            if not (want_lo <= L <= want_hi):
                continue
            seen_cells.add(cell)
            if self.bad_zones.get(cell, 0) > now:
                continue
            # prefer ground whose level is close to ours, then close by
            score = abs(L - target) * 12 + dist[p]
            if score < best_score:
                best, best_score = (p, L), score
        return best

    def blacklist_zone(self, minutes=20):
        if self.zone:
            c = self.zone[0]
            self.bad_zones[(c[0] // 8 * 8, c[1] // 8 * 8)] = time.time() + minutes * 60
        self.zone = None
        self.stats["relocations"] += 1

    # ---------------------------------------------------------------- movement
    def go(self, goal_fn, s, max_level=None, avoid_grass=False, leg=6):
        """One leg towards the nearest tile satisfying goal_fn. Returns (state, status)."""
        here = nav.tile_of(s["player"])
        mons = {(int(round(m["x"][0] / 16)), int(round(m["x"][1] / 16))) for m in s["map"]["mons"] if m.get("x")}
        path = self.world.path(here, goal_fn, blocked=self.learned_blocked | mons,
                               max_level=max_level, avoid_grass=avoid_grass)
        if not path:
            return s, "nopath"
        s, res, done = self.g.walk(path[:leg])
        s = nav.settle(self.g)
        if res == "blocked" and done < len(path):
            dx, dy = nav.DIRS[path[done]]
            pos = nav.tile_of(s["player"])
            tile = (pos[0] + dx, pos[1] + dy)
            self.bump_count[tile] = self.bump_count.get(tile, 0) + 1
            if self.bump_count[tile] >= 2:
                self.learned_blocked.add(tile)
        return s, res

    # ---------------------------------------------------------------- main loop
    def tick(self):
        """One decision. Returns the new state."""
        g = self.g
        s = g.state()
        self.note_position(s)
        if battle.in_battle(s):
            return self.fight(s)
        if not nav.is_free(s):
            g.tap("a", 2, 20)
            return g.state()
        self.checkpoint()
        frac = rest.party_hp_frac(s)
        lvl = self.lead(s)["lvl"]
        if frac < 0.65 and "sleeping bag" in s["player"]["items"]:
            if rest.rest(g, log=self.log):
                self.stats["rests"] += 1
                self.checkpoint(True)
                return g.state()
        if self.world is None:
            self.refresh_world()
        here = nav.tile_of(s["player"])
        if self.stuck():
            self.log("stuck near %s -> relocating" % (here,))
            self.hist.clear()
            self.blacklist_zone(10)
        # (re)pick a zone when we have none, or this one stopped producing fights
        if self.zone is not None and time.time() - self.zone_since > 150 and self.zone_battles == 0:
            self.log("zone %s gave no fights -> blacklisting" % (self.zone,))
            self.blacklist_zone(15)
        if self.zone is None:
            self.zone = self.choose_zone(s)
            self.zone_since, self.zone_battles = time.time(), 0
            self.log("new zone: %s (lead L%d, hp %.0f%%)" % (self.zone, lvl, frac * 100))
            if self.zone is None:
                g.wait(60)
                return g.state()
        center, zl = self.zone
        w = self.world
        self.ensure_lead(s)
        in_zone = w.ch(here) == "g" and w.level(here) == zl
        if not in_zone:
            s, st = self.go(lambda p: w.ch(p) == "g" and w.level(p) == zl and
                            abs(p[0] - center[0]) <= 6 and abs(p[1] - center[1]) <= 6, s,
                            max_level=zl + 2)
            if st == "nopath":
                self.log("no path from %s to zone %s (interior=%s)" % (here, self.zone, s["map"]["interior"]))
                self.blacklist_zone(30)
            return s
        # inside the zone: pace across grass tiles (each step may trigger an encounter)
        spots = [(here[0] + dx, here[1] + dy) for dx in range(-6, 7) for dy in range(-6, 7)
                 if abs(dx) + abs(dy) >= 4 and w.ch((here[0] + dx, here[1] + dy)) == "g"
                 and w.level((here[0] + dx, here[1] + dy)) == zl]
        target = random.choice(spots) if spots else center
        s, st = self.go(lambda p: p == target, s, max_level=zl + 2)
        if st == "nopath":
            self.blacklist_zone(30)
        return s

    def fight(self, s):
        before = (self.lead(s)["lvl"], self.lead(s)["exp"])
        r = battle.run_battle(self.g, log=self.log)
        self.stats["battles"] += 1
        self.zone_battles += 1
        s = self.g.state()
        if r["last"] == "run":
            self.stats["runs"] += 1
            # fleeing twice means this ground is too dangerous: leave it for a while
            if self.zone is not None and self.stats["runs"] % 2 == 0:
                self.blacklist_zone(25)
        else:
            self.stats["wins"] += 1
        after = self.lead(s)
        if after["lvl"] != before[0]:
            self.log("LEVEL UP: %s L%d -> L%d" % (after["specie"], before[0], after["lvl"]))
        self.checkpoint(True)
        return s
