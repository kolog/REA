"""Start menu / bag navigation (M2-M3)."""
import time


def _tap_until(g, key, getter, target, tries=12, gap=6):
    for _ in range(tries):
        if getter() == target:
            return True
        g.tap(key, 2, gap)
    return getter() == target


def _wait_for(g, name, tries=60, enabled=True):
    for _ in range(tries):
        v = g.act(name, 1)
        if v is not None and not (enabled and v.get("disabled")):
            return v
        g.wait(4)
    return None


def open_bag(g):
    """From the overworld to the item list. Returns the DrawItemMenuGen2 dump or None."""
    close_menus(g)                      # a menu left open would turn Start into "sort items"
    s = g.state()
    if "DrawBattle" in s["actions"]:
        return None
    g.tap("start", 2, 20)
    menu = _wait_for(g, "DrawPlayerMenu")
    if menu is None:
        return None
    ok = _tap_until(g, "down" if menu["currIndex"] < 1 else "up",
                    lambda: g.act("DrawPlayerMenu")["currIndex"], 1)
    if not ok:
        return None
    g.tap("a", 2, 10)
    return _wait_for(g, "DrawItemMenuGen2", tries=120)


last_error = ""


def _norm(x):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(x).lower()) if unicodedata.category(c) != "Mn")


BOX = "class:com.pkmngen.game.DrawItemMenuGen2#boxIndex"


def select_item(g, name):
    """With the bag open: put the cursor on `name` (switching tabs if needed) and press A.
    Names are compared without accents/case. Tabs are identified by the game's boxIndex: some tabs are empty and
    look identical, so comparing their contents cannot tell when we have been around all of them."""
    global last_error
    last_error = ""
    want = _norm(name)
    start_box = g.get(BOX)
    presses = 0
    for _ in range(12):
        m = g.act("DrawItemMenuGen2", 2)
        if m is None:
            last_error = "item menu not open"
            return False
        if m.get("isSorting"):          # A on the same entry just ends the sorting mode
            g.tap("a", 2, 12)
            continue
        norm = [_norm(x) for x in m["itemsList"]]
        if want in norm:
            t = norm.index(want)
            _tap_until(g, "down" if t > m["currIndex"] + m["cursorPos"] else "up",
                       lambda: (lambda x: x["currIndex"] + x["cursorPos"])(g.act("DrawItemMenuGen2", 1)), t,
                       tries=40, gap=4)
            g.tap("a", 2, 12)
            return True
        if presses and g.get(BOX) == start_box:
            last_error = "%r not in any of the %d tabs" % (name, presses)
            return False
        g.tap("right", 2, 14)
        g.wait(6)
        presses += 1
    last_error = "%r not found after %d tab switches" % (name, presses)
    return False


def use_item(g, name):
    """Open the bag, pick `name`, confirm USE. Caller handles whatever the item does next."""
    if open_bag(g) is None:
        return False
    if not select_item(g, name):
        g.tap("b", 2, 20)
        return False
    if _wait_for(g, "DrawUseTossMenu") is None:
        return False
    g.tap("a", 2, 12)      # USE is the first entry
    return True


def close_menus(g, tries=8):
    for _ in range(tries):
        s = g.state()
        if any(a in s["actions"] for a in ("DrawPlayerMenu", "DrawItemMenuGen2", "DrawUseTossMenu")):
            g.tap("b", 2, 14)
        else:
            return
