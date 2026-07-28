{{
    config(
        materialized='table'
    )
}}

with date_bounds as (
    select
        min(date_value) as min_date,
        max(date_value) as max_date
    from (
        select date as date_value
        from {{ ref('gld_production_daily_fact') }}

        union all

        select date as date_value
        from {{ ref('gld_machine_status_daily_fact') }}

        union all

        select beam_start_date as date_value
        from {{ ref('gld_beam_plan_dim') }}
    ) as all_dates
),

calendar_dates as (
    select
        cast(calendar_date as date) as date
    from date_bounds
    cross join lateral generate_series(
        min_date,
        max_date,
        interval 1 day
    ) as generated(calendar_date)
),

final as (
    select
        date,
        cast(strftime(date, '%Y%m%d') as integer) as date_key,
        extract(year from date) as year_number,
        extract(quarter from date) as quarter_number,
        extract(month from date) as month_number,
        strftime(date, '%Y-%m') as year_month,
        strftime(date, '%B') as month_name,
        extract(day from date) as day_of_month,
        extract(week from date) as week_of_year,
        extract(isodow from date) as iso_day_of_week,
        strftime(date, '%A') as day_name,
        case
            when extract(isodow from date) in (6, 7) then true
            else false
        end as is_weekend
    from calendar_dates
)

select
    date,
    date_key,
    year_number,
    quarter_number,
    month_number,
    year_month,
    month_name,
    day_of_month,
    week_of_year,
    iso_day_of_week,
    day_name,
    is_weekend
from final
