SHOW TABLES;

DESCRIBE raw_complete_beam;

SELECT COUNT(*) AS total_rows,
       MIN(TRY_CAST(date AS TIMESTAMP)) AS min_date,
       MAX(TRY_CAST(date AS TIMESTAMP)) AS max_date
FROM raw_complete_beam;

SELECT date, shift, machine, lot, worker, production_qty_kgs
FROM raw_complete_beam
ORDER BY TRY_CAST(date AS TIMESTAMP) DESC, machine, shift, worker
LIMIT 10;

SELECT date, machine, lot, shift, worker, COUNT(*) AS duplicate_count
FROM raw_complete_beam
GROUP BY 1, 2, 3, 4, 5
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, date DESC
LIMIT 20;

DESCRIBE raw_start_beam;

SELECT COUNT(*) AS total_rows,
       MIN(TRY_CAST(beam_start_date AS TIMESTAMP)) AS min_beam_start_date,
       MAX(TRY_CAST(beam_start_date AS TIMESTAMP)) AS max_beam_start_date
FROM raw_start_beam;

SELECT machine_no, beam_start_date, lot_no, beam_no, planned_output, expected_beam_end_at
FROM raw_start_beam
ORDER BY TRY_CAST(beam_start_date AS TIMESTAMP) DESC, machine_no
LIMIT 10;

SELECT machine_no, beam_no, COUNT(*) AS duplicate_count
FROM raw_start_beam
GROUP BY 1, 2
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, machine_no, beam_no
LIMIT 20;

DESCRIBE raw_textile_days;

SELECT COUNT(*) AS total_rows,
       MIN(TRY_CAST(prod_date AS TIMESTAMP)) AS min_prod_date,
       MAX(TRY_CAST(prod_date AS TIMESTAMP)) AS max_prod_date
FROM raw_textile_days;

SELECT prod_date, machine_no, lot_no, meter_reading_m, cut_length_m, prod_output_m
FROM raw_textile_days
ORDER BY TRY_CAST(prod_date AS TIMESTAMP) DESC, machine_no, lot_no
LIMIT 10;

SELECT prod_date, machine_no, lot_no, COUNT(*) AS duplicate_count
FROM raw_textile_days
GROUP BY 1, 2, 3
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, prod_date DESC
LIMIT 20;

SELECT *
FROM raw_textile_days
WHERE prod_date = '2026-06-30'
  AND machine_no = '100'
  AND lot_no = 'SC-1020';

DESCRIBE raw_machine_status;

SELECT COUNT(*) AS total_rows,
       MIN(TRY_CAST(id AS BIGINT)) AS min_id,
       MAX(TRY_CAST(id AS BIGINT)) AS max_id,
       MIN(TRY_CAST(timestamp AS TIMESTAMP)) AS min_timestamp,
       MAX(TRY_CAST(timestamp AS TIMESTAMP)) AS max_timestamp
FROM raw_machine_status;

SELECT id, machine_id, status, timestamp
FROM raw_machine_status
ORDER BY TRY_CAST(id AS BIGINT) DESC
LIMIT 10;

SELECT id, COUNT(*) AS duplicate_count
FROM raw_machine_status
GROUP BY 1
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, id DESC
LIMIT 20;
