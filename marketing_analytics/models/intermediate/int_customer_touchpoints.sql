-- int_customer_touchpoints: every visit by a known (logged-in) customer, numbered in time order.
-- A "touchpoint" = one interaction between a customer and the store; here, one visit and
-- the channel that brought them. fct_attribution uses this to decide which channel gets
-- credit for each order (first touch vs last touch).

with sessions as (

    select * from {{ ref('stg_web_sessions') }}
    where customer_id is not null          -- anonymous visits can't be linked to a customer

),

numbered as (

    select
        customer_id,
        session_id,
        session_start,
        channel,
        utm_campaign,
        device,

        -- 1 = the customer's first visit ever, 2 = second visit, ...
        -- (session_id breaks ties if two visits start at the same second)
        row_number() over (
            partition by customer_id
            order by session_start, session_id
        )                                                   as touchpoint_number,

        -- How many visits this customer has in total (same value on each of their rows).
        count(*) over (partition by customer_id)            as total_touchpoints

    from sessions

)

select
    *,
    touchpoint_number = 1                                   as is_first_touch
from numbered
