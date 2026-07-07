# parser_app

Three independent web scrapers for product data from
[brain.com.ua](https://brain.com.ua), each built on a different technology
stack and all storing their results into the same **Django + PostgreSQL**
database.

## Overview

Every scraper collects the same product fields and saves them into a shared
`Product` model, then `pprint`s the assembled data dictionary.

| # | Scraper | Stack | Entry flow |
|---|---------|-------|------------|
| 1 | `modules/1_parse_product_Requests_BS4.py` | Requests + BeautifulSoup4 | Opens a fixed product URL and parses the static HTML |
| 2 | `modules/2_selenium_parse.py`  | Selenium (headless Chrome) | Homepage → search → Find → first result → product page |
| 3 | `modules/3_playwright_parse.py` | Playwright (headless Chromium) | Same search-driven flow as Selenium |

Scrapers 2 and 3 search for `Apple iPhone 15 128GB Black`, open the first
result, and expand the **All specifications** tab before parsing.

## Collected fields

- Full product title
- Color
- Memory / storage capacity
- Manufacturer
- Regular price
- Promotional price (if present)
- All product photo URLs (list)
- Product code
- Number of reviews
- Screen diagonal
- Display resolution
- Full specifications from the specs tab (dictionary)

## Tech stack

- Python 3.12 (virtualenv in `.venv/`)
- Django 5.0 + PostgreSQL 12 (via `psycopg`)
- requests, beautifulsoup4, lxml
- selenium 4 (Selenium Manager auto-provisions chromedriver)
- playwright 1.61 (Chromium)

## Project structure

```
parser_app/
  braincomua_project/            # Django project (manage.py here)
    braincomua_project/
      settings.py                # Postgres via .env, 'parser_app' registered
    parser_app/                  # Django app
      models.py                  # Product model (all target fields)
  modules/                       # all scraper scripts
    load_django.py               # Django bootstrap for external scripts
    1_parse_product_Requests_BS4.py  # Requests / BS4
    2_selenium_parse.py          # Selenium
    3_playwright_parse.py        # Playwright
  results/                       # parsed output (CSV + DB dump)
  requirements.txt
```

Selector rules: BS4 matches by class/attribute; Selenium and Playwright locate
everything via manually chosen XPath (never positional indexes) — values are
read from their labelled element.

## Setup

```bash
# 1. Create the virtualenv and install dependencies
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# 2. Install the Playwright browser binary (Stage 3 only)
./.venv/bin/playwright install chromium

# 3. Configure the database credentials in a git-ignored .env file
#    DB_NAME=<your_db_name>
#    DB_USER=<your_db_user>
#    DB_PASSWORD=<your_db_password>
#    DB_HOST=localhost
#    DB_PORT=5432

# 4. Apply migrations
cd braincomua_project && ../.venv/bin/python manage.py migrate
```

## Running the scrapers

```bash
cd modules && ../.venv/bin/python 1_parse_product_Requests_BS4.py   # Requests / BS4
cd modules && ../.venv/bin/python 2_selenium_parse.py    # Selenium
cd modules && ../.venv/bin/python 3_playwright_parse.py  # Playwright
```

Each run prints the collected data and upserts one row into the database, keyed
on `product_code` (rerunning updates the same row instead of duplicating it).

## Exporting results

```bash
# Provide the DB password via the environment (do not hardcode it)
export PGPASSWORD=<your_db_password>


# Full SQL dump
/Library/PostgreSQL/12/bin/pg_dump -h localhost -U <your_db_user> -d <your_db_name> \
  > results/brain_db_dump.sql
  
  
  # Flat CSV of the products table
/Library/PostgreSQL/12/bin/psql -h localhost -U <your_db_user> -d <your_db_name> \
  -c "\copy (SELECT * FROM parser_app_product ORDER BY product_code) \
      TO 'results/products.csv' WITH CSV HEADER"
```
