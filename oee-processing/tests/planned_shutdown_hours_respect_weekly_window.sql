select
    date,
    machine,
    planned_shutdown_hours
from {{ ref('gld_machine_status_daily_fact') }}
where (
        extract(isodow from date) = 7
        and planned_shutdown_hours > 18.5001
    )
   or (
        extract(isodow from date) = 1
        and planned_shutdown_hours > 6.5001
    )
   or (
        extract(isodow from date) not in (1, 7)
        and planned_shutdown_hours > 0.0001
    )
