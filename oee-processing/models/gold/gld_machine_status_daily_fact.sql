{{
    config(
        materialized='table'
    )
}}

with ordered_status_events as (
    select
        id,
        machine,
        status,
        timestamp as status_started_at,
        lead(timestamp) over (
            partition by machine
            order by timestamp, id
        ) as next_status_started_at
    from {{ ref('slv_machine_status') }}
    where machine is not null
      and status is not null
      and timestamp is not null
),

status_intervals as (
    select
        machine,
        status,
        status_started_at,
        coalesce(
            next_status_started_at,
            date_trunc('day', status_started_at) + interval 1 day
        ) as status_ended_at
    from ordered_status_events
),

valid_intervals as (
    select
        machine,
        status,
        status_started_at,
        status_ended_at
    from status_intervals
    where status_ended_at > status_started_at
),

daily_segments as (
    select
        cast(day_start as date) as date,
        interval_data.machine,
        interval_data.status,
        greatest(interval_data.status_started_at, day_start) as segment_started_at,
        least(interval_data.status_ended_at, day_start + interval 1 day) as segment_ended_at,
        case
            when extract(isodow from day_start) = 7 then day_start + interval 5 hour + interval 30 minute
            when extract(isodow from day_start) = 1 then day_start
        end as planned_shutdown_started_at,
        case
            when extract(isodow from day_start) = 7 then day_start + interval 1 day
            when extract(isodow from day_start) = 1 then day_start + interval 6 hour + interval 30 minute
        end as planned_shutdown_ended_at
    from valid_intervals as interval_data
    cross join lateral generate_series(
        date_trunc('day', interval_data.status_started_at),
        date_trunc('day', interval_data.status_ended_at - interval 1 microsecond),
        interval 1 day
    ) as generated(day_start)
),

daily_status_hours as (
    select
        date,
        machine,
        status,
        (
            sum(date_diff('second', segment_started_at, segment_ended_at))
            - sum(
                case
                    when planned_shutdown_started_at is not null
                     and least(segment_ended_at, planned_shutdown_ended_at) > greatest(segment_started_at, planned_shutdown_started_at)
                        then date_diff(
                            'second',
                            greatest(segment_started_at, planned_shutdown_started_at),
                            least(segment_ended_at, planned_shutdown_ended_at)
                        )
                    else 0
                end
            )
        ) / 3600.0 as status_duration_hours,
        sum(
            case
                when planned_shutdown_started_at is not null
                 and least(segment_ended_at, planned_shutdown_ended_at) > greatest(segment_started_at, planned_shutdown_started_at)
                    then date_diff(
                        'second',
                        greatest(segment_started_at, planned_shutdown_started_at),
                        least(segment_ended_at, planned_shutdown_ended_at)
                    )
                else 0
            end
        ) / 3600.0 as planned_shutdown_hours
    from daily_segments
    group by 1, 2, 3
),

final as (
    select
        date,
        machine,
        sum(case when status = 'running' then status_duration_hours else 0 end) as running_hours,
        sum(case when status = 'stopped' then status_duration_hours else 0 end) as stopped_hours,
        sum(case when status = 'changeover' then status_duration_hours else 0 end) as changeover_hours,
        sum(case when status = 'disconnected' then status_duration_hours else 0 end) as disconnected_hours,
        sum(planned_shutdown_hours) as planned_shutdown_hours
    from daily_status_hours
    group by 1, 2
)

select
    date,
    machine,
    running_hours,
    stopped_hours,
    changeover_hours,
    disconnected_hours,
    planned_shutdown_hours
from final
