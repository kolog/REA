import sys, time
sys.path.insert(0, __file__.rsplit("bot", 1)[0] + "bot")
from rea import Game, boot, explore, nav, battle

g = Game()
s = boot.ensure_ingame(g)
ex = explore.Explorer(g)
t0 = time.time()
wins = 0
def on_int(s):
    global wins
    if battle.in_battle(s):
        r = battle.run_battle(g)
        print("battle:", r)
        if r["last"] == "run":
            ex.mark_danger(nav.tile_of(g.state()["player"]))
        wins += 1
    else:
        g.tap("a", 2, 20)
while time.time() - t0 < float(sys.argv[1] if len(sys.argv) > 1 else 300):
    s = ex.step(on_int)
    p = s["player"]
    print(round(time.time() - t0), nav.tile_of(p), [(m["specie"], m["lvl"], *battle.hp(m)) for m in p["party"]])
g.close()
