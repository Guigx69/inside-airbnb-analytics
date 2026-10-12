# Bootstrap initial manager — Lyon

**Statut : proposition de bootstrap, NON testée sur un compte Snowflake vierge.** Branche `feature/manager-bootstrap-v1`. Le déploiement ne doit pas être présenté comme réalisé avant test sur l'environnement cible.

## 1. Deux cas

**Compte existant** : ne pas exécuter le SQL de création. Comparer d'abord les structures et les droits aux attentes du loader, puis exécuter `dbt debug` et `dbt build`.

**Compte vierge** : dans le bon compte Snowflake et avec un rôle autorisé, inspecter puis exécuter `sql/bootstrap_manager_empty_raw.sql`. Ce script crée uniquement la base, le schéma RAW, trois tables, le journal et le stage. Il ne crée pas les utilisateurs, rôles ou warehouses et ne donne pas de droits ; ils doivent être provisionnés séparément par l'administrateur.

**Précaution** : `IF NOT EXISTS` ne vérifie pas la compatibilité des objets déjà présents. Les définitions proposées correspondent aux colonnes utilisées par le loader de `main`, mais restent à confronter au DDL de l'environnement source avant validation de production.

## 2. Préparer le périmètre Lyon

Le périmètre initial **validé en V1.3** comprend quatre snapshots de Lyon (12 fichiers CSV.GZ). Le manifeste `main` contient désormais **un cinquième snapshot (2026-09-17)**, soit 15 fichiers Lyon au total, et le journal `AIRBNB.RAW.INGESTION_LOG` du compte source affiche désormais trois fichiers pour chacune des cinq dates, y compris 2026-09-17. Ce constat atteste de la journalisation, pas encore de la complétude des tables RAW ni d'une reconstruction dbt après ingestion. Les dates de référence du POC sont : 2025-09-18, 2025-12-22, 2026-03-25, 2026-06-22. Confirmer leur présence effective dans le manifeste et sur disque avant ingestion ; ne jamais créer de fichiers factices.

Le `data_manifest.csv` a été synchronisé sur `main` (commit `167cc5f`, 1 629 entrées) : ne pas le réinitialiser. La sélection par `--country france --location lyon` utilise les chemins et empreintes présents dans ce manifeste.

## 3. Vérification sans chargement

Depuis le dépôt sur le poste disposant des fichiers locaux, avec les variables Snowflake correctement configurées :

```powershell
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country france --location lyon --dry-run
```

Le loader se connecte à Snowflake et inspecte le journal et l'inventaire RAW, mais n'insère pas de lignes. Vérifier que les fichiers annoncés correspondent bien aux snapshots souhaités et que les objets existent.

## 4. Ingestion initiale — après accord et contrôle du budget

```powershell
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country france --location lyon
```

**Attention** : le loader `main` utilise `PUT`, `DELETE` du lot, `COPY INTO` puis journalisation ; il a été validé sur un environnement préexistant, pas encore sur ce bootstrap vierge. Ne pas le lancer avant vérification de la structure et des droits, et préférer un premier snapshot pilote (`--snapshot 2025-09-18`) avant d'étendre le périmètre. **Attention : sans filtre `--snapshot`, la sélection Lyon prend maintenant les cinq dates du manifeste, y compris celle dont la présence dans le journal d'ingestion est confirmée, mais dont la validation dbt reste à établir.**

Après vérification des volumes RAW/journal :

```powershell
.\.venv\Scripts\dbt.exe debug
.\.venv\Scripts\dbt.exe parse
.\.venv\Scripts\dbt.exe build --threads 4
```

Le benchmark de développement complet de la V1.3 était de 1 h 05 min 46 s (480 PASS, 1 WARN connu, 0 ERROR), mais **ce résultat n'est pas une garantie** pour un autre compte ou un sous-ensemble Lyon.

## 5. Configuration et limites

Le loader utilise `SNOWFLAKE_ROLE` (défaut `INGESTION_ROLE`) et `SNOWFLAKE_SCHEMA` (défaut `RAW`), tandis que le profil dbt utilise `SNOWFLAKE_DBT_ROLE` et `DBT_SNOWFLAKE_SCHEMA`. Vérifier séparément les deux rôles et schémas. Ne jamais committer les identifiants.

Le bootstrap ne migre pas les 1 629 archives ni ne télécharge les données depuis GitHub. Le compte vierge doit avoir accès aux fichiers CSV.GZ vérifiés et à leur manifeste. Le fichier `sql/bootstrap_manager_admin_prerequisites.sql` prépare désormais les rôles et un warehouse XSMALL, suspendu par défaut et **sans reprise automatique**. Il ne crée aucun utilisateur, ne donne pas les rôles aux utilisateurs et ne définit pas de budget. Un administrateur doit contrôler la facturation et reprendre manuellement le warehouse avant le pilote. Le script ne modifie pas les tables RAW existantes mais crée des objets persistants : **ne pas exécuter sur le compte actuel sans nécessité**.

## 6. Critères GO

- Objets et droits vérifiés.
- Manifeste et archives Lyon présents, empreintes correctes.
- Dry-run affiche les lots attendus, sans incohérence.
- Ingestion pilote vérifiée, puis ingestion Lyon contrôlée.
- dbt build sans erreur et données des marts accessibles.

Sans ces contrôles, statut : **prêt pour test**, pas « déployé ».

## 7. Stage de référence vérifié (12 octobre 2026)

La commande `SHOW STAGES` confirme `AIRBNB.RAW.INSIDE_AIRBNB_STAGE` de type `INTERNAL`, sans intégration de stockage ni répertoire automatique. Le stage source appartient à `ACCOUNTADMIN` ; cela **n'implique pas** que le rôle d'ingestion dispose des droits nécessaires sur le compte cible. Le `DESCRIBE STAGE` présente les valeurs CSV par défaut. Le loader spécifie explicitement `TYPE=JSON COMPRESSION=GZIP` dans `COPY INTO` ; aucun changement du format de stage n'est requis.

**À vérifier avant le pilote** : droits de création/usage de la base et du schéma, `USAGE` sur le warehouse, `READ`/`WRITE` sur le stage interne selon les opérations, `SELECT`/`INSERT`/`DELETE` sur RAW et INGESTION_LOG, ainsi que les droits de création dans le schéma dbt. Les privilèges exacts doivent être validés avec le rôle effectif dans Snowflake.

## 8. Droits d'ingestion validés sur le compte source

Les résultats `SHOW GRANTS TO ROLE INGESTION_ROLE` et `SHOW GRANTS ON STAGE` confirment : `USAGE` sur `DBT_WH`, `AIRBNB` et `AIRBNB.RAW` ; `READ` et `WRITE` sur le stage interne ; `SELECT`, `INSERT`, `DELETE` sur les trois tables RAW et `INGESTION_LOG`. Le propriétaire du stage source est `ACCOUNTADMIN`.

Un script séparé `sql/bootstrap_manager_ingestion_grants.sql` reproduit **ces seuls droits**. À exécuter sur le compte **cible vierge**, par un administrateur autorisé, **après** création des objets et du rôle `INGESTION_ROLE` et du warehouse `DBT_WH`. Vérifier les noms avant exécution. Il ne configure pas les droits de `DBT_ROLE`, à examiner séparément.

**Séquence recommandée sur un compte vierge** : création administrative des rôles et du warehouse (`sql/bootstrap_manager_admin_prerequisites.sql`) -> attribution contrôlée des rôles aux utilisateurs -> bootstrap des objets -> grants d'ingestion -> `SHOW GRANTS` -> dry-run Lyon -> pilote Lyon -> build dbt. Aucun test de cette séquence n'a encore été effectué sur un compte vierge.

## 9. Droits dbt validés sur le compte source

Le relevé `SHOW GRANTS TO ROLE DBT_ROLE` confirme `USAGE` sur `DBT_WH` et `AIRBNB`, `CREATE SCHEMA` sur la base, `USAGE` sur RAW, `SELECT` sur les trois RAW et `INGESTION_LOG`, ainsi que la propriété des schémas `DBT_GGILLET_STAGING`, `DBT_GGILLET_INTERMEDIATE` et `DBT_GGILLET_MARTS`. Il comprend également des privilèges spécifiques Git/Streamlit, exclus du bootstrap dbt minimal.

Le script `sql/bootstrap_manager_dbt_grants.sql` accorde les privilèges de base nécessaires à un rôle `DBT_ROLE` préexistant. Les créations de schémas sont documentées pour exécution **avec le rôle DBT_ROLE** afin d'éviter tout transfert de propriété. Les noms des schémas doivent correspondre au comportement réel de `generate_schema_name` et au profil dbt du compte cible.

**Limites :** ni la création des utilisateurs et leur affectation aux rôles ni les droits de consommation des marts par le manager ne sont automatisés. Vérifier ces éléments et tester `dbt debug` avant tout `dbt build`.
