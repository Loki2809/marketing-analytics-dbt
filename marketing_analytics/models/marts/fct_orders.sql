-- fct_orders: one row per real order.
-- Removes BOTH kinds of test orders (finishing what stg_orders started):
--   * orders with status 'test'              -> stg_orders.is_test_order
--   * orders placed by @test.com accounts    -> stg_customers.is_test_account (needs this join)
-- Keeps completed, returned and cancelled orders; use is_completed for revenue reporting.

with orders as (

    select * from {{ ref('stg_orders') }}

),

customers as (

    select customer_id, is_test_account from {{ ref('stg_customers') }}

),

real_orders as (

    select orders.*
    from orders
    inner join customers
        on orders.customer_id = customers.customer_id
    where not orders.is_test_order
      and not customers.is_test_account

)

select
    order_id,
    customer_id,                         -- links to dim_customers
    ordered_at,                          -- exact time (used for attribution)
    order_date,                          -- links to dim_date
    status,
    status = 'completed'                 as is_completed,
    revenue,
    -- Revenue that counts in reports: only completed orders (returned / cancelled = 0).
    iff(status = 'completed', revenue, 0) as completed_revenue,

    -- 1 = the customer's first completed order, 2 = second, ... (NULL if not completed).
    -- The first completed order is when a visitor becomes a paying ("new") customer: key for CAC.
    case when status = 'completed' then
        row_number() over (
            partition by customer_id, status = 'completed'
            order by ordered_at, order_id
        )
    end                                  as completed_order_number

from real_orders
