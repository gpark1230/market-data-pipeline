# Market Data Pipeline

A small Python tool that pulls daily USD exchange rates from a REST API, validates the data, and stores it in a SQLite database, with logging built to pinpoint the root cause when something goes wrong.

I built it to practice the work behind enterprise data support: getting financial data out of an API and into a local system, catching problems in the data, and troubleshooting failures quickly.

## What it does

1. **Fetches** the latest USD exchange rates for EUR, GBP, JPY and CAD from the [Frankfurter API](https://www.frankfurter.app), a free REST API with no key required.
2. **Validates** the response:
   - flags any requested currency that is missing
   - flags stale data (rates more than 3 days old; weekends and holidays are expected gaps)
3. **Stores** the rates in `fx_rates.db` (SQLite), one row per currency per day. Running it twice on the same day updates the rows instead of duplicating them.
4. **Logs** every run to `fx_rates.log`, with a clear message for each type of failure.

```
Frankfurter REST API  -->  fetch_rates()  -->  validate()  -->  save()  -->  fx_rates.db
                               |                   |              |
                               +------------- fx_rates.log -------+
```

## Setup

Requires Python 3.9+.

```bash
git clone https://github.com/gpark1230/market-data-pipeline.git
cd market-data-pipeline
pip install -r requirements.txt
```

## Usage

```bash
python fx_rates.py
```
Example output from a live run:

```
USD rates for 2026-11-19:
CAD: 1.43
EUR: 0.90975
GBP: 0.76038
JPY: 159.97
```


Check the stored data:

```bash
sqlite3 fx_rates.db "SELECT * FROM rates ORDER BY rate_date DESC;"
```

## Tests

```bash
python -m pytest
```

The tests use mocked API responses, so they run without a network connection. They cover a successful run, every failure the script handles (timeout, connection error, HTTP error, invalid JSON), the data checks (missing currency, stale data, weekend gap) and the database (writes and no duplicates).

## Troubleshooting guide

Each entry follows the same format: what you see, what usually causes it, how to check, and how to fix it.

### "Connection error: check network, DNS, or firewall"

- **Symptom:** the script prints `Failed to fetch rates` and the log shows a connection error.
- **Likely cause:** no internet connection, DNS can't resolve `api.frankfurter.app`, or a firewall or proxy is blocking outbound HTTPS.
- **How to check:**
  - Open `https://api.frankfurter.app/latest` in a browser.
  - Run `nslookup api.frankfurter.app` to confirm DNS resolves.
  - Run `ping 8.8.8.8` to confirm basic connectivity.
- **Fix:** restore the network connection, fix DNS, or allow outbound HTTPS (port 443) to the API host.

### "Timeout: the API did not respond within 10 seconds"

- **Symptom:** the run hangs for about 10 seconds, then fails.
- **Likely cause:** the API is slow or temporarily down, or the network is congested.
- **How to check:** try the URL in a browser and see how long it takes to load.
- **Fix:** retry in a few minutes. If it keeps happening, raise `TIMEOUT_SECONDS` in `fx_rates.py`.

### "HTTP error 404" (or another 4xx/5xx code)

- **Symptom:** the log shows an HTTP error code.
- **Likely cause:**
  - **4xx (client error):** the request is wrong, for example a typo in `API_URL` or an invalid currency code in `CURRENCIES`.
  - **5xx (server error):** a problem on the API's side.
- **How to check:** confirm `API_URL` and each code in `CURRENCIES` (three-letter ISO codes such as `EUR`).
- **Fix:** correct the URL or currency code for 4xx errors. For 5xx errors, wait and retry.

### "Invalid response: the API did not return valid JSON"

- **Symptom:** the request succeeded but the data couldn't be read.
- **Likely cause:** the URL points to a web page instead of the API, or a proxy returned its own error page.
- **How to check:** open the URL in a browser; you should see JSON (text that starts with `{`).
- **Fix:** correct `API_URL`, or check proxy settings.

### "Missing rates for: ..."

- **Symptom:** the run succeeds but warns that some currencies are missing.
- **Likely cause:** the API doesn't publish that currency, or the code is misspelled.
- **How to check:** compare `CURRENCIES` against the API's list at `https://api.frankfurter.app/currencies`.
- **Fix:** correct or remove the currency code.

### "Stale data: rates are from ..."

- **Symptom:** the run succeeds, but the rates are more than 3 days old.
- **Likely cause:** a long holiday period, or the data source hasn't updated.
- **How to check:** look at the `date` field at `https://api.frankfurter.app/latest`.
- **Fix:** usually nothing; rates update on the next business day. If it lasts longer than a holiday would explain, the data source may have stopped publishing.

## Project structure

```
market-data-pipeline/
├── fx_rates.py          # fetch, validate, save
├── tests/
│   └── test_fx_rates.py # mocked tests for every success and failure path
├── requirements.txt
├── pytest.ini
└── README.md
```
