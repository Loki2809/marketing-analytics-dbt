-- fct_sessions: one row per website visit, with funnel progress.
-- Built on int_sessions_funnel; adds campaign_id so visits link to dim_campaigns.
--
-- INCREMENTAL model: instead of rebuilding all visits on every run, dbt only processes
-- recent visits and merges them into the existing table.
--   * First run (or `--full-refresh`): builds the whole table, like a normal table.
--   * Later runs: only visits that started in the last N days (lookback window, default 3)
--     are re-processed. MERGE on session_id updates rows that already exist (e.g. a visit
--     that got more events after the last run) and inserts the new ones.
-- The lookback catches "late-arriving" data: events that reach the warehouse after their visit
-- was first loaded. Change it with: dbt build --vars '{sessions_lookback_days: 7}'

{{
    config(
        materialized='incremental',
        unique_key='session_id',
        incremental_strategy='merge',
        on_schema_change='append_new_columns'
    )
}}

with funnel as (

    select * from {{ ref('int_sessions_funnel') }}

    {% if is_incremental() %}
    -- Only on incremental runs: keep visits from the last N days before the newest visit
    -- already in this table. {{ this }} = this model's own table in Snowflake.
    where session_start >= (
        select dateadd(day, -{{ var('sessions_lookback_days', 3) }}, max(session_start))
        from {{ this }}
    )
    {% endif %}

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
    funnel.funnel_step_number,

    -- When dbt last wrote this row. Shows which rows an incremental run touched.
    current_timestamp()                  as dbt_processed_at

from funnel
left join campaigns
    on funnel.utm_campaign = campaigns.campaign_name
