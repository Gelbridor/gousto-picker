# gousto-picker

Fetches this week's Gousto menu, drops vegan and premium-surcharge recipes, ranks the rest and shows a top 8 on a phone-friendly page.

- `python -m picker` – fetch (JSON feed `production-api.gousto.co.uk/menu/v3/menus`, Playwright fallback), rank, write `docs/data/shortlist.json`.
- `config.json` – ranking weights (rating / protein / calories / time). The page also has sliders.
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
