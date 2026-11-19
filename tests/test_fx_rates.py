"""Tests that simulate each failure the pipeline is built to catch, without calling the real API."""

import logging
import sqlite3
from datetime import date
from unittest.mock import MagicMock, patch

import requests

import fx_rates

GOOD_RESPONSE = {
    "amount": 1.0,
    "base": "USD",
    "date": "2026-11-18",
    "rates": {"EUR": 0.9, "GBP": 0.8, "JPY": 150.0, "CAD": 1.4},
}


def mock_response(json_data=None, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status_code} Error")
    return response


# --- fetch_rates ---------------------------------------------------------

def test_fetch_success():
    with patch("fx_rates.requests.get", return_value=mock_response(GOOD_RESPONSE)):
        assert fx_rates.fetch_rates() == GOOD_RESPONSE


def test_fetch_timeout_is_logged(caplog):
    with patch("fx_rates.requests.get", side_effect=requests.exceptions.Timeout):
        assert fx_rates.fetch_rates() is None
    assert "Timeout" in caplog.text


def test_fetch_connection_error_is_logged(caplog):
    with patch("fx_rates.requests.get", side_effect=requests.exceptions.ConnectionError):
        assert fx_rates.fetch_rates() is None
    assert "Connection error" in caplog.text


def test_fetch_http_error_is_logged(caplog):
    with patch("fx_rates.requests.get", return_value=mock_response(status_code=404)):
        assert fx_rates.fetch_rates() is None
    assert "HTTP error 404" in caplog.text


def test_fetch_invalid_json_is_logged(caplog):
    response = mock_response()
    response.json.side_effect = ValueError
    with patch("fx_rates.requests.get", return_value=response):
        assert fx_rates.fetch_rates() is None
    assert "Invalid response" in caplog.text


# --- validate ------------------------------------------------------------

def test_validate_clean_data_logs_no_warnings(caplog):
    caplog.set_level(logging.WARNING)
    rates, data_date = fx_rates.validate(GOOD_RESPONSE, today=date(2026, 11, 19))
    assert rates == GOOD_RESPONSE["rates"]
    assert data_date == date(2026, 11, 18)
    assert caplog.text == ""


def test_validate_flags_missing_currency(caplog):
    data = {"date": "2026-11-18", "rates": {"EUR": 0.9}}
    fx_rates.validate(data, today=date(2026, 11, 19))
    assert "Missing rates for: GBP, JPY, CAD" in caplog.text


def test_validate_flags_stale_data(caplog):
    fx_rates.validate(GOOD_RESPONSE, today=date(2026, 11, 30))
    assert "Stale data" in caplog.text


def test_validate_weekend_gap_is_not_stale(caplog):
    caplog.set_level(logging.WARNING)
    # Friday's rates checked on Monday: 3 days old, which is normal
    data = dict(GOOD_RESPONSE, date="2026-11-13")
    fx_rates.validate(data, today=date(2026, 11, 16))
    assert "Stale" not in caplog.text


# --- save ----------------------------------------------------------------

def test_save_writes_rates(tmp_path):
    db = tmp_path / "test.db"
    fx_rates.save(GOOD_RESPONSE["rates"], date(2026, 11, 18), db_file=db)
    rows = sqlite3.connect(db).execute("SELECT COUNT(*) FROM rates").fetchone()
    assert rows[0] == 4


def test_save_twice_does_not_duplicate(tmp_path):
    db = tmp_path / "test.db"
    fx_rates.save(GOOD_RESPONSE["rates"], date(2026, 11, 18), db_file=db)
    fx_rates.save(GOOD_RESPONSE["rates"], date(2026, 11, 18), db_file=db)
    rows = sqlite3.connect(db).execute("SELECT COUNT(*) FROM rates").fetchone()
    assert rows[0] == 4
