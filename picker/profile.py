"""Learn taste from past picks: how much more (or less) often you choose each tag than the menu offered it.

Each pick is compared with the menu it was actually chosen from (fetched by delivery date), so a week heavy
on chicken doesn't make you look like a chicken fan. If a past menu can't be fetched, that pick falls back to
the current menus' mix. docs/index.html repeats this maths for picks entered on the site.
"""
import json
import math
from collections import Counter
from pathlib import Path

from .tags import tag

PICKS = Path(__file__).resolve().parent.parent / "picks.json"
DIMS = ("main", "style", "dish")  # main ingredient, cuisine, dish type


def load_history():
    """[{name, week}] from picks.json; week is the delivery date the picks were for."""
    if not PICKS.exists():
        return []
    data = json.loads(PICKS.read_text())
    return [{"name": n, "week": wk["week"]} for wk in data.get("picks", []) for n in wk["recipes"]]


def shares(items):
    out = {}
    for d in DIMS:
        c = Counter(i[d] for i in items)
        total = sum(c.values()) or 1
        out[d] = {v: n / total for v, n in c.items()}
    return out


def learn(history, pool, past_menus=None, lc=None):
    """history: [{name, week}]. pool: eligible items across the current menus (the base rate for the prior).
    past_menus: {week: eligible items on that week's menu}. Returns obs/exp counts so the page can add its own picks."""
    lc = lc or {"prior": 20, "scale": 8, "tag_limit": 12}
    past_menus = past_menus or {}
    pooled = shares(pool)
    week_shares = {w: shares(items) for w, items in past_menus.items() if items}
    obs = {d: Counter() for d in DIMS}
    exp = {d: Counter() for d in DIMS}
    for h in history:
        tags = dict(zip(DIMS, tag(h["name"])))
        base = week_shares.get(h["week"], pooled)
        for d in DIMS:
            obs[d][tags[d]] += 1
            for v in pooled[d]:
                exp[d][v] += base[d].get(v, 0)
    out = {"n": len(history), "obs": {d: dict(obs[d]) for d in DIMS}, "exp": {d: {v: round(x, 3) for v, x in exp[d].items()} for d in DIMS},
           "picked": {d: dict(obs[d]) for d in DIMS}, "bonus": {}, "top": [],
           "menus_matched": sum(1 for h in history if h["week"] in week_shares)}
    out["bonus"], out["top"] = bonuses(out["obs"], out["exp"], pooled, lc) if history else ({d: {} for d in DIMS}, [])
    return out


def bonuses(obs, exp, pooled, lc):
    bonus, top = {}, []
    for d in DIMS:
        bonus[d] = {}
        for v, s in pooled[d].items():
            ratio = (obs[d].get(v, 0) + lc["prior"] * s) / (exp[d].get(v, 0) + lc["prior"] * s)
            b = max(-lc["tag_limit"], min(lc["tag_limit"], round(lc["scale"] * math.log2(ratio))))
            bonus[d][v] = b
            if v != "Other":
                top.append({"dim": d, "value": v, "bonus": b, "picked": obs[d].get(v, 0)})
    top.sort(key=lambda x: x["bonus"], reverse=True)
    return bonus, top
