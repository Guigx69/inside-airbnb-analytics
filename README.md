# Inside Airbnb Analytics — V1.3

Projet Data Engineering : **Python · Snowflake · dbt Core**, basé sur les archives publiques [Inside Airbnb](https://insideairbnb.com/).

## Documentation : commencer ici

| Document | À quoi il sert |
|---|---|
| **[1. Manuel manager A à Z](docs/MANUEL_MANAGER_A_Z.md)** | Installer, configurer Snowflake, choisir le scénario compte existant/vierge, lancer, tester et dépanner |
| **[2. Guide géographique A à Z](docs/GUIDE_GEOGRAPHIE_A_Z.md)** | Ville, pays, continent, plusieurs zones, monde, dates, types de fichiers, dry-run, ingestion |

**Ordre recommandé :** lire le manuel, puis le guide géographique si nécessaire. Les scripts exécutables restent dans `scripts/` et `sql/` ; les exemples géographiques dans `config/`.

## Architecture

```text
Inside Airbnb (CSV.GZ datés)
    -> scripts/download_inside_airbnb.py + data_manifest.csv (SHA-256)
    -> scripts/check_archives.py
    -> scripts/load_raw_to_snowflake.py
    -> Snowflake AIRBNB.RAW (listings / calendar / reviews + INGESTION_LOG)
    -> dbt STAGING -> INTERMEDIATE -> MARTS
```

## Démarrage minimal sous Windows PowerShell

```powershell
git clone https://github.com/Guigx69/inside-airbnb-analytics.git
cd inside-airbnb-analytics
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --location lyon --dry-run
.\.venv\Scripts\python.exe .\scripts\check_archives.py --location lyon --hash
```

Le contrôle d'archives suppose que les fichiers référencés dans `data_manifest.csv` ont été transférés sur ce poste ; **les archives physiques ne sont pas sur GitHub**. Le démarrage Snowflake exige des identifiants et des rôles configurés conformément au manuel. **Ne pas lancer `dbt build` avant validation des coûts et du compte cible.**

## Résultats de référence

- **25 modèles dbt**, dont 14 tables et 11 vues.
- **456 tests** ; build du 09/10/2026 : **480 PASS, 1 WARN, 0 ERROR**, en 1 h 05 min 46 s.
- Avertissement connu : `assert_stg_calendar_listing_exists` (3 163 clés orphelines).
- **1 629 archives**, 35,16 Gio, vérifiées localement par SHA-256 ; le manifeste est versionné, pas les archives.
- **Lyon :** cinq snapshots, 15 lots RAW non vides, **17 692 229 lignes** contrôlées sur l'environnement de développement le 12/10/2026.
- **Non testé :** bootstrap et build sur un compte Snowflake vierge sur l'environnement cible. La fraîcheur des marts après le dernier snapshot n'a pas été établie.

## État des données — octobre 2026

- **120 zones** recensées dans le catalogue, **553 snapshots courants** et **1 659 archives courantes**.
- **120 nouveaux snapshots** détectés par comparaison des chemins (119 zones, deux nouvelles dates pour Vaud) ; **360 nouvelles archives** téléchargées et ajoutées au manifeste.
- **1 989 entrées** dans `data_manifest.csv` après synchronisation, contre 1 629 avant ; aucune suppression ni modification des entrées historiques lors de la comparaison.
- **1 659/1 659 archives du catalogue courant vérifiées** avec `--verify` (taille et SHA-256). Les **330 autres entrées historiques** du manifeste nécessitent le contrôle global `check_archives.py --hash` pour une preuve d'intégrité complète.
- Dernière date du catalogue observée : **05/10/2026 (Vaud)**. Ce constat est daté, pas une garantie de fraîcheur future.
- **Non encore validé pour ces nouvelles données :** ingestion RAW World, exécution dbt après synchronisation, fraîcheur des marts et validation sur un compte Snowflake vierge.

> **Attention aux chiffres historiques ci-dessous :** la référence de 1 629 archives / 35,16 Gio décrit l'état **avant** la synchronisation d'octobre ; elle ne représente plus le manifeste actuel. Recalculer la volumétrie depuis `data_manifest.csv` plutôt que réutiliser cette taille.

### Cycle de maintenance autonome

Consulter **[la procédure de synchronisation World](docs/MAINTENANCE_WORLD_A_Z.md)** pour les commandes PowerShell reproductibles, les contrôles d'intégrité, le diagnostic et les conditions de passage à Snowflake. L'actualisation du manifeste **n'actualise pas automatiquement** les tables RAW ni les marts dbt.

## Points d'attention

- Les variables d'environnement et mots de passe restent **hors Git** ; `DBT_XXX` est un placeholder à remplacer.
- Le moteur de sélection JSON combine les inclusions géographiques par **OU** ; vérifier le périmètre dans le dry-run.
- Le collecteur accepte `--all` ; l'orchestrateur `run_pipeline.py` ne prend pas en charge un lancement mondial en une seule commande.
- `--sync`, l'ingestion RAW et `dbt build` sont des opérations modifiantes. Consulter les procédures avant utilisation.
- L'indisponibilité d'une nuit dans Calendar n'est pas une preuve d'occupation.

Pour les commandes complètes, la préparation du compte Snowflake, les helpers, les diagnostics et les critères de réception, consulter le **[manuel manager](docs/MANUEL_MANAGER_A_Z.md)**.
