"""
Synthetic data generator for the Marketing Analytics Warehouse project.

Creates realistic (and, later, deliberately messy) CSV files for a fictional
online store that advertises on Google, Meta and email. The files land in
data/raw/ and are later loaded into Snowflake's RAW schema.

Run from the project root, with .venv activated:
    python data_generator/generate_data.py
"""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

SEED = 42                                      # same seed -> same data every run
END_DATE = date.today()                        # data runs up to today...
START_DATE = END_DATE - timedelta(days=364)    # ...and covers the last 12 months

# data/raw/ next to this script's parent folder (the project root)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# One random number generator for the whole script, started from SEED.
rng = np.random.default_rng(SEED)

# Faker makes realistic fake emails. Seeding it makes the emails repeatable too.
fake = Faker("en_US")
Faker.seed(SEED)

# How each channel behaves. These numbers drive the CAC / ROAS story later.
#   daily_impressions: average ads shown (emails sent, for email) per campaign per day
#   ctr: click-through rate = clicks / impressions
#   cpc: cost per click, in USD
CHANNELS = {
    "google": {"daily_impressions": 350, "ctr": 0.040, "cpc": 1.80},
    "meta":   {"daily_impressions": 900, "ctr": 0.012, "cpc": 0.90},
    "email":  {"daily_impressions": 300, "ctr": 0.050, "cpc": 0.05},
}

# The 15 campaigns: (campaign_name, channel, always_on)
#   always_on=True  -> runs for (almost) the whole year, no end date yet
#   always_on=False -> a shorter burst of 2-6 months
CAMPAIGN_PLAN = [
    ("google_search_brand",        "google", True),
    ("google_search_generic",      "google", True),
    ("google_shopping",            "google", True),
    ("google_display_retargeting", "google", False),
    ("google_youtube_awareness",   "google", False),
    ("meta_prospecting_lookalike", "meta",   True),
    ("meta_retargeting_cart",      "meta",   True),
    ("meta_instagram_stories",     "meta",   False),
    ("meta_reels_video",           "meta",   False),
    ("meta_seasonal_promo",        "meta",   False),
    ("email_welcome_series",       "email",  True),
    ("email_newsletter",           "email",  True),
    ("email_abandoned_cart",       "email",  True),
    ("email_winback",              "email",  False),
    ("email_seasonal_promo",       "email",  False),
]

N_CUSTOMERS = 5_000

# Where customers live (share of all customers). Clean data uses 2-letter codes.
COUNTRY_MIX = {"US": 0.60, "CA": 0.12, "GB": 0.10, "AU": 0.07, "DE": 0.06, "IN": 0.05}

# Which channel brought each customer to the store for the first time.
# "direct" = typed the URL or found us without an ad (no UTM tags).
ACQUISITION_MIX = {"google": 0.35, "meta": 0.30, "email": 0.10, "direct": 0.25}


# ---------------------------------------------------------------------------
# 1. campaigns
# ---------------------------------------------------------------------------

def make_campaigns() -> pd.DataFrame:
    """One row per campaign, with its channel and start/end dates."""
    rows = []
    for i, (name, channel, always_on) in enumerate(CAMPAIGN_PLAN, start=1):
        if always_on:
            # Starts in the first month of the window and is still running.
            start = START_DATE + timedelta(days=int(rng.integers(0, 30)))
            end = None
        else:
            # A 60-180 day burst somewhere inside the window.
            length = int(rng.integers(60, 181))
            offset = int(rng.integers(0, 365 - length))
            start = START_DATE + timedelta(days=offset)
            end = start + timedelta(days=length - 1)

        rows.append({
            "campaign_id": f"CMP{i:03d}",      # CMP001, CMP002, ...
            "campaign_name": name,
            "channel": channel,
            "start_date": start,
            "end_date": end,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. ad_spend
# ---------------------------------------------------------------------------

def make_ad_spend(campaigns: pd.DataFrame) -> pd.DataFrame:
    """One row per campaign per day it was active: impressions -> clicks -> spend."""
    frames = []
    for c in campaigns.itertuples():
        params = CHANNELS[c.channel]
        last_day = c.end_date if c.end_date is not None else END_DATE
        days = pd.date_range(c.start_date, last_day, freq="D")
        n = len(days)

        # Weekends are a bit quieter.
        day_factor = np.where(days.dayofweek >= 5, 0.8, 1.0)

        # Impressions: random around the channel's daily average.
        impressions = rng.poisson(params["daily_impressions"] * day_factor)

        # Clicks: each impression has a ~ctr chance of a click (+/- some daily noise).
        ctr = (params["ctr"] * rng.normal(1.0, 0.15, n)).clip(0, 1)
        clicks = rng.binomial(impressions, ctr)

        # Spend: clicks x cost per click (+/- some daily noise).
        cpc = params["cpc"] * rng.normal(1.0, 0.10, n).clip(0.7, 1.3)
        spend = (clicks * cpc).round(2)

        frames.append(pd.DataFrame({
            "date": days.date,
            "channel": c.channel,
            "campaign": c.campaign_name,
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
        }))
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# 3. customers
# ---------------------------------------------------------------------------

def make_customers() -> pd.DataFrame:
    """One row per customer: id, email, signup date, country, last update time.

    Columns starting with "_" are helpers for later tables. They are NOT
    written to the CSV (real raw data wouldn't have them).
    """
    n = N_CUSTOMERS
    all_days = pd.date_range(START_DATE, END_DATE, freq="D")

    # The store is growing: later days get more signups (weight rises 1.0 -> 1.6).
    weights = np.linspace(1.0, 1.6, len(all_days))
    signup_days = pd.DatetimeIndex(rng.choice(all_days, size=n, p=weights / weights.sum()))

    # Add a random time of day, then sort so customer IDs follow signup order.
    signup_ts = signup_days + pd.to_timedelta(rng.integers(0, 86_400, n), unit="s")
    signup_ts = signup_ts.sort_values()

    # About 30% of customers changed their profile later (e.g. moved country).
    # Their updated_at is 1-120 days after signup (but never in the future).
    changed = rng.random(n) < 0.30
    later = signup_ts + pd.to_timedelta(rng.integers(1, 121, n), unit="D")
    in_future = later > pd.Timestamp(END_DATE) + pd.Timedelta(days=1)
    updated_at = np.where(changed & ~in_future, later, signup_ts)

    return pd.DataFrame({
        "customer_id": [f"C{i:05d}" for i in range(1, n + 1)],   # C00001, ...
        "email": [fake.unique.email() for _ in range(n)],
        "signup_date": signup_ts.date,
        "country": rng.choice(list(COUNTRY_MIX), size=n, p=list(COUNTRY_MIX.values())),
        "updated_at": pd.to_datetime(updated_at),
        # helpers (not written to CSV):
        "_signup_ts": signup_ts,
        "_acquisition_channel": rng.choice(
            list(ACQUISITION_MIX), size=n, p=list(ACQUISITION_MIX.values())
        ),
    })


# ---------------------------------------------------------------------------
# Main: build the tables and write them to CSV
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Generating data from {START_DATE} to {END_DATE} (seed={SEED})")

    campaigns = make_campaigns()
    ad_spend = make_ad_spend(campaigns)
    customers = make_customers()

    tables = {
        "campaigns": campaigns,
        "ad_spend": ad_spend,
        "customers": customers,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        # Leave out helper columns (names starting with "_").
        public = df.loc[:, ~df.columns.str.startswith("_")]
        path = OUTPUT_DIR / f"{name}.csv"
        public.to_csv(path, index=False)
        print(f"  {name:<12} {len(public):>8,} rows -> data/raw/{name}.csv")

    # Quick sanity checks.
    summary = ad_spend.groupby("channel")[["impressions", "clicks", "spend"]].sum()
    print("\nAd spend totals by channel:")
    print(summary.to_string())

    print("\nCustomers by first channel:")
    print(customers["_acquisition_channel"].value_counts().to_string())


if __name__ == "__main__":
    main()
