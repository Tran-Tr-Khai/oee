select
    machine,
    lot,
    beam_no,
    beam_start_date,
    source_updated_at,
    count(*) as duplicate_count
from {{ ref('slv_start_beam') }}
group by 1, 2, 3, 4, 5
having count(*) > 1
