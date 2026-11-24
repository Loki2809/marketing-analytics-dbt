-- Custom (singular) test: the KPI mart must add up to the same totals as the fact tables.
-- If a join drops or duplicates rows (or a channel/month is missing from the spine),
-- a total will be off and this test returns a row describing the difference.
-- 0 rows returned = PASS.

with mart as (

    select
        sum(spend)                  as spend,
        sum(sessions)               as sessions,
        sum(new_customers)          as new_customers,
        sum(revenue_first_touch)    as revenue_first_touch,
        sum(revenue_last_touch)     as revenue_last_touch
    from {{ ref('mart_marketing_kpis') }}

),

facts as (

    select
        (select sum(spend) from {{ ref('fct_ad_spend_daily') }})                          as spend,
        (select count(*)   from {{ ref('fct_sessions') }})                                as sessions,
        (select count(*)   from {{ ref('fct_orders') }} where completed_order_number = 1) as new_customers,
        (select sum(completed_revenue) from {{ ref('fct_orders') }})                      as revenue

),

checks as (

    select 'spend' as metric, mart.spend as mart_total, facts.spend as fact_total from mart, facts
    union all
    select 'sessions', mart.sessions, facts.sessions from mart, facts
    union all
    select 'new_customers', mart.new_customers, facts.new_customers from mart, facts
    union all
    select 'revenue_first_touch', mart.revenue_first_touch, facts.revenue from mart, facts
    union all
    select 'revenue_last_touch', mart.revenue_last_touch, facts.revenue from mart, facts

)

select *
from checks
where abs(coalesce(mart_total, 0) - coalesce(fact_total, 0)) > 0.01
