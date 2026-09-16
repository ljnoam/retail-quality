# Support oral détaillé — Retail Quality

Ce document accompagne le PowerPoint de soutenance RNCP BC01 C2 et C3. Il sert de fil conducteur pour expliquer le projet avec ses preuves réelles, ses choix techniques et ses limites.

## Positionnement à garder pendant toute la présentation

Retail Quality est un **prototype exécutable de fiabilisation des ventes avant reporting financier**. Il rapproche une extraction commerciale BigQuery et un référentiel de taux BCE chargé dans PostgreSQL, puis produit un jeu final, une quarantaine et un rapport de qualité.

Les données commerciales viennent de **TheLook**, boutique fictive publique. Elles remplacent des données d’entreprise afin de préserver leur confidentialité. Le prototype n’a pas été déployé chez Thales et son montant final ne constitue pas un chiffre d’affaires réel.

Formulations recommandées :

- « Le pipeline a été exécuté sur 2 131 lignes commerciales publiques et 25 taux BCE. »
- « Les 34 tests couvrent les cas normaux, négatifs, limites, l’intégration et le bout en bout. »
- « Aucun rejet qualité n’a été observé dans l’extraction publique réelle. Les fixtures séparées prouvent que le script détecte les anomalies prévues. »
- « Le montant EUR dépend de l’hypothèse non vérifiée que `sale_price` représente des USD. »
- « La réduction de 51,33 % concerne des octets estimés par dry run. Je ne revendique pas de gain de durée. »

Formulations à éviter :

- Toute affirmation de couverture exhaustive.
- « Le montant représente le chiffre d’affaires de l’entreprise. »
- « Le projet est utilisé ou déployé chez Thales. »
- « Le filtre temporel a réduit les octets grâce au partitionnement. » Les tables interrogées n’étaient pas partitionnées selon les métadonnées relevées.
- « L’index PostgreSQL a accéléré la requête de X %. » Aucun avant/après fiable n’a été mesuré sur seulement 25 taux.

## Chiffres à connaître

| Mesure | Valeur |
|---|---:|
| Ventes extraites de BigQuery | 2 131 |
| Taux extraits de PostgreSQL | 25 |
| Lignes acceptées | 1 167 |
| Lignes rejetées pour qualité | 0 |
| Lignes à vérifier | 450 |
| Lignes exclues par règle métier | 514 |
| Lignes en quarantaine | 964 |
| Somme EUR conditionnelle | 67 052,70 EUR |
| Tests exécutés | 34 réussis |
| Job BigQuery final | `4fb47302-bc09-449f-b2aa-6cbfe12d0e5c` |
| Octets BigQuery traités | 12 003 113 |
| Champ technique `total_bytes_billed` | 31 457 280 |
| Dry run large | 24 664 270 octets |
| Dry run final | 12 003 113 octets |
| Réduction estimée | 51,33 % |

## Slide 1 — Titre et contexte

### But de la slide

Présenter le projet et expliquer pourquoi des données publiques remplacent les données d’entreprise.

### Proposition orale

> Je présente Retail Quality, un prototype qui contrôle des ventes avant leur utilisation dans un reporting financier. J’utilise des données publiques de substitution afin de préserver la confidentialité des données d’entreprise. L’objectif de la démonstration porte sur les compétences C2 et C3 : extraire les bonnes données, puis les nettoyer, les homogénéiser et les rapprocher de façon traçable.

### Compétences introduites

- **C2** : requêtes d’extraction fonctionnelles, documentées et mesurées.
- **C3** : agrégation, nettoyage, normalisation et production d’un jeu final fiable.

### Point de vigilance

Ne pas commencer par une longue justification sur Thales. La dernière slide précise que le prototype reste local et non déployé.

## Slide 2 — Question métier et critère de décision

### But de la slide

Formuler l’unique question métier du projet : quelles lignes peuvent alimenter un montant en euros ?

### Proposition orale

> Une ligne devient exploitable seulement si ses identifiants et sa date sont valides, si son état commercial est admissible, si son prix est positif et si un taux BCE admissible peut être associé. Les autres lignes ne disparaissent pas : elles reçoivent un statut et un code de raison. Cette traçabilité permet de justifier le calcul final.

### Preuve associée

Le rapport conserve exactement les 2 131 lignes :

```text
1 167 acceptées
+   0 rejetée
+ 450 à vérifier
+ 514 exclues par règle métier
= 2 131 lignes d'entrée
```

### Critère RNCP

Cette slide introduit la finalité de C3 : produire un jeu final unique et expliquer chaque exclusion.

## Slide 3 — Sources publiques et architecture

### But de la slide

Montrer le rapprochement de deux systèmes réellement interrogés.

### Proposition orale

> BigQuery fournit les commandes, les lignes de commande et les produits de TheLook. PostgreSQL contient les taux quotidiens BCE et leur référentiel de provenance. Le pipeline Python lit les deux snapshots figés, applique les contrôles, rapproche chaque vente d’un taux admissible et produit trois sorties complémentaires.

### Sources exactes

- BigQuery : `bigquery-public-data.thelook_ecommerce.orders`
- BigQuery : `bigquery-public-data.thelook_ecommerce.order_items`
- BigQuery : `bigquery-public-data.thelook_ecommerce.products`
- BCE : série `EXR.D.USD.EUR.SP00.A`
- PostgreSQL : `rate_sources` et `exchange_rates`

### Périodes

- Ventes : `[2024-01-01, 2024-02-01)`.
- Taux chargés : du 25 décembre 2023 au 31 janvier 2024, avec 25 dates publiées entre le 27 décembre et le 31 janvier.

### Pourquoi des snapshots figés ?

Le jeu public peut évoluer. Les fichiers `data/frozen/thelook_sales.csv` et `data/frozen/ecb_rates.csv` permettent de reconstruire exactement les mêmes résultats hors connexion.

## Slide 4 — C2 : extraction BigQuery

### But de la slide

Prouver que la requête commerciale a réellement été exécutée et expliquer chaque sélection, filtre et jointure.

### Proposition orale

> `order_items` est ma table motrice, car le grain attendu est une ligne par ligne de commande. Je joins `orders` pour obtenir l’état commercial et `products` pour obtenir la catégorie. Les deux jointures sont des `LEFT JOIN` : une référence absente doit rester visible pour C3 au lieu d’être supprimée silencieusement. Le filtre utilise une borne de début incluse et une borne de fin exclue en UTC. Je ne filtre aucun statut dans le `WHERE`, car les annulations, retours et états en traitement doivent être comptés séparément.

### Requête concrète

Fichier : `sql/bigquery_sales.sql`

```sql
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
```

### Colonnes volontairement absentes

Les noms, adresses et courriels clients ne servent pas à la décision. Ils ne sont pas extraits.

### Preuve d’exécution

- Job : `4fb47302-bc09-449f-b2aa-6cbfe12d0e5c`.
- État : `DONE`.
- Résultat : 2 131 lignes.
- Doublon de `order_item_id` observé : 0.
- Fichiers : `evidence/mesures_des_requetes/bigquery_sales_job.json` et `evidence/extraits_des_resultats_sql/bigquery_sales.csv`.

### Question probable

**Pourquoi un `LEFT JOIN` et pas un `INNER JOIN` ?**

Parce qu’une commande ou un produit absent représente potentiellement un problème de qualité. Un `INNER JOIN` supprimerait la ligne avant que le pipeline puisse la signaler.

## Slide 5 — C2 : extraction PostgreSQL

### But de la slide

Prouver que le référentiel BCE a été importé et interrogé dans un SGBD relationnel.

### Proposition orale

> `exchange_rates` contient la date et la valeur. `rate_sources` contient la série, la paire de devises et l’URL officielle. L’`INNER JOIN` garantit qu’un taux sans provenance valide ne peut pas servir au calcul. J’extrais les sept jours qui précèdent janvier afin que les premières ventes du mois puissent utiliser le dernier taux antérieur publié.

### Schéma relationnel concret

Fichier : `sql/schema_postgres.sql`

```sql
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
```

### Requête concrète

Fichier : `sql/postgres_rates.sql`

```sql
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
```

### Preuve d’exécution

- PostgreSQL 17.11 local.
- 25 lignes extraites.
- Première observation : 27 décembre 2023.
- Dernière observation : 31 janvier 2024.
- Plan réel : `evidence/mesures_des_requetes/postgres_job.json`.

### Pourquoi un `INNER JOIN` ici ?

La relation de provenance fait partie des conditions d’utilisation du taux. Une observation sans ligne `rate_sources` correspondante ne doit pas alimenter la conversion.

## Slide 6 — C2 : optimisation et mesures

### But de la slide

Présenter uniquement les optimisations mesurées et leurs limites.

### Proposition orale

> Pour BigQuery, j’ai comparé en dry run une projection large et la projection finale. La version large estimait 24 664 270 octets, contre 12 003 113 pour la version finale. La baisse estimée atteint 51,33 %. Je ne transforme pas cette baisse en gain de durée, car je n’ai pas chronométré deux exécutions comparables.

### Pourquoi les octets facturables dépassent-ils les octets traités ?

La requête finale référence trois tables. Google documente, pour la tarification à la demande, un arrondi et un minimum de 10 MB par table référencée et par requête. Les métadonnées du job représentent ce minimum par `10 485 760` octets :

```text
3 tables × 10 485 760 octets = 31 457 280 octets
```

Le champ `total_bytes_processed` reste à 12 003 113 octets. `total_bytes_billed` est un champ technique de consommation. Il ne prouve pas qu’une facture a effectivement été payée, en particulier avec le quota gratuit ou le Sandbox.

Référence officielle : <https://cloud.google.com/bigquery/pricing#on_demand_pricing>

### PostgreSQL

Index versionné :

```sql
CREATE INDEX IF NOT EXISTS exchange_rates_source_date_cover
    ON exchange_rates (source_id, rate_date)
    INCLUDE (usd_per_eur, observation_status);
```

Le plan réel montre :

- `Index Scan` sur la série de la source ;
- `Index Only Scan` sur l’index couvrant ;
- 4 blocs partagés trouvés en cache ;
- 0 bloc lu du disque ;
- 0,022 ms d’exécution serveur ;
- 25 `heap fetches`.

### Limite à dire

Le plan prouve que l’index est utilisé. Il ne prouve pas un gain avant/après significatif sur un jeu de seulement 25 taux.

## Slide 7 — C3 : ordre de l’algorithme

### But de la slide

Montrer que les transformations suivent un ordre déterministe et testable.

### Proposition orale

> Le pipeline valide d’abord les fichiers et les schémas. Il normalise ensuite les identifiants, les dates, les prix et les libellés. Les corruptions et doublons sont traités avant les règles métier. Une ligne commercialement admissible cherche ensuite le dernier taux BCE antérieur dans une fenêtre maximale de sept jours. Le calcul EUR vient seulement après ces contrôles.

### Normalisation des identifiants

Fichier : `src/quality_rules.py`

```python
def positive_id(value: object) -> str | None:
    text = str(value if value is not None else "").strip()
    if not re.fullmatch(r"[0-9]+", text) or int(text) <= 0:
        return None
    return str(int(text))
```

`00042` devient `42`. Une valeur non numérique ou non positive devient invalide.

### Normalisation des dates

```python
def sale_day(value: object) -> date | None:
    text = str(value or "").strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return date.fromisoformat(text)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).date()
    except ValueError:
        return None
```

Un horodatage sans fuseau est refusé. Un horodatage avec fuseau est converti en jour UTC.

### Normalisation monétaire

```python
rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

La valeur `99.94999694824217` issue du `FLOAT` BigQuery devient `99.95` dans le POC.

## Slide 8 — C3 : règles et codes de raison

### But de la slide

Expliquer la différence entre corruption, information à vérifier et exclusion métier.

### Proposition orale

> La première règle applicable devient la décision principale. Une clé répétée, une date impossible ou un prix non positif produit un rejet qualité. Une commande annulée valide produit une exclusion métier. Une commande en traitement produit un statut à vérifier. Chaque décision non acceptée reçoit un code stable et une explication.

### Extrait concret de la décision

```python
if ids[line_id] > 1:
    reason = "DUPLICATE_LINE_ID"

if reason is not None:
    status = REJECTED
else:
    if order_status != item_status:
        reason, status = "STATUS_CONFLICT", REVIEW
    elif order_status == "cancelled":
        reason, status = "CANCELLED_ORDER", EXCLUDED
    elif order_status == "returned":
        reason, status = "RETURNED_ORDER", EXCLUDED
    elif order_status == "processing":
        reason, status = "PROCESSING_ORDER", REVIEW
```

### Distinction essentielle

- `REJETÉE` : donnée corrompue ou duplication non résolue.
- `À VÉRIFIER` : information indispensable absente ou situation non finalisée.
- `EXCLUE PAR RÈGLE MÉTIER` : donnée valide, mais non retenue pour le montant.
- `ACCEPTÉE` : tous les contrôles passent.

### Les fixtures

Les anomalies artificielles restent dans `tests/fixtures/`. Le code interdit :

- une exécution de fixture sans `--fixture-mode` ;
- l’écriture d’une exécution de fixture dans le dossier publié `output/`.

## Slide 9 — C3 : preuve d’exécution

### But de la slide

Prouver que le pipeline a réellement rapproché les deux extractions et conservé toutes les lignes.

### Proposition orale

> Le pipeline a compté les 2 131 lignes exactement une fois. Le jeu final contient 1 167 lignes. La quarantaine contient 964 lignes : 450 à vérifier et 514 exclusions métier. Aucun rejet qualité n’a été observé dans les données publiques réelles.

### Exemple réel accepté

```text
order_item_id : 331
date de vente : 2024-01-28
prix BigQuery : 99.94999694824217
prix normalisé : 99.95 supposés USD
date du taux : 2024-01-26
taux : 1.08710000 USD pour 1 EUR
âge du taux : 2 jours
montant EUR : 91.94
```

Calcul :

```text
99.95 / 1.08710000 = 91.94 EUR après ROUND_HALF_UP au centime
```

### Exemple réel exclu

```text
order_item_id : 140
statut : Cancelled
décision : EXCLUE PAR RÈGLE MÉTIER
code : CANCELLED_ORDER
```

### Vérification indépendante

Le script `src/verify_outputs.py` relit les fichiers générés et recalcule les conditions :

```python
if (amount / rate).quantize(CENT, rounding=ROUND_HALF_UP) != eur:
    raise AssertionError(
        f"Conversion EUR incorrecte dans la ligne finale {row['order_item_id']}."
    )

age = (
    date.fromisoformat(row["sale_date_utc"])
    - date.fromisoformat(row["rate_date"])
).days
if age < 0 or age > 7 or age != int(row["rate_age_days"]):
    raise AssertionError(f"Taux BCE hors fenêtre pour {row['order_item_id']}.")
```

## Slide 10 — Résultat et zéro rejet qualité observé

### But de la slide

Présenter le résultat métier du POC sans confondre absence d’anomalies observées et absence de contrôles.

### Formulation orale recommandée

> Les 1 167 lignes acceptées donnent 67 052,70 EUR sous l’hypothèse non vérifiée que les prix sont en USD. L’extraction publique réelle ne contient aucun cas déclenchant un rejet qualité. Ce zéro ne signifie pas que le script ignore les anomalies. Les fixtures artificielles et les tests négatifs prouvent qu’un prix négatif, une date impossible, un doublon ou un taux invalide provoquent bien la décision attendue. Ces fixtures restent séparées des résultats publics.

### Répartition réelle hors jeu final

- `PROCESSING_ORDER` : 450 lignes à vérifier.
- `CANCELLED_ORDER` : 280 exclusions métier.
- `RETURNED_ORDER` : 234 exclusions métier.
- Rejets qualité observés : 0.

### Tests qui défendent ce zéro

Exemples dans `tests/test_quality_rules.py` :

- `test_corrupt_ids_dates_and_prices_are_rejected`
- `test_duplicate_normalized_line_id_rejects_all_occurrences`
- `test_invalid_cancelled_price_is_rejected_by_precedence`
- `test_rate_corruption_and_wrong_series_are_reported`
- `test_corrupt_rate_causes_review_without_fabricated_fallback`

### Question probable

**Pourquoi ne pas avoir ajouté artificiellement des anomalies aux données réelles ?**

Parce que cela aurait falsifié les résultats présentés comme issus de BigQuery et PostgreSQL. Les anomalies fabriquées servent uniquement aux tests et portent explicitement `fixtures_applied=true` dans leur rapport séparé.

## Slide 11 — Reproductibilité et CI

### But de la slide

Montrer qu’une autre personne peut reconstruire le résultat et vérifier le comportement.

### Commandes principales

```sh
python3 src/build_dataset.py
python3 src/verify_outputs.py
python3 -m unittest discover -s tests -v
```

### Formulation orale recommandée

> Les 34 tests couvrent les cas normaux, négatifs, limites, l’intégration des deux extractions et le bout en bout. La CI les exécute sur Python 3.13 et 3.14, reconstruit les sorties puis vérifie qu’elles restent identiques aux fichiers versionnés. L’idempotence est testée par une seconde exécution comparée octet par octet.

### Ce que couvrent réellement les 34 tests

- Schéma manquant, fichier absent et en-tête dupliqué.
- Identifiants, dates UTC, fuseaux et prix décimaux.
- Taux du jour et repli sur le dernier taux antérieur.
- Borne de sept jours incluse et huit jours refusés.
- Taux futur interdit, taux corrompu et date de taux dupliquée.
- Statuts normaux, inconnus, contradictoires et en traitement.
- Annulation valide distincte d’une corruption.
- Doublons d’identifiant de ligne.
- Conversion et arrondi monétaires.
- Conservation des volumes et unicité des clés.
- Intégration des snapshots BigQuery et PostgreSQL.
- Exécution bout en bout et idempotence.
- Séparation des fixtures et protection du dossier `output/`.
- Détection d’une sortie volontairement altérée par le vérificateur indépendant.

### Formulation à ne pas utiliser

La couverture est fonctionnelle et ciblée sur les règles du PRD ; aucune mesure exhaustive de couverture de lignes ou de branches n’est revendiquée.

## Slide 12 — Limites et validations avant usage réel

### But de la slide

Séparer clairement la preuve technique du POC et les validations nécessaires pour un usage d’entreprise.

### Proposition orale

> Le prototype prouve le fonctionnement de la chaîne sur les données publiques retenues. Il ne prouve pas l’adéquation aux données internes ni la conformité à une politique comptable réelle. Avant un usage réel, il faudrait confirmer la devise et la précision des prix, faire valider les statuts admissibles, la date et la fenêtre du taux, puis traiter les droits d’accès, la supervision et la sécurité. Le prototype reste local et n’a pas été déployé chez Thales.

### Limites principales

- TheLook est fictif et son contenu public peut évoluer.
- `sale_price` est un `FLOAT64` sans devise documentée dans le schéma interrogé.
- `Complete` et `Shipped` sont des choix du POC à valider par les métiers.
- Le repli de sept jours est une règle du POC à valider avec Finance.
- L’arrondi s’effectue au centime par ligne avec `ROUND_HALF_UP`.
- Les mesures de performance portent sur un petit volume.
- Aucun usage en production ou chez Thales n’est revendiqué.

## Rapport par bloc de compétences

## BC01 C2 — Requêter des sources de données

### C2-1 : requête BigQuery fonctionnelle

**Preuves :**

- `sql/bigquery_sales.sql`
- `src/extract_bigquery.py`
- `evidence/mesures_des_requetes/bigquery_sales_job.json`
- `evidence/extraits_des_resultats_sql/bigquery_sales.csv`

**Résultat :** 2 131 lignes réellement extraites, job `DONE`, zéro doublon de clé observé.

### C2-2 : requête PostgreSQL fonctionnelle

**Preuves :**

- `sql/schema_postgres.sql`
- `sql/postgres_rates.sql`
- `src/import_ecb.py`
- `src/extract_postgres.py`
- `evidence/mesures_des_requetes/postgres_job.json`

**Résultat :** 25 observations réellement extraites avec provenance BCE.

### C2-3 : choix documentés

**Preuves :** `docs/requetes-sql.md` décrit l’objectif, le grain, les colonnes, les filtres, les conditions, les jointures et les exclusions volontaires.

### C2-4 : optimisations explicites et mesurées

**BigQuery :** réduction estimée de 51,33 % entre la projection large et la projection finale. Aucun gain de durée revendiqué.

**PostgreSQL :** index couvrant utilisé dans le plan réel. Aucun gain avant/après revendiqué sur ce petit référentiel.

## BC01 C3 — Agréger, nettoyer et homogénéiser

### C3-1 : validation des schémas

Le pipeline refuse les fichiers absents, colonnes indispensables absentes et en-têtes dupliqués avant toute écriture partielle.

### C3-2 : normalisation

- Identifiants en chaînes décimales canoniques positives.
- Dates converties en jour UTC.
- Prix et taux en `Decimal`.
- Prix arrondi au centime avec `ROUND_HALF_UP`.
- Libellés nettoyés avant comparaison.

### C3-3 : détection des corruptions et doublons

Les codes couvrent les identifiants invalides, dates impossibles, prix invalides, taux invalides et clés répétées. Toutes les occurrences d’une clé répétée sont rejetées.

### C3-4 : rapprochement temporel

```python
def choose_rate(day: date, rates: list[Rate], max_age_days: int = 7):
    dates = [rate.day for rate in rates]
    index = bisect_right(dates, day) - 1
    if index < 0:
        return None, "NO_PRIOR_RATE", None
    candidate = rates[index]
    age = (day - candidate.day).days
    if age > max_age_days:
        return None, "RATE_TOO_OLD", age
    return candidate, None, age
```

Le code choisit le dernier taux antérieur ou égal. Il n’utilise jamais de taux futur.

### C3-5 : règles métier

Les annulations et retours valides sont exclus par règle métier. Ils ne sont pas qualifiés de données corrompues.

### C3-6 : calcul monétaire

```python
eur = (amount / rate.value).quantize(
    Decimal("0.01"),
    rounding=ROUND_HALF_UP,
)
```

La division vient du format BCE : USD pour 1 EUR.

### C3-7 : sorties

- `output/ventes_fiables.csv` : 1 167 lignes acceptées.
- `output/quarantaine.csv` : 964 lignes non acceptées avec statut et raison.
- `output/rapport_qualite.json` : volumes, raisons, hypothèses et contrôles.
- `output/statuts.svg` : graphique des mêmes compteurs.

### Traçabilité et conservation

Le vérificateur contrôle que l’ensemble des numéros de ligne de la source correspond exactement à l’union des lignes finales et de la quarantaine :

```python
if (
    len(set(final_source_rows + nonaccepted_source_rows)) != len(sales)
    or set(final_source_rows + nonaccepted_source_rows)
       != set(range(2, len(sales) + 2))
):
    raise AssertionError(
        "Une ligne source manque ou est comptée plusieurs fois."
    )
```

## Questions courtes à préparer

### Pourquoi la devise USD reste-t-elle une hypothèse ?

Le schéma BigQuery vérifié expose `sale_price` comme `FLOAT64`, sans colonne ni description de devise. Le POC écrit donc l’hypothèse dans chaque ligne finale et dans le rapport.

### Pourquoi sept jours ?

Le PRD impose une fenêtre maximale de sept jours calendaires. Cette borne couvre les week-ends et jours fériés sans autoriser un taux trop ancien. Une politique réelle devrait être validée avec Finance.

### Pourquoi diviser par le taux ?

La BCE publie la série sous la forme USD pour 1 EUR. Avec 1,0871 USD pour 1 EUR, un montant de 99,95 USD donne `99,95 / 1,0871 = 91,94 EUR`.

### Pourquoi zéro rejet qualité ?

Parce que les 2 131 lignes réellement extraites ne déclenchent aucune règle de corruption. Les tests séparés prouvent que le code rejette les cas artificiels invalides. Aucune anomalie n’a été injectée dans les résultats publics.

### Pourquoi 31 457 280 octets facturables ?

La requête référence trois tables. Le minimum technique enregistré correspond à `3 × 10 485 760` octets. Le champ est une métadonnée BigQuery et ne prouve pas un paiement effectif.

### Le projet est-il prêt pour la production ?

Non. Il faut valider les règles métier, la devise, la précision monétaire, la politique de taux, les accès, la supervision et la sécurité sur le contexte réel.

## Chemins à ouvrir si le jury demande une preuve

| Demande | Fichier |
|---|---|
| Requête BigQuery | `sql/bigquery_sales.sql` |
| Job BigQuery | `evidence/mesures_des_requetes/bigquery_sales_job.json` |
| Dry runs BigQuery | `evidence/mesures_des_requetes/bigquery_dry_runs.json` |
| Requête PostgreSQL | `sql/postgres_rates.sql` |
| Schéma et index PostgreSQL | `sql/schema_postgres.sql` |
| Plan PostgreSQL | `evidence/mesures_des_requetes/postgres_job.json` |
| Règles Python | `src/quality_rules.py` |
| Orchestration | `src/build_dataset.py` |
| Vérification indépendante | `src/verify_outputs.py` |
| Tests des règles | `tests/test_quality_rules.py` |
| Tests d’intégration | `tests/test_pipeline_integration.py` |
| Jeu final | `output/ventes_fiables.csv` |
| Quarantaine | `output/quarantaine.csv` |
| Rapport | `output/rapport_qualite.json` |
| Matrice RNCP | `docs/matrice-preuves-rncp.md` |

## Conclusion orale possible

> Le POC répond à la question initiale de façon traçable : 1 167 lignes peuvent alimenter le calcul conditionnel en euros, 964 lignes restent hors du jeu final avec une raison explicite, et les 2 131 lignes d’entrée sont toutes comptabilisées. Les deux extractions ont été réellement exécutées, le pipeline est reproductible à partir de snapshots figés et les règles de qualité sont exercées par 34 tests ciblés. Les limites de devise, de règles métier et de mise en production restent explicitement à valider avant tout usage réel.
