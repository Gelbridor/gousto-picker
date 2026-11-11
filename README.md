# gousto-picker

Fetches this week's Gousto menu, drops vegan and premium-surcharge recipes, ranks the rest and shows a top 8 on a phone-friendly page.

- `python -m picker` – fetch (JSON feed `production-api.gousto.co.uk/menu/v3/menus`, Playwright fallback), rank, write `docs/data/shortlist.json`.
- `config.json` – ranking weights (rating / protein / calories / time). The page also has sliders.
- `.github/workflows/weekly.yml` – runs every Tuesday and publishes `docs/` to GitHub Pages (no PC needed).
  One-off setup: repo Settings → Pages → Source: **GitHub Actions**.
