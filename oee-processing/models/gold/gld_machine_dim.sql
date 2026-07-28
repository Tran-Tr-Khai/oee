{{
    config(
        materialized='table'
    )
}}

with production_machines as (
    select distinct
        machine
    from {{ ref('gld_production_daily_fact') }}
),

status_machines as (
    select distinct
        machine
    from {{ ref('gld_machine_status_daily_fact') }}
),

beam_plan_machines as (
    select distinct
        machine
    from {{ ref('gld_beam_plan_dim') }}
),

all_machines as (
    select machine from status_machines
),

final as (
    select
        all_machines.machine,
        case
            when production_machines.machine is not null then true
            else false
        end as is_in_production_fact,
        case
            when status_machines.machine is not null then true
            else false
        end as is_in_status_fact,
        case
            when beam_plan_machines.machine is not null then true
            else false
        end as is_in_beam_plan_dim
    from all_machines
    left join production_machines
        on production_machines.machine = all_machines.machine
    left join status_machines
        on status_machines.machine = all_machines.machine
    left join beam_plan_machines
        on beam_plan_machines.machine = all_machines.machine
)

select
    machine,
    is_in_production_fact,
    is_in_status_fact,
    is_in_beam_plan_dim
from final
