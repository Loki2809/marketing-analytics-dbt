-- mart_marketing_kpis: one row per month per channel with the KPIs leadership asked for.
--
-- Attribution choices (metric definitions are business decisions):
--   * new customers & CAC  -> FIRST touch  (a customer is acquired by the channel that found them)
--   * revenue & ROAS       -> BOTH first touch and last touch, side by side
--   * sessions & conversion -> the visit's own channel
-- Revenue = completed orders only. 'direct' has no ad spend, so its CAC and ROAS are NULL.
-- Every month x channel combination appears (zeros where nothing happened), so charts have no gaps.

with months as (

    select distinct month_start from {{ ref('dim_date') }}

),

channels as (

    select column1 as channel
    from values ('google'), ('meta'), ('email'), ('direct')

),

-- The "spine": every month for every channel. Everything else is left-joined onto it.
spine as (

    select months.month_start, channels.channel
    from months
    cross join channels

),

spend as (

    select
        date_trunc('month', spend_date)     as month_start,
        channel,
        sum(spend)                          as spend,
        sum(impressions)                    as impressions,
        sum(clicks)                         as clicks
    from {{ ref('fct_ad_spend_daily') }}
    group by 1, 2

),

sessions as (

    select
        date_trunc('month', session_date)   as month_start,
        channel,
        count(*)                            as sessions,
        count_if(has_add_to_cart)           as add_to_cart_sessions,
        count_if(has_begin_checkout)        as checkout_sessions,
        count_if(has_purchase)              as purchase_sessions
    from {{ ref('fct_sessions') }}
    group by 1, 2

),

-- New paying customers: their first completed order, credited to their first-touch channel.
new_customers as (

    select
        date_trunc('month', orders.order_date)  as month_start,
        customers.first_touch_channel           as channel,
        count(*)                                as new_customers
    from {{ ref('fct_orders') }} as orders
    inner join {{ ref('dim_customers') }} as customers
        on orders.customer_id = customers.customer_id
    where orders.completed_order_number = 1
    group by 1, 2

),

revenue_first_touch as (

    select
        date_trunc('month', order_date)     as month_start,
        first_touch_channel                 as channel,
        count_if(is_completed)              as orders_first_touch,
        sum(completed_revenue)              as revenue_first_touch
    from {{ ref('fct_attribution') }}
    group by 1, 2

),

revenue_last_touch as (

    select
        date_trunc('month', order_date)     as month_start,
        last_touch_channel                  as channel,
        count_if(is_completed)              as orders_last_touch,
        sum(completed_revenue)              as revenue_last_touch
    from {{ ref('fct_attribution') }}
    group by 1, 2

),

joined as (

    select
        spine.month_start,
        spine.channel,

        coalesce(spend.spend, 0)                            as spend,
        coalesce(spend.impressions, 0)                      as impressions,
        coalesce(spend.clicks, 0)                           as clicks,

        coalesce(sessions.sessions, 0)                      as sessions,
        coalesce(sessions.add_to_cart_sessions, 0)          as add_to_cart_sessions,
        coalesce(sessions.checkout_sessions, 0)             as checkout_sessions,
        coalesce(sessions.purchase_sessions, 0)             as purchase_sessions,

        coalesce(new_customers.new_customers, 0)            as new_customers,

        coalesce(revenue_first_touch.orders_first_touch, 0)  as orders_first_touch,
        coalesce(revenue_first_touch.revenue_first_touch, 0) as revenue_first_touch,
        coalesce(revenue_last_touch.orders_last_touch, 0)    as orders_last_touch,
        coalesce(revenue_last_touch.revenue_last_touch, 0)   as revenue_last_touch

    from spine
    left join spend
        on spine.month_start = spend.month_start and spine.channel = spend.channel
    left join sessions
        on spine.month_start = sessions.month_start and spine.channel = sessions.channel
    left join new_customers
        on spine.month_start = new_customers.month_start and spine.channel = new_customers.channel
    left join revenue_first_touch
        on spine.month_start = revenue_first_touch.month_start and spine.channel = revenue_first_touch.channel
    left join revenue_last_touch
        on spine.month_start = revenue_last_touch.month_start and spine.channel = revenue_last_touch.channel

)

select
    channel || '|' || to_varchar(month_start, 'YYYY-MM')       as kpi_id,
    month_start,
    channel,
    *  exclude (month_start, channel),

    -- Ratios. nullif(x, 0) turns 0 into NULL, so dividing by it gives NULL instead of an error.
    -- No spend (direct) -> CAC and ROAS are NULL: "not applicable", not "zero".
    round(nullif(spend, 0) / nullif(new_customers, 0), 2)       as cac,
    round(revenue_first_touch / nullif(spend, 0), 2)            as roas_first_touch,
    round(revenue_last_touch  / nullif(spend, 0), 2)            as roas_last_touch,
    round(purchase_sessions / nullif(sessions, 0), 4)           as conversion_rate,
    round(add_to_cart_sessions / nullif(sessions, 0), 4)        as add_to_cart_rate,
    round(div0null(clicks, impressions), 4)                     as ctr

from joined
