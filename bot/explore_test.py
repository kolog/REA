import sys, time
sys.path.insert(0, __file__.rsplit("bot", 1)[0] + "bot")
from rea import Game, boot, explore, nav

g = Game()
s = boot.ensure_ingame(g)
ex = explore.Explorer(g)
t0 = time.time()
seen_acts = set()
def interrupted(s):
    names = [a for a in s["actions"] if not a.startswith("Pokemon")]
    print("  interrupted:", names[-6:], s.get("battle"))
    g.tap("a", 2, 20)
while time.time() - t0 < float(sys.argv[1] if len(sys.argv) > 1 else 120):
    s = ex.step(interrupted)
    print(round(time.time() - t0), nav.tile_of(s["player"]), len(ex.seen))
g.close()
