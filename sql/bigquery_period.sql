-- Period diagnostics: real counts and boundary dates must be recorded from a job.
SELECT 'orders' AS source_table, MIN(DATE(created_at, 'UTC')) AS first_date,
       MAX(DATE(created_at, 'UTC')) AS last_date, COUNT(*) AS row_count
FROM `bigquery-public-data.thelook_ecommerce.orders`
UNION ALL
SELECT 'order_items', MIN(DATE(created_at, 'UTC')),
       MAX(DATE(created_at, 'UTC')), COUNT(*)
FROM `bigquery-public-data.thelook_ecommerce.order_items`;
