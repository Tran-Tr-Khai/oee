{{
    config(
        materialized='incremental',
        unique_key=['date', 'machine', 'lot']
    )
}}

with source as (
    select *
    from {{ source('raw', 'raw_textile_days') }}
),

typed as (
    select
        cast(try_cast(prod_date as timestamp) as date) as date,
        {{ standardize_machine('machine_no') }} as machine,
        {{ clean_code('lot_no') }} as lot,
        try_cast(prod_output_m as double) as production_qty_mts,
        try_cast(meter_reading_m as double) as meter_reading_m,
        try_cast(cut_length_m as double) as cut_length_m
    from source
),

deduped as (
    select
        *,
        row_number() over (
            partition by date, machine, lot
            order by
                production_qty_mts desc nulls last,
                meter_reading_m desc nulls last,
                cut_length_m desc nulls last
        ) as row_priority
    from typed
    where date is not null
      and machine is not null
      and lot is not null
),

final as (
    select
        date,
        machine,
        lot,
        production_qty_mts,
        meter_reading_m,
        cut_length_m
    from deduped
    where row_priority = 1
)

select
    date,
    machine,
    lot,
    production_qty_mts,
    meter_reading_m,
    cut_length_m
from final
{% if is_incremental() %}
where not exists (
    select 1
    from {{ this }} existing
    where existing.date = final.date
      and existing.machine = final.machine
      and existing.lot = final.lot
)
{% endif %}
