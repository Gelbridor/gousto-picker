"""Learn taste from past picks: how much more (or less) often you choose each tag than the menu offers it."""
import json
import math
from collections import Counter
from pathlib import Path

from .tags import tag

PICKS = Path(__file__).resolve().parent.parent / "picks.json"
DIMS = ("main", "style", "dish")  # main ingredient, cuisine, dish type
PRIOR = 20      # pseudo-picks drawn from the menu mix; larger = slower to trust a small history
SCALE = 8       # score points per doubling of how often you pick something
LIMIT = 16


def load_picks():
    if not PICKS.exists():
        return []
    data = json.loads(PICKS.read_text())
    return [n for wk in data.get("picks", []) for n in wk["recipes"]]


def learn(menu_items):
    """menu_items: unique recipe dicts (with main/style/dish) the shortlist could draw from."""
    names = load_picks()
    if not names:
        return {"n": 0, "bonus": {d: {} for d in DIMS}, "picked": {d: {} for d in DIMS}, "top": []}
    tagged = [dict(zip(DIMS, tag(n))) for n in names]
    out = {"n": len(names), "bonus": {}, "picked": {}}
    summary = []
    for d in DIMS:
        menu = Counter(i[d] for i in menu_items)
        total = sum(menu.values())
        picked = Counter(t[d] for t in tagged)
        out["picked"][d] = dict(picked)
        out["bonus"][d] = {}
        for value, count in menu.items():
            share = count / total
            p = (picked.get(value, 0) + PRIOR * share) / (len(names) + PRIOR)
            b = max(-LIMIT, min(LIMIT, round(SCALE * math.log2(p / share))))
            out["bonus"][d][value] = b
            if value != "Other":
                summary.append({"dim": d, "value": value, "bonus": b, "picked": picked.get(value, 0)})
    summary.sort(key=lambda x: x["bonus"], reverse=True)
    out["top"] = summary
    return out
