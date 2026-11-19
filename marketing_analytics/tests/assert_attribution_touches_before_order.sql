-- Custom (singular) test: attribution must never give credit to a visit that happened AFTER the order.
--
-- How dbt tests work: the query looks for BAD rows.
--   0 rows returned  -> PASS
--   1+ rows returned -> FAIL (the rows show exactly which orders are wrong)
--
-- Rules checked for every order in fct_attribution:
--   1. the last-touch visit started at or before the order
--   2. the first-touch visit started at or before the order
--   3. the first touch is not later than the last touch
--   4. there was at least one visit before the order

select
    order_id,
    customer_id,
    ordered_at,
    first_touch_at,
    last_touch_at,
    touchpoints_before_order
from {{ ref('fct_attribution') }}
where last_touch_at  > ordered_at
   or first_touch_at > ordered_at
   or first_touch_at > last_touch_at
   or coalesce(touchpoints_before_order, 0) < 1
