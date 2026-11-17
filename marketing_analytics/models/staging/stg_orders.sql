-- stg_orders: one clean row per order.
-- Cleaning done here:
--   * remove exact duplicate rows (the same order loaded twice)
--   * status: 'Completed' / 'COMPLETED' -> 'completed' (all lowercase)
--   * text -> real types: TIMESTAMP, DATE, money with 2 decimals
--   * order_date holds a date AND time, so it becomes ordered_at (timestamp) + order_date (date)
--   * flag test orders (status 'test') instead of deleting them.
--     Orders from test accounts are caught via stg_customers.is_test_account in the marts.

with source as (

    select * from {{ source('raw', 'orders') }}

),

cleaned as (

    select
        order_id,
        customer_id,
        cast(order_date as timestamp_ntz)           as ordered_at,
        cast(order_date as date)                    as order_date,
        cast(revenue as number(12, 2))              as revenue,
        lower(trim(status))                         as status,
        lower(trim(status)) = 'test'                as is_test_order,
        cast(_loaded_at as timestamp_ntz)           as loaded_at

    from source

),

deduplicated as (

    select *
    from cleaned
    qualify row_number() over (partition by order_id order by loaded_at) = 1

)

select * from deduplicated
