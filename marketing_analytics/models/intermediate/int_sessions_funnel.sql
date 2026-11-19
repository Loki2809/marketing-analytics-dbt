-- int_sessions_funnel: one row per website visit, with how far it got in the funnel.
-- Logic:
--   1. Summarise stg_events per visit: how many page views, and did it reach each step?
--   2. Join that summary onto stg_web_sessions (visit details: channel, customer, device...).
--   3. Name the deepest step reached (funnel_stage), so drop-off is easy to count.

with sessions as (

    select * from {{ ref('stg_web_sessions') }}

),

events as (

    select * from {{ ref('stg_events') }}

),

events_per_session as (

    select
        session_id,
        count_if(event_name = 'page_view')          as page_views,
        count_if(event_name = 'add_to_cart')    > 0 as has_add_to_cart,
        count_if(event_name = 'begin_checkout') > 0 as has_begin_checkout,
        count_if(event_name = 'purchase')       > 0 as has_purchase,
        min(event_timestamp)                        as first_event_at,
        max(event_timestamp)                        as last_event_at
    from events
    group by session_id

),

joined as (

    select
        sessions.session_id,
        sessions.customer_id,
        sessions.session_start,
        cast(sessions.session_start as date)                    as session_date,
        sessions.channel,
        sessions.utm_source,
        sessions.utm_medium,
        sessions.utm_campaign,
        sessions.device,
        sessions.is_logged_in,

        -- coalesce = "use this value, or the fallback if it's NULL" (a visit with no events)
        coalesce(e.page_views, 0)                               as page_views,
        coalesce(e.has_add_to_cart, false)                      as has_add_to_cart,
        coalesce(e.has_begin_checkout, false)                   as has_begin_checkout,
        coalesce(e.has_purchase, false)                         as has_purchase,
        datediff('second', e.first_event_at, e.last_event_at)   as session_duration_seconds

    from sessions
    left join events_per_session as e
        on sessions.session_id = e.session_id

),

final as (

    select
        *,
        -- The deepest funnel step this visit reached.
        case
            when has_purchase       then 'purchase'
            when has_begin_checkout then 'begin_checkout'
            when has_add_to_cart    then 'add_to_cart'
            when page_views > 0     then 'page_view'
            else 'no_events'
        end                                                     as funnel_stage,
        -- The same as a number (1-4), handy for sorting in reports.
        case
            when has_purchase       then 4
            when has_begin_checkout then 3
            when has_add_to_cart    then 2
            when page_views > 0     then 1
            else 0
        end                                                     as funnel_step_number
    from joined

)

select * from final
