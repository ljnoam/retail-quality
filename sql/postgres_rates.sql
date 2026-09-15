-- Bind :start_date and :end_date using psql -v (ISO YYYY-MM-DD).
-- Seven prior days are included so the first sale can use a prior publication.
SELECT r.rate_date,
       s.quote_currency,
       s.base_currency,
       r.usd_per_eur,
       r.observation_status,
       s.series_key,
       s.source_url
FROM exchange_rates AS r
INNER JOIN rate_sources AS s ON s.source_id = r.source_id
WHERE s.series_key = 'EXR.D.USD.EUR.SP00.A'
  AND r.rate_date >= (:'start_date'::date - INTERVAL '7 days')
  AND r.rate_date < :'end_date'::date
ORDER BY r.rate_date;
