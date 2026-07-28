SHOW TABLES;

DESCRIBE gld_date_dim;

SELECT COUNT(*) AS total_rows,
       MIN(date) AS min_date,
       MAX(date) AS max_date
FROM gld_date_dim;

SELECT *
FROM gld_date_dim
ORDER BY date DESC
LIMIT 10;

SELECT date, COUNT(*) AS duplicate_count
FROM gld_date_dim
GROUP BY 1
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, date DESC
LIMIT 20;

DESCRIBE gld_machine_dim;

SELECT COUNT(*) AS total_rows
FROM gld_machine_dim;

SELECT *
FROM gld_machine_dim
ORDER BY machine
LIMIT 20;

SELECT machine, COUNT(*) AS duplicate_count
FROM gld_machine_dim
GROUP BY 1
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, machine
LIMIT 20;

DESCRIBE gld_beam_plan_dim;

SELECT COUNT(*) AS total_rows,
       MIN(beam_start_date) AS min_beam_start_date,
       MAX(beam_start_date) AS max_beam_start_date
FROM gld_beam_plan_dim;

SELECT *
FROM gld_beam_plan_dim
ORDER BY beam_start_date DESC, machine, lot, beam_no
LIMIT 20;

SELECT beam_plan_key, COUNT(*) AS duplicate_count
FROM gld_beam_plan_dim
GROUP BY 1
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, beam_plan_key
LIMIT 20;

DESCRIBE gld_production_daily_fact;

SELECT COUNT(*) AS total_rows,
       MIN(date) AS min_date,
       MAX(date) AS max_date
FROM gld_production_daily_fact;

SELECT *
FROM gld_production_daily_fact
ORDER BY date DESC, machine, lot
LIMIT 20;

SELECT date, machine, lot, COUNT(*) AS duplicate_count
FROM gld_production_daily_fact
GROUP BY 1, 2, 3
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, date DESC, machine, lot
LIMIT 20;

SELECT is_start_beam, COUNT(*) AS row_count
FROM gld_production_daily_fact
GROUP BY 1
ORDER BY is_start_beam DESC;

SELECT COUNT(*) AS missing_beam_plan_key_rows
FROM gld_production_daily_fact
WHERE beam_plan_key IS NULL;

DESCRIBE gld_machine_status_daily_fact;

SELECT COUNT(*) AS total_rows,
       MIN(date) AS min_date,
       MAX(date) AS max_date
FROM gld_machine_status_daily_fact;

SELECT *
FROM gld_machine_status_daily_fact
ORDER BY date DESC, machine
LIMIT 20;

SELECT date, machine, COUNT(*) AS duplicate_count
FROM gld_machine_status_daily_fact
GROUP BY 1, 2
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, date DESC, machine
LIMIT 20;

SELECT SUM(running_hours) AS total_running_hours,
       SUM(stopped_hours) AS total_stopped_hours,
       SUM(changeover_hours) AS total_changeover_hours,
       SUM(disconnected_hours) AS total_disconnected_hours
FROM gld_machine_status_daily_fact;
