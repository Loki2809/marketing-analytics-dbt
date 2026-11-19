-- dim_customers: one row per real customer (internal test accounts removed).
-- Adds who brought them in (first-touch channel) and a summary of their orders.

with customers as (

    select * from {{ ref('stg_customers') }}
    where not is_test_account

),

first_touch as (

    select
        customer_id,
        channel             as first_touch_channel,
        utm_campaign        as first_touch_campaign,
        session_start       as first_visit_at
    from {{ ref('int_customer_touchpoints') }}
    where is_first_touch

),

-- Summarise orders per customer FIRST, then join (1 row per customer).
-- Joining raw orders directly would repeat each customer once per order ("fan-out").
order_summary as (

    select
        customer_id,
        count(*)                as completed_orders,
        sum(revenue)            as lifetime_revenue,
        min(order_date)         as first_order_date,
        max(order_date)         as last_order_date
    from {{ ref('stg_orders') }}
    where status = 'completed'
      and not is_test_order
    group by customer_id

)

select
    customers.customer_id,
    customers.email,
    customers.country,
    customers.signup_date,

    first_touch.first_touch_channel,
    first_touch.first_touch_campaign,
    first_touch.first_visit_at,

    coalesce(order_summary.completed_orders, 0)     as completed_orders,
    coalesce(order_summary.lifetime_revenue, 0)     as lifetime_revenue,
    order_summary.first_order_date,
    order_summary.last_order_date,
    order_summary.customer_id is not null           as has_purchased,

    customers.updated_at

from customers
left join first_touch
    on customers.customer_id = first_touch.customer_id
left join order_summary
    on customers.customer_id = order_summary.customer_id
