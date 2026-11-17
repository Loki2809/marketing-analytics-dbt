-- stg_customers: one clean row per customer (their latest version).
-- Cleaning done here:
--   * keep only the newest row per customer -> removes older versions AND exact duplicates
--   * emails: remove spaces around them, make lowercase
--   * countries: 'usa', 'United States', 'U.S.' -> 'US'; other codes trimmed and uppercased
--   * text -> real DATE / TIMESTAMP
--   * flag internal test accounts (@test.com) instead of deleting them, so orders that
--     point to them stay traceable. Marts will filter them out.
-- Full change history (old countries etc.) will be kept by a snapshot in M4.

with source as (

    select * from {{ source('raw', 'customers') }}

),

cleaned as (

    select
        customer_id,
        lower(trim(email))                          as email,
        cast(signup_date as date)                   as signup_date,

        case
            when upper(trim(country)) in ('US', 'USA', 'U.S.', 'UNITED STATES') then 'US'
            else upper(trim(country))
        end                                         as country,    -- NULL stays NULL (unknown)

        cast(updated_at as timestamp_ntz)           as updated_at,
        lower(trim(email)) like '%@test.com'        as is_test_account,
        cast(_loaded_at as timestamp_ntz)           as loaded_at

    from source

),

latest as (

    select *
    from cleaned
    -- row_number() numbers each customer's rows 1, 2, 3... starting from the newest.
    -- qualify keeps only row 1 = the latest version. Exact duplicates get 2, 3... and are dropped too.
    qualify row_number() over (partition by customer_id order by updated_at desc) = 1

)

select * from latest
