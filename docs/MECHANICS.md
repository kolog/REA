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

## Building (BUILD field move, FIGHTING-type pokemon) — requirements per tile
Default for any tile: 1 grass + 1 log. Exceptions: campfire 4 log + 2 grass; bridge 1 log + 1 hard stone;
**chest1 2 log** (pokemon storage: STORE/TAKE in the party menu); chimney 1 log; stairs_up 2 log; fence1 default;
torch default; house6_* hard stone; house8_/house9_ grass+log; house_gym1 2 hard stone; statue1 2 hard stone;
house_bed1 4 log + soft bedding; house_couch 1 log + soft wool; house_plant 1 log + miracle seed; potted
hard stone + miracle seed; picture thin paper; window clear glass + log; clock log + clear glass;
ball_kiln1 2 hard stone + 2 charcoal (kiln crafts); warp_tile1 2 dusk stone + 2 psi energy + 2 life force;
terrain tiles (DIG): sand1 soft sand, desert4 dry sand, mountain1 light clay, snow2 nevermeltice, green1 grass,
flower4 flowers, volcano1 ashen soil, green12 cursed soil, green_savanna1 dry soil, ledges3_none hard stone.
Outdoor list: torch1, house5_door1, house5_middle1, house5_roof_middle1, exteriorwindows1, chimney1, campfire1,
fence1, bridge1, potted3/4, statue1, house_gym1, house_plant1/2, gravestone3, sign_built1, warp_tile1, chest1.
R/L cycle the selected build tile (`player.currBuildTile`), A builds on the faced free tile.
Crafting happens at a built **campfire** (A on it).

## Farming: pokemon produce items
* DROP (party menu) puts a pokemon on the faced free tile; owned pokemon on the map accumulate
  `harvestTimer` while `inHabitat` (x2 if `inShelter`); at 9000 they hold `hasItem` (one of the species'
  `harvestables`). Face it and press A to collect.
* Habitat (terrain/object nearby) and produce by type: BUG flower|potted -> silky thread; WATER water -> hard
  shell; FLYING tree|bush -> soft feather; ROCK rock|statue|gym -> hard stone; FIRE campfire|lava|soot|volcano ->
  charcoal; GRASS grass -> miracle seed; POISON poison barb; GROUND mountain|sand|desert -> soft sand; STEEL
  mountain -> metal coat; PSYCHIC psi energy; DARK dark energy; GHOST gravestone|green12 -> life force;
  FIGHTING binding band; FAIRY stardust; ICE snow -> nevermeltice; ELECTRIC magnet; DRAGON dragon fang/scale.
  Specials: mareep line soft wool; cutiefly/combee/beedrill honey; miltank moomoo milk; delibird anything;
  unown ancientpowder; default manure.
* Key crafting inputs from farming: hard shell + magnet -> pokeball; life force + thin paper -> spell tag;
  metal coat -> great ball; berry juice + ancientpowder -> rare candy.
* Taking a pokemon/egg anywhere angers nearby same-species / egg-group wild pokemon (their parents hunt you):
  never pick up eggs.
