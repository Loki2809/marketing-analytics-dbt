-- fct_attribution: one row per real order, with which channel gets the credit.
--   * first touch = the channel of the customer's very first visit (who FOUND them)
--   * last touch  = the channel of their last visit at or before the order (who CLOSED the sale)
-- Orders have no session_id, so we match on customer_id AND time (a "time-based join").

with orders as (

    select * from {{ ref('fct_orders') }}

),

touchpoints as (

    select * from {{ ref('int_customer_touchpoints') }}

),

-- Every visit the customer made up to the moment of the order.
-- The join condition has two parts: same customer, AND the visit started before (or at) the order time.
order_touchpoints as (

    select
        orders.order_id,
        touchpoints.session_id,
        touchpoints.session_start,
        touchpoints.channel,
        touchpoints.utm_campaign,
        touchpoints.touchpoint_number
    from orders
    inner join touchpoints
        on  orders.customer_id = touchpoints.customer_id
        and touchpoints.session_start <= orders.ordered_at

),

first_touch as (

    select
        order_id,
        channel         as first_touch_channel,
        utm_campaign    as first_touch_campaign,
        session_start   as first_touch_at
    from order_touchpoints
    where touchpoint_number = 1

),

last_touch as (

    select
        order_id,
        session_id      as last_touch_session_id,
        channel         as last_touch_channel,
        utm_campaign    as last_touch_campaign,
        session_start   as last_touch_at
    from order_touchpoints
    -- Newest visit first; keep only that one per order.
    qualify row_number() over (
        partition by order_id
        order by session_start desc, session_id desc
    ) = 1

),

touch_counts as (

    select order_id, count(*) as touchpoints_before_order
    from order_touchpoints
    group by order_id

)

select
    orders.order_id,
    orders.customer_id,
    orders.ordered_at,
    orders.order_date,
    orders.status,
    orders.is_completed,
    orders.completed_revenue,
    orders.completed_order_number,

    first_touch.first_touch_channel,
    first_touch.first_touch_campaign,
    first_touch.first_touch_at,

    last_touch.last_touch_channel,
    last_touch.last_touch_campaign,
    last_touch.last_touch_at,
    last_touch.last_touch_session_id,

    touch_counts.touchpoints_before_order,
    datediff('day', first_touch.first_touch_at, orders.ordered_at)  as days_from_first_touch,
    first_touch.first_touch_channel = last_touch.last_touch_channel as is_same_channel

from orders
left join first_touch  on orders.order_id = first_touch.order_id
left join last_touch   on orders.order_id = last_touch.order_id
left join touch_counts on orders.order_id = touch_counts.order_id
