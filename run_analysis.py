"""End-to-end: ABN Bulk Extract -> private companies -> analysis table -> results, SQL, charts.

Usage:
    python run_analysis.py              # use data/processed/companies.parquet (about 15 s)
    python run_analysis.py --rebuild    # re-read the ABN Bulk Extract zips in data/raw
"""
import argparse
import json
import time
import urllib.request

import pandas as pd

from src import analysis, charts, config as cfg, extract, prepare, sql_queries
from src.industry import PASSIVE, SECTORS, UNCLASSIFIED


def rebuild():
    if not cfg.POSTCODES.exists():
        print("Downloading the postcode reference file")
        cfg.POSTCODES.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(cfg.POSTCODES_URL, cfg.POSTCODES)
    if not cfg.RAW_EXTRACT.exists():
        print("Extracting private companies from the ABN Bulk Extract (about 2 minutes)")
        extract.extract(cfg.RAW_ZIPS, cfg.RAW_EXTRACT)
    print("Cleaning, classifying industries and adding regions (about 3 minutes)")
    print(" ", prepare.build())


CAPITAL_SA4 = (r"^(?:Sydney|Melbourne|Brisbane|Perth|Adelaide) - |^(?:Hobart|Darwin|Australian Capital Territory)$"
               r"|^(?:Mornington Peninsula|Central Coast|Ipswich|Logan - Beaudesert|Moreton Bay - North"
               r"|Moreton Bay - South)$")


def save_dims(df):
    """Small lookup tables for the Power BI model (see powerbi/README.md)."""
    cfg.POWERBI_DIR.mkdir(exist_ok=True)
    regions = df.loc[df["sa4"] != "Unmatched", ["state", "sa4"]].drop_duplicates().sort_values(["state", "sa4"])
    regions["greater_capital_city"] = regions["sa4"].str.contains(CAPITAL_SA4).astype(int)
    regions.to_csv(cfg.POWERBI_DIR / "dim_region.csv", index=False)
    sectors = pd.DataFrame({"sector": SECTORS})
    sectors["operating"] = (~sectors["sector"].isin(PASSIVE)).astype(int)
    sectors["classified"] = (sectors["sector"] != UNCLASSIFIED).astype(int)
    sectors.to_csv(cfg.POWERBI_DIR / "dim_sector.csv", index=False)


def main():
    parser = argparse.ArgumentParser(description="GST-registered company targeting analysis")
    parser.add_argument("--rebuild", action="store_true", help="rebuild data/processed from data/raw")
    args = parser.parse_args()
    start = time.perf_counter()
    if args.rebuild or not cfg.PROCESSED.exists():
        rebuild()

    print("Analysing")
    df = prepare.read_processed()
    out = cfg.OUTPUT_DIR
    out.mkdir(exist_ok=True)
    market = analysis.market_summary(df)
    monthly = analysis.monthly_new(df)
    season = analysis.seasonality(monthly)
    flow = analysis.yearly_flow(df)
    curve, timing = analysis.gst_timing(df)
    by_age = analysis.gst_by_age(df)
    sectors = analysis.sector_summary(df)
    regions = analysis.region_summary(df)
    seg = analysis.segments(df)
    head = analysis.headline(df)

    market.round(1).to_csv(out / "market_by_state.csv", index=False)
    monthly.to_csv(out / "monthly_new_companies.csv", index=False, date_format="%Y-%m")
    season.round(1).to_csv(out / "seasonality.csv", index=False)
    flow.to_csv(out / "yearly_started_and_cancelled.csv", index=False)
    curve.round(1).to_csv(out / "gst_timing.csv", index=False)
    by_age.round(1).to_csv(out / "gst_by_company_age.csv", index=False)
    sectors.round(1).to_csv(out / "sectors.csv", index=False)
    regions.round(1).to_csv(out / "vic_regions.csv", index=False)
    seg.round(1).to_csv(out / "vic_segments.csv", index=False)
    summary = {"headline": head, "gst_timing": {k: round(float(v), 1) for k, v in timing.items()},
               "segment_grid": {k: round(v, 1) for k, v in seg.attrs.items()}}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    sql_dir = out / "sql"
    sql_dir.mkdir(exist_ok=True)
    for name, result in sql_queries.run_all().items():
        numeric = result.select_dtypes("number").columns
        result.round({c: 2 for c in numeric}).to_csv(sql_dir / f"{name}.csv", index=False, date_format="%Y-%m")

    save_dims(df)

    cfg.IMAGES_DIR.mkdir(exist_ok=True)
    charts.monthly_new(monthly, cfg.IMAGES_DIR / "monthly_new_companies.png")
    charts.gst_timing(curve, cfg.IMAGES_DIR / "gst_timing.png")
    charts.sector_growth(sectors, cfg.IMAGES_DIR / "sector_growth.png")
    charts.vic_regions(regions, cfg.IMAGES_DIR / "vic_regions.png")
    charts.segment_matrix(seg, cfg.IMAGES_DIR / "vic_segments.png")

    print(f"  {head['active_companies']:,} active Pty Ltd companies, {head['gst_registered_pct']}% GST-registered")
    print(f"  {head['new_last_12m']:,} new in the last 12 months ({head['growth_pct']:+.1f}%), "
          f"{head['leads_last_12m']:,} of them leads")
    print(f"  Victoria: {head['vic_leads_last_12m']:,} leads, {(seg['quadrant'].str.startswith('Priority')).sum()} "
          f"priority segments")
    print(f"Done in {time.perf_counter() - start:.1f}s")


if __name__ == "__main__":
    main()
