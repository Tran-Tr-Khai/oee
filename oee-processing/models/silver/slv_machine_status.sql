{{
    config(
        materialized='incremental',
        unique_key='id'
    )
}}

with source as (
    select *
    from {{ source('raw', 'raw_machine_status') }}
    {% if is_incremental() %}
    where try_cast(id as bigint) > (
        select coalesce(max(id), 0)
        from {{ this }}
    )
    {% endif %}
),

typed as (
    select
        try_cast(id as bigint) as id,
        {{ standardize_machine('machine_id') }} as machine,
        lower({{ clean_text('status') }}) as status,
        try_cast(timestamp as timestamp) as timestamp
    from source
)

select
    id,
    machine,
    status,
    timestamp,
    cast(timestamp as date) as date
from typed
where id is not null
  and machine is not null
  and timestamp is not null
