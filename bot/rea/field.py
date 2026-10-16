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


def party_action(g, party_idx, word, log=print):
    """Start -> POKEMON -> member -> `word` (DROP, SWITCH, STATS ...). Returns True if the word was pressed."""
    items.close_menus(g)
    g.tap("start", 2, 20)
    if _wait_act(g, "DrawPlayerMenu") is None:
        return False
    for _ in range(6):
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
        log("%s not offered: %s" % (word, sel and sel["words"]))
        items.close_menus(g)
        return False
    target = sel["words"].index(word)
    for _ in range(10):
        cur = g.act("DrawPokemonMenu$SelectedMenu", 1)["curr"]
        if cur == target:
            break
        g.tap("down" if target > cur else "up", 2, 8)
    g.tap("a", 2, 14)
    return True


def drop_eggs(g, log=print):
    """Put every egg in the party on the ground (they anger parents and take ages to hatch). Returns count dropped."""
    from . import economy, nav, recruit
    dropped = 0
    for _ in range(6):
        s = nav.ensure_free(g)
        idx = next((i for i, m in enumerate(s["player"]["party"]) if m.get("egg")), None)
        if idx is None or len(s["player"]["party"]) <= 1:
            break
        clear(g)
        d = economy.free_neighbor(g)
        if d is None:
            log("no free tile to drop an egg")
            break
        recruit.face(g, d)
        before_n = len(s["player"]["party"])
        if not party_action(g, idx, "DROP", log):
            break
        for _ in range(30):
            s = g.state()
            if "DrawYesNoMenu" in s["actions"]:
                recruit.yes_no(g, True)
            elif "DisplayText" in s["actions"]:
                g.tap("a", 2, 14)
            elif "PlayerStanding" in s["actions"] and not any("Menu" in a for a in s["actions"]):
                break
            else:
                g.wait(8)
        if len(g.state()["player"]["party"]) < before_n:
            dropped += 1
            log("dropped an egg")
    return dropped


def drop_member(g, idx, log=print):
    """DROP party member `idx` onto a free adjacent tile. Returns True when the party shrank."""
    from . import economy, nav, recruit
    s = nav.ensure_free(g)
    n = len(s["player"]["party"])
    if n <= 1:
        return False
    clear(g)
    d = economy.free_neighbor(g)
    if d is None:
        log("no free tile to drop a pokemon")
        return False
    recruit.face(g, d)
    if not party_action(g, idx, "DROP", log):
        return False
    for _ in range(30):
        s = g.state()
        if "DrawYesNoMenu" in s["actions"]:
            recruit.yes_no(g, True)
        elif "DisplayText" in s["actions"]:
            g.tap("a", 2, 14)
        elif "PlayerStanding" in s["actions"] and not any("Menu" in a for a in s["actions"]):
            break
        else:
            g.wait(8)
    return len(g.state()["player"]["party"]) < n


def set_lead(g, idx, log=print):
    """Make party member idx follow the player (FOLLOW): it then opens every battle, so it takes part in the
    fight and earns exp even when a stronger mon is swapped in. Water-only species cannot follow."""
    s = g.state()
    if s["player"]["hm"] == idx and s["player"]["field"] == "":
        return True
    if s["player"]["field"] != "":
        clear(g)
    if not party_action(g, idx, "FOLLOW", log):
        return False
    for _ in range(30):
        s = g.state()
        if "DisplayText" in s["actions"]:
            g.tap("a", 2, 14)
        elif "PlayerStanding" in s["actions"] and not any("Menu" in a for a in s["actions"]):
            break
        else:
            g.wait(8)
    return g.state()["player"]["hm"] == idx
