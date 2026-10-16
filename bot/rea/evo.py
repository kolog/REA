"""Evolution knowledge read from the running game (Specie.gen2Evos: {species: {level_or_item: evolved}})."""
_cache = {}

# species whose evolution unlocks something the base needs (FLY = free travel, no encounters)
FLY_LINE = {"natu", "spearow", "pidgey", "pidgeotto", "hoothoot", "taillow", "wingull", "golbat", "gligar"}


def load(g):
    if not _cache:
        _cache.update(g.get("class:com.pkmngen.game.Specie#gen2Evos", 3) or {})
    return _cache


def next_level_evo(g, specie):
    """(level, evolved species) of the next level-based evolution, or None."""
    best = None
    for key, target in (load(g).get(specie) or {}).items():
        if str(key).isdigit() and (best is None or int(key) < best[0]):
            best = (int(key), target)
    return best


def trainee(g, s):
    """Party index worth feeding exp to via the lead-swap trick, or None."""
    party = s["player"]["party"]
    top = max(m["lvl"] for m in party)
    best, bscore = None, 0.0
    for i, m in enumerate(party):
        if m.get("egg") or m["stats"]["hp"] <= 0 or m["lvl"] >= top:
            continue
        ev = next_level_evo(g, m["specie"])
        score = (top - m["lvl"]) * 1.0
        if ev:
            score += 6.0 + (12.0 if m["specie"] in FLY_LINE else 0.0)
            score += max(0, 10 - (ev[0] - m["lvl"]))      # about to evolve
        if score > bscore:
            best, bscore = i, score
    return best
