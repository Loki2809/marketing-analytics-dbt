-- dim_campaigns: one row per marketing campaign, with a summary of its ad spend.

with campaigns as (

    select * from {{ ref('stg_campaigns') }}

),

-- Summarise spend per campaign first, then join (avoids fan-out).
spend_summary as (

    select
        campaign_name,
        sum(spend)              as total_spend,
        sum(impressions)        as total_impressions,
        sum(clicks)             as total_clicks,       -- days with NULL clicks are skipped by SUM
        min(spend_date)         as first_spend_date,
        max(spend_date)         as last_spend_date,
        count(*)                as active_days
    from {{ ref('stg_ad_spend') }}
    group by campaign_name

)

select
    campaigns.campaign_id,
    campaigns.campaign_name,
    campaigns.channel,
    campaigns.start_date,
    campaigns.end_date,
    campaigns.is_always_on,

    coalesce(spend_summary.total_spend, 0)          as total_spend,
    coalesce(spend_summary.total_impressions, 0)    as total_impressions,
    coalesce(spend_summary.total_clicks, 0)         as total_clicks,
    spend_summary.first_spend_date,
    spend_summary.last_spend_date,
    coalesce(spend_summary.active_days, 0)          as active_days

from campaigns
left join spend_summary
    on campaigns.campaign_name = spend_summary.campaign_name
