# Matrice de preuves RNCP BC01 C2 et C3

Audit réalisé le **16 septembre 2026** contre les exigences des sections 5, 6, 7, 9, 11 et 12 de `PRD.md`. Une preuve est dite conforme lorsqu’un fichier versionné et une exécution observable permettent de la vérifier. Les données commerciales viennent de **TheLook, boutique fictive publique utilisée comme substitution**. Le projet n’a pas été déployé ni utilisé chez Thales.

| Critère | Fichier ou code vérifiable | Preuve d’exécution réelle | Slide | État factuel |
|---|---|---|---:|---|
| C2-1 — Requête BigQuery fonctionnelle | `sql/bigquery_sales.sql`, `src/extract_bigquery.py` | `evidence/mesures_des_requetes/bigquery_sales_job.json` : job `4fb47302-bc09-449f-b2aa-6cbfe12d0e5c`, état `DONE`, 2 131 lignes, validation `PASSED` | 4 | Conforme |
| C2-1 — Tables et jointures commerciales | `sql/bigquery_sales.sql`, `docs/requetes-sql.md` | Extrait réel `evidence/extraits_des_resultats_sql/bigquery_sales.csv` issu de `order_items LEFT JOIN orders LEFT JOIN products` | 4 | Conforme |
| C2-1 — Sélection des seules colonnes utiles | `sql/bigquery_sales.sql` | Métadonnées de schéma dans `bigquery_discovery.json` et CSV réel à neuf colonnes, sans nom, adresse ni courriel | 4 | Conforme |
| C2-1 — Période fixe et états explicites | `sql/bigquery_sales.sql`, `sql/bigquery_period.sql`, `sql/bigquery_statuses.sql` | Jobs de diagnostic `e1e8698d-6f49-4ab4-9144-442cf569bcca` et `96fc4dc7-c65e-436c-ba9c-cd47d44a7594`; fenêtre `[2024-01-01, 2024-02-01)` | 4 | Conforme |
| C2-2 — Requête PostgreSQL fonctionnelle | `sql/postgres_rates.sql`, `src/extract_postgres.py` | `postgres_job.json` : PostgreSQL 17.11, 25 lignes du 27/12/2023 au 31/01/2024 | 5 | Conforme |
| C2-2 — Jointure du taux et de sa source | `sql/schema_postgres.sql`, `sql/postgres_rates.sql` | Plan `EXPLAIN ANALYZE` réel : `Nested Loop`, `Index Scan` sur la source et `Index Only Scan` sur les taux | 5 | Conforme |
| C2-2 — Import BCE reproductible | `src/import_ecb.py`, commandes du `README.md` | `ecb_import.json` : série `EXR.D.USD.EUR.SP00.A`, SHA-256 du CSV brut, 25 observations; `postgres_import_idempotence.json` | 5 | Conforme |
| C2-3 — Sélections, filtres, conditions et jointures justifiés | `docs/requetes-sql.md` | Les fiches relient chaque clause SQL à sa fonction métier, aux exclusions et à la forme du résultat | 4–5 | Conforme |
| C2-3 — Commandes de reproduction | `README.md` | Commandes distinctes pour diagnostic, comparaison, extraction BigQuery, schéma/import/extraction PostgreSQL et contrôle d’intégrité | 11 | Conforme |
| C2-4 — Optimisation BigQuery mesurée | `sql/bigquery_sales_baseline.sql`, `sql/bigquery_sales.sql`, `docs/optimisations-et-mesures.md` | Dry runs : 24 664 270 contre 12 003 113 octets, soit 51,33 % estimés en moins; aucune amélioration de durée revendiquée | 6 | Conforme avec portée limitée |
| C2-4 — Métadonnées du job BigQuery | `evidence/mesures_des_requetes/bigquery_sales_job.json` | 12 003 113 octets traités, 31 457 280 octets dans le champ technique facturable, 69 slot-ms, cache absent, 343 ms SQL | 6 | Conforme |
| C2-4 — Index et plan PostgreSQL | `sql/schema_postgres.sql`, `docs/optimisations-et-mesures.md` | Index couvrant utilisé; 25 heap fetches, 4 blocs en cache, 0 lu du disque, 0,022 ms serveur; aucun gain avant/après revendiqué | 6 | Conforme avec portée limitée |
| C3-1 — Validation des schémas | `src/build_dataset.py`, `tests/test_pipeline_integration.py` | Tests de fichier absent, colonne absente et en-tête dupliqué réussis | 7 | Conforme |
| C3-2 — Normalisation des formats | `src/quality_rules.py`, `docs/algorithme-et-regles-qualite.md` | Tests des identifiants, dates UTC/fuseaux, libellés, décimaux et `ROUND_HALF_UP` réussis | 7–8 | Conforme |
| C3-3 — Corruptions et doublons | `src/quality_rules.py`, `tests/test_quality_rules.py`, `tests/fixtures/` | Tests négatifs : identifiants, dates, prix, taux et doublons; fixtures artificielles séparées | 8 | Conforme |
| C3-4 — Rapprochement des taux à sept jours | `src/quality_rules.py`, `tests/test_quality_rules.py` | Tests : taux du jour, week-end, dernier taux antérieur, futur interdit, 7 jours inclus et 8 jours exclus | 7–8 | Conforme |
| C3-5 — Exclusion métier distincte du rejet qualité | `src/quality_rules.py`, catalogue des règles | Tests de précédence; données réelles : 280 annulations et 234 retours exclus, 0 rejet qualité observé | 8–10 | Conforme |
| C3-6 — Calcul monétaire décimal | `src/quality_rules.py`, `src/verify_outputs.py` | Formule contrôlée ligne par ligne; exemple réel 99,95 / 1,0871 = 91,94 EUR; contrôle indépendant `eur_conversion=PASSED` | 9–10 | Conforme sous hypothèse USD |
| C3-7 — Jeu final, quarantaine et rapport | `output/ventes_fiables.csv`, `output/quarantaine.csv`, `output/rapport_qualite.json` | 1 167 acceptées + 0 rejetée + 450 à vérifier + 514 exclues = 2 131; 964 lignes en quarantaine | 9–10 | Conforme |
| C3 — Traçabilité par statut et code de raison | `src/quality_rules.py`, `output/quarantaine.csv`, `output/rapport_qualite.json` | `reason_traceability=PASSED`; compteurs réels : `PROCESSING_ORDER` 450, `CANCELLED_ORDER` 280, `RETURNED_ORDER` 234 | 8–10 | Conforme |
| C3 — Contenu et unicité du jeu final | `output/ventes_fiables.csv`, `src/verify_outputs.py` | 1 167 clés uniques; montants et taux positifs; âge du taux compris entre 0 et 7 jours; source BCE présente | 9 | Conforme |
| C3 — Conservation des volumes | `output/rapport_qualite.json`, `c3_output_verification.json` | `volume_conservation=PASSED` et `source_line_partition=PASSED`; chaque vente apparaît une fois dans une seule sortie | 9 | Conforme |
| C3 — Anomalies artificielles séparées des données réelles | `tests/fixtures/`, garde-fous de `src/build_dataset.py` | `fixture_separation=PASSED`; le mode fixture ne peut ni être présenté comme réel ni écraser `output/` | 8 | Conforme |
| C3 — Idempotence | `tests/test_pipeline_integration.py`, hashes du vérificateur | Deux exécutions donnent des fichiers identiques octet par octet; hashes publiés dans `c3_output_verification.json` | 11 | Conforme |
| C3 — Tests unitaires, intégration et bout en bout | `tests/`, `evidence/rapport_de_tests/c3_unittest.txt` | 34 tests exécutés, tous réussis; nouvel audit local du 16/09/2026 également réussi | 11 | Conforme |
| C3 — Dépendances, configuration et CI | `requirements.txt`, `.env.example`, `.github/workflows/quality.yml` | Dépendances C2 fixées; C3 sur bibliothèque standard; CI Python 3.13/3.14 réussie sur le commit `87cfbbd` | 11 | Conforme |
| C3 — Script versionné et dépôt accessible | `src/`, historique Git | Dépôt public `https://github.com/ljnoam/retail-quality`; `main` distant vérifié sur `87cfbbd993ea110a0e205a7e80b74813ac9d757e` avant le présent audit | 11 | Conforme |
| Documentation et limites | `README.md`, `docs/` | Reproduction C2/C3, règles, hypothèses et limites explicites; aucune affirmation d’usage chez Thales | 1–3, 11–12 | Conforme |

## Réconciliation des fichiers finaux

| Élément | Valeur vérifiée le 16/09/2026 |
|---|---:|
| Ventes BigQuery extraites | 2 131 |
| Taux PostgreSQL extraits | 25 |
| Ventes acceptées | 1 167 |
| Ventes rejetées pour qualité | 0 |
| Ventes à vérifier | 450 |
| Ventes exclues par règle métier | 514 |
| Quarantaine totale | 964 |
| Somme EUR conditionnelle à l’hypothèse USD | 67 052,70 EUR |
| Tests | 34 réussis, 0 échec |

Les hashes SHA-256 recalculés correspondent à `evidence/rapport_de_tests/c3_output_verification.json`. La somme EUR reste un résultat de démonstration, car la devise de `sale_price` n’est pas documentée officiellement dans le schéma interrogé.
