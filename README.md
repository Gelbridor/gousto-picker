# gousto-picker

Fetches this week's Gousto menu, drops vegan and premium-surcharge recipes, ranks the rest and shows a top 8 on a phone-friendly page.

- `python -m picker` – fetch (JSON feed `production-api.gousto.co.uk/menu/v3/menus`, Playwright fallback), rank, write `docs/data/shortlist.json`.
- `config.json` – ranking weights (rating / protein / calories / time) and learning settings. The page also has sliders.
- `python tools/backtest.py [--sweep]` – re-scores each past week's real menu using only the picks made before it and reports where your actual picks landed. Run it after changing `config.json` or the scoring.

## How recipes are scored

1. **Base score (0–100):** a weighted mix of Bayesian rating, protein, calories and cook time. Each part is a percentile against that week's eligible recipes, so one extreme recipe can't squash the rest.
2. **Tag bonus (up to ±20 in total):** how much more often you pick a main ingredient, cuisine or dish type than the menu you picked from offered it, plus small nudges from thumbs.
3. **Picked before (up to +35):** the same recipe, or a close variant, fading with a 6-month half-life.
4. **Votes:** each thumbs up adds 10. A thumbs down from anyone hides the recipe.
5. **Mix it up (on by default):** at most 2 of one main ingredient, and no near-identical variants, in the top 8.

"Use history" on the Preferences tab scales parts 2 and 3.

Double-protein swaps are hidden. Lean mince swaps are hidden when that week has the standard recipe with the same meat, but kept when they're the only way to get that meat (e.g. lean beef where the standard is pork & beef). Turn this off under Preferences > Limits.
- `.github/workflows/weekly.yml` – runs every Tuesday and publishes `docs/` to GitHub Pages (no PC needed).
  One-off setup: repo Settings → Pages → Source: **GitHub Actions**.

## Syncing preferences and votes between devices

The page can save preferences and votes to your own free Supabase database so every device shares them.

1. Create a project at supabase.com (free tier).
2. SQL Editor > New query > paste `supabase/setup.sql` > Run.
3. Project Settings > API: copy the Project URL and the Publishable key (never the secret key).
4. Open the site > Preferences > Sync between devices. Enter your name, open "First device", paste the URL and key, then Connect.
5. Copy the sync link shown and open it once on your PC and your wife's phone, entering their name there.

The table cannot be read directly. All access goes through three functions that require the secret code inside the link.
