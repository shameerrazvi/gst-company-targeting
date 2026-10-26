"""Extract Australian private companies (Pty Ltd) from the ABN Bulk Extract.

Source: ABN Bulk Extract, Australian Business Register, published weekly on data.gov.au
(dataset "abn-bulk-extract"). It comes as two zip files, each holding ten XML files
(yyyymmddPublic01.xml to Public20.xml). Together they hold every ABN, active or cancelled.

The XML is read straight from the zips with a streaming parser, so nothing is unzipped
and memory stays low. Only records with entity type PRV (Australian Private Company) are
kept, with the fields the analysis needs.

Usage:
    python -m src.extract data/raw data/raw/companies_full.csv.gz
"""
import csv
import gzip
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from lxml import etree

FIELDS = ["abn", "abn_status", "abn_status_from", "record_updated", "name", "state", "postcode", "acn",
          "gst_status", "gst_status_from", "dgr", "n_business_names", "business_names"]
MAX_NAMES = 5          # business names kept per company (some have over 300)
KEEP_TYPE = "PRV"      # Australian Private Company


def _text(el, path):
    found = el.find(path)
    return found.text.strip() if found is not None and found.text else ""


def parse_record(abr) -> dict | None:
    """One <ABR> element -> a dict, or None if it isn't a private company."""
    if _text(abr, "EntityType/EntityTypeInd") != KEEP_TYPE:
        return None
    abn = abr.find("ABN")
    gst = abr.find("GST")
    names = []
    for other in abr.iterfind("OtherEntity/NonIndividualName"):
        text = other.findtext("NonIndividualNameText")
        if other.get("type") in ("BN", "TRD") and text and text.strip():
            names.append(text.strip())
    return {
        "abn": abn.text.strip() if abn is not None else "",
        "abn_status": abn.get("status", "") if abn is not None else "",
        "abn_status_from": abn.get("ABNStatusFromDate", "") if abn is not None else "",
        "record_updated": abr.get("recordLastUpdatedDate", ""),
        "name": _text(abr, "MainEntity/NonIndividualName/NonIndividualNameText"),
        "state": _text(abr, "MainEntity/BusinessAddress/AddressDetails/State"),
        "postcode": _text(abr, "MainEntity/BusinessAddress/AddressDetails/Postcode"),
        "acn": _text(abr, "ASICNumber"),
        "gst_status": gst.get("status", "") if gst is not None else "",
        "gst_status_from": gst.get("GSTStatusFromDate", "") if gst is not None else "",
        "dgr": int(abr.find("DGR") is not None),
        "n_business_names": len(names),
        "business_names": " | ".join(names[:MAX_NAMES]),
    }


def parse_stream(stream):
    """Yield private-company records from an open XML file, clearing parsed elements as it goes."""
    for _, abr in etree.iterparse(stream, events=("end",), tag="ABR", huge_tree=True):
        rec = parse_record(abr)
        if rec:
            yield rec
        abr.clear()
        while abr.getprevious() is not None:
            del abr.getparent()[0]


def _process_member(args):
    zip_path, member, out_dir = args
    out = Path(out_dir) / (Path(member).stem + ".csv.gz")
    seen = kept = 0
    with zipfile.ZipFile(zip_path) as zf, zf.open(member) as stream, \
            gzip.open(out, "wt", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, FIELDS)
        writer.writeheader()
        for rec in parse_stream(stream):
            writer.writerow(rec)
            kept += 1
    return member, kept, str(out)


def extract(raw_dir, out_path, workers=4):
    raw_dir, out_path = Path(raw_dir), Path(out_path)
    zips = sorted(raw_dir.glob("*.zip"))
    jobs = []
    parts = out_path.parent / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    for z in zips:
        with zipfile.ZipFile(z) as zf:
            jobs += [(str(z), m, str(parts)) for m in zf.namelist() if m.lower().endswith(".xml")]
    if not jobs:
        raise FileNotFoundError(f"No XML files found in zips in {raw_dir}")
    total = 0
    with ProcessPoolExecutor(workers) as pool:
        results = sorted(pool.map(_process_member, jobs))
    with gzip.open(out_path, "wt", newline="", encoding="utf-8") as fh:
        fh.write(",".join(FIELDS) + "\n")
        for member, kept, part in results:
            with gzip.open(part, "rt", encoding="utf-8") as pf:
                next(pf)
                for line in pf:
                    fh.write(line)
            total += kept
            print(f"  {member}: {kept:,} private companies", flush=True)
    print(f"{total:,} private companies written to {out_path}", flush=True)
    return total


if __name__ == "__main__":
    extract(sys.argv[1], sys.argv[2])
