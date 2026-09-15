-- Deliberately wider projection for a dry-run comparison. No claim of speedup
-- follows from this query unless the measured job metadata supports it.
SELECT oi.*, o.*, p.*
FROM `bigquery-public-data.thelook_ecommerce.order_items` AS oi
LEFT JOIN `bigquery-public-data.thelook_ecommerce.orders` AS o
    ON o.order_id = oi.order_id
LEFT JOIN `bigquery-public-data.thelook_ecommerce.products` AS p
    ON p.id = oi.product_id
WHERE oi.created_at >= TIMESTAMP('2024-01-01 00:00:00+00')
  AND oi.created_at < TIMESTAMP('2024-02-01 00:00:00+00');
