# Retail Quality

Prototype de contrôle de ventes avant un calcul de chiffre d’affaires en euros, construit avec des données publiques de démonstration pour les compétences RNCP BC01 C2 et C3. Le besoin métier est envisagé ; ce dépôt ne constitue ni un déploiement ni une utilisation chez Thales.

Le [cahier des charges](PRD.md) définit le périmètre. La série officielle BCE `EXR.D.USD.EUR.SP00.A` fournit des **USD pour 1 EUR**. La devise des prix `sale_price` de TheLook n’a pas encore été établie par une source officielle : le traitement comme USD sera une **hypothèse du POC**, à valider avant tout usage réel.

## État des preuves

La réponse BCE pour janvier 2024 a été interrogée réellement le 16 septembre 2026. PostgreSQL 17.11 local a exécuté l’import et la requête C2 : 25 taux entre le 27 décembre 2023 et le 31 janvier 2024, avec extrait et plan `EXPLAIN ANALYZE` dans `evidence/`. Les schémas et la période commerciale TheLook doivent encore être vérifiés par une interrogation BigQuery. Aucune requête BigQuery n’est pour l’instant revendiquée comme exécutée.

## Reproduction C2

Prévoir Python 3.10+, PostgreSQL 17 et un projet Google Cloud autorisé à lancer des jobs BigQuery sur le jeu public. Les dépendances sont figées dans [requirements.txt](requirements.txt). `docker-compose.yml` permet de démarrer PostgreSQL avec Docker si disponible ; le développement présent a utilisé PostgreSQL 17 local via Homebrew. Copier `.env.example` vers `.env` et fournir uniquement les paramètres locaux nécessaires, sans versionner `.env`.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Variante Docker : renseigner PGPASSWORD dans .env, puis docker compose up -d
# Variante Homebrew : brew install postgresql@17 ; brew services start postgresql@17 ; createdb retail_quality
psql -d retail_quality -v ON_ERROR_STOP=1 -f sql/schema_postgres.sql
curl -L --fail -o data/raw/ecb_2023-12-25_2024-01-31.csv 'https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2023-12-25&endPeriod=2024-01-31&format=csvdata'
.venv/bin/python src/import_ecb.py --start 2023-12-25 --end 2024-02-01 --csv data/raw/ecb_2023-12-25_2024-01-31.csv
.venv/bin/python src/extract_postgres.py --start 2024-01-01 --end 2024-02-01
```

`src/import_ecb.py` peut aussi télécharger l’API directement si `--csv` est omis. Le hash du CSV brut et l’URL exacte sont enregistrés. L’import est idempotent : une seconde exécution met à jour les mêmes clés `(rate_date, source_id)`.

La partie BigQuery exige `gcloud auth application-default login`, un `GOOGLE_CLOUD_PROJECT` correspondant à un projet autorisé, et la localisation `US` du jeu public :

```sh
export GOOGLE_CLOUD_PROJECT=ID_DU_PROJET
export BIGQUERY_LOCATION=US
.venv/bin/python src/extract_bigquery.py discover
.venv/bin/python src/extract_bigquery.py compare
.venv/bin/python src/extract_bigquery.py extract
```

`discover` vérifie le schéma réel, les types, la disponibilité temporelle et les états ; `compare` lance deux *dry runs* et enregistre les octets estimés ; `extract` exécutera la requête finale et enregistrera ses métadonnées et un extrait. La fenêtre candidate [2024-01-01, 2024-02-01) ne sera retenue qu’après ce diagnostic. Les extractions complètes sont locales dans `data/raw/` et ignorées par Git ; les extraits consultables et les métadonnées sans données personnelles sont dans `evidence/`.

Les choix de colonnes, filtres, conditions et jointures sont expliqués dans [les fiches SQL](docs/requetes-sql.md). Les hypothèses et limites figurent dans [les sources](docs/sources-et-hypotheses.md), et les mesures dans [les optimisations](docs/optimisations-et-mesures.md).

## Sources

- [TheLook dans BigQuery](https://console.cloud.google.com/marketplace/product/bigquery-public-data/thelook-ecommerce) : boutique fictive, tables commerciales publiques.
- [API BCE et exemples](https://data.ecb.europa.eu/help/api/data-examples) : série quotidienne `EXR.D.USD.EUR.SP00.A`, `TIME_PERIOD` et `OBS_VALUE` dans l’export `csvdata`.

Le code, les commandes de reproduction et les preuves d’exécution seront documentés au fil de la construction. Aucun nom, courriel ou adresse de client n’est extrait.
