# Optimisations et mesures C2

## BigQuery

La requête finale ne projette que les identifiants, la date, les deux états, le prix et la catégorie nécessaires. Un filtre sur `oi.created_at` fixe la période. La version de référence `sql/bigquery_sales_baseline.sql` projette toutes les colonnes des trois tables, mais sera utilisée uniquement en *dry run* afin de ne pas extraire de données personnelles. `python src/extract_bigquery.py compare` enregistrera pour chaque version le job ID et les octets estimés par BigQuery. La requête finale exécutée enregistrera les octets traités/facturés, les `slot_millis`, les horodatages et le cache. À ce stade, **aucun gain BigQuery n’est annoncé** : aucun job n’a encore été exécuté. Aucun gain lié au partitionnement n’est présumé.

## PostgreSQL

Le schéma comporte une clé primaire sur `(rate_date, source_id)` et un index couvrant `(source_id, rate_date) INCLUDE (usd_per_eur, observation_status)` adapté à la recherche d’une série sur une période. Le plan réel `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` enregistré montre un `Index Scan` sur `rate_sources_series_key_key`, puis un `Index Only Scan` sur `exchange_rates_source_date_cover` avec la condition source/date. Pour les 25 lignes extraites, le plan a relevé **25 heap fetches**, **0 bloc lu du disque**, **4 blocs partagés en cache**, et **0,019 ms d’exécution serveur** (mesure du plan). L’extraction Python et le transfert des 25 lignes ont pris **2,103 ms** sur cette exécution distincte. Ces valeurs ne sont pas comparables directement et ne mesurent aucun gain avant/après. L’index est pertinent pour la structure de recherche ; son avantage en temps n’a pas été établi sur ce petit jeu.
