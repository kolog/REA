---
name: pokewilds-bot
description: Use when the user wants to play, continue, debug or extend the autonomous PokeWilds bot (REA) — starting the game with the agent attached, running a mission (train, balls, flyer, auto), saving/loading the bot's world, or fixing bot behaviour (battles, rest, farm pens, house, flying).
---

# PokeWilds bot (REA)

Autonomous player for PokeWilds v0.8.11 (offline). Repo: `C:\Users\Lucas\REA` (GitHub `kolog/REA`, branch `main`).
Game: `C:\Users\Lucas\Desktop\pokewilds-v0.8.11-windows-64`. Answer in pt-BR.

## How it works
Java agent (`agent/rea-agent.jar`, injected with `-javaagent`) reads the game state by reflection and injects button
presses frame by frame on `127.0.0.1:7777`. Python (`bot/rea/`) decides. Decompiled-source notes: `docs/MECHANICS.md`,
`docs/ROUTES.md`, `docs/PRIORITIES.md`.

## Start playing (do this first)
1. `bash tools/restart.sh` — kills old java, rebuilds the agent, launches the game with it (wait for `serving on 127.0.0.1:7777`).
   (`powershell tools/play.ps1` does the same plus the first mission.)
2. `python bot/run_brain.py <seconds> <mission>` — loads the bot's save (`default.sav`) from the title screen automatically
   (or creates a new world named REA) and plays.
   Missions: `auto` (everything), `train` (survive + level the trainee/zone), `balls` (collect apricorns, craft balls,
   farm harvest), `flyer` (hunt a flying mon; mostly obsolete now that Xatu flies).
3. **Run each call in the FOREGROUND and under ~110 s** (the user dislikes background commands; a message arriving
   mid-run auto-backgrounds long ones). Call repeatedly. Never `sleep` in a loop.
4. Save often: `Game().save()` (agent command) — the bot also saves every 45 s and after each battle.

## Hard rules
* Only ever use the bot's own save `default.sav`. NEVER load or touch `default100.sav` / `ds.sav` (the user's worlds).
* Never recruit eggs (their parents hunt you). Never pick fights above the team level; flee or fly.
* Check HP every decision; sleep at home (door at (16,-69)) when the team is under 60 %.
* Interior vs exterior: build/cut/farm only from OUTSIDE; furniture only from INSIDE; doors are not standing tiles.
* The player can only leave the house by walking down from the door tile (`nav.ensure_outside` does it).
* Test code against the live game in short foreground calls; read the decompiled source before guessing
  (source: decompile `com/pkmngen` from `app/pokewilds.jar` with CFR 0.152, or see docs).

## Current state (last session)
Party: machop 27, bayleef 18, rhyhorn 15, **xatu 25 (FLY)**, chansey 14. Base around the campfire at (7,-64): house 5x3 at
(14..18,-69..-67) with chest + ball kiln inside, pens (gates) for ponyta (fire), minun (electric), shellder
(water); magikarp swims in the lake. Items: secret key (mansion), 5 poke balls, 2 level, 1 heavy, 1 love.

## Key modules (bot/rea)
`brain` priorities (battle > rest > goals) · `battle` (fight/switch/catch by real catch probability, plain poke ball
preferred) · `rest` (sleep home/bag) · `fly` (take_off/goto/land/trip; FLY works even with fainted mon, but only
BEFORE contact) · `farm` (pens: 3 fences + gate, cut flank fences; water-only species dropped into water) ·
`base` (house, furnish, kiln) · `economy` (gather/build/craft) · `trainer` (zones, lead-swap exp trick; natu->xatu done,
chikorita->bayleef->meganium pending for large trees) · `nav/world/travel` (paths) · `recruit`.

## Known quirks and fixes
* Stuck, no movement but `PlayerStanding`: `playerCanMove` false after a refused menu action -> Start then B (nav.ensure_free does it).
* Stuck in the house: `nav.ensure_outside`. Asleep after a restart: B (ensure_free does it).
* Bag has 5 tabs, two empty; balls are in tab 4 (use `items.select_item`, tabs identified by `boxIndex`).
* Game stdout is in `tools/game.log` (shows what tile A is facing).

## Next steps (priority)
1. Preventive take-off: when a strong aggressive mon approaches, FLY home with Xatu BEFORE the battle starts.
2. Quick balls at the kiln (fast ball + magnet, x5 on turn 1); keep ~20 balls.
3. Pokemon Mansion with the secret key; capture the Skarmory (L10, FLY) on the unreachable island by flying.
4. SURF, Meganium (large trees), fossils/stones via DIG on `*_cracked` tiles, regis, more biomes.
5. Water farm / habitat for more species; plant apricorns and miracle seeds for renewable materials.
