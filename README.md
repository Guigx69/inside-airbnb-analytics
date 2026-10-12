# Inside Airbnb Analytics — V1.3

Projet Data Engineering : **Python · Snowflake · dbt Core**, basé sur les archives publiques [Inside Airbnb](https://insideairbnb.com/).

## Documentation : commencer ici

| Document | À quoi il sert |
|---|---|
| **[1. Manuel manager A à Z](docs/MANUEL_MANAGER_A_Z.md)** | Installer, configurer Snowflake, choisir le scénario compte existant/vierge, lancer, tester et dépanner |
| **[2. Guide géographique A à Z](docs/GUIDE_GEOGRAPHIE_A_Z.md)** | Ville, pays, continent, plusieurs zones, monde, dates, types de fichiers, dry-run, ingestion |

**Ordre recommandé :** lire le manuel, puis le guide géographique si nécessaire. Les anciennes versions redondantes ont été supprimées ; l'historique des modifications reste disponible dans Git. Les scripts exécutables restent dans `scripts/` et `sql/` ; les exemples géographiques dans `config/`.

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
- **Lyon :** cinq snapshots, 15 lots RAW non vides, **17 692 229 lignes** contrôlées sur le compte source le 12/10/2026.
- **Non testé :** bootstrap et build sur un compte Snowflake vierge chez le manager. La fraîcheur des marts après le dernier snapshot n'a pas été établie.

## Points d'attention

- Les variables d'environnement et mots de passe restent **hors Git** ; `DBT_XXX` est un placeholder à remplacer.
- Le moteur de sélection JSON combine les inclusions géographiques par **OU** ; vérifier le périmètre dans le dry-run.
- Le collecteur accepte `--all` ; l'orchestrateur `run_pipeline.py` ne prend pas en charge un lancement mondial en une seule commande.
- `--sync`, l'ingestion RAW et `dbt build` sont des opérations modifiantes. Consulter les procédures avant utilisation.
- L'indisponibilité d'une nuit dans Calendar n'est pas une preuve d'occupation.

Pour les commandes complètes, la préparation du compte Snowflake, les helpers, les diagnostics et les critères de réception, consulter le **[manuel manager](docs/MANUEL_MANAGER_A_Z.md)**.
