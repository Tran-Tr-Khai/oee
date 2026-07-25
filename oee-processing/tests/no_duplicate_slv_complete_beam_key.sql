select
    date,
    machine,
    lot,
    shift,
    worker,
    count(*) as duplicate_count
from {{ ref('slv_complete_beam') }}
group by 1, 2, 3, 4, 5
having count(*) > 1
