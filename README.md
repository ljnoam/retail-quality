# Retail Quality

Prototype de contrôle de ventes avant un calcul de chiffre d’affaires en euros, construit avec des données publiques de démonstration pour les compétences RNCP BC01 C2 et C3. Le besoin métier est envisagé ; ce dépôt ne constitue ni un déploiement ni une utilisation chez Thales.

Le [cahier des charges](PRD.md) définit le périmètre. La série officielle BCE `EXR.D.USD.EUR.SP00.A` fournit des **USD pour 1 EUR**. La devise des prix `sale_price` de TheLook n’a pas été établie par une source officielle : le traitement comme USD est une **hypothèse du POC**, à valider avant tout usage réel.

## État des preuves

La réponse BCE et les tables publiques TheLook ont été interrogées réellement le 16 septembre 2026. PostgreSQL 17.11 local a exécuté l’import et la requête C2 : **25 taux** entre le 27 décembre 2023 et le 31 janvier 2024, avec extrait et plan `EXPLAIN ANALYZE`. BigQuery, avec le projet dédié `ljnoam-retail-quality-2026`, a vérifié les schémas et extrait **2 131 lignes de commande** du 1er au 31 janvier 2024 ; le job, ses volumes et les *dry runs* sont dans `evidence/`. Les CSV figés sans identifiant personnel sont dans `data/frozen/`. Le pipeline C3 exécuté sur ces snapshots a produit **1 167 lignes acceptées**, **0 rejetée**, **450 à vérifier** et **514 exclues par règle métier**, avec conservation exacte des 2 131 lignes. Les montants EUR sont conditionnels à l’hypothèse non vérifiée que les prix TheLook sont en USD.

## Reproduction C2

Prévoir Python 3.10+, PostgreSQL 17 et un projet Google Cloud autorisé à lancer des jobs BigQuery sur le jeu public. Les dépendances sont figées dans [requirements.txt](requirements.txt). `docker-compose.yml` permet de démarrer PostgreSQL avec Docker si disponible ; le développement présent a utilisé PostgreSQL 17 local via Homebrew. Copier `.env.example` vers `.env` et fournir uniquement les paramètres locaux nécessaires, sans versionner `.env`. Docker Compose lit `.env` automatiquement ; pour les scripts Python et `psql`, exporter les variables de `.env` dans le shell (`set -a; . ./.env; set +a`). Avec PostgreSQL Homebrew, définir `PGUSER` au rôle local utilisé lors de `createdb` ou laisser cette variable non définie.

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
export GOOGLE_CLOUD_PROJECT=ljnoam-retail-quality-2026
export BIGQUERY_LOCATION=US
.venv/bin/python src/extract_bigquery.py discover
.venv/bin/python src/extract_bigquery.py compare
.venv/bin/python src/extract_bigquery.py extract
```

`discover` vérifie le schéma réel, les types, la disponibilité temporelle et les états ; `compare` lance deux *dry runs* et enregistre les octets estimés ; `extract` exécutera la requête finale et enregistrera ses métadonnées et un extrait. La fenêtre candidate [2024-01-01, 2024-02-01) ne sera retenue qu’après ce diagnostic. Les extractions figées sont dans `data/frozen/` et versionnées pour un traitement hors connexion. Le CSV brut de l’API BCE, retéléchargeable et contrôlé par hash, reste dans `data/raw/` et n’est pas versionné. Les extraits consultables et les métadonnées des jobs sont dans `evidence/`.
La fenêtre [2024-01-01, 2024-02-01) a été confirmée par les diagnostics. Après les deux extractions, `.venv/bin/python src/summarize_extractions.py` contrôle leurs volumes, dates, clés et SHA-256. Le jeu TheLook public peut évoluer ; les snapshots figés permettent de rejouer les étapes suivantes sur les mêmes lignes.

## Reconstruction C3 hors connexion

C3 utilise uniquement la bibliothèque standard Python ; `requirements.txt` fixe les dépendances nécessaires aux extractions C2 (`google-cloud-bigquery` et `psycopg`). Après l’installation Python ci-dessus, aucune connexion BigQuery ou PostgreSQL n’est nécessaire pour reconstruire le résultat depuis les snapshots figés :

```sh
.venv/bin/python src/build_dataset.py
.venv/bin/python src/verify_outputs.py
.venv/bin/python -m unittest discover -s tests -v
```

Les paramètres `RQ_START_DATE=2024-01-01`, `RQ_END_DATE=2024-02-01` et `RQ_RATE_MAX_AGE_DAYS=7` ont des défauts documentés dans `.env.example` ; les mêmes valeurs peuvent être passées par `--start`, `--end` et `--rate-max-age-days`. Le script refuse une fenêtre de taux supérieure à sept jours. Une source manquante ou un schéma incomplet donne une erreur lisible avant toute écriture dans `output/`.

Le livrable principal est [ventes_fiables.csv](output/ventes_fiables.csv). [quarantaine.csv](output/quarantaine.csv) indique pour chaque autre ligne le statut, le code stable et l’explication ; [rapport_qualite.json](output/rapport_qualite.json) réconcilie les volumes et les sommes. [statuts.svg](output/statuts.svg) sert aux slides. Le contrôle indépendant versionné est dans [la preuve C3](evidence/rapport_de_tests/c3_output_verification.json), et la sortie des tests dans `evidence/rapport_de_tests/`.

Les anomalies artificielles sont uniquement dans `tests/fixtures/` et dans les tests de règles. Pour les exécuter comme démonstration séparée, utiliser `--sales tests/fixtures/sales_artificial.csv --rates tests/fixtures/rates_artificial.csv --output-dir /tmp/retail-quality-fixtures --fixture-mode` ; le rapport porte alors `fixtures_applied=true` et ne remplace jamais les résultats réels du dépôt. La CI [quality.yml](.github/workflows/quality.yml) lance les tests sur Python 3.13 et 3.14, reconstruit les sorties et vérifie qu’elles restent identiques aux fichiers versionnés.

Les choix de colonnes, filtres, conditions et jointures sont expliqués dans [les fiches SQL](docs/requetes-sql.md). L’ordre du pipeline et chaque décision sont dans [les règles C3](docs/algorithme-et-regles-qualite.md). Les hypothèses figurent dans [les sources](docs/sources-et-hypotheses.md), les chiffres observés et limites dans [les résultats](docs/resultats-et-limites.md), et les mesures dans [les optimisations](docs/optimisations-et-mesures.md). La [matrice de preuves RNCP](docs/matrice-preuves-rncp.md) relie chaque critère à ses fichiers, ses preuves d’exécution et sa slide de soutenance.

## Audit RNCP et soutenance

L’audit daté du 16 septembre 2026 a reconstruit le pipeline, exécuté le vérificateur indépendant et relancé les 34 tests. Son relevé se trouve dans [rncp_audit_2026-09-16.json](evidence/rapport_de_tests/rncp_audit_2026-09-16.json). Le [PowerPoint final corrigé](presentation/retail-quality-soutenance-rncp-c2-c3-corrige.pptx) contient 12 slides, des tableaux et graphiques éditables, ainsi que des notes d’oral sur chaque slide. Le [support oral détaillé](docs/support-oral-soutenance.md) fournit le discours, les compétences et les extraits de code concrets pour chaque slide. La preuve de validation et de revue visuelle figure dans [presentation_validation_2026-09-16.json](evidence/rapport_de_tests/presentation_validation_2026-09-16.json).

## Sources

- [TheLook dans BigQuery](https://console.cloud.google.com/marketplace/product/bigquery-public-data/thelook-ecommerce) : boutique fictive, tables commerciales publiques.
- [API BCE et exemples](https://data.ecb.europa.eu/help/api/data-examples) : série quotidienne `EXR.D.USD.EUR.SP00.A`, `TIME_PERIOD` et `OBS_VALUE` dans l’export `csvdata`.

Le code, les commandes de reproduction et les preuves d’exécution sont versionnés dans ce dépôt. Aucun nom, courriel ou adresse de client n’est extrait.
