# Cahier des charges — Retail Quality

**Sous-titre :** POC de fiabilisation des données commerciales avant reporting financier  
**Échéance :** soutenance de rattrapage du 19 septembre 2026  
**Compétences visées :** BC01 — C2 et C3  
**Nature du projet :** prototype exécutable, documenté et versionné, présenté dans un PowerPoint. Aucune mise en production n’est attendue.

## 1. Contexte et problème métier

Dans une organisation, les données utilisées pour un reporting financier peuvent provenir de plusieurs systèmes et présenter des écarts : commandes annulées incluses par erreur, prix invalides, doublons, références produit absentes, dates de formats différents ou taux de change manquants.

**Retail Quality** construit une chaîne de contrôle avant reporting. Elle extrait les données commerciales d’un système big data, récupère un référentiel de taux de change depuis une base relationnelle, rapproche les sources, applique des règles de qualité traçables et produit un jeu de données final fiable.

Le prototype emploie des données publiques de substitution. Ce choix permet de présenter l’architecture, le code et les résultats sans divulguer de données de l’entreprise d’alternance. La présentation doit distinguer clairement **le besoin métier envisagé**, **le POC effectivement réalisé** et **les données de démonstration**. Elle ne doit pas affirmer que le prototype a été déployé ou utilisé par l’entreprise si cela n’a pas eu lieu.

## 2. Objectif unique du projet

Répondre à la question :

> **Quelles lignes de ventes peut-on utiliser pour calculer un chiffre d’affaires en euros, et pourquoi les autres lignes ont-elles été écartées ou mises à vérifier ?**

Le projet doit produire :

- un jeu de données final unique contenant uniquement les lignes jugées exploitables ;
- un rapport de qualité indiquant les volumes et les motifs de rejet ou de mise à vérifier ;
- les requêtes SQL, le script d’agrégation, leurs résultats et leur documentation ;
- un dépôt Git accessible ;
- les éléments probants nécessaires au PowerPoint de soutenance.

Le rapport de qualité est une **preuve du fonctionnement du pipeline**. Le jeu de données final reste le livrable principal demandé par C3.

## 3. Sources et choix techniques

### Source A — système big data : BigQuery

Utiliser les tables publiques du jeu **TheLook e-commerce** : commandes, lignes de commandes et produits. Les noms exacts des colonnes et leurs types doivent être vérifiés dans le schéma réel avant d’écrire les requêtes définitives. Les requêtes doivent être exécutées sur BigQuery, pas simplement rédigées dans un fichier.

TheLook représente une boutique fictive. Cette caractéristique doit figurer dans la documentation et sur une slide « Sources et limites ». [Documentation Google sur les tables TheLook](https://docs.cloud.google.com/bigquery/docs/gemini-analyze-data?authuser=110).

**Données à extraire, selon le schéma vérifié :** identifiant de commande, identifiant de ligne, identifiant de produit, date de vente, état de commande, prix de vente et catégorie de produit. Ne pas extraire de noms, adresses ou courriels de clients : ils ne sont pas nécessaires à l’objectif.

### Source B — SGBD relationnel : PostgreSQL

Créer une base PostgreSQL locale contenant les taux de change quotidiens USD/EUR provenant de l’API ou d’un export CSV de la **Banque centrale européenne**. Conserver la date, la paire de devises, le taux numérique et une référence à la source. L’import doit être reproductible par une commande documentée. [Documentation de l’API BCE](https://data.ecb.europa.eu/help/api/data-examples).

Le modèle relationnel doit comporter au minimum une table de taux et une table de référence des devises ou des sources, afin que la requête PostgreSQL démontre une **jointure justifiée**, en plus de la sélection et du filtrage.

**Point à valider avant le développement :** vérifier comment les prix du jeu TheLook sont libellés. Si la devise n’est pas explicitement documentée dans la source, l’hypothèse « prix traités comme USD pour le POC » doit être visible dans la documentation et dans le PowerPoint. Elle ne doit pas être présentée comme un fait établi.

### Périmètre des données

Choisir une **période historique fixe**, après avoir vérifié que les ventes et les taux BCE existent effectivement sur cette période. La période retenue, sa justification et les volumes initiaux doivent être enregistrés. Une période fixe permet de reproduire les mêmes résultats lors de la soutenance.

## 4. Architecture attendue

```text
BigQuery : commandes + lignes + produits
             │
             ├─ requête SQL documentée ─→ extraction des ventes
             │
PostgreSQL : taux BCE + référentiel des devises
             │
             └─ requête SQL documentée ─→ extraction des taux
                                           │
                                script Python Retail Quality
                                           │
                           normalisation → contrôles → rapprochement
                                           │
                         ├─ ventes fiables : jeu final unique
                         ├─ lignes écartées : fichier de quarantaine
                         └─ rapport de qualité : JSON et graphiques
```

Le script doit fonctionner à partir d’extractions figées enregistrées localement. Il doit également permettre de refaire les extractions lorsque les accès BigQuery et PostgreSQL sont disponibles. Ainsi, le jury peut examiner le résultat et les preuves sans dépendre d’une connexion en direct.

## 5. Exigences C2 — requêtes SQL d’extraction

**C2-1. Requête BigQuery fonctionnelle.** Elle doit joindre les tables commerciales nécessaires, sélectionner seulement les colonnes utiles, filtrer la période choisie et distinguer explicitement les états de commande pertinents. Elle doit produire une extraction exploitable par le script. Le dépôt doit contenir la requête et un extrait de son résultat réel.

**C2-2. Requête PostgreSQL fonctionnelle.** Elle doit sélectionner les taux USD/EUR sur la période utile, joindre les tables relationnelles prévues et retourner des dates et des taux cohérents. Le dépôt doit contenir la requête et un extrait de son résultat réel.

**C2-3. Documentation des choix.** Chaque requête doit avoir une fiche indiquant : objectif de collecte, tables utilisées, colonnes retenues, filtres, conditions, type et clé de jointure, lignes volontairement exclues et forme du résultat. Une commande ou procédure de reproduction doit être fournie.

**C2-4. Optimisations explicites et mesurées.** Pour BigQuery, documenter la projection des colonnes, le filtre temporel, le volume traité et la durée du travail SQL. Comparer une version initiale à la version finale avec un *dry run* ou les informations du job ; ne pas prétendre à un gain dû au partitionnement si les tables utilisées ne sont pas partitionnées de cette manière. Pour PostgreSQL, créer un index pertinent pour la recherche par date et montrer le plan d’exécution ou une mesure avant/après lorsque la comparaison a du sens. [Google documente les *dry runs* et le contrôle des octets traités](https://docs.cloud.google.com/bigquery/docs/best-practices-costs).

**Critère de réception C2 :** les deux requêtes s’exécutent sur leurs systèmes respectifs, extraient réellement les données visées et leurs décisions comme leurs optimisations peuvent être expliquées à partir du dépôt.

## 6. Exigences C3 — agrégation, nettoyage et homogénéisation

Le script Python doit lire les deux extractions et réaliser les étapes dans un ordre explicite et testable :

1. **Valider les schémas d’entrée.** Signaler toute colonne indispensable absente.
2. **Normaliser les formats.** Convertir les dates dans un format unique, les taux et prix en nombres décimaux, les identifiants dans un type stable et les libellés dans une forme cohérente. Documenter les fuseaux et l’arrondi monétaire.
3. **Détecter les entrées corrompues.** Traiter notamment les identifiants manquants, prix nuls ou négatifs, dates impossibles, taux nuls ou négatifs et doublons d’identifiants de ligne.
4. **Rapprocher les sources.** Associer chaque vente à un taux BCE applicable à sa date. Pour une vente sans taux publié ce jour-là, utiliser le dernier taux antérieur disponible dans une fenêtre maximale documentée de **sept jours calendaires**. Si aucun taux admissible n’existe, mettre la ligne à vérifier et l’exclure du jeu fiable.
5. **Appliquer les règles métier.** Les commandes annulées ne doivent pas alimenter le chiffre d’affaires. Leur exclusion doit être distinguée d’une erreur de qualité : une commande annulée n’est pas une donnée « corrompue ».
6. **Calculer le montant en euros.** Si le taux BCE utilisé est exprimé en **USD pour 1 EUR**, appliquer `montant_eur = montant_usd / taux_usd_par_eur`. Utiliser une arithmétique décimale et une règle d’arrondi documentée.
7. **Produire les sorties.** Écrire le jeu final, la quarantaine et le rapport de qualité.

### Statuts et traçabilité

Chaque ligne traitée doit obtenir un statut déterministe :

- **ACCEPTÉE** : tous les contrôles requis passent ; elle entre dans le jeu final.
- **REJETÉE** : donnée corrompue ou duplication non résolue ; elle n’entre pas dans le jeu final.
- **À VÉRIFIER** : une information indispensable manque, notamment un taux admissible ; elle n’entre pas dans le jeu final.
- **EXCLUE PAR RÈGLE MÉTIER** : commande annulée ou état non retenu ; elle n’entre pas dans le jeu final.

Pour toute ligne non acceptée, enregistrer un **code de raison stable** et une explication lisible. Le rapport doit compter les lignes par statut et par raison. Il doit permettre de vérifier que chaque ligne d’entrée est comptabilisée exactement une fois.

### Jeu final

Chaque ligne du fichier final doit contenir au minimum : identifiants de commande, de ligne et de produit ; catégorie ; date normalisée ; montant source ; devise ou hypothèse de devise ; date et valeur du taux utilisé ; montant en euros ; référence de la source du taux. La clé de ligne doit être unique. Aucun identifiant personnel de client n’est nécessaire.

### Cas de test et données réellement observées

Créer des **fixtures de test séparées** avec des prix invalides, dates mal formées, doublons et taux absents afin de prouver que le script sait les traiter. Ne pas injecter silencieusement ces anomalies dans les résultats présentés comme issus des données publiques. Le rapport et le PowerPoint doivent distinguer :

- les anomalies réellement observées dans les données extraites ;
- les cas artificiels utilisés uniquement pour valider les règles du POC.

**Critère de réception C3 :** une commande documentée exécute le script et génère un seul jeu de données final nettoyé et normalisé ; les autres sorties expliquent les transformations et les exclusions. Le script et sa documentation sont accessibles dans Git.

## 7. Qualité technique minimale

Le projet doit être petit et reproductible. Une interface web ou une API ne sont **pas nécessaires** pour valider BC01. Des graphiques statiques suffisent à rendre le résultat présentable.

Prévoir :

- Python avec dépendances fixées dans un fichier dédié ;
- PostgreSQL démarrable localement, idéalement avec Docker Compose ;
- requêtes SQL versionnées séparément ;
- configuration par variables d’environnement, avec un exemple sans secrets ;
- aucune clé ou donnée d’entreprise dans le dépôt ;
- sorties générées à partir d’une période et d’extractions identifiées ;
- messages d’erreur compréhensibles lorsqu’une source ou une colonne manque ;
- tests ciblés sur les règles de nettoyage, le rapprochement des taux et l’absence de doublons dans le jeu final.

Le script doit être **idempotent** : pour les mêmes fichiers d’entrée et la même configuration, il produit les mêmes lignes, les mêmes statuts et les mêmes montants.

## 8. Structure attendue du dépôt

```text
retail-quality/
├── README.md
├── requirements.txt ou pyproject.toml
├── .env.example
├── docker-compose.yml
├── sql/
│   ├── bigquery_sales.sql
│   ├── postgres_rates.sql
│   └── schema_postgres.sql
├── src/
│   ├── extract_bigquery.py
│   ├── import_ecb.py
│   ├── extract_postgres.py
│   ├── quality_rules.py
│   └── build_dataset.py
├── tests/
│   └── fixtures/ et tests des règles
├── docs/
│   ├── sources-et-hypotheses.md
│   ├── requetes-sql.md
│   ├── algorithme-et-regles-qualite.md
│   ├── optimisations-et-mesures.md
│   └── resultats-et-limites.md
├── evidence/
│   ├── extraits_des_resultats_sql/
│   ├── mesures_des_requetes/
│   └── rapport_de_tests/
└── output/
    ├── ventes_fiables.csv
    ├── quarantaine.csv
    └── rapport_qualite.json
```

Les noms exacts peuvent évoluer, mais chacun des livrables ci-dessus doit rester facile à retrouver.

## 9. Documentation obligatoire pour le jury

Le README doit permettre à une autre personne de reconstruire le projet sans échange oral : prérequis, accès BigQuery, démarrage PostgreSQL, import des taux BCE, commandes d’extraction, commande d’agrégation, tests et emplacement des sorties.

La documentation technique doit expliquer **l’enchaînement logique de l’algorithme** et justifier chaque décision de nettoyage. Pour les règles ambiguës — par exemple un doublon ou un taux absent — écrire ce qui est fait, pourquoi, et quel effet cela a sur le chiffre d’affaires final.

Une courte section « limites » doit indiquer que le jeu commercial est fictif, que le prototype n’est pas validé sur les données de l’entreprise et qu’une utilisation réelle demanderait la validation des règles métier, des devises et des droits d’accès par les équipes concernées.

## 10. PowerPoint de soutenance

Préparer un support de **10 à 12 slides**. Il doit raconter un projet métier tout en donnant au jury les preuves demandées :

1. **Titre et contexte** — POC de fiabilisation avant reporting ; usage de données publiques de substitution.
2. **Problème métier et objectif** — risque d’un chiffre d’affaires calculé sur des lignes non fiables.
3. **Sources et architecture** — BigQuery, PostgreSQL, script, jeu final.
4. **C2 : extraction BigQuery** — requête lisible, choix des tables, jointure, filtre et extrait de résultat exécuté.
5. **C2 : extraction PostgreSQL** — requête lisible, jointure, filtre et extrait de résultat exécuté.
6. **C2 : optimisation** — choix techniques et chiffres mesurés ; préciser ce qui est une estimation et ce qui vient d’une exécution.
7. **C3 : algorithme** — étapes de normalisation, contrôle, rapprochement et calcul.
8. **C3 : règles de qualité** — tableau « anomalie → décision → raison enregistrée ».
9. **C3 : preuve d’exécution** — volumes à chaque étape, exemple de ligne acceptée et de ligne écartée, extrait du jeu final.
10. **Résultat métier** — chiffre d’affaires exploitable et répartition des motifs d’exclusion, uniquement à partir des résultats réellement calculés.
11. **Reproductibilité** — dépôt Git, commandes, tests et documentation.
12. **Limites et suites possibles** — données fictives, hypothèses, contrôles nécessaires avant un usage réel.

Les slides doivent montrer les **résultats du code exécuté**. Aucun chiffre ne doit être inventé pour améliorer le récit.

## 11. Correspondance explicite avec la grille RNCP

| Critère du mail | Preuve exigée dans le projet |
|---|---|
| Requêtes SQL fonctionnelles | Requêtes BigQuery et PostgreSQL exécutées, résultats enregistrés, commandes de reproduction |
| Sélections, filtrages, conditions, jointures documentés | Fiche par requête et explication sur les slides C2 |
| Optimisations explicitées | Version initiale/finale, mesures BigQuery et PostgreSQL, limites des comparaisons |
| Agrégation, nettoyage et normalisation fonctionnels | Script exécutable, deux extractions rapprochées, jeu final, quarantaine et rapport |
| Script versionné sur Git | Dépôt accessible avec historique de modifications |
| Dépendances, commandes et algorithme documentés | README et documentation technique complète |
| Choix de nettoyage et d’homogénéisation expliqués | Catalogue des règles, codes de raison, exemples avant/après |

## 12. Conditions de réussite avant la soutenance

Le projet est prêt uniquement lorsque :

- les deux requêtes ont été **réellement exécutées** et ont produit des données ;
- l’exécution complète du pipeline a généré les fichiers attendus ;
- le jeu final ne contient ni doublon de clé, ni montant invalide, ni vente sans taux admissible ;
- les volumes du rapport de qualité sont cohérents avec les volumes extraits ;
- les tests des cas corrompus et des cas limites réussissent ;
- le dépôt Git contient le code, les requêtes, les commandes, la documentation et des preuves consultables ;
- tous les chiffres du PowerPoint correspondent aux sorties enregistrées ;
- l’auteur peut expliquer en quelques phrases la jointure des ventes, le choix du taux, la différence entre rejet qualité et exclusion métier, et les optimisations mesurées.

**Priorité absolue : C2 et C3.** Toute fonctionnalité qui ne renforce pas directement une preuve de ces compétences doit être reportée après la soutenance.