"""Run the goal-driven trainer: python bot/run_trainer.py [seconds]"""
import sys
import time

sys.path.insert(0, __file__.rsplit("bot", 1)[0] + "bot")
from rea import Game, boot, trainer, nav

g = Game()
boot.resume_or_new(g)
t = trainer.Trainer(g, log=lambda m: print("  " + m, flush=True))
t0 = time.time()
limit = float(sys.argv[1]) if len(sys.argv) > 1 else 300
last = 0
try:
    while time.time() - t0 < limit:
        s = t.tick()
        if time.time() - last > 15:
            last = time.time()
            lead = t.lead(s)
            print("%4ds %s %s L%d hp %d/%d exp %d  %s" % (
                time.time() - t0, nav.tile_of(s["player"]), lead["specie"], lead["lvl"],
                lead["stats"]["hp"], lead["max"]["hp"], lead["exp"], t.stats), flush=True)
finally:
    t.checkpoint(True)
    g.close()
