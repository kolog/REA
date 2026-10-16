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


BOT_SAVE = "default.sav"      # the bot's own world; the user's saves are never touched


def load_save(g, filename=BOT_SAVE):
    """Title screen -> Load mode (right arrow) -> pick the file (left/right) -> Start."""
    assert filename == BOT_SAVE, "refusing to load a save that is not the bot's own"
    def menu():
        return g.act("DrawSetupMenu", 2)
    m = menu()
    if m is None:
        return g.state()
    if filename not in m["fileNames"]:
        return None
    while g.get(C + "currIndex") != 1:
        g.tap("down", 2, 10)
    if menu()["newLoadIndex"] == 0:
        g.tap("right", 2, 10)                   # New -> Load
    for _ in range(len(m["fileNames"]) + 1):
        m = menu()
        if m["fileNames"][m["fileIndex"]] == filename:
            break
        g.tap("right", 2, 10)
        while g.get(C + "currIndex") != 2:      # the file row is where the arrows act on the file
            g.tap("down", 2, 10)
    for _ in range(8):
        if g.get(C + "currIndex") == 3:
            break
        g.tap("down", 2, 10)
    g.tap("a", 2, 30)
    for _ in range(120):
        s = g.wait(60)
        if "DrawSetupMenu" not in s["actions"] and s.get("player", {}).get("party"):
            break
    for _ in range(40):
        s = g.state()
        if "DisplayText" not in s["actions"] and "PlayerStanding" in s["actions"]:
            break
        g.tap("a", 2, 20)
    return g.state()


def resume_or_new(g):
    """Use the bot's save if there is one, otherwise start a fresh world."""
    s = g.state()
    if "DrawSetupMenu" not in s["actions"]:
        return s
    m = g.act("DrawSetupMenu", 2)
    if BOT_SAVE in m["fileNames"]:
        r = load_save(g)
        if r is not None:
            return r
    return ensure_ingame(g)
