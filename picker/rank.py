"""Filter and rank recipes. Weights live in config.json so preferences are easy to change."""
import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config.json"


def load_config():
    return json.loads(CONFIG.read_text())


def _norm(value, lo, hi, invert=False):
    if hi == lo:
        return 0.5
    x = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    return 1 - x if invert else x


def usable(r):
    return bool(r.get("is_available", True)) and bool(r.get("nutritional_information"))


def simplify(r):
    n = r["nutritional_information"]["per_portion"]
    img = next((c["url"] for i in r.get("images", []) for c in i["crops"] if c["width"] == 400), None)
    rating = r.get("rating") or {}
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
        "image": img,
        "url": "https://www.gousto.co.uk/menu",
    }


def rank(recipes, cfg):
    w = cfg["weights"]
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

    def rng(key):
        vals = [i[key] for i in items if i[key] is not None]
        return min(vals), max(vals)

    ranges = {k: rng(k) for k in ("bayes_rating", "calories", "cook_time")}
    pr = [i["protein_g"] / max(i["calories"], 1) * 100 for i in items]
    pr_lo, pr_hi = min(pr), max(pr)

    for it, protein_density in zip(items, pr):
        parts = {
            "rating": _norm(it["bayes_rating"], *ranges["bayes_rating"]),
            "protein": _norm(protein_density, pr_lo, pr_hi),
            "calories": _norm(it["calories"], *ranges["calories"], invert=True),
            "time": _norm(it["cook_time"], *ranges["cook_time"], invert=True),
        }
        it["components"] = {k: round(v, 3) for k, v in parts.items()}
        it["score"] = round(sum(w[k] * parts[k] for k in parts) / sum(w.values()) * 100, 1)
        it["why"] = explain(it, parts, w)
    items.sort(key=lambda i: i["score"], reverse=True)
    return items


def explain(it, parts, w):
    text = {
        "rating": f"rated {it['rating']}/5 by {it['rating_count']:,} cooks",
        "protein": f"{it['protein_g']}g protein for {it['calories']} kcal",
        "calories": f"light at {it['calories']} kcal",
        "time": f"ready in {it['cook_time']} min",
    }
    top = sorted(parts, key=lambda k: parts[k] * w[k], reverse=True)[:3]
    return "; ".join(text[k] for k in top if parts[k] >= 0.5 and not (k == "calories" and it["calories"] > 600)).capitalize() or "Balanced all-rounder"
