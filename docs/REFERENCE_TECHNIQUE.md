# Référence technique et historique — Inside Airbnb V1.3

Ce document regroupe les six anciens guides/audits techniques retirés du parcours principal afin de **préserver toutes les informations** sans multiplier les points d'entrée. Pour exécuter le projet, utiliser [le manuel manager](MANUEL_MANAGER_A_Z.md), puis [le guide géographique](GUIDE_GEOGRAPHIE_A_Z.md). Les sections archivées ci-dessous sont historiques : leurs mentions de branches et de PR peuvent être périmées.

---

## Archive documentaire : docs/guide_livraison_fr.md

> Reproduction de la documentation historique à titre de traçabilité. Les mentions de PR non fusionnées et d'états de données sont datées ; pour exécuter, se référer au manuel principal et au code de main.

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

Le premier contrôle a déjà réussi sur le poste de développement. Le manifeste GitHub `main` inclut désormais **trois fichiers Lyon supplémentaires du 17/09/2026** (commit `167cc5f`) ; le `git diff` initial a confirmé qu'il n'y a ni suppression ni modification d'entrée existante. **Ne pas confondre disponibilité des archives et ingestion/validation dbt du cinquième snapshot.** Le second contrôle permet de **constater**, sans supposer, combien de fichiers et de snapshots Lyon sont effectivement présents. Ne pas modifier le manifeste sans contrôle préalable et ne pas exécuter `git reset --hard` ni `git clean`.

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


---

## Archive documentaire : docs/v1_3_manager_deployment.md

> Reproduction de la documentation historique à titre de traçabilité. Les mentions de PR non fusionnées et d'états de données sont datées ; pour exécuter, se référer au manuel principal et au code de main.

# V1.3 — Guide de livraison manager (Snowflake + dbt Core)

## Statut

Version V1.3 fusionnée dans `main` via la PR #3 (commit `6871e0726ad914d8ae57066209f140ed2d4cdfaa`). Le benchmark final a été validé le 9 octobre 2026.

Cette livraison modifie **uniquement** la matérialisation de deux modèles :
- `int_listing_calendar_metrics` : vue → table.
- `int_listing_availability_horizon` : vue → table.

La logique SQL métier, les tables RAW et les interfaces des marts ne sont pas modifiées. Les prototypes de rechargement RAW restent sur `feature/performance-v1-3`, hors livraison.

## Prérequis sur l'environnement cible

- Compte Snowflake opérationnel, warehouse et rôle avec les droits nécessaires.
- Base `AIRBNB` et tables sources `RAW.RAW_LISTINGS`, `RAW.RAW_CALENDAR`, `RAW.RAW_REVIEWS` préalablement alimentées.
- Python et environnement virtuel avec dbt Core et adaptateur dbt-snowflake compatibles (environnement de validation : dbt Core 1.12.4, adaptateur Snowflake 1.12.1).
- `profiles.yml` dérivé de `profiles.yml.example`, dans le dossier de profils dbt ; renseigner les variables d'environnement **sans committer les secrets** : `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `DBT_SNOWFLAKE_PASSWORD`, `SNOWFLAKE_DBT_ROLE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_WAREHOUSE`, `DBT_SNOWFLAKE_SCHEMA`.
- Vérifier les autorisations de création/remplacement des vues et tables dans les schémas dbt.

**Important :** le projet n'approvisionne pas automatiquement un nouveau compte Snowflake avec les 1 629 archives historiques. Prévoir la disponibilité et les droits d'accès aux données RAW dans le compte cible. Aucun transfert de données entre comptes n'est inclus dans cette PR.

## Déploiement Windows PowerShell

Depuis la racine du dépôt, avec l'environnement Python installé et activé :

```powershell
git fetch origin
git switch main
git pull --ff-only origin main

.\.venv\Scripts\dbt.exe debug
.\.venv\Scripts\dbt.exe parse
.\.venv\Scripts\dbt.exe build --threads 4
```

Ne pas réinitialiser ni écraser les fichiers locaux non commités, notamment `data_manifest.csv`. Sur un environnement neuf, installer d'abord les dépendances Python nécessaires.

## Critères de validation

1. `dbt debug` confirme la connexion à Snowflake.
2. `dbt parse` ne présente aucune erreur.
3. `dbt build --threads 4` : zéro erreur et tous les modèles construits ; conserver `target/run_results.json` et le journal du build.
4. Vérifier les résultats des tests. Référence pré-optimisation : **PASS=480, WARN=1, ERROR=0, TOTAL=481**, temps **2 h 02 min 44 s**. Le benchmark complet du 9 octobre 2026 figure ci-dessous.
5. Avertissement historique connu : test `assert_stg_calendar_listing_exists`, **3 163 clés calendar orphelines** réparties sur 103 groupes ville/snapshot. L'avertissement doit rester visible ; ne pas supprimer les observations sources pour le faire disparaître.
6. Contrôler les deux intermédiaires et les marts dépendants ; les tests ciblés déjà exécutés sur la branche expérimentale ont donné 105/105 PASS.

## Benchmark complet validé — 9 octobre 2026

Exécution : `dbt build --threads 4` sur l'environnement de développement Snowflake.

| Mesure | Avant V1.3 | Après V1.3 |
| --- | ---: | ---: |
| Durée totale | 2 h 02 min 44 s | 1 h 05 min 46,11 s |
| Modèles tables | 12 | 14 |
| Modèles vues | 13 | 11 |
| Tests | 456 | 456 |
| PASS | 480 | 480 |
| WARN | 1 | 1 |
| ERROR | 0 | 0 |
| TOTAL | 481 | 481 |

**Gain : environ 56 min 58 s, soit 46,4 % de réduction de durée** sur ce benchmark. Les temps peuvent varier selon la charge, la taille du warehouse et son cache.

L'avertissement `assert_stg_calendar_listing_exists` est inchangé : 3 163 résultats, configurés en warning. Aucune suppression de données Calendar n'a été réalisée.

Le benchmark valide l'environnement de développement ; la migration des données et l'exécution sur le compte Snowflake du manager restent à réaliser.

## Résultats de performance déjà observés

| Modèle aval | Avant | Après (run ciblé) |
| --- | ---: | ---: |
| `fct_listing_snapshot` | 27,98 min | 132,27 s |
| `mart_availability_snapshot` | 21,51 min | 2,45 s |
| `mart_availability_horizon_snapshot` | 13,82 min | 2,94 s |

Ces durées sont issues d'exécutions différentes et ne représentent **pas** le gain total du `dbt build`. Les deux tables intermédiaires ont un coût de reconstruction : leur matérialisation déplace une partie du calcul en amont.

## Exploitation et retour arrière

- Après chaque nouvel apport ou correction des données RAW, reconstruire les modèles intermédiaires et leurs dépendants avec `dbt build` ; les tables intermédiaires ne se rafraîchissent pas automatiquement.
- Si le build échoue, conserver les journaux et identifier le modèle ou test en cause avant tout nouveau déploiement.
- Retour arrière applicatif : revenir à la version précédente des deux fichiers SQL via Git et relancer `dbt build` sur l'environnement concerné. Cette opération reconstruit les objets dbt ; planifier son coût Snowflake. Ne jamais vider ou réinitialiser les tables RAW pour ce retour arrière.
- La fusion V1.3 dans `main` est effectuée ; le déploiement sur le compte du manager nécessite encore une validation explicite.

## Hors périmètre V1.3

Rechargement atomique RAW, certification exhaustive des archives historiques, incrémentalisation, migration de compte et couche BI : chantiers distincts, non bloquants pour cette optimisation dbt.


---

## Archive documentaire : docs/manager_deployment_two_scenarios.md

> Reproduction de la documentation historique à titre de traçabilité. Les mentions de PR non fusionnées et d'états de données sont datées ; pour exécuter, se référer au manuel principal et au code de main.

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


---

## Archive documentaire : docs/bootstrap_manager_lyon.md

> Reproduction de la documentation historique à titre de traçabilité. Les mentions de PR non fusionnées et d'états de données sont datées ; pour exécuter, se référer au manuel principal et au code de main.

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


---

## Archive documentaire : docs/audit_livraison_2026-10-12.md

> Reproduction de la documentation historique à titre de traçabilité. Les mentions de PR non fusionnées et d'états de données sont datées ; pour exécuter, se référer au manuel principal et au code de main.

# Audit de livraison — 12 octobre 2026

## Synthèse

**Objectif :** transmettre un dépôt exploitable, lisible en français, sans prétendre que le compte du responsable a été déployé.

### Constats confirmés

| Contrôle | Constat | Traitement |
|---|---|---|
| README | En anglais et ancien résultat (445 tests) | Réécrit en français, benchmark V1.3 exact |
| Guide V1.3 | Mentionne encore la branche et PR #3 avant fusion | Statut et commandes corrigés |
| Dépendances | `requirements-dev.txt` présent ; dbt-core 1.12.4 fixé, dbt-snowflake non fixé | Version validée 1.12.1 documentée ; verrouillage complet à réaliser avant livraison reproductible |
| Manifeste `main` | 1 629 lignes de données depuis le commit `167cc5f` | Écart résolu : trois nouvelles archives Lyon du 17/09/2026, committées et poussées sur `main` |
| Lyon dans le manifeste `main` | 15 archives, 5 dates, 3 types par date sur `main` | Périmètre de départ confirmé sur GitHub |
| Orchestration | `run_pipeline.py` propose un mode aperçu par défaut | Préserver ; le dry-run RAW se connecte à Snowflake |
| Infrastructure Snowflake | Scripts de bootstrap sur PR #5 | Pas encore fusionnés ni testés sur un compte vierge |
| Documentation des deux scénarios | PR #4 | À rapprocher du guide français et du bootstrap |
| Workflow CI | Aucun `.github/workflows/ci.yml` trouvé | Contrôles Python hors réseau ajoutés dans cette PR |

### Historique Lyon présent dans `main`

- 2025-09-18 : listings, calendar, reviews
- 2025-12-22 : listings, calendar, reviews
- 2026-03-25 : listings, calendar, reviews
- 2026-06-22 : listings, calendar, reviews

La cinquième date (2026-09-17, trois fichiers) a été confirmée par `git diff`, puis publiée sur `main` au commit `167cc5f`. Les cinq dates de `main` sont présentes dans le **manifeste GitHub**, pas dans les archives elles-mêmes. L'utilisateur a effectué séparément un contrôle local SHA-256 réussi sur 1 629 archives. La synchronisation du manifeste a été effectuée par commit ciblé, sans remplacement aveugle ni modification des archives.

### Nettoyage du dépôt — politique

- Conserver le code métier, les modèles, les tests et les scripts expérimentaux sur leurs branches respectives.
- Ne pas supprimer de fichiers sur simple présomption d'inutilité.
- Ne pas versionner les 35,16 Gio d'archives ni les mots de passe.
- Conserver les PR #4, #5 et #6 distinctes jusqu'à revue des dépendances ; **aucune fusion automatique**.
- La documentation utilisateur est rédigée en français ; les noms de fichiers, variables d'environnement, identifiants SQL et commandes conservent leur orthographe technique.

### Contrôles de qualité ajoutés

Le workflow `verification-hors-ligne.yml` installe uniquement `country_converter` pour les tests géographiques, puis exécute `python -m compileall` et les tests Python `unittest` dans GitHub Actions, sans accès Snowflake. Il ne valide pas l'ingestion réelle, le dbt build ou le provisionnement d'un compte vierge. Les résultats de ce workflow doivent être consultés après ouverture de la PR.

### Risques ouverts

1. **Statut manifeste Git/local :** 1 629 entrées GitHub après le push du commit `167cc5f`, correspondant aux 1 629 archives vérifiées localement. Le `git diff` initial identifiait trois ajouts, sans suppression ni modification : `data/raw/france/lyon/2026-09-17/{calendar,listings,reviews}.csv.gz`. L'outil de comparaison **en lecture seule** `python scripts/comparer_manifestes.py --reference origin/main` reste disponible. Les trois archives sont vérifiées localement par SHA-256, mais leur ingestion et leurs transformations dbt ne sont pas validées.
2. **Dépendances Python :** absence de lock complet ; les nouvelles installations peuvent résoudre d'autres versions de `dbt-snowflake`.
3. **Compte vierge :** absence de test réel des scripts SQL, des rôles, du warehouse et des données.
4. **Accès du responsable :** droits de lecture des marts, Streamlit et éventuels objets BI à définir selon le besoin.
5. **Conservation :** les archives locales n'ont pas de seconde sauvegarde confirmée.

### Critère de clôture

Une PR n'est « prête » que lorsque les tests pertinents passent, les commandes sont relues, les secrets sont absents et les limites non testées sont explicites. La réussite du build V1.3 de développement ne vaut pas homologation de l'environnement du responsable.


---

## Archive documentaire : docs/controle_raw_lyon_2026-10-12.md

> Reproduction de la documentation historique à titre de traçabilité. Les mentions de PR non fusionnées et d'états de données sont datées ; pour exécuter, se référer au manuel principal et au code de main.

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
