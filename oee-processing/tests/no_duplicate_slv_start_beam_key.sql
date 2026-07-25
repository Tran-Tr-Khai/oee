select
    machine,
    lot,
    beam_no,
    beam_start_date,
    count(*) as duplicate_count
from {{ ref('slv_start_beam') }}
group by 1, 2, 3, 4
having count(*) > 1
