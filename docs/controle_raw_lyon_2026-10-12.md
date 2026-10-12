# Contrôle RAW Lyon — 12 octobre 2026

## Périmètre et preuve

Résultats transmis depuis le compte Snowflake source : requête en lecture seule sur `AIRBNB.RAW.INGESTION_LOG`, puis agrégations `COUNT(*)` par `SOURCE_CITY = 'lyon'` et `SNAPSHOT_DATE` dans les trois tables `AIRBNB.RAW.RAW_*`.

**Constat :** cinq dates journalisées, trois fichiers par date, quinze combinaisons date/type présentes en RAW, avec des volumes strictement positifs. Ce contrôle ne remplace pas une comparaison ligne à ligne aux archives ni une exécution dbt après le dernier chargement.

| Snapshot | RAW_CALENDAR | RAW_LISTINGS | RAW_REVIEWS |
|---|---:|---:|---:|
| 2025-09-18 | 3 521 155 | 9 647 | 428 301 |
| 2025-12-22 | 3 577 000 | 9 800 | 450 436 |
| 2026-03-25 | 1 607 095 | 4 403 | 350 235 |
| 2026-06-22 | 3 414 575 | 9 317 | 469 378 |
| 2026-09-17 | 3 358 365 | 9 201 | 473 321 |

**Totaux vérifiés :** CALENDAR **15 478 190**, LISTINGS **42 368**, REVIEWS **2 171 671**, soit **17 692 229 lignes RAW** sur les cinq snapshots.

**Point d'attention :** le volume CALENDAR du 2026-03-25 est sensiblement inférieur à celui des autres dates. Le contrôle établit sa présence, pas l'explication de cette variation.

## Critères et limites

- **OK :** manifeste GitHub `main` à 1 629 entrées depuis `167cc5f` ; vérification locale SHA-256 des 1 629 archives communiquée par l'utilisateur.
- **OK :** cinq snapshots Lyon dans le journal, trois fichiers par date.
- **OK :** quinze lots Lyon non vides dans les tables RAW.
- **Non démontré :** correspondance exacte des nombres de lignes avec les archives sources, absence de doublons, fraîcheur des marts après le snapshot 2026-09-17, état de l'environnement cible du manager.
- **Benchmark antérieur :** dbt V1.3 PASS=480, WARN=1, ERROR=0 sur le compte source ; ne pas l'interpréter comme un nouveau build effectué après le dernier chargement.

## Requête de vérification reproductible

```sql
SELECT 'CALENDAR' AS TYPE_FICHIER, SNAPSHOT_DATE, COUNT(*) AS NB_LIGNES
FROM AIRBNB.RAW.RAW_CALENDAR
WHERE LOWER(SOURCE_CITY) = 'lyon'
GROUP BY SNAPSHOT_DATE
UNION ALL
SELECT 'LISTINGS', SNAPSHOT_DATE, COUNT(*)
FROM AIRBNB.RAW.RAW_LISTINGS
WHERE LOWER(SOURCE_CITY) = 'lyon'
GROUP BY SNAPSHOT_DATE
UNION ALL
SELECT 'REVIEWS', SNAPSHOT_DATE, COUNT(*)
FROM AIRBNB.RAW.RAW_REVIEWS
WHERE LOWER(SOURCE_CITY) = 'lyon'
GROUP BY SNAPSHOT_DATE
ORDER BY SNAPSHOT_DATE, TYPE_FICHIER;
```
