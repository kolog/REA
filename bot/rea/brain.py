"""Top-level decision loop. Priorities (re-evaluated every tick, so nothing is "only at the start of a cycle"):

1. in a battle            -> battle.run_battle (fight / switch / catch / run)
2. team hurt              -> sleep in the bag (rest.rest), leaving grass first
3. useful friendly mon    -> walk to it and recruit it (new field moves first)
4. items lying around     -> pick up (poke balls etc.)
5. low on balls           -> gather apricorns, build a campfire if needed, craft balls
6. otherwise              -> train in a grass zone that matches the team level (Trainer)
"""
import time

from . import base, battle, economy, farm, field, fly, nav, recruit, rest, travel
from .trainer import Trainer
from .world import World

BALL_FOR = {"black apricorn": "heavy ball", "blue apricorn": "lure ball", "green apricorn": "friend ball",
            "pink apricorn": "love ball", "red apricorn": "level ball", "white apricorn": "fast ball",
            "yellow apricorn": "moon ball"}
MOVE_VALUE = {"SMASH": 6, "SURF": 6, "DIG": 4, "FLY": 5, "HEADBUTT": 3, "CUT": 2, "BUILD": 2, "POWER": 1,
              "RIDE": 1, "FLASH": 1, "CHARM": 1, "TELEPORT": 1, "ATTACK": 1}


GHOST_BIOMES = {"deep_forest", "graveyard", "wooded_lake"}


class Brain:
    def __init__(self, g, log=print, mission="auto"):
        self.mission = mission          # "auto" = all goals; "train" = only survive + train the trainee/zone
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
            owned = {m[0] for m in self.mons if m[2] == "owned"}
            battle.OWNED.update(owned)
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

    def ghost_exposed(self, s):
        """Night in a ghost biome, away from light (campfire/torch/FLASH mon within 4 tiles) and not flying."""
        m = s["map"]
        if m.get("time") != "night" or m.get("biome") not in GHOST_BIOMES or s["player"]["field"] == "FLY":
            return False
        here = nav.tile_of(s["player"])
        lit = any(("campfire" in o[2] or "torch" in o[2]) and abs(o[0] - here[0]) <= 4 and abs(o[1] - here[1]) <= 4
                  for o in self.objs)
        follower = s["player"]["hm"]
        flash = follower >= 0 and "FLASH" in s["player"]["party"][follower].get("hms", [])
        return not (lit or flash)

    def known_moves(self, s):
        return {h for m in s["player"]["party"] for h in m.get("hms", [])}

    def balls(self, s):
        return sum(v for k, v in s["player"]["items"].items() if k in battle.BALLS)

    def apricorns(self, s):
        return sum(s["player"]["items"].get(a, 0) for a in BALL_FOR)

    # ---------------------------------------------------------------- goals
    def goal_rest(self, s):
        if rest.party_hp_frac(s) < 0.6 and "sleeping bag" in s["player"]["items"]:
            door = rest.home_door(self.objs) if self.objs else None
            ok = False
            if door is not None:
                ok = rest.rest_home(self.g, door, log=self.log)
            if not ok:
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
        # every farm animal that walks around loose gets a pen (they wander far otherwise)
        loose = farm.loose_farm_mons(self.mons, self.objs)
        party_species = {m["specie"] for m in s["player"]["party"]}
        if loose and self.camp is not None and self.failed.get("penning", 0) < 6:
            specie, tile = loose[0]
            if specie not in party_species and len(s["player"]["party"]) < 6:
                self.log("bringing %s to a pen" % specie)
                if not farm.recall(self.g, self.world, specie, log=self.log, avoid=danger):
                    self.failed["penning"] = self.failed.get("penning", 0) + 1
                    return True
                s = self.g.state()
            if specie in {m["specie"] for m in s["player"]["party"]}:
                idx = next(i for i, m in enumerate(s["player"]["party"]) if m["specie"] == specie)
                r = farm.deploy_pen(self.g, self.world, self.g.objects(), idx, log=self.log, avoid=danger, near=self.camp)
                if r is True:
                    self.stats["penned"] = self.stats.get("penned", 0) + 1
                    self.trainer.checkpoint(True)
                elif r is False:
                    self.failed["penning"] = self.failed.get("penning", 0) + 1
                self.refresh(True)
                return True
        idx = farm.deployable(s)
        if idx is not None and self.failed.get(("deploy", s["player"]["party"][idx]["specie"]), 0) < 2:
            ok = farm.deploy_pen(self.g, self.world, self.objs, idx, log=self.log, avoid=danger, near=self.camp)
            if ok is True:
                self.stats["deployed"] = self.stats.get("deployed", 0) + 1
                self.trainer.checkpoint(True)
            elif ok is False:
                k = ("deploy", s["player"]["party"][idx]["specie"])
                self.failed[k] = self.failed.get(k, 0) + 1
            return True
        return False

    def goal_flyer(self, s):
        """No FLY pokemon yet: hunt the weakest wild one (a skarmory/xatu ... can be caught outright)."""
        party = s["player"]["party"]
        if any("FLY" in m.get("hms", []) for m in party) or self.failed.get("flyer", 0) >= 8:
            return False
        top = max(m["lvl"] for m in party)
        here = nav.tile_of(s["player"])
        dist = self.world.dist_map(here)
        def reachable(m):
            return any((m[3] + dx, m[4] + dy) in dist for dx in range(-5, 6) for dy in range(-5, 6))
        cands = [m for m in self.mons if "FLY" in m[7] and m[2] in ("aggro", "friendly") and m[1] <= top + 6
                 and reachable(m)]
        if not cands:
            return False
        cands.sort(key=lambda m: (m[1] > top + 4, abs(m[3] - here[0]) + abs(m[4] - here[1]) + 3 * m[1]))
        m = cands[0]
        tile = (m[3], m[4])
        self.log("flyer hunt: %s L%d (%s) at %s" % (m[0], m[1], m[2], tile))
        r = travel.go_near(self.g, self.world, tile, dist=4, avoid_grass=True, max_legs=150, avoid=self.danger_tiles(s))
        if r == "battle":
            return True
        if r != "arrived":
            self.failed["flyer"] = self.failed.get("flyer", 0) + 1
            return True
        fresh = [x for x in self.g.allmons() if x[0] == m[0] and abs(x[3] - tile[0]) + abs(x[4] - tile[1]) < 12]
        if not fresh:
            self.failed["flyer"] = self.failed.get("flyer", 0) + 1
            return True
        x = min(fresh, key=lambda y: abs(y[3] - here[0]) + abs(y[4] - here[1]))
        field.clear(self.g)
        if x[2] == "friendly":
            recruit.recruit(self.g, m[0], log=self.log)
        else:
            recruit.provoke(self.g, (x[3], x[4]), log=self.log)
        return True

    def goal_balls(self, s):
        """Keep ~20 balls: apricorns (CUT) -> campfire balls; magnet + hard shell -> poke ball; fast ball + magnet ->
        quick ball (x5 on turn 1) at the kiln inside the house."""
        if self.camp is None or "CUT" not in self.known_moves(s):
            return False
        items = s["player"]["items"]
        balls = self.balls(s)
        apr = self.apricorns(s)
        door = rest.home_door(self.objs)
        origin = (door[0] - 2, door[1]) if door else None
        if balls >= 20 and apr == 0:
            return False
        if apr + balls < 14 and self.failed.get("apricorns", 0) < 4:
            before = self.apricorns(s)
            economy.gather(self.g, self.world, {"apricorn": min(10, 16 - balls - apr) + apr}, "CUT", log=self.log, max_trips=14)
            field.clear(self.g)
            if self.apricorns(self.g.state()) <= before:
                self.failed["apricorns"] = self.failed.get("apricorns", 0) + 1
            return True
        if apr > 0 or (items.get("magnet", 0) and items.get("hard shell", 0)):
            if economy.open_crafts(self.g, self.camp):
                for apri, ball in BALL_FOR.items():
                    n = self.g.state()["player"]["items"].get(apri, 0)
                    if n:
                        self.stats["crafted"] += economy.craft(self.g, ball, n, log=self.log)
                it = self.g.state()["player"]["items"]
                spare = it.get("magnet", 0) - it.get("fast ball", 0)        # keep one magnet per fast ball for quick balls
                pairs = min(spare, it.get("hard shell", 0))
                if pairs > 0:
                    self.stats["crafted"] += economy.craft(self.g, "poké ball", pairs, log=self.log)
                economy.close_crafts(self.g)
                self.trainer.checkpoint(True)
            return True
        it = items
        n = min(it.get("fast ball", 0), it.get("magnet", 0))
        if n and origin:
            got = base.kiln_craft(self.g, self.world, origin, [("quick ball", n)], log=self.log)
            self.stats["crafted"] += sum(got.values())
            self.trainer.checkpoint(True)
            return bool(got)
        return False

    def goal_house(self, s):
        """Build the 5x3 house next to the camp (once): it is the pen for captured pokemon and the best bed."""
        if self.camp is None or rest.home_door(self.objs) is not None or self.failed.get("house", 0) >= 2:
            return False
        if "CUT" not in self.known_moves(s) or "BUILD" not in self.known_moves(s):
            return False
        site = base.find_site(self.world, self.objs, self.mons, self.camp)
        if site is None:
            self.failed["house"] = 9
            return False
        self.log("building the house at %s" % (site,))
        placed, total = base.build_house(self.g, self.world, self.objs, site, log=self.log, avoid=self.danger_tiles(s))
        self.refresh(True)
        if placed == 0:
            self.failed["house"] = self.failed.get("house", 0) + 1
        return True

    def goal_pickup(self, s):
        here = nav.tile_of(s["player"])
        dist = self.world.dist_map(here)
        flyer = any("FLY" in m.get("hms", []) and m["stats"]["hp"] > 0 for m in s["player"]["party"])
        best, bd = None, 1e9
        for o in self.objs:
            if not o[3] or (o[0], o[1]) in self.done_items or self.failed.get(("item", o[0], o[1]), 0) >= 2:
                continue
            near = [dist[(o[0] + dx, o[1] + dy)] for dx, dy in nav.DIRS.values() if (o[0] + dx, o[1] + dy) in dist]
            if near and min(near) < bd and min(near) <= 120:
                best, bd = o, min(near)
            elif flyer and abs(o[0] - here[0]) + abs(o[1] - here[1]) < bd:      # not reachable on foot: fly
                best, bd = o, abs(o[0] - here[0]) + abs(o[1] - here[1])
        if best is None:
            return False
        tile = (best[0], best[1])
        self.log("pickup target: %s at %s" % (best[3], tile))
        can_fly = any("FLY" in m.get("hms", []) and m["stats"]["hp"] > 0 for m in s["player"]["party"])
        if can_fly and abs(tile[0] - here[0]) + abs(tile[1] - here[1]) > 25:
            if fly.trip(self.g, self.world, tile, log=self.log) is None:
                self.failed[("item", tile[0], tile[1])] = self.failed.get(("item", tile[0], tile[1]), 0) + 1
                return True
            r = "arrived"
        else:
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
        if not s["player"]["isSleeping"] and self.trainer.stuck(120, 1):      # watchdog: nothing moved for 2 minutes
            self.log("watchdog: no movement for 2 min at %s (interior=%s)" % (nav.tile_of(s["player"]), s["map"]["interior"]))
            self.trainer.hist.clear()
            nav.ensure_outside(g)
            field.clear(g)
            self.failed["watchdog"] = self.failed.get("watchdog", 0) + 1
            return g.state()
        if self.goal_rest(s):
            return g.state()
        self.refresh()
        battle.OWNED.update(m["specie"] for m in s["player"]["party"])
        if self.camp is not None and self.ghost_exposed(s):
            self.log("night in %s without light: going back to the camp" % s["map"]["biome"])
            travel.go_near(g, self.world, self.camp, dist=2, avoid_grass=True, max_legs=40, avoid=self.danger_tiles(s))
            return g.state()
        goals = (self.goal_flyer, self.goal_farm, self.goal_recruit, self.goal_pickup, self.goal_supplies, self.goal_house)
        if self.mission == "train":
            goals = ()
        elif self.mission == "flyer":
            goals = (self.goal_flyer,)
        elif self.mission == "balls":
            goals = (self.goal_farm, self.goal_balls)
        for goal in goals:
            s = nav.ensure_free(g)
            if battle.in_battle(s):
                return self.trainer.fight(s)
            if rest.party_hp_frac(s) < 0.6 and "sleeping bag" in s["player"]["items"]:
                return g.state()                         # hurt in the middle of a goal: rest first
            if goal(s):
                return g.state()
        if g.state()["player"]["field"] != "":      # keep a FOLLOW trainee, drop only active field moves
            field.clear(g)
        return self.trainer.tick()
