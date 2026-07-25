select
    date,
    machine,
    lot,
    count(*) as duplicate_count
from {{ ref('slv_textile_days') }}
group by 1, 2, 3
having count(*) > 1
