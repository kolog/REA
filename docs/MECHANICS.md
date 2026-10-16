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

## Catching (Battle.java)
* a = (3*maxHP - 2*curHP) * (catchRate * ballMult) / (3*maxHP) (HP terms /4 when 3*maxHP > 255), min 1, +10 if
  sleep/freeze, cap 255. Caught at once with prob (a+1)/256, otherwise three shake checks against b (lookup table
  of a): P = p1 + (1-p1)*(b/256)^3. Master ball always.
* Ball multipliers: great 1.5, ultra 2, dusk 3.5 (night/caves), fast 4 (base speed >= 100), quick 5 (turn 1),
  net up to 4 (WATER/BUG, grows with turns), nest (41-level)/10 (level <= 29), dream 4 (asleep), heavy +30/+20/0/-20
  catch rate by weight, level 2/4/8 by our lead level vs theirs (>, >/2, >/4), love 8 (same species, other gender),
  moon 4 (clefairy, jigglypuff, nidorina, nidorino). A good ball can be thrown at full HP.

## Exp / evolution / lead
* Exp after a win is split among party members with `participatedInBattle` (the pokemon that was out at any
  point). Lead of every battle = `hmPokemon` if alive (FOLLOW or any field move) else first alive. So a weak mon
  can lead, be swapped for a strong one, and still gain exp.
* `Specie.gen2Evos[species] = {level: evolved}`. natu 25 -> xatu (FLY), machop 28, chikorita 16, rhyhorn 42,
  tentacool 30, spearow 20 -> fearow (FLY), pidgey 18.

## FLY
* Party menu -> FLY word (FLY species: pidgeot aerodactyl charizard dragonair dragonite salamence ho_oh lugia
  skarmory articuno zapdos moltres crobat noctowl xatu flygon togekiss swellow pelipper altaria rayquaza drifblim
  honchkrow yanmega garchomp volcarona fearow mewtwo mantine toucannon noivern). While `currFieldMove == FLY`
  wild pokemon never aggro/contact the player (Pokemon.java checks `!FLY`); B lands on a non-solid, non-ledge tile
  with no pokemon on it. Overworld only.

## Fences, doors, gates, pens
* Wild/dropped pokemon cannot enter tiles that are solid, ledges, have another pokemon, or whose name/nameUpper
  contains `door` or `gate`. The player can walk through gates.
* A built `house5_door1` stands for a house door: stepping on it enters the interior map (`map.interior = true`).
  If it has fences on both sides in a line the game converts it into `fence1gate1` (a gate; walkable, stays
  outdoors). Fences auto-tile their names (fence1_NS, fence1_NSEW ...).
* Pen test (Minun): 3 fences + 2 side fences + gate keeps the pokemon on its tile (stayed put for minutes), BUT the
  pen tile itself became `fence1_NSEW` (solid) and pressing A from the gate no longer interacts with the pokemon.
  Open question: how to collect from a fully enclosed 1x1 pen.
* Pokemon wander widely when free (a dropped Ponyta moved ~15 tiles in minutes), so unpenned farms drift away.

## The in-game guide (DrawItemMenu "GUIDE") — verbatim facts
Hold X(B) still to stop a field move. Craft at a campfire. White out -> last place a sleeping bag was used. Ghosts
appear in woods at night; a campfire wards them off. Grass types know CUT (trees/tall grass -> building materials).
Fighting types know BUILD; **use CUT on buildings to remove them**. Eggs when near a compatible mate. Fences keep
pokemon from wandering; pokemon are happier fenced in and near a shelter, happier in their natural habitat, and if
happy enough they give items. Angry parents attack when you take eggs. A door between two house tiles = back/side
door; a door between two fences = gate. Sleeping indoors restores hp twice as fast; a bed also cures status. Escape
rope = nearest shore. Plant Miracle Seeds / Apricorns to grow grass / trees (renewable). Eggs hatch only while
carried (RIDE counts, FLY does not). Rock types know SMASH on boulders (rocks respawn daily). Soft Feather + Silky
Thread -> soft bed. Bug -> silky thread, Flying -> soft feather.

## Where caught pokemon go (CatchPokemonWobblesThenCatch)
Party < 6: joins the party. Party full: "sent to the last safe place" = `player.spawnLoc` (where the sleeping bag
was last used); if that was inside a house (`spawnIndex != -1`) the pokemon appears in that interior. So nothing
extra needs to be built; sleeping inside the house makes it the pokemon pen.

## Houses (PkmnMap.adjustSurroundingTiles, experiments)
* Standing on a built door tile puts the player in the interior map (`map.interior`), whose build list is different
  (carpets, chest1, bed, couches, shelf, wardrobe, window, clock, plushies, kiln, stairs, torch, plants).
  The outdoor build list (roof/wall/door/fence/campfire...) is only offered while outside.
* Build tile families depend on terrain (house5_, house6_, house9_ ...): select by role (roof/wall/door/fence).
* Test house: walls `house5_middle1` left/right of a `house5_door1` became house5_left1/right1; roofs
  (`house5_roof_middle1`) go on the row above. Interior floor tiles are created under the footprint.
* Pen recipe that works: fences on 3 sides + 2 fences flanking the open side + door in between (auto-converts to
  `fence1gate1`); the game fills the enclosed tile with a fence (`fence1_NSEW`): remove it with CUT; collect from the
  gate tile (A facing the pokemon).

## Large trees need a fully evolved CUT user
`tree_large1` / `tree_savanna1` (4 logs) can only be cut when `hmPokemon.hasEvo()` is false: chikorita must reach
meganium (chikorita 16 -> bayleef, 32 -> meganium) before large trees can be felled.

## DIG
With DIG selected the build tile is `hole1` (L/R do not cycle in hole mode): A digs a hole and gives a terrain item
by ground type (grass, soft sand, light clay, dry soil, damp soil ...). `*_cracked` tiles drop stones/fossils
(sun/fire/leaf/dusk/ice/water/thunder stones, revive, star piece, ultra ball ...). Tidal tiles are named
`*_tidalwater` so they satisfy the WATER habitat; the tide flips shore tiles between sand and water.

## Pen recipe (automated in farm.deploy_pen)
fences N/E/W of the pen tile, gate (door between two fences) on the south side with two flanking fences; stand
on the gate to CUT the fence the game puts on the enclosed tile, then DROP the pokemon from the gate. Collect by
facing the pokemon from the gate. Works for the Ponyta next to the campfire (FIRE habitat).
