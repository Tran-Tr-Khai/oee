{{
    config(
        materialized='table'
    )
}}

with textile_days as (
    select
        date,
        machine,
        lot,
        production_qty_mts,
        meter_reading_m,
        cut_length_m
    from {{ ref('slv_textile_days') }}
),

status_machines as (
    select distinct
        machine
    from {{ ref('gld_machine_status_daily_fact') }}
),

beam_plan_dim as (
    select
        beam_plan_key,
        machine,
        lot,
        beam_no,
        beam_start_date
    from {{ ref('gld_beam_plan_dim') }}
),

beam_plan_ranges as (
    select
        beam_plan_key,
        machine,
        lot,
        beam_no,
        beam_start_date,
        lead(beam_start_date) over (
            partition by machine, lot
            order by beam_start_date, beam_no
        ) as next_beam_start_date
    from beam_plan_dim
),

start_beam_machine_dates as (
    select distinct
        beam_start_date as date,
        machine
    from beam_plan_dim
),

final as (
    select
        td.date,
        td.machine,
        td.lot,
        td.production_qty_mts,
        td.meter_reading_m,
        td.cut_length_m,
        case
            when sbmd.machine is not null then true
            else false
        end as is_start_beam,
        bpr.beam_plan_key
    from textile_days as td
    inner join status_machines
        on status_machines.machine = td.machine
    left join start_beam_machine_dates as sbmd
        on sbmd.date = td.date
       and sbmd.machine = td.machine
    left join beam_plan_ranges as bpr
        on bpr.machine = td.machine
       and bpr.lot = td.lot
       and td.date >= bpr.beam_start_date
       and (
            bpr.next_beam_start_date is null
            or td.date < bpr.next_beam_start_date
       )
)

select
    date,
    machine,
    lot,
    production_qty_mts,
    meter_reading_m,
    cut_length_m,
    is_start_beam,
    beam_plan_key
from final
