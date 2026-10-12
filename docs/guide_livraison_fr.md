# Guide de livraison et d'exploitation — Inside Airbnb Analytics V1.3

**Langue de référence : français.** Public : responsable de projet, ingénieur data, administrateur Snowflake. Date de consolidation : 12 octobre 2026.

## 1. Périmètre et statut

Le projet traite les archives datées `listings.csv.gz`, `calendar.csv.gz` et `reviews.csv.gz`. Il fournit 25 modèles dbt : 3 staging, 10 intermediate et 12 marts/fact. Les deux intermédiaires lourds `int_listing_calendar_metrics` et `int_listing_availability_horizon` sont matérialisés en tables depuis la V1.3.

**Validé sur le compte de développement :** build complet du 9 octobre 2026, 14 tables, 11 vues, 456 tests, 480 PASS, 1 WARN, 0 ERROR, 1 h 05 min 46,11 s. Ancien build : 2 h 02 min 44 s ; gain ≈46,4 %. Avertissement `assert_stg_calendar_listing_exists` : 3 163 clés calendrier orphelines. Aucun effacement de lignes source pour masquer l'avertissement.

**Vérifié localement par l'utilisateur le 12 octobre 2026 :** 1 629 archives, 35,16 Gio, aucune manquante ni invalide, contrôle SHA-256 réussi. Cette vérification n'est pas une sauvegarde indépendante.

**Non validé :** installation sur un compte Snowflake entièrement vierge, ingestion initiale chez le responsable, exécution dbt sur son compte, sauvegarde externe des archives.

## 2. Prérequis

- Poste Windows avec Git, Python et environnement virtuel ; dbt Core 1.12.4 et dbt-snowflake 1.12.1 ont été utilisés lors de la validation.
- Accès réseau au compte Snowflake, warehouse disponible, rôle administrateur pour provisionner les objets si nécessaire.
- Fichiers `data_manifest.csv` et `data/raw/...` accessibles sur le poste d'ingestion. Les archives ne sont pas dans Git.
- Profil `profiles.yml` basé sur `profiles.yml.example` ; secrets injectés par variables d'environnement, jamais committés.
- Budget et dimensionnement Snowflake approuvés avant un build ou une ingestion importante.

## 3. Architecture et responsabilités

```text
Archives Inside Airbnb + manifeste SHA-256
     └─ scripts/check_archives.py (local, lecture seule)
     └─ scripts/load_raw_to_snowflake.py (PUT/COPY/contrôles/journal)
           └─ AIRBNB.RAW (3 tables + INGESTION_LOG + stage)
                 └─ dbt staging → intermediate → marts
```

Le loader vérifie taille et SHA-256, contrôle l'inventaire RAW et le journal avant l'ingestion, et ne doit pas être utilisé comme mécanisme de réinitialisation globale. Chaque lot nouveau est chargé et journalisé ; une incohérence entre RAW et journal provoque un arrêt.

## 4. Contrôles hors Snowflake — à effectuer en premier

```powershell
cd C:\Projects\inside_airbnb
.\.venv\Scripts\python.exe .\scripts\check_archives.py --hash
.\.venv\Scripts\python.exe .\scripts\check_archives.py --country france --location lyon --hash
```

Le premier contrôle a déjà réussi sur le poste de développement. Le second permet de **constater**, sans supposer, combien de fichiers et de snapshots Lyon sont effectivement présents. Ne pas modifier le manifeste local non committé et ne pas exécuter `git reset --hard` ni `git clean`.

## 5. Scénario A — compte avec RAW existant

1. Vérifier le compte, la base, le warehouse, les rôles et les schémas utilisés.
2. Contrôler les quatre objets RAW et `INGESTION_LOG`, leurs colonnes, types et volumes. Ne pas exécuter le bootstrap de création sur un compte déjà provisionné.
3. Vérifier les droits de lecture de `DBT_ROLE` et de création des objets analytiques.
4. Exécuter `dbt debug`, `dbt parse` puis `dbt build --threads 4`.
5. Contrôler les résultats, les écarts de volumétrie et les avertissements. Conserver `target/run_results.json` et les journaux en dehors du répertoire nettoyé.

## 6. Scénario B — compte entièrement vierge

**Les scripts proposés sont sur la PR #5 et n'ont pas été exécutés sur un compte vierge.** Les valider et les fusionner avant une livraison officielle.

1. L'administrateur crée un warehouse et les rôles `INGESTION_ROLE` et `DBT_ROLE` ; attribue ces rôles aux utilisateurs de service autorisés. Ne pas partager de mot de passe.
2. Exécuter, avec le rôle habilité, `sql/bootstrap_manager_empty_raw.sql` pour créer la base, RAW, les tables, le journal et le stage interne. Les instructions sont additives (`IF NOT EXISTS`) et ne migrent pas d'objets existants.
3. Exécuter les scripts d'attribution `sql/bootstrap_manager_ingestion_grants.sql` et `sql/bootstrap_manager_dbt_grants.sql`. Vérifier le résultat de `SHOW GRANTS`.
4. Vérifier la configuration `DBT_SNOWFLAKE_SCHEMA` et la convention de nommage des schémas `_STAGING`, `_INTERMEDIATE`, `_MARTS`. Les schémas générés doivent appartenir au rôle qui exécute dbt.
5. Vérifier les archives Lyon avec `check_archives.py --country france --location lyon --hash`. Contrôler les dates présentes dans le manifeste ; ne pas inventer les snapshots.
6. Effectuer un dry-run de l'ingestion, puis charger **un seul snapshot pilote**. Examiner `INGESTION_LOG` et les nombres de lignes RAW.
7. Étendre au périmètre Lyon validé, lancer `dbt debug`, `dbt parse` et `dbt build --threads 4`.
8. Documenter les résultats sur le compte cible et faire valider les droits de consultation des marts.

```powershell
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country france --location lyon --dry-run
# À exécuter uniquement après validation du compte cible et de la date :
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country france --location lyon --snapshot 2025-09-18
```

**Important :** le loader `main` fait un `PUT`, puis un `DELETE` du lot ciblé avant `COPY INTO`. Ne pas l'exécuter contre une table RAW incompatible ou contenant des données non journalisées ; le contrôle préalable du journal est indispensable.

## 7. Vérifications après installation

```sql
SELECT COUNT(*) FROM AIRBNB.RAW.RAW_LISTINGS;
SELECT COUNT(*) FROM AIRBNB.RAW.RAW_CALENDAR;
SELECT COUNT(*) FROM AIRBNB.RAW.RAW_REVIEWS;
SELECT COUNT(*) FROM AIRBNB.RAW.INGESTION_LOG;
SELECT SOURCE_COUNTRY, SOURCE_CITY, SNAPSHOT_DATE, SOURCE_FILE, ROW_COUNT
FROM AIRBNB.RAW.INGESTION_LOG
ORDER BY SOURCE_COUNTRY, SOURCE_CITY, SNAPSHOT_DATE, SOURCE_FILE;
```

Les nombres de lignes doivent être comparés au périmètre réellement ingéré, pas au benchmark de développement. Le build doit terminer sans erreur ; les warnings doivent être examinés et documentés.

## 8. Sécurité, coûts et réversibilité

- Aucun secret dans Git, la documentation ou les captures partagées.
- Aucune ingestion mondiale ni reconstruction coûteuse sans estimation et accord.
- Ne pas exécuter de `DROP`, `TRUNCATE`, `CREATE OR REPLACE` sur RAW ou de commande Git destructive pour « nettoyer ».
- Les archives locales ne sont pas couvertes par Git ; prévoir une copie indépendante lorsque possible.
- Un retour arrière applicatif consiste à revenir à une version du code et à reconstruire les objets dbt concernés ; **ne pas vider RAW**.
- Après expiration du compte de développement, les archives locales permettent de reconstituer les sources, mais pas les objets Snowflake non exportés ni les identifiants du compte.

## 9. Acceptation / transmission

| Critère | Situation au 12/10/2026 |
|---|---|
| Archives locales vérifiées | Oui : 1 629 / 35,16 Gio / SHA-256 OK |
| Build dbt de référence | Oui : 480 PASS / 1 WARN / 0 ERROR |
| Tables, stage et rôles de référence inspectés | Oui |
| Scripts bootstrap préparés | Oui, PR #5 ouverte |
| Test sur compte vierge | Non |
| Build sur compte manager | Non |
| Livraison et approbation finale | En attente |

## 10. Références

- [README principal](../README.md)
- [Benchmark et notes de déploiement V1.3](v1_3_manager_deployment.md)
- [PR #4 : scénarios de déploiement](https://github.com/Guigx69/inside-airbnb-analytics/pull/4)
- [PR #5 : bootstrap SQL et guide Lyon](https://github.com/Guigx69/inside-airbnb-analytics/pull/5)
