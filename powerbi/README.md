# Power BI model

The analysis table is ready to load into Power BI as it is. This folder holds the two lookup tables
and the measures for a targeting dashboard.

## Tables

| Table | Source | Rows | Key |
|---|---|---:|---|
| `Companies` (fact) | `data/processed/companies.parquet` | 4.09 million | one row per company (active and cancelled) |
| `Region` | `powerbi/dim_region.csv` | one per state and SA4 region | `state` + `sa4` |
| `Sector` | `powerbi/dim_sector.csv` | 20 | `sector` |
| `Date` | DAX calendar (below) | one per day | `Date` |

In Power BI Desktop: **Get data → Parquet**, pick the file, then **Get data → Text/CSV** for the two
lookup tables.

## Relationships

- `Companies[sector]` → `Sector[sector]` (many to one)
- `Companies[region_key]` → `Region[region_key]` (many to one). Add `region_key = [state] & "|" & [sa4]`
  as a custom column in Power Query on both tables.
- `Companies[abn_status_from]` → `Date[Date]` (many to one, active)
- `Companies[gst_status_from]` → `Date[Date]` (many to one, **inactive**, used with `USERELATIONSHIP`)

## Date table

```dax
Date =
ADDCOLUMNS (
    CALENDAR ( DATE ( 1999, 11, 1 ), DATE ( 2026, 10, 21 ) ),
    "Year", YEAR ( [Date] ),
    "Month", FORMAT ( [Date], "mmm yyyy" ),
    "Month start", DATE ( YEAR ( [Date] ), MONTH ( [Date] ), 1 ),
    "Financial year", "FY" & ( YEAR ( [Date] ) + IF ( MONTH ( [Date] ) >= 7, 1, 0 ) )
)
```

## Measures

```dax
Active companies =
-- every active company, whatever dates are selected
CALCULATE ( COUNTROWS ( Companies ), Companies[abn_status] = "ACT", REMOVEFILTERS ( 'Date' ) )

GST registered % =
DIVIDE (
    CALCULATE (
        COUNTROWS ( Companies ),
        Companies[abn_status] = "ACT", Companies[gst_status] = "ACT", REMOVEFILTERS ( 'Date' )
    ),
    [Active companies]
)

New companies =
-- active companies whose ABN started in the dates selected on the Date table
CALCULATE ( COUNTROWS ( Companies ), Companies[abn_status] = "ACT" )

New companies (previous year) =
CALCULATE ( [New companies], DATEADD ( 'Date'[Date], -1, YEAR ) )

New companies growth % =
DIVIDE ( [New companies] - [New companies (previous year)], [New companies (previous year)] )

Leads =
-- operating companies (not holding, trustee or numbered) registered for GST
CALCULATE (
    [New companies],
    Companies[operating] = 1,
    Companies[gst_status] = "ACT"
)

Lead share % =
DIVIDE ( [Leads], [New companies] )

GST registered same day % =
VAR gst =
    FILTER (
        Companies,
        Companies[abn_status] = "ACT" && Companies[gst_status] = "ACT"
    )
RETURN
    DIVIDE (
        COUNTROWS ( FILTER ( gst, Companies[gst_status_from] = Companies[abn_status_from] ) ),
        COUNTROWS ( gst )
    )
```

## Suggested pages

1. **Market overview:** cards for active companies, GST-registered % and leads in the last 12 months;
   new companies by month (column chart) with the financial year as a slicer.
2. **Where:** a filled map or bar chart of new companies by SA4 region, with a state slicer, coloured
   by growth %.
3. **Who:** new companies by sector (bar), with `Sector[operating]` as a slicer so holding and trustee
   companies can be excluded.
4. **Segments:** a scatter chart with leads on the x axis, growth % on the y axis and one dot per
   region and sector, matching `images/vic_segments.png`.

Set the Date slicer to 1 Oct 2025 to 30 Sep 2026 to match the figures in the main README.
