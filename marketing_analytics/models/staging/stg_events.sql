-- stg_events: one clean row per action inside a website visit.
-- Cleaning done here:
--   * remove exact duplicate rows (the same event loaded twice)
--   * event_name trimmed and lowercased
--   * text -> real TIMESTAMP

with source as (

    select * from {{ source('raw', 'events') }}

),

cleaned as (

    select
        event_id,
        session_id,
        lower(trim(event_name))                 as event_name,
        cast(event_timestamp as timestamp_ntz)  as event_timestamp,
        cast(_loaded_at as timestamp_ntz)       as loaded_at

    from source

),

deduplicated as (

    select *
    from cleaned
    -- Same pattern as stg_customers: number the copies of each event_id, keep the first.
    qualify row_number() over (partition by event_id order by loaded_at) = 1

)

select * from deduplicated
