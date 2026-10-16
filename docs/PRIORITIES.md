# Strategy and priorities (derived from the decompiled game)

PokeWilds has **no ending**: it is a sandbox. Goals are therefore: survive, build a self-sustaining base, collect
every species/legendary, and keep the team strong. World facts: small island ~413x387 tiles, mostly sea; routes
(wild level by biome): beach 2-12, savanna/graveyard/volcano/ruins 22-25, deep forest 33, mountain 33, wooded lake
30-40, desert/forest/ocean 40, snow/regi cave/sand pit 44, mansion 30-40. Aggressive wild mons (evolved or in the
aggro list) hunt the player; flying makes the player untouchable.

## Order of play (what the Brain does, highest first)
1. **Survive**: in a battle -> fight/switch/catch/run. Team below 60% hp -> sleep at home (twice the healing) or
   in the bag away from grass. Never walk through grass when hurt; avoid strong aggressive mons (path penalty).
2. **Team**: recruit friendly wild mons (free) that add field moves (SMASH, DIG, SURF, FLY, HEADBUTT ...) or farm
   value (water: hard shell, electric: magnet ...). Never eggs. Train the weakest valuable mon via the lead-swap
   (natu -> xatu = FLY).
3. **Economy**: CUT/SMASH gather logs, grass, apricorns, hard stone. Campfire (4 log + 2 grass) is the workshop:
   apricorns -> balls; magnet + hard shell -> poke ball. Plant apricorns/miracle seeds to renew resources.
4. **Base**: camp -> house 5x3 (15 log + 15 grass; built from outside) -> sleep inside once so captured mons beyond
   6 appear in the house; chest/bed/furniture from inside. Farm pokemon in penned habitat spots.
5. **Collection**: pick up the poke balls and the mansion key lying on the map; capture new species with the ball
   whose catch probability is best; keep party <= 6, the rest live at home / on the farm.
6. **Late**: fly to far routes, SURF over water, mansion (secret key), fossils (revive), Regis (47x item + spell tag),
   legendaries.

## Efficiency rules learned
* Accumulate materials first, then build everything in one go.
* Clear vegetation (CUT) before building; it also yields materials.
* Exterior pieces only from outside; interior pieces only from inside; doors/gates are not standing tiles.
* Fence + door between fences = gate; fully enclosed tile gets filled by the game -> CUT it.
* Pokemon wander far when free: pen them or keep the farm near the camp.
* A good ball can be thrown at full hp; weaken only when the best chance is low.
* Check hp in every decision, not only at the start of a goal.
