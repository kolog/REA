"""Top-level decision loop. Priorities (re-evaluated every tick, so nothing is "only at the start of a cycle"):

1. in a battle            -> battle.run_battle (fight / switch / catch / run)
2. team hurt              -> sleep in the bag (rest.rest), leaving grass first
3. useful friendly mon    -> walk to it and recruit it (new field moves first)
4. items lying around     -> pick up (poke balls etc.)
5. low on balls           -> gather apricorns, build a campfire if needed, craft balls
6. otherwise              -> train in a grass zone that matches the team level (Trainer)
"""
import time

from . import battle, economy, farm, field, nav, recruit, rest, travel
from .trainer import Trainer
from .world import World

BALL_FOR = {"black apricorn": "heavy ball", "blue apricorn": "lure ball", "green apricorn": "friend ball",
            "pink apricorn": "love ball", "red apricorn": "level ball", "white apricorn": "fast ball",
            "yellow apricorn": "moon ball"}
MOVE_VALUE = {"SMASH": 6, "SURF": 6, "DIG": 4, "FLY": 5, "HEADBUTT": 3, "CUT": 2, "BUILD": 2, "POWER": 1,
              "RIDE": 1, "FLASH": 1, "CHARM": 1, "TELEPORT": 1, "ATTACK": 1}


class Brain:
    def __init__(self, g, log=print):
        self.g = g
        self.log = log
        self.trainer = Trainer(g, log)
        self.world = None
        self.objs = []
        self.mons = []
        self.refreshed = 0.0
        self.failed = {}                 # (kind, tile) -> failures
        self.done_items = set()
        self.camp = None
        self.stats = {"recruits": 0, "pickups": 0, "crafted": 0, "rests": 0}

    # ---------------------------------------------------------------- knowledge
    def refresh(self, force=False):
        if force or self.world is None or time.time() - self.refreshed > 90:
            self.world = World(self.g.world())
            self.trainer.world = self.world
            self.objs = self.g.objects()
            self.mons = self.g.allmons()
            camps = [o for o in self.objs if "campfire" in o[2]]
            self.camp = (camps[0][0], camps[0][1]) if camps else None
            self.refreshed = time.time()

    def danger_tiles(self, s, r=6):
        """Tiles close to aggressive wild pokemon that would crush our team (they hunt us when close)."""
        top = max(m["lvl"] for m in s["player"]["party"])
        out = set()
        for m in self.mons:
            if m[2] == "aggro" and m[1] >= top + 3:
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        out.add((m[3] + dx, m[4] + dy))
        return out

    def known_moves(self, s):
        return {h for m in s["player"]["party"] for h in m.get("hms", [])}

    def balls(self, s):
        return sum(v for k, v in s["player"]["items"].items() if k in battle.BALLS)

    def apricorns(self, s):
        return sum(s["player"]["items"].get(a, 0) for a in BALL_FOR)

    # ---------------------------------------------------------------- goals
    def goal_rest(self, s):
        if rest.party_hp_frac(s) < 0.6 and "sleeping bag" in s["player"]["items"]:
            ok = rest.rest(self.g, log=self.log)
            if ok:
                self.stats["rests"] += 1
                self.trainer.checkpoint(True)
            return True
        return False

    def recruit_score(self, m, have, here, dist):
        specie, lvl, temper, x, y, holds, types, hms = m[:8]
        if temper != "friendly":          # eggs anger their parents and take ages to hatch
            return 0
        new = sum(MOVE_VALUE.get(h, 0) for h in hms if h not in have)
        fv = farm.produce_value(types) if farm.farmable(types) else 0
        score = new * 10 + lvl * 0.5 + fv * 3
        return score / (1.0 + dist / 40.0)

    def goal_recruit(self, s):
        if len(s["player"]["party"]) >= 6:
            return False
        have = self.known_moves(s)
        here = nav.tile_of(s["player"])
        dist = self.world.dist_map(here)
        best, best_score = None, 4.0
        party_species = {m["specie"] for m in s["player"]["party"]}
        danger = self.danger_tiles(s)
        for m in self.mons:
            tile = (m[3], m[4])
            if m[0] in party_species and m[2] != "egg" or self.failed.get(("rec", m[0], tile), 0) >= 2:
                continue
            near = [dist[(tile[0] + dx, tile[1] + dy)] for dx, dy in nav.DIRS.values() if (tile[0] + dx, tile[1] + dy) in dist]
            if not near or min(near) > 150 or tile in danger:
                continue
            sc = self.recruit_score(m, have, here, min(near))
            if sc > best_score:
                best, best_score = m, sc
        if best is None:
            return False
        tile = (best[3], best[4])
        self.log("recruit target: %s L%d at %s (score %.1f)" % (best[0], best[1], tile, best_score))
        r = travel.go_near(self.g, self.world, tile, dist=3, avoid_grass=True, max_legs=60, avoid=self.danger_tiles(s))
        if r != "arrived":
            self.failed[("rec", best[0], tile)] = self.failed.get(("rec", best[0], tile), 0) + 1
            return True
        field.clear(self.g)
        ok = recruit.recruit(self.g, best[0], log=self.log)
        if ok:
            self.stats["recruits"] += 1
            self.trainer.checkpoint(True)
            self.refresh(True)
        else:
            self.failed[("rec", best[0], tile)] = self.failed.get(("rec", best[0], tile), 0) + 1
            self.refresh(True)
        return True

    def goal_farm(self, s):
        """Harvest what dropped pokemon produce; drop surplus pokemon where they can produce."""
        self.mons = self.g.allmons()
        danger = self.danger_tiles(s)
        if farm.ready_items(self.mons):
            farm.collect(self.g, self.world, self.mons, log=self.log, avoid=danger)
            self.stats["harvests"] = self.stats.get("harvests", 0) + 1
            return True
        if self.camp is not None and farm.relocate_far(self.g, self.world, self.objs, self.camp, log=self.log, avoid=danger):
            return True
        idx = farm.deployable(s)
        if idx is not None and self.failed.get(("deploy", s["player"]["party"][idx]["specie"]), 0) < 2:
            ok = farm.deploy(self.g, self.world, self.objs, idx, log=self.log, avoid=danger, near=self.camp)
            if ok is True:
                self.stats["deployed"] = self.stats.get("deployed", 0) + 1
                self.trainer.checkpoint(True)
            elif ok is False:
                k = ("deploy", s["player"]["party"][idx]["specie"])
                self.failed[k] = self.failed.get(k, 0) + 1
            return True
        return False

    def goal_pickup(self, s):
        here = nav.tile_of(s["player"])
        dist = self.world.dist_map(here)
        best, bd = None, 1e9
        for o in self.objs:
            if not o[3] or (o[0], o[1]) in self.done_items or self.failed.get(("item", o[0], o[1]), 0) >= 2:
                continue
            near = [dist[(o[0] + dx, o[1] + dy)] for dx, dy in nav.DIRS.values() if (o[0] + dx, o[1] + dy) in dist]
            if near and min(near) < bd and min(near) <= 120:
                best, bd = o, min(near)
        if best is None:
            return False
        tile = (best[0], best[1])
        self.log("pickup target: %s at %s" % (best[3], tile))
        r = travel.go_near(self.g, self.world, tile, dist=1, avoid_grass=True, max_legs=60, avoid=self.danger_tiles(s))
        if r == "arrived":
            field.clear(self.g)
            if recruit.pick_up(self.g, tile, log=self.log):
                self.stats["pickups"] += 1
                self.done_items.add(tile)
            else:
                self.failed[("item", tile[0], tile[1])] = self.failed.get(("item", tile[0], tile[1]), 0) + 1
        else:
            self.failed[("item", tile[0], tile[1])] = self.failed.get(("item", tile[0], tile[1]), 0) + 1
        return True

    def goal_supplies(self, s):
        items = s["player"]["items"]
        apr = self.apricorns(s)
        has_farm_pair = items.get("magnet", 0) and items.get("hard shell", 0)
        if self.balls(s) >= 3 and apr == 0 and not has_farm_pair:
            return False
        if "CUT" not in self.known_moves(s) or "BUILD" not in self.known_moves(s):
            return False
        # 0) hard shell + magnet (farm produce) -> poke ball at the campfire
        if self.camp is not None and items.get("magnet", 0) and items.get("hard shell", 0):
            if economy.open_crafts(self.g, self.camp):
                n = min(items["magnet"], items["hard shell"])
                self.stats["crafted"] += economy.craft(self.g, "poké ball", n, log=self.log)
                economy.close_crafts(self.g)
            return True
        # 1) apricorns -> balls at a campfire
        if apr > 0 and self.camp is not None and (apr >= 3 or self.balls(s) == 0):
            if economy.open_crafts(self.g, self.camp):
                for apri, ball in BALL_FOR.items():
                    n = self.g.state()["player"]["items"].get(apri, 0)
                    if n:
                        self.stats["crafted"] += economy.craft(self.g, ball, n, log=self.log)
                economy.close_crafts(self.g)
                self.trainer.checkpoint(True)
            return True
        # 2) campfire materials
        if self.camp is None and apr > 0:
            need = {"log": 4, "grass": 2}
            if economy.missing(economy.inv(s), need):
                economy.gather(self.g, self.world, need, "CUT", log=self.log, max_trips=12)
            else:
                economy.build(self.g, "campfire1", log=self.log)
                self.refresh(True)
            field.clear(self.g)
            return True
        # 3) more apricorns
        if apr < 4:
            economy.gather(self.g, self.world, {"apricorn": 4}, "CUT", log=self.log, max_trips=10)
            field.clear(self.g)
            return True
        return False

    # ---------------------------------------------------------------- main
    def tick(self):
        g = self.g
        s = nav.ensure_free(g)
        if battle.in_battle(s):
            return self.trainer.fight(s)
        self.trainer.note_position(s)
        self.trainer.checkpoint()
        if self.goal_rest(s):
            return g.state()
        self.refresh()
        for goal in (self.goal_farm, self.goal_recruit, self.goal_pickup, self.goal_supplies):
            s = nav.ensure_free(g)
            if battle.in_battle(s):
                return self.trainer.fight(s)
            if rest.party_hp_frac(s) < 0.6 and "sleeping bag" in s["player"]["items"]:
                return g.state()                         # hurt in the middle of a goal: rest first
            if goal(s):
                return g.state()
        field.clear(g)
        return self.trainer.tick()
