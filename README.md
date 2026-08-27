# Basket Check

A local Flask dashboard for building grocery lists and comparing NZ shop prices.

## Current scope

- Create named shopping lists.
- Add products and quantities.
- Manually record prices for Vegiking, which has no website.
- Manually trigger price checks for Pak'nSave, Woolworths NZ, and 4 Square.
- Store the last check in SQLite.

Retailer pages and anti-bot protections change over time. The scraper currently looks for schema.org JSON-LD offers and is intentionally conservative when a price cannot be verified. Before relying on live data, tune and test each retailer adapter and respect its terms, robots.txt, and rate limits.

## Run locally

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

## Project structure

- `app.py` - Flask routes and SQLite persistence.
- `scraper.py` - retailer search requests and structured-price parsing.
- `templates/` - dashboard views.
- `static/` - dashboard styling.

# To do:
- Check legality of scraping target sites.
- Install requirements.
