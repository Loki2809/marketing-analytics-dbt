-- stg_ad_spend: one clean row per campaign per day.
-- Cleaning done here:
--   * messy channel names ('Google Ads', 'google_ads', 'META', ...) -> 'google' / 'meta' / 'email'
--   * text -> real types (DATE, whole numbers, money with 2 decimals)
--   * rename columns: date -> spend_date, campaign -> campaign_name
--   * add ad_spend_id, a key made from campaign + day, so we can test one row per campaign per day
-- Missing clicks stay NULL ("unknown"), not 0: we don't know there were no clicks.

with source as (

    select * from {{ source('raw', 'ad_spend') }}

),

cleaned as (

    select
        campaign || '|' || date             as ad_spend_id,
        cast(date as date)                  as spend_date,

        {{ clean_channel('channel') }}      as channel,     -- macros/clean_channel.sql

        campaign                            as campaign_name,
        cast(impressions as integer)        as impressions,
        cast(clicks as integer)             as clicks,          -- NULL = not reported
        cast(spend as number(12, 2))        as spend,

        cast(_loaded_at as timestamp_ntz)   as loaded_at

    from source

)

select * from cleaned
