{{
    config(
        materialized='incremental',
        unique_key=['machine', 'lot', 'beam_no', 'beam_start_date']
    )
}}

with source as (
    select *
    from {{ source('raw', 'raw_start_beam') }}
),

typed as (
    select
        case
            when {{ clean_text('machine_no') }} is null then null
            when regexp_matches({{ clean_text('machine_no') }}, '^[0-9]+(\.0)?$') then
                'WEV' || lpad(cast(cast(cast({{ clean_text('machine_no') }} as double) as bigint) as varchar), 3, '0')
            else upper({{ clean_text('machine_no') }})
        end as machine,
        {{ clean_code('lot_no') }} as lot,
        try_cast(beam_start_date as timestamp) as raw_beam_start_date,
        {{ clean_text('beam_no') }} as beam_no,
        try_cast(planned_output as double) as planned_output,
        try_cast(expected_beam_end_at as timestamp) as expected_beam_end_at,
        try_cast(daily_output_mts as double) as daily_output_mts
    from source
),

cleaned as (
    select
        machine,
        lot,
        case
            when raw_beam_start_date <= timestamp '1970-01-02' then null
            else raw_beam_start_date
        end as beam_start_date,
        beam_no,
        planned_output,
        expected_beam_end_at,
        daily_output_mts
    from typed
    where machine is not null
      and lot is not null
),

final as (
    select
        cast(beam_start_date as date) as date,
        machine,
        lot,
        beam_start_date,
        beam_no,
        planned_output,
        expected_beam_end_at,
        daily_output_mts,
        true as is_beam_start
    from cleaned
    where beam_start_date is not null
)

select *
from final
{% if is_incremental() %}
where not exists (
    select 1
    from {{ this }} existing
    where existing.machine = final.machine
      and existing.lot = final.lot
      and existing.beam_no = final.beam_no
      and existing.beam_start_date = final.beam_start_date
)
{% endif %}
