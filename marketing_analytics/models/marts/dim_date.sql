-- dim_date: one row per calendar day, covering all the data up to today.
-- Like a date table in Power BI: join any fact on its date to group by month, week, weekday...
--
-- How it works: Snowflake's generator() makes a list of numbers 0, 1, 2, ...
-- We add each number as days to the first date we need, and stop at today.

with bounds as (

    -- Earliest date in any fact, and today.
    select
        least(
            (select min(spend_date)   from {{ ref('stg_ad_spend') }}),
            (select min(cast(session_start as date)) from {{ ref('stg_web_sessions') }}),
            (select min(order_date)   from {{ ref('stg_orders') }})
        )                   as start_date,
        current_date()      as end_date

),

numbers as (

    -- 3,660 numbers = room for 10 years. row_number() gives 0, 1, 2... with no gaps.
    select row_number() over (order by seq4()) - 1 as n
    from table(generator(rowcount => 3660))

),

days as (

    select dateadd(day, numbers.n, bounds.start_date) as date_day
    from numbers
    cross join bounds          -- bounds has 1 row, so this just attaches start/end to every number
    where dateadd(day, numbers.n, bounds.start_date) <= bounds.end_date

)

select
    date_day,
    year(date_day)                          as year,
    quarter(date_day)                       as quarter,
    month(date_day)                         as month,
    monthname(date_day)                     as month_name,          -- Jan, Feb, ...
    date_trunc('month', date_day)           as month_start,         -- first day of the month
    date_trunc('week', date_day)            as week_start,          -- Monday of that week
    dayofweekiso(date_day)                  as day_of_week,         -- 1 = Monday ... 7 = Sunday
    dayname(date_day)                       as day_name,            -- Mon, Tue, ...
    dayofweekiso(date_day) in (6, 7)        as is_weekend
from days
