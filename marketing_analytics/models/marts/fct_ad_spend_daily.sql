-- fct_ad_spend_daily: one row per campaign per day, with spend and ad performance.
-- Adds campaign_id (links to dim_campaigns) and two standard ad metrics:
--   CTR (click-through rate) = clicks / impressions
--   CPC (cost per click)     = spend / clicks

with spend as (

    select * from {{ ref('stg_ad_spend') }}

),

campaigns as (

    select campaign_id, campaign_name from {{ ref('stg_campaigns') }}

)

select
    spend.ad_spend_id,
    spend.spend_date,                    -- links to dim_date
    campaigns.campaign_id,               -- links to dim_campaigns
    spend.campaign_name,
    spend.channel,
    spend.impressions,
    spend.clicks,                        -- NULL = not reported that day
    spend.spend,

    -- div0null: divide, but return 0 instead of an error when dividing by 0 (and NULL stays NULL).
    round(div0null(spend.clicks, spend.impressions), 4)   as ctr,
    round(div0null(spend.spend, spend.clicks), 2)         as cpc

from spend
left join campaigns
    on spend.campaign_name = campaigns.campaign_name
