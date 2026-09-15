-- Run against the US public dataset before finalizing extraction columns.
SELECT table_name, column_name, data_type, is_nullable
FROM `bigquery-public-data.thelook_ecommerce.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN ('orders', 'order_items', 'products')
ORDER BY table_name, ordinal_position;
