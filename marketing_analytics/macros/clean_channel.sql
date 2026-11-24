{#
  clean_channel: turn any spelling of a marketing channel into a standard name.

    'Google Ads', 'google_ads', 'GOOGLE'  -> 'google'
    'Meta Ads', 'META', 'facebook', 'fb'  -> 'meta'
    'Email', 'email'                      -> 'email'
    anything else                         -> NULL (so a not_null / accepted_values test catches it)

  Usage in a model:   {{ clean_channel('channel') }} as channel
  dbt replaces the call with the CASE expression below before sending the SQL to Snowflake.
  To support a new channel or spelling, change it HERE and every model picks it up.
#}

{% macro clean_channel(column_name) %}
    case
        when lower(trim({{ column_name }})) in ('google', 'google ads', 'google_ads')                 then 'google'
        when lower(trim({{ column_name }})) in ('meta', 'meta ads', 'meta_ads', 'facebook', 'fb')    then 'meta'
        when lower(trim({{ column_name }})) in ('email')                                            then 'email'
    end
{% endmacro %}
