-- stg_web_sessions: one clean row per website visit.
-- Cleaning done here:
--   * utm_source: 'Google'/'GOOGLE' -> 'google'; 'fb'/'Facebook' -> 'facebook'
--   * add channel: the marketing channel behind the visit, using the same names as
--     stg_ad_spend and stg_campaigns ('google', 'meta', 'email'), or 'direct' when the
--     visit has no UTM tags (typed URL, bookmark... or an ad link that lost its tags)
--   * text -> real TIMESTAMP
--   * add is_logged_in: TRUE when we know which customer it was

with source as (

    select * from {{ source('raw', 'web_sessions') }}

),

cleaned as (

    select
        session_id,
        customer_id,                                        -- NULL = anonymous visitor
        cast(session_start as timestamp_ntz)                as session_start,

        case
            when lower(trim(utm_source)) in ('fb', 'facebook') then 'facebook'
            else lower(trim(utm_source))
        end                                                 as utm_source,
        lower(trim(utm_medium))                             as utm_medium,
        trim(utm_campaign)                                  as utm_campaign,
        lower(trim(device))                                 as device,

        cast(_loaded_at as timestamp_ntz)                   as loaded_at

    from source

),

final as (

    select
        session_id,
        customer_id,
        session_start,

        -- No UTM tags -> 'direct'. Otherwise map the source with the shared macro
        -- (macros/clean_channel.sql): google -> google, facebook -> meta, email -> email.
        -- Note: "when null" would never match in SQL (NULL is never equal to anything),
        -- so missing tags are handled with "is null".
        case
            when utm_source is null then 'direct'
            else {{ clean_channel('utm_source') }}
        end                                                 as channel,

        utm_source,
        utm_medium,
        utm_campaign,
        device,
        customer_id is not null                             as is_logged_in,
        loaded_at

    from cleaned

)

select * from final
