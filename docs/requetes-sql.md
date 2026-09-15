# Fiches de requêtes C2

## BigQuery — `sql/bigquery_sales.sql`

**Objectif de collecte.** Une ligne par ligne de commande dans une période historique fixe, avec les attributs indispensables au contrôle et au rapprochement des taux. Le schéma a été confirmé et la requête exécutée sur BigQuery.

**Tables et grain.** `order_items` est la table motrice et donne le grain `oi.id`. `orders` apporte l’état de la commande et `products` la catégorie. Les jointures `LEFT JOIN orders ON o.order_id = oi.order_id` et `LEFT JOIN products ON p.id = oi.product_id` conservent les lignes orphelines pour les signaler au contrôle qualité. Ces clés sont les références métier attendues ; leur unicité réelle doit être vérifiée sur les données interrogées. Une ligne de commande dont la référence produit est absente n’est pas écartée silencieusement.

**Colonnes.** `order_id`, `order_item_id`, `product_id` assurent la traçabilité et la détection de doublons. `sale_date_utc` est dérivée de `oi.created_at` pour la jointure temporelle avec la BCE. `order_status` et `item_status` permettent de distinguer exclusion métier et anomalie. `order_disposition` indique si la commande est candidate au CA (`Complete`/`Shipped`), exclue par règle métier (`Cancelled`/`Returned`), sans référence ou dans un autre état à vérifier. `sale_price` est le montant source ; `product_category` sert à expliquer la ligne sans exposer d’information personnelle.

**Filtre et condition.** La condition `oi.created_at >= 2024-01-01 00:00 UTC AND oi.created_at < 2024-02-01 00:00 UTC` définit un mois fixe sans ambiguïté de borne. Aucun état n’est supprimé dans le `WHERE` : les lignes annulées doivent être comptées séparément et les états inattendus doivent rester visibles. Les lignes volontairement exclues de l’extraction sont uniquement celles hors période ; les champs clients sont volontairement non projetés. Le `CASE` constitue une décision provisoire à confronter aux états observés par `sql/bigquery_statuses.sql`.

**Forme du résultat et exécution réelle.** CSV trié par `oi.id`, neuf colonnes utiles, **2 131 lignes** pour 2 131 lignes source dans la période, aucun doublon de `order_item_id`. Le job `4fb47302-bc09-449f-b2aa-6cbfe12d0e5c` a traité 12 003 113 octets et indiqué 31 457 280 **octets facturables** dans ses métadonnées, avec `cache_hit=false` ; cela ne prouve pas un paiement effectif dans le Sandbox. Le snapshot est dans `data/frozen/thelook_sales.csv`, l’extrait dans `evidence/extraits_des_resultats_sql/bigquery_sales.csv`, les métadonnées dans `evidence/mesures_des_requetes/bigquery_sales_job.json`. Les 2 131 lignes se répartissent en 1 167 candidates au CA, 514 exclues par la règle métier provisoire et 450 à vérifier pour l’état `Processing`. Ces classifications d’extraction ne sont pas des lignes C3 acceptées. `sql/bigquery_sales_baseline.sql` ne sert qu’à un *dry run* de comparaison de projection ; ses champs personnels ne sont jamais extraits.

**Reproduction.** Avec Application Default Credentials et `GOOGLE_CLOUD_PROJECT=ljnoam-retail-quality-2026` (ou un autre projet de jobs autorisé), exécuter successivement `python src/extract_bigquery.py discover`, `compare`, puis `extract`. Les commandes complètes sont dans le README. Le jeu public peut évoluer ; pour rejouer exactement les mêmes lignes hors connexion, utiliser le CSV figé et son SHA-256 dans `evidence/mesures_des_requetes/extractions_integrity.json`.

## PostgreSQL — `sql/postgres_rates.sql`

**Objectif de collecte.** Extraire les taux BCE USD/EUR quotidiens utilisables pour les ventes du mois, en incluant sept jours antérieurs.

**Tables et jointure.** `exchange_rates r` contient la date et la valeur numérique. `rate_sources s` donne la série, les deux devises et l’URL officielle. `INNER JOIN s ON s.source_id = r.source_id` est justifiée par la clé étrangère : un taux sans source valide ne doit pas alimenter la conversion. La relation garantit que l’identifiant source existe. Les deux tables sont distinctes pour conserver un référentiel de provenance réutilisable sans répéter l’URL dans chaque observation.

**Colonnes.** `rate_date`, `quote_currency`, `base_currency`, `usd_per_eur`, `observation_status`, `series_key`, `source_url` permettent le rapprochement, la conversion et la traçabilité de la source. Aucun autre taux n’est projeté.

**Filtres et conditions.** `series_key = 'EXR.D.USD.EUR.SP00.A'` impose la série voulue. `rate_date >= start_date - 7 jours` et `< end_date` bornent la fenêtre utile ; le début et la fin sont injectés comme paramètres `psql` ou Python. Les observations d’autres devises, séries et périodes sont volontairement exclues. La contrainte `usd_per_eur > 0` empêche le stockage d’un taux invalide. Le `ORDER BY rate_date` fournit la série chronologique pour la recherche du dernier taux antérieur.

**Forme et exécution réelle.** Le 16 septembre 2026, cette requête a renvoyé **25 lignes** du 27 décembre 2023 au 31 janvier 2024 sur PostgreSQL 17.11 local. L’extrait est dans `evidence/extraits_des_resultats_sql/postgres_rates.csv`, les métadonnées et le plan réel dans `evidence/mesures_des_requetes/postgres_job.json`. La fenêtre paramétrée était [2024-01-01, 2024-02-01), élargie au 25 décembre 2023 pour le rapprochement.

**Reproduction.** Exécuter le schéma, l’import BCE, puis `python src/extract_postgres.py --start 2024-01-01 --end 2024-02-01`. La requête versionnée peut aussi être lancée avec `psql -v start_date=2024-01-01 -v end_date=2024-02-01 -f sql/postgres_rates.sql`.
