"""Tests for extraction, industry rules, cleaning and the segment logic, plus checks that
the SQL and pandas versions give the same answers on the real data."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import analysis, config as cfg, extract, industry, prepare, sql_queries

HERE = Path(__file__).parent


# ---------- extraction ----------
def test_extract_keeps_only_private_companies():
    with open(HERE / "sample_extract.xml", "rb") as fh:
        rows = list(extract.parse_stream(fh))
    assert [r["abn"] for r in rows] == ["11111111111", "33333333333"]      # the sole trader is dropped


def test_extract_reads_every_field():
    with open(HERE / "sample_extract.xml", "rb") as fh:
        first, second = list(extract.parse_stream(fh))
    assert first["name"] == "EXAMPLE PLUMBING PTY LTD"
    assert (first["state"], first["postcode"]) == ("VIC", "3064")
    assert (first["gst_status"], first["gst_status_from"]) == ("ACT", "20240201")
    assert first["business_names"] == "Example Plumbing"                  # OTN names are ignored
    assert second["abn_status"] == "CAN" and second["dgr"] == 1


# ---------- industry rules ----------
@pytest.mark.parametrize("name, business, expected", [
    ("SMITH PLUMBING PTY LTD", "", "Construction and trades"),
    ("SMITH FAMILY HOLDINGS PTY LTD", "Smith Plumbing", "Construction and trades"),   # trading name wins
    ("SMITH FAMILY HOLDINGS PTY LTD", "", "Holding, investment or trustee"),
    ("XYZ PROPERTY HOLDINGS PTY LTD", "", "Holding, investment or trustee"),          # holding beats property
    ("ACN 123456789 PTY LTD", "", "Numbered company"),
    ("BLAFIN PTY LTD", "", "Unclassified"),
    ("QUEENSLAND TRADERS PTY LTD", "", "Retail and wholesale"),
    ("ISLAND CAFE PTY LTD", "", "Food and hospitality"),                              # LAND inside ISLAND ignored
    ("JONES CONSULTING PTY LTD", "", "Professional services"),
])
def test_industry_rules(name, business, expected):
    assert industry.classify_one(name, business) == expected


# ---------- cleaning ----------
def _raw(**overrides):
    row = {"abn": "1", "abn_status": "ACT", "abn_status_from": "20250101", "record_updated": "20250101",
           "name": "TEST PLUMBING PTY LTD", "state": "VIC", "postcode": "3000", "acn": "1",
           "gst_status": "ACT", "gst_status_from": "20250101", "dgr": "0", "n_business_names": "0",
           "business_names": ""}
    row.update(overrides)
    return row


POSTCODES = pd.DataFrame({"sa4": ["Melbourne - Inner"], "sa3": ["Melbourne City"], "pc_state": ["VIC"]},
                         index=pd.Index(["3000"], name="postcode"))


def test_clean_handles_dates_states_and_regions():
    raw = pd.DataFrame([
        _raw(),
        _raw(gst_status="NON", gst_status_from="19000101"),     # no GST: the 1900 date is a placeholder
        _raw(abn_status_from="20271201"),                        # future-dated: removed
        _raw(state="NSW"),                                       # postcode doesn't belong to NSW
        _raw(state="", postcode="0000"),
    ])
    df, log = prepare.clean(raw, POSTCODES)
    assert log["future_dated_removed"] == 1 and len(df) == 4
    assert pd.isna(df.loc[1, "gst_status_from"])
    assert df["sa4"].tolist() == ["Melbourne - Inner", "Melbourne - Inner", "Unmatched", "Unmatched"]
    assert df.loc[3, "state"] == "Unknown"
    assert df["sector"].iloc[0] == "Construction and trades" and df["operating"].iloc[0] == 1


# ---------- segment logic ----------
def test_segments_quadrants_and_minimum_size(monkeypatch):
    monkeypatch.setattr(cfg, "MIN_SEGMENT_SIZE", 2)
    rows = []

    def add(n, date, sa4, sector):
        rows.extend([{"abn_status": "ACT", "abn_status_from": pd.Timestamp(date), "state": "VIC", "sa4": sa4,
                      "sector": sector, "operating": 1, "gst_status": "ACT"}] * n)
    # recent window vs prior window
    add(10, "2026-03-01", "A", "Construction and trades"); add(5, "2025-03-01", "A", "Construction and trades")
    add(10, "2026-03-01", "B", "Construction and trades"); add(10, "2025-03-01", "B", "Construction and trades")
    add(3, "2026-03-01", "C", "Construction and trades"); add(1, "2025-03-01", "C", "Construction and trades")
    add(3, "2026-03-01", "D", "Construction and trades"); add(3, "2025-03-01", "D", "Construction and trades")
    add(1, "2026-03-01", "E", "Construction and trades")                                 # too small
    seg = analysis.segments(pd.DataFrame(rows), min_size=2).set_index("sa4")
    assert "E" not in seg.index
    assert seg.loc["A", "quadrant"].startswith("Priority") and seg.loc["B", "quadrant"].startswith("Core")
    assert seg.loc["C", "quadrant"].startswith("Emerging") and seg.loc["D", "quadrant"].startswith("Monitor")
    assert seg.loc["A", "growth_pct"] == pytest.approx(100.0)


# ---------- checks on the real processed data ----------
@pytest.fixture(scope="module")
def real():
    return prepare.read_processed()


def test_real_data_size_and_snapshot(real):
    active = analysis.active(real)
    assert len(real) > 4_000_000 and 2_100_000 < len(active) < 2_300_000
    assert real["abn_status_from"].max() <= cfg.SNAPSHOT
    assert set(real["state"]) <= set(cfg.STATES) | {"Unknown"}


def test_sql_matches_pandas_market_by_state(real):
    sql = sql_queries.run("01_market_by_state").set_index("state")
    py = analysis.market_summary(real).set_index("state").loc[sql.index]
    for col in ["active_companies", "new_last_12m", "new_prior_12m", "leads_last_12m"]:
        assert (sql[col].astype(int) == py[col].astype(int)).all(), col
    assert np.allclose(sql["gst_registered_pct"], py["gst_registered_pct"])


def test_sql_matches_pandas_monthly_and_gst_timing(real):
    sql_m = sql_queries.run("02_monthly_new")
    py_m = analysis.monthly_new(real)
    assert sql_m["new_companies"].tolist() == py_m["new_companies"].tolist()
    sql_t = sql_queries.run("03_gst_timing")
    py_t, _ = analysis.gst_timing(real)
    assert np.allclose(sql_t["share_of_gst_registered_pct"], py_t["share_of_gst_registered_pct"])


def test_sql_matches_pandas_segments(real):
    sql = sql_queries.run("04_vic_segments")
    py = analysis.segments(real)
    assert sql[["sa4", "sector", "quadrant"]].values.tolist() == py[["sa4", "sector", "quadrant"]].values.tolist()
    assert (sql["new_leads"].astype(int) == py["new_leads"].astype(int)).all()
