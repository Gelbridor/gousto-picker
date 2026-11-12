"""Filter and rank recipes. Weights and learning settings live in config.json.

docs/index.html repeats the personal parts of this maths (tag bonus, repeat bonus, variety) so the page can
re-rank instantly; keep the two in step.
"""
import json
import re
from bisect import bisect_left, bisect_right
from datetime import date
from pathlib import Path

from .tags import tag

CONFIG = Path(__file__).resolve().parent.parent / "config.json"
STOP = {"with", "and", "the", "a", "of", "in", "on", "style", "n", "w", "s"}


def load_config():
    return json.loads(CONFIG.read_text())


def usable(r):
    return bool(r.get("is_available", True)) and bool(r.get("nutritional_information"))


def eligible(i):
    return not i["vegan"] and not i["premium"] and not i.get("swap_hidden")


# ---------- protein swaps: "double" portions and "lean" mince versions of a standard recipe ----------
MEATS = {"beef", "pork", "chicken", "turkey", "lamb", "basa", "cod", "salmon", "sausage", "haddock", "hake"}
SWAP_WORDS = {"lean", "double", "mince", "wholewheat", "wholemeal"}


def swap_kind(it):
    w = words(it["name"])
    if "double" in w and it["premium"]:   # "Double Cheese" etc. aren't protein swaps and aren't premium
        return "double"
    return "lean" if "lean" in w else None


def mark_swaps(items, sim=0.6):
    """Hide every double-protein swap. Hide a lean swap when the same week offers the standard recipe with the same
    meat (Lean Beef Bolognese vs Beef Bolognese); keep it when that's the only way to get that meat
    (lean beef where the standard is pork & beef or lamb, or there's no standard version at all)."""
    def core(n):
        return words(n) - SWAP_WORDS - MEATS
    standard = [i for i in items if not swap_kind(i) and "vegetarian" not in i["diet"] and not i["vegan"]]
    for it in items:
        kind = it["swap"] = swap_kind(it)
        hidden = kind == "double"
        if kind == "lean":
            mine, c = words(it["name"]) & MEATS, core(it["name"])
            for s in standard:
                cs = core(s["name"])
                if c and cs and len(c & cs) / len(c | cs) >= sim and words(s["name"]) & MEATS in (mine, set()):
                    hidden = True
                    it["swap_of"] = s["name"]
                    break
        it["swap_hidden"] = hidden


def simplify(r):
    n = r["nutritional_information"]["per_portion"]
    img = next((c["url"] for i in r.get("images", []) for c in i["crops"] if c["width"] == 400), None)
    rating = r.get("rating") or {}
    protein_tag, cuisine_tag, dish_tag = tag(r["name"])
    return {
        "id": r["id"],
        "name": r["name"],
        "cook_time": r.get("prep_time"),
        "calories": n.get("energy_kcal"),
        "protein_g": round((n.get("protein_mg") or 0) / 1000),
        "carbs_g": round((n.get("carbs_mg") or 0) / 1000),
        "fat_g": round((n.get("fat_mg") or 0) / 1000),
        "five_a_day": r.get("five_a_day"),
        "rating": rating.get("average"),
        "rating_count": rating.get("count") or 0,
        "diet": sorted(c["slug"] for c in r.get("dietary_claims") or []),
        "vegan": any(c["slug"] == "vegan" for c in r.get("dietary_claims") or []),
        "premium": bool(r.get("surcharge")),  # extra-cost recipe
        "surcharge_pp": ((r.get("surcharge") or {}).get("price_per_portion") or 0) / 100,
        "cuisine": (r.get("food_brand") or {}).get("name"),
        "main": protein_tag,
        "style": cuisine_tag,
        "dish": dish_tag,
        "image": img,
        "url": "https://www.gousto.co.uk/menu",
    }


def _percentile(value, ordered, invert=False):
    """Share of the eligible menu this value beats (ties count half). Outliers can't squash everyone else."""
    if value is None or not ordered:
        return 0.5
    below, upto = bisect_left(ordered, value), bisect_right(ordered, value)
    p = (below + (upto - below) / 2) / len(ordered)
    return 1 - p if invert else p


def menu_items(recipes, cfg):
    """Raw feed recipes -> unique simplified items with rating and the 0-1 component scores."""
    prior_mean, prior_n = cfg["rating_prior_mean"], cfg["rating_prior_count"]
    seen, items = set(), []
    for r in recipes:
        if not usable(r) or r["name"] in seen:
            continue
        seen.add(r["name"])
        items.append(simplify(r))
    for it in items:  # Bayesian average so a 5.0 from 3 votes doesn't beat a 4.6 from 20k
        n = it["rating_count"]
        it["bayes_rating"] = ((it["rating"] or 0) * n + prior_mean * prior_n) / (n + prior_n)

    pool = [i for i in items if eligible(i)] or items  # compare against what you'd actually choose from
    ordered = {k: sorted(i[k] for i in pool if i[k] is not None) for k in ("bayes_rating", "protein_g", "calories", "cook_time")}
    for it in items:
        it["components"] = {
            "rating": round(_percentile(it["bayes_rating"], ordered["bayes_rating"]), 3),
            "protein": round(_percentile(it["protein_g"], ordered["protein_g"]), 3),
            "calories": round(_percentile(it["calories"], ordered["calories"], invert=True), 3),
            "time": round(_percentile(it["cook_time"], ordered["cook_time"], invert=True), 3),
        }
        it["score"] = base_score(it, cfg["weights"])
    mark_swaps(items, cfg["learning"]["similar"])
    return items


def base_score(it, w):
    total = sum(w.values())
    return round(sum(w[k] * it["components"][k] for k in w) / total * 100, 1) if total else 50.0


# ---------- personal parts: shared with docs/index.html ----------

def key(name):
    """Name for matching: Gousto mixes straight and curly quotes between weeks."""
    return re.sub(r"\s+", " ", name.replace("‘", "'").replace("’", "'").replace("`", "'")).strip().lower()


def words(name):
    return {t for t in re.split(r"[^a-z0-9]+", name.lower().replace("'", "").replace("’", "")) if t and t not in STOP}


def similarity(a, b):
    wa, wb = words(a), words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def _days(a, b):
    return (date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days


def repeat_bonus(name, history, menu_start, lc):
    """Points for recipes you've picked before (or a close variant), fading with time.
    Picks dated in this menu's own week are the choice being made, not history, so they are skipped."""
    pts = 0.0
    for h in history:
        gap = _days(h["week"], menu_start)
        if 0 <= gap < 10:
            continue
        s = 1.0 if key(h["name"]) == key(name) else similarity(h["name"], name)
        if s < lc["similar"]:
            continue
        pts += lc["repeat_points"] * (1.0 if s == 1.0 else 0.7) * 0.5 ** (abs(gap) / 7 / lc["repeat_half_life_weeks"])
    return min(lc["repeat_max"], pts)


def tag_bonus(it, profile, lc):
    b = profile.get("bonus", {})
    total = sum(b.get(d, {}).get(it[d], 0) for d in ("main", "style", "dish"))
    return max(-lc["tag_cap"], min(lc["tag_cap"], total))


def vary(ranked, cfg):
    """Greedy re-order so the shortlist isn't six of the same thing: at most N per main ingredient and no
    near-identical variants. Only the top N is re-ordered; everything else keeps its score order below it."""
    cap, sim, n = cfg["variety"]["max_per_main"], cfg["learning"]["similar"], cfg["top_n"]
    top, count = [], {}
    for it in ranked:
        if len(top) == n:
            break
        if it["main"] != "Other" and count.get(it["main"], 0) >= cap:
            continue
        if any(similarity(it["name"], o["name"]) >= sim for o in top):
            continue
        top.append(it)
        count[it["main"]] = count.get(it["main"], 0) + 1
    chosen = {id(i) for i in top}
    return top + [i for i in ranked if id(i) not in chosen]


def personalise(items, profile, history, menu_start, cfg, variety=True):
    """Final ranking the page would show with no votes or manual settings: base + capped tag bonus + repeat bonus."""
    lc = cfg["learning"]
    for it in items:
        it["tag_bonus"] = tag_bonus(it, profile, lc)
        it["repeat_bonus"] = round(repeat_bonus(it["name"], history, menu_start, lc), 1)
        it["final"] = round(it["score"] + it["tag_bonus"] + it["repeat_bonus"], 1)
        it["why"] = explain(it, cfg["weights"])
    ranked = sorted(items, key=lambda i: i["final"], reverse=True)
    return vary(ranked, cfg) if variety else ranked


def rank(recipes, cfg):
    """Base ranking only (no personal history). Kept for callers that just want the menu scored."""
    return sorted(menu_items(recipes, cfg), key=lambda i: i["score"], reverse=True)


def explain(it, w):
    parts = it["components"]
    text = {
        "rating": f"rated {it['rating']}/5 by {it['rating_count']:,} cooks",
        "protein": f"{it['protein_g']}g protein",
        "calories": f"light at {it['calories']} kcal",
        "time": f"ready in {it['cook_time']} min",
    }
    lead = []
    if it.get("repeat_bonus", 0) > 0:
        lead.append("you've picked this before")
    if it.get("tag_bonus", 0) >= 8:
        lead.append("like your usual picks")
    top = sorted((k for k in parts if w.get(k)), key=lambda k: parts[k] * w[k], reverse=True)[:3]
    rest = [text[k] for k in top if parts[k] >= 0.5 and not (k == "calories" and it["calories"] > 600)]
    return "; ".join(lead + rest).capitalize() or "Balanced all-rounder"
