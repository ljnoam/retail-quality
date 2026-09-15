# Sources, période et hypothèses

## Données commerciales

TheLook e-commerce est une boutique **fictive** dans le projet public `bigquery-public-data.thelook_ecommerce`. Les tables visées sont `orders`, `order_items` et `products`. Le schéma réel, ses types, les dates disponibles et les volumes seront enregistrés par `python src/extract_bigquery.py discover` dans `evidence/mesures_des_requetes/bigquery_discovery.json`. Tant que ce fichier n’existe pas, les colonnes utilisées dans `sql/bigquery_sales.sql` sont **candidates**, appuyées par les exemples publics de Google mais non validées sur l’instance interrogée.

La fenêtre commerciale candidate est **[2024-01-01, 2024-02-01)** en UTC. Elle est fixe pour rendre l’extraction rejouable ; elle deviendra définitive uniquement si le diagnostic BigQuery confirme des ventes sur cette période. `order_items.created_at` sert de date de vente observable : il ne prouve pas une date de paiement ou de comptabilisation. La conversion `DATE(..., 'UTC')` rend le jour explicite.

La colonne `sale_price` ne comporte pas de code devise dans les colonnes attendues. La documentation officielle consultée ne fournit pas ici de preuve claire de la devise de chaque ligne. **Hypothèse du POC : les prix sont traités comme USD.** Cela ne constitue pas un fait sur les prix TheLook. La conversion en euros et son interprétation métier restent conditionnelles à cette hypothèse.

Les identifiants de client, noms, adresses et courriels sont hors périmètre. Les deux `LEFT JOIN` conservent les lignes dont la commande ou le produit est absent, afin que cette absence soit contrôlée en aval plutôt que masquée à l’extraction.

## Taux de change

L’API officielle BCE expose la série quotidienne `EXR.D.USD.EUR.SP00.A` en CSV avec `TIME_PERIOD` (date) et `OBS_VALUE` (taux). Les dimensions `CURRENCY=USD` et `CURRENCY_DENOM=EUR` signifient **USD pour 1 EUR**. Un montant supposé en USD sera donc divisé par le taux pour obtenir un montant en EUR. Le script refuse une autre série, une autre paire, un taux non numérique, nul ou négatif et une date doublonnée.

Pour les ventes de janvier 2024, l’import couvre **[2023-12-25, 2024-02-01)** : les sept jours antérieurs sont requis pour chercher le dernier taux publié avant une vente du début de mois. L’API a réellement renvoyé 25 observations entre le 27 décembre 2023 et le 31 janvier 2024. Les jours sans publication, notamment le 1er janvier, ne sont pas inventés. Le hash SHA-256 du CSV source figure dans `evidence/mesures_des_requetes/ecb_import.json` ; le snapshot brut local est dans `data/raw/` et peut être retéléchargé à l’URL enregistrée.

## Portée

Ce POC démontre un pipeline sur des données publiques de substitution. Il n’est ni validé sur les données de Thales, ni déployé, ni utilisé par l’entreprise. Une application réelle demanderait la validation des états commerciaux, de la devise, de la date comptable, des droits d’accès et des règles de change avec les équipes concernées.
