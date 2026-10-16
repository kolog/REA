"""Run the full bot: python bot/run_brain.py [seconds]"""
import sys
import time

sys.path.insert(0, __file__.rsplit("bot", 1)[0] + "bot")
from rea import Game, boot, brain, nav

g = Game()
boot.resume_or_new(g)
mission = sys.argv[2] if len(sys.argv) > 2 else "auto"
b = brain.Brain(g, log=lambda m: print("  " + m, flush=True), mission=mission)
t0 = time.time()
limit = float(sys.argv[1]) if len(sys.argv) > 1 else 90
last = 0
try:
    while time.time() - t0 < limit:
        s = b.tick()
        if time.time() - last > 20:
            last = time.time()
            print("%4ds %s party=%s items=%s %s" % (
                time.time() - t0, nav.tile_of(s["player"]),
                [(m["specie"], m["lvl"], "%d/%d" % (m["stats"]["hp"], m["max"]["hp"])) for m in s["player"]["party"]],
                {k: v for k, v in s["player"]["items"].items() if k not in ("escape rope",)}, b.stats), flush=True)
finally:
    b.trainer.checkpoint(True)
    g.close()
