# Déploiement manager — deux environnements Snowflake

Version de référence : `main`, V1.3 fusionnée via PR #3. Ce document distingue **déploiement du code dbt** et **provisionnement des données RAW**. Il ne constitue pas une preuve de déploiement sur le compte du manager.

## Préparation commune

1. Cloner `main` sur un poste/runner avec Python et dbt Core + adaptateur Snowflake (versions de validation : dbt Core 1.12.4, dbt-snowflake 1.12.1).
2. Créer un environnement virtuel et installer les dépendances dans des versions compatibles. Vérifier `dbt --version` et `python --version`.
3. Configurer le profil dbt à partir de `profiles.yml.example` ; ne jamais versionner le mot de passe.
4. Configurer les variables : `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `DBT_SNOWFLAKE_PASSWORD`, `SNOWFLAKE_DBT_ROLE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_WAREHOUSE`, `DBT_SNOWFLAKE_SCHEMA`. Pour le loader Python, les variables sont **distinctes** : `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA` (défaut RAW).
5. Confirmer les droits d'usage du warehouse et de la base, et les droits nécessaires sur les schémas dbt. Vérifier que le rôle d'ingestion possède les droits de stage et de DML sur RAW si l'ingestion est nécessaire.
6. Exécuter `dbt debug`, puis `dbt parse` ; ne pas lancer un build si ces étapes échouent.

## Cas A — compte Snowflake avec RAW déjà chargé

**Contrôles préalables en lecture seule**, à adapter au nom de base réel :

```sql
SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE();
SELECT COUNT(*) FROM AIRBNB.RAW.RAW_LISTINGS;
SELECT COUNT(*) FROM AIRBNB.RAW.RAW_CALENDAR;
SELECT COUNT(*) FROM AIRBNB.RAW.RAW_REVIEWS;
SELECT COUNT(*) FROM AIRBNB.RAW.INGESTION_LOG;
```

Ces comptes ne démontrent pas à eux seuls la compatibilité. Vérifier les colonnes techniques `SOURCE_COUNTRY`, `SOURCE_CITY`, `SNAPSHOT_DATE`, `SOURCE_FILE`, `RAW_DATA` et la cohérence des dates/villes attendues. Confirmer les droits et l'absence de collision avec des schémas dbt existants.

Puis :

```powershell
.\.venv\Scripts\dbt.exe debug
.\.venv\Scripts\dbt.exe parse
.\.venv\Scripts\dbt.exe build --threads 4
```

Conserver le journal, `target/run_results.json` et les versions de dépendances. Un environnement cible avec un périmètre RAW différent peut produire d'autres volumes et résultats : ne pas imposer artificiellement les totaux du POC.

## Cas B — compte Snowflake vierge

**Étapes préalables manuelles et à valider avec le responsable Snowflake :**

1. Créer/configurer le warehouse, les rôles, la base `AIRBNB`, le schéma `RAW`, les tables `RAW_LISTINGS`, `RAW_CALENDAR`, `RAW_REVIEWS`, `INGESTION_LOG`, et le stage `INSIDE_AIRBNB_STAGE` avec les colonnes et types attendus par le loader. **Ne pas inventer un schéma DDL** : reprendre les définitions réelles de l'environnement source, notamment les types des colonnes techniques et du journal.
2. Obtenir les fichiers sources CSV.GZ et le `data_manifest.csv` correspondant. Le dépôt GitHub seul ne garantit pas que les archives historiques sont disponibles sur le poste du manager.
3. Définir un périmètre de démarrage réduit et explicite (par exemple une ville et un snapshot), puis préparer un fichier de sélection géographique valide ; le `config/geography.example.json` est un exemple, **pas** une sélection de production.
4. Vérifier les archives et le manifeste avant chargement ; exécuter d'abord le loader avec `--dry-run` et `--selection-file`. Ne lancer l'ingestion effective qu'après vérification des objets RAW, des droits, des crédits et de la sélection.
5. Contrôler le journal d'ingestion, les volumes et les clés source après le chargement.
6. Lancer `dbt debug`, `dbt parse`, puis `dbt build --threads 4`. Sur un petit périmètre, les totaux de tests et certains warnings peuvent différer.

**Point de vigilance :** la création automatique de l'infrastructure Snowflake et la migration intercomptes ne sont pas fournies par la PR V1.3. Le loader actuel ne remplace pas un bootstrap complet du compte. Ne pas exécuter un chargement de 1 629 archives sur un essai gratuit sans estimation de coût ni validation.

## Validation V1.3 sur le compte de développement (référence, pas promesse de résultat cible)

- Build complet : 1 h 05 min 46,11 s contre 2 h 02 min 44 s avant optimisation (gain ≈46,4 %).
- 25 modèles (14 tables, 11 vues), 456 tests ; `PASS=480 WARN=1 ERROR=0 TOTAL=481`.
- Warning préexistant : `assert_stg_calendar_listing_exists`, 3 163 clés Calendar orphelines ; ne pas supprimer les données pour masquer ce warning.

## Go / No-Go pour le manager

- **GO code :** profil valide, RAW compatible, `dbt build` terminé sans erreur, résultats documentés, droits d'accès aux marts vérifiés.
- **NO-GO :** RAW absent/incompatible, droits insuffisants, échec dbt, divergence de données non expliquée ou absence de budget Snowflake.
- Pour rollback, revenir au commit applicatif précédent et reconstruire les objets dbt concernés ; aucune purge RAW.

## Informations à récupérer avant le déploiement effectif

Identifiant du compte Snowflake cible (sans secret), nom de la base, warehouse et rôles, présence/absence de RAW, volumes/périmètre géographique, accès aux fichiers sources et contraintes de budget. Ne jamais transmettre les mots de passe dans les tickets ou GitHub.
