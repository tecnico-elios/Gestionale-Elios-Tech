"""Regressioni /api/movimenti con filtro mensile sul gestionale locale."""
import requests
import pytest
from datetime import date

from conftest import BASE_URL, _ensure_admin_token, _ensure_op_token


def _op_hdr():
    admin_tok, _ = _ensure_admin_token()
    tok, _ = _ensure_op_token(admin_tok)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update(_op_hdr())
    return s


def _current_month():
    d = date.today()
    return f"{d.year:04d}-{d.month:02d}"


def test_movimenti_default_no_month(api):
    r = api.get(f"{BASE_URL}/api/movimenti", timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert "items" in j and "count" in j
    assert j.get("month") is None
    assert j.get("date_from") is None
    assert j.get("date_to") is None


def test_movimenti_month_current(api):
    m = _current_month()
    r = api.get(f"{BASE_URL}/api/movimenti", params={"month": m}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert j["month"] == m
    assert j["date_from"] == f"{m}-01"
    from calendar import monthrange
    y, mm = int(m.split("-")[0]), int(m.split("-")[1])
    last = monthrange(y, mm)[1]
    assert j["date_to"] == f"{m}-{last:02d}"
    for it in j["items"]:
        d = it.get("date")
        if d:
            assert d[:7] == m, f"item date {d} fuori mese {m}"


def test_movimenti_month_past(api):
    r = api.get(f"{BASE_URL}/api/movimenti", params={"month": "2020-01"}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert j["month"] == "2020-01"
    for it in j["items"]:
        d = it.get("date")
        if d:
            assert d[:7] == "2020-01"


def test_movimenti_month_invalid_format(api):
    r = api.get(f"{BASE_URL}/api/movimenti", params={"month": "not-a-date"}, timeout=30)
    assert r.status_code == 400
    r = api.get(f"{BASE_URL}/api/movimenti", params={"month": "2026-13"}, timeout=30)
    assert r.status_code == 400


def test_movimenti_sorted_desc(api):
    r = api.get(f"{BASE_URL}/api/movimenti", timeout=30)
    assert r.status_code == 200, r.text[:200]
    dates = [it.get("date") for it in r.json()["items"] if it.get("date")]
    assert dates == sorted(dates, reverse=True), "movimenti non ordinati desc"
