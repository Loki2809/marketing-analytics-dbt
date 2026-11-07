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

# --- web sessions (website visits) ---
CLICK_TO_SESSION = 0.90        # 90% of ad clicks turn into a recorded visit
N_DIRECT_SESSIONS = 17_000     # visits with no ad at all (no UTM tags)
RETURN_VISITS_PER_YEAR = 5     # average return visits per customer per year

# Which channel brings customers BACK (email is strong for repeat visits).
RETURN_CHANNEL_MIX = {"email": 0.35, "direct": 0.30, "google": 0.20, "meta": 0.15}

# UTM tags each channel puts on its links: channel -> (utm_source, utm_medium)
UTM_TAGS = {
    "google": ("google", "cpc"),            # cpc = cost per click (search ads)
    "meta":   ("facebook", "paid_social"),
    "email":  ("email", "email"),
    "direct": (None, None),                 # no tags
}

# Device split per channel: [desktop, mobile, tablet]. Meta is mostly phones.
DEVICES = ["desktop", "mobile", "tablet"]
DEVICE_MIX = {
    "google": [0.55, 0.38, 0.07],
    "meta":   [0.20, 0.75, 0.05],
    "email":  [0.45, 0.48, 0.07],
    "direct": [0.55, 0.38, 0.07],
}


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
        day_factor = np.where(days.day_of_week >= 5, 0.8, 1.0)

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
# 4. web_sessions
# ---------------------------------------------------------------------------

def _random_time_on(days: pd.Series) -> pd.Series:
    """Give each date a random time of day."""
    seconds = rng.integers(0, 86_400, len(days))
    return days + pd.to_timedelta(seconds, unit="s")


def make_web_sessions(ad_spend: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """One row per website visit.

    How it works:
      A. Ad clicks become anonymous visits (with UTM tags).
      B. Extra "direct" visits are added (no UTM tags).
      C. Each customer gets a first visit (on their signup day, via their
         acquisition channel) plus some return visits later.
      D. Those customer visits are matched to anonymous visits from the same
         day and channel, i.e. the visitor "logged in". This keeps visits
         consistent with ad clicks.
    """
    # A. Ad clicks -> anonymous visits. Repeat each ad_spend row once per visit.
    visits_per_row = rng.binomial(ad_spend["clicks"], CLICK_TO_SESSION)
    paid = (
        ad_spend.loc[ad_spend.index.repeat(visits_per_row), ["date", "channel", "campaign"]]
        .reset_index(drop=True)
    )

    # B. Direct visits, more of them later in the year (the store is growing).
    all_days = pd.date_range(START_DATE, END_DATE, freq="D")
    weights = np.linspace(1.0, 1.6, len(all_days))
    direct_days = rng.choice(all_days, size=N_DIRECT_SESSIONS, p=weights / weights.sum())
    direct = pd.DataFrame({"date": direct_days, "channel": "direct", "campaign": None})

    pool = pd.concat([paid, direct], ignore_index=True)
    pool["date"] = pd.to_datetime(pool["date"])
    pool["session_start"] = _random_time_on(pool["date"])
    pool["customer_id"] = None

    # C1. First visit: on the signup day, a few minutes before signing up.
    signup_day = pd.to_datetime(customers["signup_date"])
    minutes_before = pd.to_timedelta(rng.integers(1, 31, len(customers)), unit="min")
    first = pd.DataFrame({
        "customer_id": customers["customer_id"],
        "date": signup_day,
        "channel": customers["_acquisition_channel"],
        "session_start": (customers["_signup_ts"] - minutes_before).clip(lower=signup_day),
    })

    # C2. Return visits: more for customers who signed up earlier (more time to come back).
    days_left = (pd.Timestamp(END_DATE) - signup_day).dt.days
    n_returns = rng.poisson(days_left / 365 * RETURN_VISITS_PER_YEAR)
    ret = customers.loc[customers.index.repeat(n_returns), ["customer_id"]].reset_index(drop=True)
    ret_signup = signup_day.repeat(n_returns).reset_index(drop=True)
    ret_days_left = days_left.repeat(n_returns).to_numpy()
    ret["date"] = ret_signup + pd.to_timedelta(rng.integers(1, ret_days_left + 1), unit="D")
    ret["channel"] = rng.choice(
        list(RETURN_CHANNEL_MIX), size=len(ret), p=list(RETURN_CHANNEL_MIX.values())
    )
    ret["session_start"] = _random_time_on(ret["date"])

    requests = pd.concat([first, ret], ignore_index=True)

    # D. Match each customer visit to an unused anonymous visit (same day + channel).
    #    Shuffle the pool, number the visits inside each (day, channel) group as
    #    slots 0, 1, 2, ... and do the same for the requests. Then join on slot.
    pool = pool.iloc[rng.permutation(len(pool))].reset_index(drop=True)
    pool["_slot"] = pool.groupby(["date", "channel"]).cumcount()
    requests["_slot"] = requests.groupby(["date", "channel"]).cumcount()
    matched = requests.merge(
        pool[["date", "channel", "_slot"]].reset_index(names="_pool_row"),
        on=["date", "channel", "_slot"],
        how="left",
    )

    found = matched["_pool_row"].notna()
    rows = matched.loc[found, "_pool_row"].astype(int)
    pool.loc[rows, "customer_id"] = matched.loc[found, "customer_id"].to_numpy()
    pool.loc[rows, "session_start"] = matched.loc[found, "session_start"].to_numpy()

    # No free anonymous visit that day (e.g. campaign not running yet)?
    # Then the customer simply came in directly.
    extra = matched.loc[~found, ["customer_id", "date", "session_start"]].copy()
    extra["channel"] = "direct"
    extra["campaign"] = None

    sessions = pd.concat([pool.drop(columns="_slot"), extra], ignore_index=True)

    # UTM tags and device, based on the channel.
    sessions["utm_source"] = sessions["channel"].map(lambda ch: UTM_TAGS[ch][0])
    sessions["utm_medium"] = sessions["channel"].map(lambda ch: UTM_TAGS[ch][1])
    sessions["device"] = None
    for channel, probs in DEVICE_MIX.items():
        is_ch = sessions["channel"] == channel
        sessions.loc[is_ch, "device"] = rng.choice(DEVICES, size=is_ch.sum(), p=probs)

    # Sort by time and number the visits: S000001, S000002, ...
    sessions = sessions.sort_values("session_start", ignore_index=True)
    sessions["session_id"] = [f"S{i:06d}" for i in range(1, len(sessions) + 1)]

    return pd.DataFrame({
        "session_id": sessions["session_id"],
        "customer_id": sessions["customer_id"],
        "session_start": sessions["session_start"],
        "utm_source": sessions["utm_source"],
        "utm_medium": sessions["utm_medium"],
        "utm_campaign": sessions["campaign"],
        "device": sessions["device"],
        # helper (not written to CSV): the true channel, used for funnel behavior
        "_channel": sessions["channel"],
    })


# ---------------------------------------------------------------------------
# Main: build the tables and write them to CSV
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Generating data from {START_DATE} to {END_DATE} (seed={SEED})")

    campaigns = make_campaigns()
    ad_spend = make_ad_spend(campaigns)
    customers = make_customers()
    web_sessions = make_web_sessions(ad_spend, customers)

    tables = {
        "campaigns": campaigns,
        "ad_spend": ad_spend,
        "customers": customers,
        "web_sessions": web_sessions,
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

    logged_in = web_sessions["customer_id"].notna()
    print("\nWeb sessions by channel (total / logged in):")
    print(pd.DataFrame({
        "sessions": web_sessions["_channel"].value_counts(),
        "logged_in": web_sessions.loc[logged_in, "_channel"].value_counts(),
    }).to_string())


if __name__ == "__main__":
    main()
