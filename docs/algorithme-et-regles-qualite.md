# Algorithme C3 et règles de qualité

## Entrées et ordre de traitement

`src/build_dataset.py` lit les deux CSV figés de C2 dans `data/frozen/`. Il refuse une source absente, une colonne indispensable absente ou un en-tête dupliqué. Les colonnes de vente indispensables sont les trois identifiants, la date UTC, les deux états, le prix et la catégorie ; celles de taux sont la date, la paire, la valeur, le statut d’observation, la série et l’URL source. `order_disposition` de C2 reste visible dans la quarantaine, mais C3 **recalcule** sa décision depuis les états afin de ne pas faire confiance à une classification en amont.

L’ordre est déterministe :

1. Normaliser les clés, dates, prix et libellés ; compter les identifiants de ligne dupliqués après normalisation.
2. Contrôler les taux BCE : série `EXR.D.USD.EUR.SP00.A`, paire USD/EUR, statut `A`, URL, date unique et valeur strictement positive. Une observation invalide est conservée dans `rate_issues` du rapport et n’est jamais utilisée. Si deux taux candidats portent la même date, les deux sont ignorés.
3. Sur chaque ligne de vente, attribuer **une décision principale** selon la priorité ci-dessous. Les occurrences d’une clé de ligne dupliquée sont toutes rejetées ; aucune n’est choisie arbitrairement.
4. Pour une ligne commercialement admissible, chercher le taux publié à sa date ou le dernier antérieur dans une fenêtre inclusive de **sept jours calendaires**. Ne jamais utiliser un taux futur. Si aucun taux admissible n’existe, classer la ligne `À VÉRIFIER`.
5. Diviser le prix source normalisé par le taux USD par EUR, arrondir l’EUR au centime, puis écrire **un seul** jeu final accepté. Les lignes non acceptées vont dans la quarantaine avec source_row, statut, code et explication ; le rapport compte chaque ligne une fois.

## Normalisation

Les identifiants sont des entiers strictement positifs représentés comme chaînes décimales canoniques (`00042` devient `42`). Une clé absente ou invalide est une corruption. Les dates `YYYY-MM-DD` représentent un jour UTC ; un horodatage ISO doit indiquer son fuseau et est converti en jour UTC. Une date impossible, un horodatage sans fuseau ou une vente hors de [2024-01-01, 2024-02-01) est rejeté. Les états sont comparés après suppression des espaces et `casefold`. La catégorie est conservée comme texte après suppression des espaces autour du libellé.

`sale_price` est un `FLOAT` dans BigQuery, avec parfois une approximation binaire (`99.94999694824217`). C3 lit sa représentation décimale, la **normalise au centime avec `ROUND_HALF_UP`**, puis vérifie qu’elle reste strictement positive. Cette normalisation est une règle du POC : elle doit être validée avec la précision monétaire du système source dans un cas réel. Le taux BCE reste en arithmétique `Decimal` ; pour un taux de `1.20000000` USD par EUR et un montant source de `12.00` supposé USD, `12.00 / 1.20000000 = 10.00` EUR. L’EUR est arrondi **par ligne** à `0.01` avec `ROUND_HALF_UP`, et le total est la somme des montants de ligne déjà arrondis. L’hypothèse « prix source USD » est écrite dans chaque ligne finale et dans le rapport ; elle n’est pas une devise prouvée par TheLook.

## Décisions et codes stables

La première règle applicable dans ce tableau détermine le statut principal. Le motif est enregistré dans `reason_code` et expliqué dans `reason_explanation`. Une corruption d’une commande annulée est donc un rejet qualité selon cet ordre, tandis qu’une commande annulée valide est une exclusion métier ; aucune des deux n’entre dans le jeu final.

| Priorité | Condition | Statut | Codes | Effet sur le montant final |
|---|---|---|---|---|
| 1 | Clé de ligne répétée après normalisation | REJETÉE | `DUPLICATE_LINE_ID` | Toutes les occurrences écartées ; évite un double comptage ou un choix arbitraire. |
| 2 | Identifiant de ligne, commande ou produit absent/invalide | REJETÉE | `MISSING_*_ID`, `INVALID_*_ID` | Ligne impossible à tracer ou rapprocher. |
| 3 | Date impossible, sans fuseau, ou hors période | REJETÉE | `INVALID_SALE_DATE`, `SALE_OUTSIDE_PERIOD` | Ligne incompatible avec la période et la date du taux. |
| 4 | Prix absent, non numérique, non fini, nul/négatif, ou nul après arrondi | REJETÉE | `MISSING_PRICE`, `INVALID_PRICE`, `NON_POSITIVE_PRICE`, `PRICE_ROUNDS_TO_ZERO` | Montant non exploitable. |
| 5 | État commande ou ligne absent, ou contradiction entre eux | À VÉRIFIER | `MISSING_ORDER_STATUS`, `MISSING_ITEM_STATUS`, `STATUS_CONFLICT` | Décision commerciale impossible sans revue. |
| 6 | Commande `Cancelled` ou `Returned` | EXCLUE PAR RÈGLE MÉTIER | `CANCELLED_ORDER`, `RETURNED_ORDER` | Exclusion commerciale ; ce n’est pas une donnée corrompue. |
| 7 | Commande `Processing` ou état inconnu | À VÉRIFIER | `PROCESSING_ORDER`, `UNKNOWN_ORDER_STATUS` | Vente non finalisée ou règle métier non établie. |
| 8 | Catégorie produit absente | À VÉRIFIER | `MISSING_PRODUCT_CATEGORY` | Référence produit à vérifier. |
| 9 | Aucun taux antérieur, ou dernier taux âgé de plus de sept jours | À VÉRIFIER | `NO_PRIOR_RATE`, `RATE_TOO_OLD` | Conversion EUR impossible selon la fenêtre du POC. |
| 10 | Tous les contrôles passent | ACCEPTÉE | aucun code d’exclusion | Ligne dans `ventes_fiables.csv`. |

Les taux corrompus ont leurs propres codes et explications lisibles dans `rate_issues` (`INVALID_RATE_DATE`, `INVALID_RATE_SERIES_OR_PAIR`, `RATE_NOT_PUBLISHED_AS_VALID`, `MISSING_RATE_SOURCE`, `INVALID_RATE_VALUE`, `NON_POSITIVE_RATE`, `DUPLICATE_RATE_DATE`). Ils ne sont pas comptés comme des lignes de vente ; ils sont retirés des taux utilisables. Une vente touchée peut utiliser un taux antérieur encore admissible ; sinon elle est mise à vérifier. Cette règle évite de fabriquer un taux et préserve la conservation des volumes de ventes.

## Sorties et contrôles

`output/ventes_fiables.csv` contient uniquement les lignes acceptées, avec les identifiants, catégorie, date UTC, prix source normalisé, hypothèse de devise, date/valeur/âge du taux, montant EUR et URL BCE. `output/quarantaine.csv` contient chaque autre ligne, son numéro dans la source, les valeurs originales, les valeurs normalisées disponibles et la décision. `output/rapport_qualite.json` contient les compteurs par statut/raison, les anomalies de taux, les empreintes des entrées, la formule, la précision et les contrôles de conservation/unicité. `output/statuts.svg` représente les mêmes compteurs sans données fabriquées. Le rapport n’inclut pas d’horodatage variable : avec les mêmes fichiers et paramètres, les quatre sorties sont identiques octet pour octet.

Les cas artificiels sont exclusivement dans `tests/fixtures/` et dans les tests unitaires. Une exécution avec ces fichiers exige `--fixture-mode` et un répertoire de sortie hors de `output/` ; le code refuse de les présenter comme résultats réels ou d’écraser les sorties publiées. Leur rapport d’essai porte `fixtures_applied=true`. Les comptes réels dans `output/` proviennent des snapshots publics C2, pas des fixtures.
