CREATE TABLE IF NOT EXISTS rate_sources (
    source_id text PRIMARY KEY,
    series_key text NOT NULL UNIQUE,
    source_url text NOT NULL,
    quote_currency char(3) NOT NULL,
    base_currency char(3) NOT NULL,
    CHECK (quote_currency = 'USD' AND base_currency = 'EUR')
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    rate_date date NOT NULL,
    source_id text NOT NULL REFERENCES rate_sources(source_id),
    usd_per_eur numeric(18, 8) NOT NULL CHECK (usd_per_eur > 0),
    observation_status text NOT NULL,
    PRIMARY KEY (rate_date, source_id)
);

-- Primary key already indexes rate_date; this covering index is relevant to
-- extraction by source and date and will be evaluated with EXPLAIN.
CREATE INDEX IF NOT EXISTS exchange_rates_source_date_cover
    ON exchange_rates (source_id, rate_date) INCLUDE (usd_per_eur, observation_status);
