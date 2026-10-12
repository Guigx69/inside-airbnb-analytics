# Inside Airbnb Analytics — plateforme d'analyse historique

**Projet de démonstration Data Engineering | Python · Snowflake · dbt Core**

Plateforme analytique fondée sur les archives publiques [Inside Airbnb](https://insideairbnb.com/). Elle conserve les observations datées, les transforme en modèles dbt contrôlés et fournit des indicateurs de marché, de quartier, d'hôtes, de prix, de disponibilité et d'avis.

> **Statut au 12 octobre 2026 :** V1.3 validée sur l'environnement Snowflake de développement. Déploiement sur le compte du responsable **non réalisé**. Les scripts de création d'un compte vierge sont proposés dans la [PR #5](https://github.com/Guigx69/inside-airbnb-analytics/pull/5), non fusionnée et non validée sur un compte vierge.

## Résultats vérifiés

| Indicateur | Résultat |
|---|---:|
| Modèles dbt | 25 : 14 tables et 11 vues |
| Tests dbt | 456 |
| Résultat du build V1.3 | 480 PASS · 1 WARN · 0 ERROR |
| Durée du build V1.3 | 1 h 05 min 46 s |
| Durée avant optimisation | 2 h 02 min 44 s |
| Réduction de durée mesurée | 46,4 % |
| Archives locales vérifiées par SHA-256 | 1 629 (manifeste local, incluant Lyon septembre 2026) |
| Volume local des archives | 35,16 Gio |
| Archives manquantes ou invalides | 0 |

Le build a été réalisé le 9 octobre 2026 sur le compte de développement. Les chiffres ne sont **pas** une promesse de performance ou de résultats identiques chez le responsable. L'avertissement connu `assert_stg_calendar_listing_exists` signale **3 163 clés calendrier sans correspondance dans listings** ; il est conservé volontairement.

## Architecture

```text
Inside Airbnb (listings / calendar / reviews)
          │  Archives CSV.GZ datées + manifeste SHA-256
          ▼
Python : contrôle des archives et ingestion
          ▼
Snowflake AIRBNB.RAW
  RAW_LISTINGS / RAW_CALENDAR / RAW_REVIEWS
  INGESTION_LOG / INSIDE_AIRBNB_STAGE
          ▼
dbt STAGING (3 modèles)
          ▼
dbt INTERMEDIATE (10 modèles)
          ▼
dbt MARTS (12 modèles)
          ▼
Analyses et tableaux de bord
```

La couche RAW conserve les données sources dans une colonne `VARIANT` et ajoute les métadonnées de provenance (pays, ville, date du snapshot, fichier et date de chargement). Les modèles analytiques distinguent les **changements observés entre snapshots** des événements réellement survenus sur le marché.

**Attention :** une nuit indisponible dans `calendar` ne constitue pas une réservation ni une occupation démontrée. Les indicateurs de disponibilité ne sont pas des ventes réelles.

## Démarrage rapide — Windows PowerShell

Depuis la racine du dépôt, avec Python et l'environnement virtuel déjà installés :

```powershell
.\.venv\Scripts\python.exe .\scripts\check_archives.py --hash
.\.venv\Scripts\python.exe .\scripts\check_archives.py --country france --location lyon --hash
```

Ces commandes sont **locales et en lecture seule**. Elles exigent que `data_manifest.csv` et les archives référencées soient présents sur le poste.

Pour accéder à Snowflake, configurer le profil dbt à partir de `profiles.yml.example`, puis définir les variables d'environnement hors Git :

| Variable | Usage |
|---|---|
| `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `DBT_SNOWFLAKE_PASSWORD` | Connexion |
| `SNOWFLAKE_DATABASE` | Base, défaut `AIRBNB` |
| `SNOWFLAKE_WAREHOUSE` | Warehouse, défaut `DBT_WH` |
| `SNOWFLAKE_ROLE` | Ingestion, défaut `INGESTION_ROLE` |
| `SNOWFLAKE_SCHEMA` | Schéma d'ingestion, défaut `RAW` |
| `SNOWFLAKE_DBT_ROLE` | Transformations, défaut `DBT_ROLE` |
| `DBT_SNOWFLAKE_SCHEMA` | Schéma cible dbt, obligatoire |

Contrôles de connexion et de compilation :

```powershell
.\.venv\Scripts\dbt.exe debug
.\.venv\Scripts\dbt.exe parse
```

**Après validation des droits, des données RAW et du budget Snowflake seulement :**

```powershell
.\.venv\Scripts\dbt.exe build --threads 4
```

## Déploiement chez le responsable

Deux scénarios distincts :

1. **Compte Snowflake avec RAW déjà présent :** vérifier les objets, les droits et la cohérence du journal ; ne jamais réinitialiser RAW ; exécuter ensuite dbt.
2. **Compte Snowflake vierge :** provisionner le warehouse et les rôles, créer les objets RAW, attribuer les privilèges, vérifier les archives, charger un snapshot pilote, puis étendre l'historique et lancer dbt.

Le second scénario **n'a pas encore été testé sur un compte vierge**. Les scripts SQL sont dans la [PR #5](https://github.com/Guigx69/inside-airbnb-analytics/pull/5) ; ne pas les considérer comme disponibles sur `main` tant que cette PR n'est pas fusionnée.

## Documentation de référence

| Document | Contenu |
|---|---|
| [Guide de lecture et de livraison](docs/guide_livraison_fr.md) | Installation, exploitation, contrôles, risques et critères d'acceptation |
| [Déploiement manager V1.3](docs/v1_3_manager_deployment.md) | Benchmark et recommandations de migration |
| [Deux scénarios Snowflake — PR #4](https://github.com/Guigx69/inside-airbnb-analytics/pull/4) | Compte existant ou vierge |
| [Bootstrap RAW et droits — PR #5](https://github.com/Guigx69/inside-airbnb-analytics/pull/5) | Scripts SQL et chargement Lyon |
| [Profil Snowflake dbt](profiles.yml.example) | Exemple de configuration sans secrets |

## Structure du dépôt

- `models/staging/` : typage et normalisation des sources.
- `models/intermediate/` : calculs historiques réutilisables.
- `models/marts/` : tables et vues d'analyse.
- `scripts/` : collecte, vérification, ingestion et orchestration.
- `tests/` : tests de qualité complémentaires.
- `macros/` : macros dbt.
- `config/` : sélections géographiques d'exemple.
- `docs/` : documentation technique et livraison.
- `data_manifest.csv` : inventaire et empreintes des archives, à préserver.

Le manifeste GitHub `main` contient désormais **1 629 entrées** (commit `167cc5f`) : les trois ajouts correspondent à Lyon au 17 septembre 2026. Les documents décrivant la version déployée restent fondés sur les quatre snapshots antérieurs jusqu'à nouvelle ingestion et validation dbt.

Les archives `data/raw/`, les secrets, les environnements virtuels et les résultats dbt générés ne doivent pas être versionnés. **GitHub ne constitue pas une sauvegarde des 35,16 Gio d'archives locales.**

## Limites et feuille de route

La V1.3 valide les transformations et la qualité des données sur l'environnement de développement. Les coûts Snowflake, le déploiement sur un nouveau compte, les droits d'accès finaux du responsable et la sauvegarde indépendante des archives restent à traiter. La feuille de route géographique est : **Lyon → France → Europe → monde**.

Les anomalies sources sont documentées, jamais masquées par une suppression arbitraire de lignes.


## Reprise du projet par un responsable

Le [manuel complet A à Z](docs/MANUEL_MANAGER_A_Z.md) détaille l'installation Windows, les deux scénarios Snowflake, les commandes d'ingestion et de build, les helpers, les contrôles, le diagnostic et les critères de livraison. Lire ce manuel avant toute exécution sur un nouveau compte.


### Sélection géographique complète

Consulter le [guide opérationnel ville / pays / continent / multi-zones / monde](docs/GUIDE_GEOGRAPHIE_A_Z.md) avant toute collecte ou ingestion à grande échelle.
