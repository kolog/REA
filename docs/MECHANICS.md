# PokeWilds v0.8.11 — mechanics (from the decompiled jar)

Source references are `com.pkmngen.game.*`. Update this file as more is learned.

## World
* Tile = 16 px. `map.tiles` (overworld) is a `HashMap<Vector2, Tile>`; the whole island is generated at
  game start (small world ~413x387 tiles, mostly water). Tile has two layers: `name` (ground) and
  `nameUpper` (object on top: tree2, rock1, bush2_color, grass3 ...).
* `routeBelongsTo` (Route) gives `name` and `level`; the wild level of encounters follows the route.
* Wild encounter (PlayerStanding.checkWildEncounter): only when standing on `isGrass` tile that belongs to a
  route; ~9 % per step (`rate=10`), 4 % indoors, 7 % desert2, **0 % on tidal tiles**.
* Walking: hold a direction >3 frames to move (first frames only turn). A tile takes ~16 frames.
* Ledges: jump only in `ledgeDir`; water needs SURF; solid tiles/pokemon bump.

## Field moves (the economy)
`Specie.hms` is derived from the **type** of the species:

| type | field move | use |
|---|---|---|
| GRASS | CUT | cut trees/grass -> log, grass, apricorns |
| ROCK | SMASH | rocks -> hard stone (+ moon/fire stone) |
| FIGHTING | BUILD | build structures (sleeping bag spot, houses, campfire ...) |
| GROUND | DIG | dig terrain tiles / holes (fossils) |
| ELECTRIC / porygon | POWER | machines |
| FAIRY | CHARM | |
| POISON | REPEL | |
| FIRE (+ some) | FLASH | light |
| DARK | ATTACK | attack overworld pokemon (starts battle) |
| PSYCHIC | TELEPORT | |
| some species | HEADBUTT, RIDE, FLY, SURF | HEADBUTT shakes trees (can start a battle) |

Pick a field move: Start -> POKEMON -> choose the pokemon -> choose the word (CUT, SMASH, ..., FOLLOW, STATS,
SWITCH, DROP). That sets `player.currFieldMove` and `player.hmPokemon`. Then **A facing a tile** applies it
(`Tile.onPressA`, `PlayerStanding`). B (hold) clears the field move. L/R cycle the build/dig tile.
Starter Machop only has BUILD -> team composition decides what can be gathered.

## Items on the ground / resources (Tile.items())
* `hasItem` on a tile: press A facing it -> "Found X!" (`Tile.onPressA` -> `pickUpItem`). Pokeballs can lie
  on the map this way.
* Resource tiles (collected with CUT/SMASH): `tree2`,`tree4` -> 2 log (+50 %: 2 random apricorns),
  `bush2_color` -> log (+50 %: 1 apricorn), `tree5/6` 2 log, `tree_large1` 4 log, `grass2..4` grass (grass2 25 % miracle
  seed), `rock1` hard stone (10 % moon stone), `rock_volcano1` hard stone (10 % fire stone),
  `gravestone2` hard stone + life force, `rock_ice2` nevermeltice, `berrytree_*` berry seed.
* Apricorn colours: black, blue, green, pink, red, white, yellow.

## Crafting (Player.crafts) — requirement lists
Balls from apricorns (1 each): black->heavy, blue->lure, green->friend, pink->love, red->level, white->fast,
yellow->moon.
`poké ball` = magnet + hard shell; great = poke + metal coat; ultra = great + life force.
dusk = moon + dark energy; net = lure + silky thread; dive = lure + hard shell; quick = fast + magnet;
heal = friend + stardust; nest = friend + binding band; dream = love + psi energy; timer = heavy + hard stone.
Other: repel = charcoal + manure; max repel = poison barb + repel; rare candy = 3 berry juice + ancientpowder;
old rod = log + silky thread; good rod = old rod + 2 metal coat; super rod = good rod + 3 magnet;
binding band = 3 grass; thin paper = log; spell tag = life force + thin paper; clear glass = 3 soft sand;
soft bedding = 3 soft feather + 3 silky thread.
Fossil revival: fossil item -> pokemon. Regis: 47 of an item + spell tag (+ extras for dragon/eleki).

## Pokemon on the map
* Overworld pokemon wander. Face one and press A (`Tile.onPressA`):
  * eggs: "Pick it up?" -> yes.
  * `previousOwner == player` and `hasItem` != null -> harvest its item (wool, hard shell, manure ...).
  * `skittish` species (ekans, pidgey, spearow, rattata, chansey) -> a battle starts.
  * aggressive = `aggroAnyway` (poochyena, sneasel, skarmory, pinsir, tauros, duraludon) OR (not a base species
    and not in `dontAggro`): first A -> "seems aggressive"; second A -> battle.
  * otherwise "seems friendly. Add X to your party?" -> Yes joins the party for free (`AddToInventory`).
    Party max 6 (extra must be stored/dropped).
* Owned pokemon in the field have `harvestTimer` and `hasItem` (manure, wool, hard shell ... `Specie.harvestables`).

## Healing
* Sleeping bag (item, needs free tile on the right, not grass/desert/mountain/snow/dungeon, no aggro pokemon
  near): every 128 frames +1/50 max hp outdoors (+1/15 more in the bag); also sets the white-out spawn.
* No pokemon center. Potions via the Pokemon menu.

## Menus (button map: A=Z, B=X, Start=Enter, L=C, R=V)
* Start -> `DrawPlayerMenu` (POKeMON, ITEM, MAP, GUIDE, SAVE). ITEM -> `DrawItemMenuGen2` (tabs with L/R arrows)
  -> item -> `DrawUseTossMenu` (USE/TOSS).
* Battle menu `DrawBattleMenuNormal`: FIGHT(tl) POKeMON(tr) ITEM(bl) RUN(br). Moves: `DrawAttacksMenu.curr`.
* No PP system. Damage: gen-2 formula in `Battle.gen2CalcDamage` (random 217..255/255).

## Saving
* `map.saveToFileNew(game)` writes `<mapname>.sav` (agent command `save`). Title screen: row1 right = Load.
