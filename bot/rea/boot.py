"""Get from the title screen to an in-world state (new game named REA)."""
C = "class:com.pkmngen.game.DrawSetupMenu#"


def ensure_ingame(g, name="REA"):
    s = g.state()
    if "DrawSetupMenu" not in s["actions"]:
        return s
    while g.get(C + "currIndex") != 4:
        g.tap("down", 2, 10)
    g.call("type " + name)
    g.wait(5)
    while g.get(C + "currIndex") != 6:
        g.tap("down", 2, 10)
    g.tap("a", 2, 30)
    for _ in range(120):  # world generation + intro text
        s = g.wait(60)
        if "DrawSetupMenu" not in s["actions"] and s.get("player", {}).get("party"):
            break
    # dismiss intro text boxes
    for _ in range(40):
        s = g.state()
        if "DisplayText" not in s["actions"] and "PlayerStanding" in s["actions"]:
            break
        g.tap("a", 2, 20)
    return g.state()
