-- fct_sessions: one row per website visit, with funnel progress.
-- Built on int_sessions_funnel; adds campaign_id so visits link to dim_campaigns.
-- (In M4 this model becomes "incremental": only new visits get processed on each run.)

with funnel as (

    select * from {{ ref('int_sessions_funnel') }}

),

campaigns as (

    select campaign_id, campaign_name from {{ ref('stg_campaigns') }}

)

select
    funnel.session_id,
    funnel.session_start,
    funnel.session_date,                 -- links to dim_date
    funnel.customer_id,                  -- links to dim_customers (NULL = anonymous)
    campaigns.campaign_id,               -- links to dim_campaigns (NULL = no campaign)
    funnel.channel,
    funnel.utm_source,
    funnel.utm_medium,
    funnel.utm_campaign,
    funnel.device,
    funnel.is_logged_in,
    funnel.page_views,
    funnel.session_duration_seconds,
    funnel.has_add_to_cart,
    funnel.has_begin_checkout,
    funnel.has_purchase,
    funnel.funnel_stage,
    funnel.funnel_step_number

from funnel
left join campaigns
    on funnel.utm_campaign = campaigns.campaign_name
