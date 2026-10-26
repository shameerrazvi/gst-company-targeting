"""Market size, new-company trends, GST timing, sectors, regions and target segments."""
import numpy as np
import pandas as pd

from . import config as cfg
from .industry import UNCLASSIFIED


def active(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["abn_status"] == "ACT"]


def started_between(df: pd.DataFrame, start, end) -> pd.DataFrame:
    """Active companies whose ABN became active between two dates (inclusive)."""
    a = active(df)
    return a[(a["abn_status_from"] >= start) & (a["abn_status_from"] <= end)]


def is_lead(df: pd.DataFrame) -> pd.Series:
    """A target lead: an operating company (not a holding, trustee or numbered company)
    that is registered for GST, so it lodges BAS and needs bookkeeping, payroll and tax help."""
    return (df["operating"] == 1) & (df["gst_status"] == "ACT")


def market_summary(df: pd.DataFrame) -> pd.DataFrame:
    a = active(df)
    recent = started_between(df, cfg.RECENT_START, cfg.RECENT_END)
    prior = started_between(df, cfg.PRIOR_START, cfg.PRIOR_END)
    out = pd.DataFrame({
        "active_companies": a.groupby("state").size(),
        "gst_registered_pct": a.groupby("state")["gst_status"].apply(lambda s: (s == "ACT").mean() * 100),
        "new_last_12m": recent.groupby("state").size(),
        "new_prior_12m": prior.groupby("state").size(),
        "leads_last_12m": recent[is_lead(recent)].groupby("state").size(),
    }).reindex(cfg.STATES)
    out["growth_pct"] = (out["new_last_12m"] / out["new_prior_12m"] - 1) * 100
    out["new_per_100_active"] = out["new_last_12m"] / out["active_companies"] * 100
    total = pd.DataFrame({
        "active_companies": [len(a)], "gst_registered_pct": [(a["gst_status"] == "ACT").mean() * 100],
        "new_last_12m": [len(recent)], "new_prior_12m": [len(prior)],
        "leads_last_12m": [int(is_lead(recent).sum())],
        "growth_pct": [(len(recent) / len(prior) - 1) * 100],
        "new_per_100_active": [len(recent) / len(a) * 100]}, index=["Australia"])
    return pd.concat([out, total]).rename_axis("state").reset_index()


def monthly_new(df: pd.DataFrame, start="2023-01-01", end=cfg.RECENT_END) -> pd.DataFrame:
    """New companies (still active) by the month their ABN started, and how many of them
    are registered for GST."""
    a = started_between(df, pd.Timestamp(start), end)
    out = (a.assign(month=a["abn_status_from"].dt.to_period("M").dt.to_timestamp(),
                    gst=a["gst_status"].eq("ACT"))
            .groupby("month").agg(new_companies=("gst", "size"), gst_registered=("gst", "sum")))
    return out.reset_index()


def yearly_flow(df: pd.DataFrame, start=2015, end=2025) -> pd.DataFrame:
    """Companies started each year that are still active, and ABNs cancelled each year."""
    a = active(df)
    c = df[df["abn_status"] == "CAN"]
    out = pd.DataFrame({"started_still_active": a.groupby(a["abn_status_from"].dt.year).size(),
                        "cancelled": c.groupby(c["abn_status_from"].dt.year).size()})
    return out.loc[start:end].rename_axis("year").reset_index()


def seasonality(monthly: pd.DataFrame) -> pd.DataFrame:
    """Each calendar month's share of a year's new companies, averaged over full years."""
    m = monthly.copy()
    m["year"], m["month_no"] = m["month"].dt.year, m["month"].dt.month
    full = m.groupby("year")["month_no"].transform("count") == 12
    m = m[full]
    m["share"] = m["new_companies"] / m.groupby("year")["new_companies"].transform("sum")
    out = m.groupby("month_no")["share"].mean().mul(100).rename("share_of_year_pct").reset_index()
    out["vs_average_month_pct"] = (out["share_of_year_pct"] / (100 / 12) - 1) * 100
    return out


def gst_timing(df: pd.DataFrame, start="2023-01-01", end="2025-09-30") -> tuple[pd.DataFrame, dict]:
    """Days from a company's ABN start to its GST registration date, for companies started in
    a window that have had at least 12 months to register."""
    c = started_between(df, pd.Timestamp(start), pd.Timestamp(end))
    g = c[c["gst_status"] == "ACT"]
    days = (g["gst_status_from"] - g["abn_status_from"]).dt.days
    points = [0, 7, 30, 60, 90, 180, 365]
    curve = pd.DataFrame({"days_after_abn": points,
                          "share_of_gst_registered_pct": [(days <= d).mean() * 100 for d in points]})
    stats = {"companies": len(c), "gst_registered": len(g),
             "gst_registered_pct": len(g) / len(c) * 100,
             "same_day_pct": (days == 0).mean() * 100,
             "within_30_days_pct": (days <= 30).mean() * 100,
             "within_90_days_pct": (days <= 90).mean() * 100,
             "backdated_before_abn_pct": (days < 0).mean() * 100}
    return curve, stats


def gst_by_age(df: pd.DataFrame, months=12) -> pd.DataFrame:
    """Share of companies registered for GST by how many months old they are at the snapshot."""
    a = started_between(df, cfg.SNAPSHOT - pd.DateOffset(months=months), cfg.SNAPSHOT)
    age = ((cfg.SNAPSHOT - a["abn_status_from"]).dt.days // 30).clip(upper=months - 1)
    out = a.groupby(age)["gst_status"].agg(companies="size", gst_pct=lambda s: (s == "ACT").mean() * 100)
    return out.rename_axis("age_months").reset_index()


def sector_summary(df: pd.DataFrame) -> pd.DataFrame:
    a = active(df)
    recent = started_between(df, cfg.RECENT_START, cfg.RECENT_END)
    prior = started_between(df, cfg.PRIOR_START, cfg.PRIOR_END)
    out = pd.DataFrame({
        "active_companies": a.groupby("sector").size(),
        "gst_registered_pct": a.groupby("sector")["gst_status"].apply(lambda s: (s == "ACT").mean() * 100),
        "new_last_12m": recent.groupby("sector").size(),
        "new_prior_12m": prior.groupby("sector").size()}).fillna(0)
    out["growth_pct"] = (out["new_last_12m"] / out["new_prior_12m"] - 1) * 100
    out["share_of_active_pct"] = out["active_companies"] / out["active_companies"].sum() * 100
    return out.sort_values("new_last_12m", ascending=False).rename_axis("sector").reset_index()


def region_summary(df: pd.DataFrame, state=cfg.FOCUS_STATE) -> pd.DataFrame:
    a = active(df)
    a = a[a["state"] == state]
    recent = started_between(df, cfg.RECENT_START, cfg.RECENT_END)
    prior = started_between(df, cfg.PRIOR_START, cfg.PRIOR_END)
    recent, prior = recent[recent["state"] == state], prior[prior["state"] == state]
    out = pd.DataFrame({
        "active_companies": a.groupby("sa4").size(),
        "new_last_12m": recent.groupby("sa4").size(),
        "new_prior_12m": prior.groupby("sa4").size(),
        "leads_last_12m": recent[is_lead(recent)].groupby("sa4").size()}).fillna(0)
    out = out.drop(index="Unmatched", errors="ignore")
    out["growth_pct"] = (out["new_last_12m"] / out["new_prior_12m"] - 1) * 100
    out["new_per_100_active"] = out["new_last_12m"] / out["active_companies"] * 100
    return out.sort_values("new_last_12m", ascending=False).rename_axis("sa4").reset_index()


def segments(df: pd.DataFrame, state=cfg.FOCUS_STATE, min_size=cfg.MIN_SEGMENT_SIZE) -> pd.DataFrame:
    """Region x industry segments of new leads, placed on a size-growth grid.

    Only classified industries are used: an unclassified company can't be offered an
    industry-specific message. Segments with fewer than `min_size` new leads are dropped,
    because growth on small counts is mostly noise."""
    recent = started_between(df, cfg.RECENT_START, cfg.RECENT_END)
    prior = started_between(df, cfg.PRIOR_START, cfg.PRIOR_END)
    keys = ["sa4", "sector"]

    def leads(x):
        x = x[(x["state"] == state) & is_lead(x) & (x["sector"] != UNCLASSIFIED) & (x["sa4"] != "Unmatched")]
        return x.groupby(keys).size()

    out = pd.DataFrame({"new_leads": leads(recent), "prior_leads": leads(prior)}).fillna(0)
    out = out[out["new_leads"] >= min_size].copy()
    out["growth_pct"] = (out["new_leads"] / out["prior_leads"].replace(0, np.nan) - 1) * 100
    size_cut, growth_cut = out["new_leads"].median(), out["growth_pct"].median()
    big, fast = out["new_leads"] >= size_cut, out["growth_pct"] >= growth_cut
    out["quadrant"] = np.select([big & fast, big & ~fast, ~big & fast],
                                ["Priority: large and growing", "Core: large, steady",
                                 "Emerging: small, growing"], "Monitor: small, steady")
    order = {"Priority: large and growing": 0, "Core: large, steady": 1, "Emerging: small, growing": 2,
             "Monitor: small, steady": 3}
    out = (out.reset_index().assign(q=lambda x: x["quadrant"].map(order))
              .sort_values(["q", "new_leads", "sa4", "sector"], ascending=[True, False, True, True])
              .drop(columns="q")
              .reset_index(drop=True))
    out.insert(0, "rank", range(1, len(out) + 1))
    out.attrs.update(size_cut=float(size_cut), growth_cut=float(growth_cut))
    return out


def headline(df: pd.DataFrame) -> dict:
    a = active(df)
    recent = started_between(df, cfg.RECENT_START, cfg.RECENT_END)
    prior = started_between(df, cfg.PRIOR_START, cfg.PRIOR_END)
    vic = recent[recent["state"] == cfg.FOCUS_STATE]
    return {
        "snapshot": str(cfg.SNAPSHOT.date()),
        "records_in_extract": int(len(df)),
        "active_companies": int(len(a)),
        "gst_registered_pct": round(float((a["gst_status"] == "ACT").mean() * 100), 1),
        "holding_trustee_numbered_pct": round(float((1 - a["operating"].mean()) * 100), 1),
        "unclassified_pct": round(float((a["sector"] == UNCLASSIFIED).mean() * 100), 1),
        "new_last_12m": int(len(recent)),
        "new_prior_12m": int(len(prior)),
        "growth_pct": round(float((len(recent) / len(prior) - 1) * 100), 1),
        "leads_last_12m": int(is_lead(recent).sum()),
        "vic_new_last_12m": int(len(vic)),
        "vic_leads_last_12m": int(is_lead(vic).sum()),
    }
