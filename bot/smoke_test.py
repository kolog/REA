"""Milestone 0 check: connect, read state, walk a few tiles, print what changed."""
import json
import sys
sys.path.insert(0, __file__.rsplit("bot", 1)[0] + "bot")
from rea import Game

g = Game()
s = g.state()
print("frame", s["frame"], "actions", s["actions"][-6:])
p = s.get("player")
if p:
    print("player", p["x"], p["y"], p["dir"], "party", [(m["specie"], m["lvl"]) for m in p["party"]])
    print("items", p["items"])
    for d in ("right", "down", "left", "up"):
        s = g.hold(d, 16)
        print(d, "->", s["player"]["x"], s["player"]["y"], s["player"]["state"])
g.close()
