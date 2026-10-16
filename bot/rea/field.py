"""Field moves: choose CUT/SMASH/BUILD/... on a party member, then use it with A on the facing tile."""
from . import items

PM_CURR = "class:com.pkmngen.game.DrawPokemonMenu#currIndex"


def _wait_act(g, name, tries=60, depth=1):
    for _ in range(tries):
        v = g.act(name, depth)
        if v is not None and not v.get("disabled"):
            return v
        g.wait(4)
    return None


def select(g, party_idx, word, log=print):
    """Start -> POKEMON -> member -> word. Returns True when `word` is now the active field move."""
    s = g.state()
    if s["player"]["field"] == word and s["player"]["hm"] == party_idx:
        return True
    g.tap("start", 2, 20)
    menu = _wait_act(g, "DrawPlayerMenu")
    if menu is None:
        return False
    for _ in range(6):                                  # POKeMON is entry 0
        if g.act("DrawPlayerMenu")["currIndex"] == 0:
            break
        g.tap("up", 2, 6)
    g.tap("a", 2, 10)
    if _wait_act(g, "DrawPokemonMenu", tries=120) is None:
        items.close_menus(g)
        return False
    g.wait(20)
    for _ in range(8):
        cur = g.get(PM_CURR)
        if cur == party_idx:
            break
        g.tap("down" if party_idx > cur else "up", 2, 8)
    g.tap("a", 2, 12)
    sel = _wait_act(g, "DrawPokemonMenu$SelectedMenu", depth=2)
    if sel is None or word not in sel["words"]:
        log("field move %s not offered: %s" % (word, sel and sel["words"]))
        items.close_menus(g)
        return False
    target = sel["words"].index(word)
    for _ in range(10):
        cur = g.act("DrawPokemonMenu$SelectedMenu", 1)["curr"]
        if cur == target:
            break
        g.tap("down" if target > cur else "up", 2, 8)
    g.tap("a", 2, 12)
    for _ in range(40):                                 # menus fade out, maybe a "following you" text
        s = g.state()
        if "DisplayText" in s["actions"]:
            g.tap("a", 2, 14)
        elif "PlayerStanding" in s["actions"] and not any("Menu" in a for a in s["actions"]):
            break
        else:
            g.wait(6)
    s = g.state()
    return s["player"]["field"] == word


def clear(g):
    """Drop the active field move (hold B). Needed before the sleeping bag; also makes the strongest mon lead."""
    for _ in range(4):
        s = g.state()
        if s["player"]["field"] == "" and s["player"]["hm"] < 0:
            return True
        g.hold("b", 40)
        g.wait(10)
        s = g.state()
        if "DisplayText" in s["actions"]:
            g.tap("a", 2, 14)
    s = g.state()
    return s["player"]["field"] == "" and s["player"]["hm"] < 0
