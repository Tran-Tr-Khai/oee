{{
    config(
        materialized='table'
    )
}}

with latest_beam_plan as (
    select
        machine,
        lot,
        beam_no,
        beam_start_date,
        total_yarn,
        length_m,
        planned_output,
        expected_beam_end_at,
        daily_output_mts as planned_daily_output_mts,
        source_updated_at,
        row_number() over (
            partition by machine, lot, beam_no, beam_start_date
            order by source_updated_at desc nulls last
        ) as row_priority
    from {{ ref('slv_start_beam') }}
),

final as (
    select
        concat_ws(
            '|',
            machine,
            lot,
            cast(beam_start_date as varchar),
            beam_no
        ) as beam_plan_key,
        machine,
        lot,
        beam_no,
        beam_start_date,
        total_yarn,
        length_m,
        planned_output,
        expected_beam_end_at,
        planned_daily_output_mts,
        source_updated_at
    from latest_beam_plan
    where row_priority = 1
)

select
    beam_plan_key,
    machine,
    lot,
    beam_no,
    beam_start_date,
    total_yarn,
    length_m,
    planned_output,
    expected_beam_end_at,
    planned_daily_output_mts,
    source_updated_at
from final
