-- Candidate period 2024-01-01 inclusive to 2024-02-01 exclusive.
-- Finalize only after schema and period diagnostics are executed.
-- LEFT JOINs retain missing order/product references as quality findings.
SELECT oi.order_id,
       oi.id AS order_item_id,
       oi.product_id,
       DATE(oi.created_at, 'UTC') AS sale_date_utc,
       o.status AS order_status,
       oi.status AS item_status,
       CASE
         WHEN LOWER(TRIM(o.status)) IN ('complete', 'shipped') THEN 'CANDIDATE_CA'
         WHEN LOWER(TRIM(o.status)) IN ('cancelled', 'returned') THEN 'EXCLUE_METIER'
         WHEN o.status IS NULL THEN 'REFERENCE_COMMANDE_ABSENTE'
         ELSE 'A_VERIFIER_ETAT'
       END AS order_disposition,
       oi.sale_price,
       p.category AS product_category
FROM `bigquery-public-data.thelook_ecommerce.order_items` AS oi
LEFT JOIN `bigquery-public-data.thelook_ecommerce.orders` AS o
    ON o.order_id = oi.order_id
LEFT JOIN `bigquery-public-data.thelook_ecommerce.products` AS p
    ON p.id = oi.product_id
WHERE oi.created_at >= TIMESTAMP('2024-01-01 00:00:00+00')
  AND oi.created_at < TIMESTAMP('2024-02-01 00:00:00+00')
ORDER BY oi.id;
