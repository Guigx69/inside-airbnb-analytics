# V1.3 — Guide de livraison manager (Snowflake + dbt Core)

## Statut

Branche de livraison : `release/performance-v1-3` ; PR #3 vers `main` (brouillon jusqu'au benchmark final).

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
git switch release/performance-v1-3
git pull --ff-only origin release/performance-v1-3

.\.venv\Scripts\dbt.exe debug
.\.venv\Scripts\dbt.exe parse
.\.venv\Scripts\dbt.exe build --threads 4
```

Ne pas réinitialiser ni écraser les fichiers locaux non commités, notamment `data_manifest.csv`. Sur un environnement neuf, installer d'abord les dépendances Python nécessaires.

## Critères de validation

1. `dbt debug` confirme la connexion à Snowflake.
2. `dbt parse` ne présente aucune erreur.
3. `dbt build --threads 4` : zéro erreur et tous les modèles construits ; conserver `target/run_results.json` et le journal du build.
4. Vérifier les résultats des tests. Référence pré-optimisation : **PASS=480, WARN=1, ERROR=0, TOTAL=481**, temps **2 h 02 min 44 s**. Ne pas prétendre à une accélération globale avant une mesure complète.
5. Avertissement historique connu : test `assert_stg_calendar_listing_exists`, **3 163 clés calendar orphelines** réparties sur 103 groupes ville/snapshot. L'avertissement doit rester visible ; ne pas supprimer les observations sources pour le faire disparaître.
6. Contrôler les deux intermédiaires et les marts dépendants ; les tests ciblés déjà exécutés sur la branche expérimentale ont donné 105/105 PASS.

## Résultats de performance déjà observés

| Modèle aval | Avant | Après (run ciblé) |
| --- | ---: | ---: |
| `fct_listing_snapshot` | 27,98 min | 132,27 s |
| `mart_availability_snapshot` | 21,51 min | 2,45 s |
| `mart_availability_horizon_snapshot` | 13,82 min | 2,94 s |

Ces durées sont issues d'exécutions différentes et ne représentent **pas** le gain total du `dbt build`. Les deux tables intermédiaires ont un coût de reconstruction : leur matérialisation déplace une partie du calcul en amont.

## Exploitation et retour arrière

- Après chaque nouvel apport ou correction des données RAW, reconstruire les modèles intermédiaires et leurs dépendants avec `dbt build` ; les tables intermédiaires ne se rafraîchissent pas automatiquement.
- Si le build échoue, conserver les journaux, identifier le modèle ou test en cause et ne pas fusionner la PR.
- Retour arrière applicatif : revenir à la version précédente des deux fichiers SQL via Git et relancer `dbt build` sur l'environnement concerné. Cette opération reconstruit les objets dbt ; planifier son coût Snowflake. Ne jamais vider ou réinitialiser les tables RAW pour ce retour arrière.
- La fusion dans `main` et le déploiement sur le compte du manager nécessitent une validation explicite.

## Hors périmètre V1.3

Rechargement atomique RAW, certification exhaustive des archives historiques, incrémentalisation, migration de compte et couche BI : chantiers distincts, non bloquants pour cette optimisation dbt.
