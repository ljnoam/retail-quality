SELECT status, COUNT(*) AS orders_count
FROM `bigquery-public-data.thelook_ecommerce.orders`
WHERE created_at >= TIMESTAMP('2024-01-01 00:00:00+00')
  AND created_at < TIMESTAMP('2024-02-01 00:00:00+00')
GROUP BY status
ORDER BY status;
