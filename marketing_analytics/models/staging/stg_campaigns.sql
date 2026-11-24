-- stg_campaigns: one clean row per marketing campaign.
-- Cleaning done here:
--   * channel labels ('Google Ads', 'Meta Ads', 'Email') -> standard names ('google', 'meta', 'email')
--   * text dates -> real DATE columns
--   * flag campaigns that are still running (no end date)

with source as (

    select * from {{ source('raw', 'campaigns') }}

),

cleaned as (

    select
        campaign_id,
        campaign_name,

        -- Standard channel names (macros/clean_channel.sql), shared with ad_spend and web_sessions.
        {{ clean_channel('channel') }} as channel,

        cast(start_date as date)    as start_date,
        cast(end_date as date)      as end_date,        -- NULL = still running
        end_date is null            as is_always_on,

        cast(_loaded_at as timestamp_ntz) as loaded_at

    from source

)

select * from cleaned
