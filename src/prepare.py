"""Clean the extracted company records, add industry and region, and save the analysis table.

The analysis table has no names or ABNs: it keeps only what the analysis uses, which keeps
it small enough for GitHub (each company's industry is worked out here, from its names).
It is saved as Parquet: about 35 MB, against 55 MB as a compressed CSV, and it loads in under a
second. DuckDB and Power BI read Parquet directly.
"""
import pandas as pd

from . import config as cfg
from . import industry

DATE_SENTINEL = "19000101"          # used by the ABR for "no GST registration"
CATEGORIES = ["abn_status", "gst_status", "state", "postcode", "sector", "sa4", "sa3"]


def _date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.where(s != DATE_SENTINEL), format="%Y%m%d", errors="coerce")


def load_postcodes(path=cfg.POSTCODES) -> pd.DataFrame:
    """Postcode -> SA4 and SA3 region (ABS 2016 areas), taking the most common region across
    each postcode's localities. A region whose postcodes are mostly in another state is not
    trusted for that postcode (for example Albury 2640 is listed under Victoria's Hume)."""
    pc = pd.read_csv(path, dtype=str, keep_default_na=False)
    pc = pc[(pc["sa4name"] != "") & pc["postcode"].str.fullmatch(r"\d{4}")]
    sa4_state = pc.groupby("sa4name")["state"].agg(lambda s: s.mode().iloc[0])
    m = pc.groupby("postcode").agg(sa4=("sa4name", lambda s: s.mode().iloc[0]),
                                   sa3=("sa3name", lambda s: s.mode().iloc[0]),
                                   pc_state=("state", lambda s: s.mode().iloc[0]))
    wrong_state = m["sa4"].map(sa4_state) != m["pc_state"]
    m.loc[wrong_state, ["sa4", "sa3"]] = ""
    for code, (sa4, sa3) in cfg.POSTCODE_PATCHES.items():
        m.loc[code, ["sa4", "sa3", "pc_state"]] = [sa4, sa3, "VIC"]
    return m


def clean(raw: pd.DataFrame, postcodes: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    log = {"rows_read": len(raw)}
    df = pd.DataFrame({
        "abn_status": raw["abn_status"],
        "abn_status_from": _date(raw["abn_status_from"]),
        "gst_status": raw["gst_status"].where(raw["gst_status"].isin(["ACT", "CAN", "NON"]), "NON"),
        "gst_status_from": _date(raw["gst_status_from"]),
        "state": raw["state"].str.upper().str.strip(),
        "postcode": raw["postcode"].str.strip().str.zfill(4),
        "has_business_name": (pd.to_numeric(raw["n_business_names"], errors="coerce").fillna(0) > 0).astype(int),
        "dgr": pd.to_numeric(raw["dgr"], errors="coerce").fillna(0).astype(int),
    })
    df.loc[df["gst_status"] == "NON", "gst_status_from"] = pd.NaT

    future = df["abn_status_from"] > cfg.SNAPSHOT
    log["future_dated_removed"] = int(future.sum())
    no_date = df["abn_status_from"].isna()
    log["missing_status_date_removed"] = int(no_date.sum())
    df = df[~future & ~no_date]

    bad_state = ~df["state"].isin(cfg.STATES)
    log["no_or_overseas_state"] = int(bad_state.sum())
    df.loc[bad_state, "state"] = "Unknown"

    df["sector"] = industry.classify(raw.loc[df.index, "name"], raw.loc[df.index, "business_names"])
    df["operating"] = (~df["sector"].isin(industry.PASSIVE)).astype(int)

    region = postcodes.reindex(df["postcode"])
    same_state = region["pc_state"].to_numpy() == df["state"].to_numpy()
    df["sa4"] = pd.Series(region["sa4"].to_numpy(), index=df.index).where(same_state, "")
    df["sa3"] = pd.Series(region["sa3"].to_numpy(), index=df.index).where(same_state, "")
    df["sa4"] = df["sa4"].fillna("").replace("", "Unmatched")
    df["sa3"] = df["sa3"].fillna("").replace("", "Unmatched")
    log["postcode_unmatched"] = int((df["sa4"] == "Unmatched").sum())
    log["rows_clean"] = len(df)
    log["active"] = int((df["abn_status"] == "ACT").sum())
    return df.reset_index(drop=True), log


def build(raw_path=cfg.RAW_EXTRACT, out_path=cfg.PROCESSED) -> dict:
    raw = pd.read_csv(raw_path, dtype=str, keep_default_na=False)
    df, log = clean(raw, load_postcodes())
    for col in CATEGORIES:
        df[col] = df[col].astype("category")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return log


def read_processed(path=cfg.PROCESSED) -> pd.DataFrame:
    df = pd.read_parquet(path)
    for col in CATEGORIES:
        df[col] = df[col].astype(str)
    return df
