# Basket Check

A personal, local-first grocery list and price comparison app for New Zealand
retailers.

## What works

- Create and delete shopping lists.
- Add and remove products, set quantities, and enter or clear manual Vegiking
  prices.
- Check Pak’nSave and Woolworths product sitemaps and product pages for
  structured NZD offers.
- The lookup checks each retailer’s current `robots.txt` before requesting a
  sitemap or product page, uses a descriptive user agent, and spaces requests.
- Save and revisit comparison history. Results include status, source links,
  and a basket total only when every required price is available.
- Show unavailable, blocked, and unsupported results instead of generating
  placeholder prices.

4 Square has no automated adapter yet. Its prices are reported as unsupported.
The retailer pages and their robots/terms can change; structured offers may be
absent, and a live lookup may return no price. Robots.txt is a crawler policy,
not legal permission: review each retailer’s current terms and use a permitted
official data source where available.

## Run locally

Python 3.10 or later is recommended.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The SQLite database is created as
`basket_check.db` in the project directory and is excluded from Git. Set
`SECRET_KEY` in the environment if you need Flask sessions to remain valid
across restarts.

## Tests

Run the app and scraper tests without making requests to retailers:

```sh
python -m unittest discover -v
```

## Project structure

- `app.py` - Flask application, list management, and SQLite persistence.
- `scraper.py` - robots.txt-aware sitemap discovery and schema.org offer
  parsing for Pak’nSave and Woolworths.
- `templates/` - list and comparison views.
- `static/` - dashboard styling.
- `tests/` - offline app and scraper tests.

The original retailer scripts and `Helper.py` are early standalone prototypes;
the web application uses `scraper.py` instead.
