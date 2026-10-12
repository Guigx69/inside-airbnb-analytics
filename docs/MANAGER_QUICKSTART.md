# Démarrage rapide manager — Windows et Snowflake

Ce document est un résumé. Le guide de référence est le [Manuel manager A à Z](MANUEL_MANAGER_A_Z.md), complété par le [Guide géographique A à Z](GUIDE_GEOGRAPHIE_A_Z.md).

## Prérequis

Git, Python compatible avec dbt-core 1.12, PowerShell et un compte Snowflake. Les rôles, droits, entrepôts et tables RAW doivent être préparés selon le scénario du manuel. Ne jamais transmettre de mot de passe personnel ni versionner de secret.

## Cloner et préparer

```powershell
git clone https://github.com/Guigx69/inside-airbnb-analytics.git
cd inside-airbnb-analytics
.\scripts\setup.ps1
```

Créer le profil `$HOME\.dbt\profiles.yml` avec **son propre compte**, rôle, entrepôt, base et schéma Snowflake. Le profil dbt se nomme `inside_airbnb`. Le fichier `.env` local n'est **pas chargé automatiquement**.

Pour l'ingestion RAW, définir les variables `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `DBT_SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE` et `SNOWFLAKE_SCHEMA`.

## Vérifications sans écriture

```powershell
.\scripts\check_environment.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Scénario A — RAW Snowflake déjà disponible

Vérifier les droits de lecture sur RAW et les droits de création des objets dbt. Contrôler la cible avant :

```powershell
.\.venv\Scripts\dbt.exe build
```

**Attention :** cette commande crée ou actualise des objets et lance les tests.

## Scénario B — Compte neuf

Le dépôt ne contient pas les archives physiques `data/raw/`. Le collecteur télécharge les snapshots encore publiés ; les archives historiques absentes du catalogue exigent une copie autorisée. Utiliser le bootstrap et l'ordre d'exécution du manuel ; vérifier les archives, les coûts et les droits avant ingestion.

Pilote Lyon, en lecture seule :

```powershell
.\.venv\Scripts\python.exe scripts\download_inside_airbnb.py --location lyon --dry-run --verify
.\.venv\Scripts\python.exe scripts\check_archives.py --country france --location lyon --hash
.\.venv\Scripts\python.exe scripts\load_raw_to_snowflake.py --dry-run --country france --location lyon
```

Le pilote Lyon du 17/09/2026 a été contrôlé sur le compte de développement, **pas sur un compte vierge**.

## Streamlit dans Snowflake

Le manifeste `streamlit/snowflake.yml` peut contenir des identifiants propres au développement. Adapter les objets, rôles et privilèges avant tout déploiement.

## Limites

Aucune reconstruction historique intégrale ni installation de bout en bout sur compte Snowflake neuf n'est certifiée. Il n'existe pas d'orchestration planifiée de production démontrée dans ce dépôt.
