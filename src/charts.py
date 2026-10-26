"""Charts for the README."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

NAVY, ORANGE, RED, GREEN = "#1F4E79", "#D68910", "#B03A2E", "#4E8F3A"
GREY, LIGHT, DARK = "#8A949E", "#D5DBE1", "#2E3A46"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 12.5, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": GREY, "axes.labelcolor": DARK, "xtick.color": DARK, "ytick.color": DARK,
    "figure.dpi": 150, "savefig.bbox": "tight",
})
THOUSANDS = mtick.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v else "0")


def monthly_new(monthly: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(11, 4))
    peak = monthly["month"].dt.month.isin([6, 7])
    colours = [ORANGE if p else NAVY for p in peak]
    ax.bar(monthly["month"], monthly["new_companies"], width=24, color=colours)
    ax.yaxis.set_major_formatter(THOUSANDS)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.set_ylabel("New companies (still active)")
    ax.bar([0], [0], color=ORANGE, label="June and July")
    ax.bar([0], [0], color=NAVY, label="Other months")
    ax.set_xlim(monthly["month"].min() - pd.Timedelta(days=20), monthly["month"].max() + pd.Timedelta(days=20))
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("New Pty Ltd companies each month, January 2023 to September 2026")
    fig.savefig(path)
    plt.close(fig)


def gst_timing(curve: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    x, y = curve["days_after_abn"], curve["share_of_gst_registered_pct"]
    ax.plot(x, y, color=NAVY, lw=2, marker="o", ms=5)
    for xi, yi in zip(x, y):
        if xi in (0, 30, 90, 365):
            ax.annotate(f"{yi:.0f}%", (xi, yi), xytext=(8, -12) if xi == 0 else (0, 8),
                        textcoords="offset points", ha="left" if xi == 0 else "center", fontsize=9, color=DARK)
    ax.set_ylim(70, 100)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xticks([0, 30, 90, 180, 365])
    ax.set_xlabel("Days after the company's ABN started")
    ax.set_ylabel("Share registered for GST by then")
    ax.set_title("3 in 4 GST-registered companies register on the day their ABN starts")
    fig.savefig(path)
    plt.close(fig)


def sector_growth(sectors: pd.DataFrame, path):
    s = sectors[~sectors["sector"].isin(["Unclassified", "Numbered company"])].sort_values("growth_pct")
    fig, ax = plt.subplots(figsize=(9.5, 6))
    colours = [LIGHT if sec == "Holding, investment or trustee" else GREY if v < 5 else NAVY
               for sec, v in zip(s["sector"], s["growth_pct"])]
    ax.barh(s["sector"], s["growth_pct"], color=colours, height=0.65)
    for yi, (sec, g, n) in enumerate(zip(s["sector"], s["growth_pct"], s["new_last_12m"])):
        note = ", not leads" if sec == "Holding, investment or trustee" else ""
        ax.text(g + (0.6 if g >= 0 else -0.6), yi, f"{g:+.0f}%  ({n:,.0f} new{note})", va="center",
                ha="left" if g >= 0 else "right", fontsize=8.5, color=DARK)
    ax.axvline(0, color=GREY, lw=1)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlim(s["growth_pct"].min() - 12, s["growth_pct"].max() + 16)
    ax.set_xlabel("Change in new companies, last 12 months vs the 12 months before")
    ax.set_title("New companies by industry: IT, transport and property are growing fastest")
    fig.savefig(path)
    plt.close(fig)


def vic_regions(regions: pd.DataFrame, path):
    r = regions.sort_values("new_last_12m")
    fig, ax = plt.subplots(figsize=(9.5, 6))
    colours = [ORANGE if n == r["new_last_12m"].max() else NAVY for n in r["new_last_12m"]]
    ax.barh(r["sa4"], r["new_last_12m"], color=colours, height=0.65)
    for yi, (n, g) in enumerate(zip(r["new_last_12m"], r["growth_pct"])):
        ax.text(n + 120, yi, f"{n:,.0f}  ({g:+.0f}%)", va="center", fontsize=8.5, color=DARK)
    ax.xaxis.set_major_formatter(THOUSANDS)
    ax.set_xlim(0, r["new_last_12m"].max() * 1.2)
    ax.set_xlabel("New companies, Oct 2025 to Sep 2026 (change vs the year before)")
    ax.set_title("Victoria: new companies by region")
    fig.savefig(path)
    plt.close(fig)


def segment_matrix(seg: pd.DataFrame, path, label_top=8):
    fig, ax = plt.subplots(figsize=(10, 6))
    colour = {"Priority: large and growing": NAVY, "Core: large, steady": ORANGE,
              "Emerging: small, growing": GREEN, "Monitor: small, steady": GREY}
    for q, c in colour.items():
        d = seg[seg["quadrant"] == q]
        ax.scatter(d["new_leads"], d["growth_pct"], s=40, color=c, label=q, zorder=3,
                   edgecolor="white", linewidth=0.8)
    ax.axvline(seg.attrs["size_cut"], color=LIGHT, lw=1, zorder=1)
    ax.axhline(seg.attrs["growth_cut"], color=LIGHT, lw=1, zorder=1)
    short = {"Construction and trades": "Construction", "Transport and logistics": "Transport",
             "Professional services": "Professional", "IT and digital": "IT"}
    for _, row in seg.head(label_top).iterrows():
        region = row["sa4"].replace("Melbourne - ", "")
        ax.annotate(f"{region}: {short.get(row['sector'], row['sector'])}", (row["new_leads"], row["growth_pct"]),
                    xytext=(6, 4), textcoords="offset points", fontsize=8, color=DARK)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.xaxis.set_minor_formatter(mtick.NullFormatter())
    ax.set_xticks([100, 200, 400, 800])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlabel("New GST-registered operating companies, last 12 months (log scale)")
    ax.set_ylabel("Change vs the year before")
    ax.legend(frameon=False, fontsize=8.5, loc="upper center", ncol=4, bbox_to_anchor=(0.5, -0.13))
    ax.set_title("Victoria: region x industry segments of new leads (each dot has 100+)")
    fig.savefig(path)
    plt.close(fig)
