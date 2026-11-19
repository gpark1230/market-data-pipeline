"""Market Data Pipeline: pull daily USD exchange rates, validate them, store them in SQLite.

Data source: Frankfurter API (https://www.frankfurter.app), a free REST API
that publishes reference exchange rates. No API key required.
"""

import logging
import sqlite3
from datetime import date, datetime

import requests

API_URL = "https://api.frankfurter.app/latest"
BASE_CURRENCY = "USD"
CURRENCIES = ["EUR", "GBP", "JPY", "CAD"]
DB_FILE = "fx_rates.db"
LOG_FILE = "fx_rates.log"
TIMEOUT_SECONDS = 10
STALE_AFTER_DAYS = 3  # markets close on weekends and holidays, so 1-2 days old is normal

logger = logging.getLogger("fx_rates")


def setup_logging(log_file=LOG_FILE):
    """Send log messages to a file, with a timestamp and severity level."""
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def fetch_rates(currencies=CURRENCIES):
    """Call the API and return the JSON response, or None if the request failed."""
    params = {"from": BASE_CURRENCY, "to": ",".join(currencies)}
    try:
        response = requests.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("Timeout: the API did not respond within %s seconds", TIMEOUT_SECONDS)
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Connection error: check network, DNS, or firewall")
        return None
    except requests.exceptions.HTTPError as err:
        logger.error("HTTP error %s: %s", response.status_code, err)
        return None

    try:
        return response.json()
    except ValueError:
        logger.error("Invalid response: the API did not return valid JSON")
        return None


def validate(data, currencies=CURRENCIES, today=None):
    """Check for missing currencies and stale data. Returns (rates, data_date)."""
    today = today or date.today()
    rates = data.get("rates", {})

    missing = [c for c in currencies if c not in rates]
    if missing:
        logger.warning("Missing rates for: %s", ", ".join(missing))

    data_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
    days_old = (today - data_date).days
    if days_old > STALE_AFTER_DAYS:
        logger.warning("Stale data: rates are from %s, %s days old", data_date, days_old)

    return rates, data_date


def save(rates, data_date, db_file=DB_FILE):
    """Store rates in SQLite. Running twice on the same day updates instead of duplicating."""
    conn = sqlite3.connect(db_file)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rates (
               rate_date TEXT,
               currency  TEXT,
               rate      REAL,
               PRIMARY KEY (rate_date, currency)
           )"""
    )
    for currency, rate in rates.items():
        conn.execute(
            "INSERT OR REPLACE INTO rates VALUES (?, ?, ?)",
            (str(data_date), currency, rate),
        )
    conn.commit()
    conn.close()
    logger.info("Saved %s rates for %s", len(rates), data_date)


def main():
    setup_logging()
    data = fetch_rates()
    if data is None:
        print(f"Failed to fetch rates. See {LOG_FILE} for details.")
        return 1

    rates, data_date = validate(data)
    save(rates, data_date)
    print(f"{BASE_CURRENCY} rates for {data_date}:")
    for currency, rate in rates.items():
        print(f"  {currency}: {rate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
