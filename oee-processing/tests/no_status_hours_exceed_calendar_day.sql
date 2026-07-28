select
    date,
    machine,
    running_hours,
    stopped_hours,
    changeover_hours,
    disconnected_hours,
    planned_shutdown_hours
from {{ ref('gld_machine_status_daily_fact') }}
where running_hours < 0
   or stopped_hours < 0
   or changeover_hours < 0
   or disconnected_hours < 0
   or planned_shutdown_hours < 0
   or (
        running_hours
        + stopped_hours
        + changeover_hours
        + disconnected_hours
        + planned_shutdown_hours
   ) > 24.0001
