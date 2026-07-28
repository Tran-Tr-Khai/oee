select distinct
    production.machine
from {{ ref('gld_production_daily_fact') }} as production
left join {{ ref('gld_machine_dim') }} as machine_dim
    on machine_dim.machine = production.machine
where machine_dim.machine is null
   or machine_dim.is_in_status_fact = false
