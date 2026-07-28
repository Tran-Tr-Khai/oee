SHOW TABLES;

DESCRIBE slv_complete_beam;

SELECT COUNT(*) AS total_rows
FROM slv_complete_beam;

SELECT *
FROM slv_complete_beam
LIMIT 10;

DESCRIBE slv_start_beam;

SELECT COUNT(*) AS total_rows
FROM slv_start_beam;

SELECT *
FROM slv_start_beam
LIMIT 10;

DESCRIBE slv_textile_days;

SELECT COUNT(*) AS total_rows,
       MIN(TRY_CAST(date AS TIMESTAMP)) AS min_date,
       MAX(TRY_CAST(date AS TIMESTAMP)) AS max_date
FROM slv_textile_days;

SELECT *
FROM slv_textile_days
ORDER BY TRY_CAST(date AS TIMESTAMP) DESC, machine, lot
LIMIT 10;

SELECT machine, date, lot, COUNT(*) AS duplicate_count
FROM slv_textile_days
GROUP BY 1, 2, 3
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, date DESC
LIMIT 20;

DESCRIBE slv_machine_status;

SELECT COUNT(*) AS total_rows
FROM slv_machine_status;

SELECT *
FROM slv_machine_status
LIMIT 10;


SELECT 'slv_textile_days' AS table_name, COUNT(DISTINCT machine) AS machine_count
FROM slv_textile_days
UNION ALL
SELECT 'slv_start_beam' AS table_name, COUNT(DISTINCT machine) AS machine_count
FROM slv_start_beam
UNION ALL
SELECT 'slv_complete_beam' AS table_name, COUNT(DISTINCT machine) AS machine_count
FROM slv_complete_beam
UNION ALL
SELECT 'slv_machine_status' AS table_name, COUNT(DISTINCT machine) AS machine_count
FROM slv_machine_status;