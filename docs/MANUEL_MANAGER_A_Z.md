# Manuel d'installation et d'exploitation A à Z — Inside Airbnb Analytics

**Public :** responsable / ingénieur repreneur. **Plateforme :** Windows PowerShell, Python, Snowflake, dbt, Git. **Version de référence :** V1.3, commit de données `167cc5f` sur `main` ; la documentation et le bootstrap proposés doivent être intégrés à `main` avant livraison définitive.

> **Important.** Le dépôt GitHub contient le code, les scripts et le manifeste, **pas les 1 629 archives CSV.GZ (35,16 Gio)**. Une copie indépendante des archives est nécessaire pour reconstruire RAW sur un autre compte. Un compte Snowflake expiré ne constitue pas une sauvegarde. Ne jamais committer de secrets.

**Pour lancer une ville, un pays, un continent, plusieurs zones ou le monde entier, suivre également le [guide géographique A à Z](GUIDE_GEOGRAPHIE_A_Z.md).** Il contient les commandes et les limites exactes du code.

## 0. Choisir son parcours

- **A — Compte Snowflake existant avec RAW compatible :** sections 1, 2, 3, 4A, 5, 6, 7, 8. **Ne pas exécuter les scripts bootstrap.**
- **B — Compte Snowflake neuf/vierge :** sections 1, 2, 3, 4B, 5, 6, 7, 8. Il faut un administrateur Snowflake et les archives physiques.
- **C — Reprendre uniquement le code sans Snowflake :** sections 1, 2 et contrôles hors ligne de 3. Aucun `dbt build` possible sans compte et données.

Le **premier lancement n'est pas totalement sans intervention humaine** : identifiants, rôles, droits, budget, accès aux archives et validation du compte cible doivent être fournis par son propriétaire.

## 1. Récupérer le dépôt et préparer Windows

Installer **Git**, **Python 3** et **Visual Studio Code**. Ouvrir PowerShell :

```powershell
git clone https://github.com/Guigx69/inside-airbnb-analytics.git
cd inside-airbnb-analytics
git status --short
git log -1 --oneline
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\dbt.exe --version
```

**Version de référence du build validé :** dbt-core 1.12.4 et dbt-snowflake 1.12.1. `requirements-dev.txt` ne fige pas actuellement toutes les dépendances transitives : consigner `pip freeze` dans un fichier de livraison **hors dépôt** pour la reproductibilité. En cas d'incompatibilité, comparer les versions avant de les modifier.

Si le poste contient déjà le projet, **ne pas re-cloner par-dessus ni exécuter `git reset --hard` / `git clean`**. Utiliser le répertoire existant et vérifier son état avant toute mise à jour.

## 2. Comprendre ce qui est exécuté

```text
Inside Airbnb (listings / calendar / reviews CSV.GZ)
  -> data/raw/... + data_manifest.csv (chemin, taille, SHA-256)
  -> scripts/check_archives.py (contrôle local, lecture seule)
  -> scripts/load_raw_to_snowflake.py (chargement Snowflake)
  -> AIRBNB.RAW.RAW_LISTINGS / RAW_CALENDAR / RAW_REVIEWS
  -> AIRBNB.RAW.INGESTION_LOG (journal)
  -> dbt STAGING (normalisation)
  -> dbt INTERMEDIATE (calculs métiers)
  -> dbt MARTS (tables/vues analytiques)
```

**25 modèles dbt :** 3 staging, 10 intermediate, 12 marts/fact. La V1.3 a été validée sur le compte source le 09/10/2026 : 14 tables, 11 vues, 456 tests, `PASS=480 WARN=1 ERROR=0`, durée 1 h 05 min 46 s. Le WARN `assert_stg_calendar_listing_exists` (3 163 clés orphelines) est connu ; ne pas le masquer en supprimant les données. **Ce benchmark ne prouve pas la validation d'un compte cible ni d'un build postérieur au snapshot septembre.**

**Prudence métier :** une journée indisponible dans Calendar ne prouve pas qu'elle a été louée ; ne pas présenter l'indisponibilité comme une occupation réelle.

## 3. Configuration commune et vérifications sans écriture

### 3.1 Archives et manifeste

Sur le poste contenant les archives, respecter exactement les chemins du manifeste : `data/raw/<pays>/<ville>/<date>/listings.csv.gz`, `calendar.csv.gz`, `reviews.csv.gz`.

```powershell
.\.venv\Scripts\python.exe .\scripts\check_archives.py --country france --location lyon --hash
# Contrôle intégral (plus long, 35,16 Gio dans le référentiel source)
.\.venv\Scripts\python.exe .\scripts\check_archives.py --hash
```

Attendu : `Missing: 0; invalid: 0` et `[OK]`. **Une absence d'archives n'est pas corrigée par `git pull`**. Demander leur transfert sécurisé ou les récupérer auprès de la source légitime en contrôlant les empreintes.

### 3.2 Variables d'environnement Snowflake

Dans la **session PowerShell courante**, saisir les valeurs fournies par l'administrateur. Ne pas copier ces valeurs dans un fichier versionné ni publier de capture avec secrets.

```powershell
$env:SNOWFLAKE_ACCOUNT = "<identifiant_compte>"
$env:SNOWFLAKE_USER = "<utilisateur>"
$securePassword = Read-Host "Mot de passe Snowflake" -AsSecureString
$env:DBT_SNOWFLAKE_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
$env:SNOWFLAKE_DATABASE = "AIRBNB"
$env:SNOWFLAKE_WAREHOUSE = "DBT_WH"
$env:SNOWFLAKE_ROLE = "INGESTION_ROLE"
$env:SNOWFLAKE_SCHEMA = "RAW"
$env:SNOWFLAKE_DBT_ROLE = "DBT_ROLE"
$env:DBT_SNOWFLAKE_SCHEMA = "DBT_XXX"
```

**Adapter `DBT_SNOWFLAKE_SCHEMA` à l'environnement cible** : `DBT_XXX` est un placeholder à remplacer avant exécution, elle ne doit pas écraser les schémas d'un autre utilisateur. Les schémas générés peuvent porter les suffixes `_STAGING`, `_INTERMEDIATE`, `_MARTS`.

### 3.3 Profil dbt

`profiles.yml.example` est le modèle. Créer le profil dans le dossier utilisateur dbt (`$HOME\.dbt\profiles.yml`) **sans committer le fichier** :

```powershell
New-Item -ItemType Directory -Force "$HOME\.dbt" | Out-Null
if (-not (Test-Path "$HOME\.dbt\profiles.yml")) { Copy-Item .\profiles.yml.example "$HOME\.dbt\profiles.yml" } else { Write-Host "Profil existant : ne pas écraser ; vérifier la configuration manuellement." }
.\.venv\Scripts\dbt.exe debug
.\.venv\Scripts\dbt.exe parse
```

**Attention :** si un profil `$HOME\.dbt\profiles.yml` existe déjà, le sauvegarder et le comparer avant `Copy-Item` : ne pas écraser d'autres projets. Le mot de passe est injecté via `DBT_SNOWFLAKE_PASSWORD`.

## 4A. Scénario A — Snowflake RAW déjà présent

Dans un worksheet Snowflake, confirmer **compte, rôle, warehouse, objets et droits** :

```sql
SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE();
SHOW TABLES IN SCHEMA AIRBNB.RAW;
SHOW STAGES IN SCHEMA AIRBNB.RAW;
DESCRIBE TABLE AIRBNB.RAW.RAW_LISTINGS;
DESCRIBE TABLE AIRBNB.RAW.RAW_CALENDAR;
DESCRIBE TABLE AIRBNB.RAW.RAW_REVIEWS;
DESCRIBE TABLE AIRBNB.RAW.INGESTION_LOG;
SELECT SOURCE_CITY, SNAPSHOT_DATE, COUNT(*) AS NB_FICHIERS
FROM AIRBNB.RAW.INGESTION_LOG
GROUP BY SOURCE_CITY, SNAPSHOT_DATE
ORDER BY SOURCE_CITY, SNAPSHOT_DATE;
```

Les tables RAW doivent contenir les colonnes `SOURCE_COUNTRY`, `SOURCE_CITY`, `SNAPSHOT_DATE`, `SOURCE_FILE`, `RAW_DATA`. Les droits `DBT_ROLE` doivent permettre la lecture de RAW et la création des objets analytiques.

**Si RAW est déjà chargé et cohérent, ne pas lancer le loader : passer directement à la section 6.** Si un lot manque, suivre la section 5 en ciblant explicitement ville/date après vérification du journal.

## 4B. Scénario B — compte Snowflake neuf

**Ne jamais appliquer ces scripts à un compte existant sans revue administrative.** Scripts désormais inclus dans cette branche de livraison consolidée ; ils ne sont pas encore homologués sur compte vierge.

Dans Snowflake, avec un rôle administrateur habilité, **lire les SQL avant de les exécuter**, puis suivre l'ordre :

1. `sql/bootstrap_manager_admin_prerequisites.sql` : crée `INGESTION_ROLE`, `DBT_ROLE` et `DBT_WH` XSMALL suspendu, sans reprise automatique ; **n'attribue pas les rôles aux utilisateurs**.
2. Attribuer manuellement les rôles aux utilisateurs autorisés ; définir budget/alertes et politique de suspension ; prévoir la reprise manuelle du warehouse.
3. `sql/bootstrap_manager_empty_raw.sql` : crée `AIRBNB`, `RAW`, trois tables RAW, `INGESTION_LOG`, stage interne.
4. `sql/bootstrap_manager_ingestion_grants.sql` : droits de chargement RAW/stage.
5. `sql/bootstrap_manager_dbt_grants.sql` : droits de lecture RAW et de création de schémas dbt.
6. Vérifier `SHOW GRANTS TO ROLE INGESTION_ROLE`, `SHOW GRANTS TO ROLE DBT_ROLE`, `SHOW WAREHOUSES LIKE 'DBT_WH'` ; contrôler que le rôle dbt possède ses schémas.

Ces scripts ne créent pas d'utilisateur et n'assurent ni sauvegarde, ni budget, ni droits de lecture des marts pour le responsable. Un `CREATE IF NOT EXISTS` **ne vérifie pas** la compatibilité d'un objet existant.

## 5. Ingestion RAW — uniquement si des lots manquent

**Dry-run (connexion Snowflake, mais aucune écriture RAW) :**

```powershell
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country france --location lyon --dry-run
```

**Pilote ciblé, après validation explicite des droits et des coûts :**

```powershell
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country france --location lyon --snapshot 2025-09-18
```

**Extension Lyon (seulement si les cinq dates doivent être chargées et ne sont pas déjà journalisées) :**

```powershell
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country france --location lyon
```

Le loader vérifie les archives, interroge le journal et l'inventaire RAW, puis utilise `PUT`, `DELETE` du lot ciblé et `COPY INTO`. Il peut modifier des lignes : **ne jamais l'utiliser comme simple vérification**. Sur le compte source, les cinq snapshots Lyon sont déjà journalisés et les 15 lots sont présents en RAW ; **ne pas les recharger**.

### Référence RAW Lyon source — contrôle du 12/10/2026

| Snapshot | Calendar | Listings | Reviews |
|---|---:|---:|---:|
| 2025-09-18 | 3 521 155 | 9 647 | 428 301 |
| 2025-12-22 | 3 577 000 | 9 800 | 450 436 |
| 2026-03-25 | 1 607 095 | 4 403 | 350 235 |
| 2026-06-22 | 3 414 575 | 9 317 | 469 378 |
| 2026-09-17 | 3 358 365 | 9 201 | 473 321 |

**17 692 229 lignes RAW** sur Lyon, toutes tables et dates confondues. La baisse de Calendar en mars est à investiguer si l'exhaustivité source est exigée. Ces volumes sont des références du compte source, **pas des contraintes imposées au compte cible**.

## 6. Construire et vérifier dbt

Après `dbt debug` et `dbt parse` réussis, si les tables RAW existent et que les coûts sont acceptés :

```powershell
# Prévisualiser la sélection sans construire
.\.venv\Scripts\dbt.exe ls
# Exécution réelle : écrit/remplace les objets analytiques dbt, peut coûter des crédits
.\.venv\Scripts\dbt.exe build --threads 4
```

Ne pas relancer le build complet sur le compte source uniquement pour produire une preuve documentaire. Pour une correction ciblée, utiliser `dbt build --select <modele>+` après étude des dépendances. Les sorties `target/run_results.json`, `target/manifest.json` et les logs doivent être **copiées hors du répertoire temporaire avant nettoyage**.

Pour visualiser la documentation dbt (si disponible sur le poste) :

```powershell
.\.venv\Scripts\dbt.exe docs generate
.\.venv\Scripts\dbt.exe docs serve
```

`docs serve` lance un serveur local ; l'arrêter avec Ctrl+C. `docs generate` peut interroger Snowflake.

## 7. Helpers / commandes opérationnelles

| Objectif | Commande |
|---|---|
| Vérifier les archives Lyon | `.\.venv\Scripts\python.exe .\scripts\check_archives.py --country france --location lyon --hash` |
| Vérifier toutes les archives | `.\.venv\Scripts\python.exe .\scripts\check_archives.py --hash` |
| Vérifier la connexion dbt | `.\.venv\Scripts\dbt.exe debug` |
| Valider la syntaxe dbt | `.\.venv\Scripts\dbt.exe parse` |
| Voir les modèles | `.\.venv\Scripts\dbt.exe ls` |
| Construire et tester | `.\.venv\Scripts\dbt.exe build --threads 4` |
| Tester uniquement | `.\.venv\Scripts\dbt.exe test` |
| Modèle ciblé | `.\.venv\Scripts\dbt.exe build --select mart_market_snapshot` |
| Prévisualiser ingestion Lyon | `.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country france --location lyon --dry-run` |
| Afficher aide du loader | `.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --help` |
| Afficher aide orchestrateur | `.\.venv\Scripts\python.exe .\scripts\run_pipeline.py --help` |
| Contrôle Python local | `.\.venv\Scripts\python.exe -m unittest discover -s tests` |

### Orchestrateur `run_pipeline.py`

**Par défaut**, l'orchestrateur prévisualise collecte, vérification archives et RAW. Son argument `--selection-file` est **obligatoirement un fichier JSON de sélection existant**, même si la valeur par défaut pointe sur `config/geography.lyon.example.json`. Le fichier Lyon sélectionne la ville par son nom : contrôler la liste effective des fichiers, car ce critère seul ne filtre pas le pays. Le moteur géographique combine les critères inclusifs par **OU** (et non par ET) : ajouter `countries: [\"France\"]` inclurait **toutes les villes françaises**. Contrôler la sélection avant toute exécution ; le fichier géographique générique inclut Japon/Sydney et ne doit pas servir au pilote Lyon.

```powershell
# Aperçu, sans écriture RAW (connexion Snowflake néanmoins)
.\.venv\Scripts\python.exe .\scripts\run_pipeline.py --selection-file config/geography.lyon.example.json

# Exécution réelle : RAW, sans téléchargement ni dbt build ; APRÈS validation
.\.venv\Scripts\python.exe .\scripts\run_pipeline.py --selection-file config/geography.lyon.example.json --execute

# Exécution avec téléchargement et build : opération coûteuse / modifiante
.\.venv\Scripts\python.exe .\scripts\run_pipeline.py --selection-file config/geography.lyon.example.json --execute --sync --dbt-build
```

**Ne pas lancer le dernier exemple tel quel en production** : vérifier le JSON de sélection Lyon fourni et l'adapter si nécessaire, vérifier les villes et dates, le budget et les archives. L'orchestrateur s'arrête au premier code retour non nul ; il ne fournit pas de rollback transactionnel inter-étapes.

## 8. Diagnostic, sécurité et transfert

| Symptôme | Vérifier / action sûre |
|---|---|
| `dbt` introuvable | Utiliser `.\.venv\Scripts\dbt.exe` ; vérifier installation et `dbt --version`. |
| Profil introuvable | Vérifier `$HOME\.dbt\profiles.yml` et `DBT_SNOWFLAKE_SCHEMA`. |
| Échec d'authentification | Contrôler account/user/mot de passe **sans afficher le secret** ; contacter l'administrateur. |
| Accès refusé au warehouse | Contrôler `SHOW GRANTS`, état suspendu, rôle et budget ; ne pas accorder `ACCOUNTADMIN` au loader. |
| Archives manquantes | Obtenir les fichiers physiques et vérifier SHA-256 ; Git ne les contient pas. |
| RAW/journal incohérents | Arrêter le loader ; comparer les lots ; ne pas supprimer les données pour « réparer ». |
| Avertissement dbt | Lire le nom et le nombre de lignes ; comparer au WARN connu ; ne pas ignorer un nouveau WARN. |
| Dépassement de crédits | Suspendre le warehouse selon la procédure de l'administrateur ; ne pas relancer un build. |

### Checklist de remise au manager

- [ ] Code et documentation des PR validées intégrés sur une branche de livraison clairement identifiée.
- [ ] Compte cible, rôle, warehouse et budget confirmés ; identifiants transmis hors Git.
- [ ] Archives physiques transmises et SHA-256 vérifiés **ou** RAW déjà présent et compatible.
- [ ] Profil dbt installé sans écraser un profil existant.
- [ ] Scénario A ou B exécuté ; objets et droits vérifiés.
- [ ] `dbt debug` et `dbt parse` réussis.
- [ ] Build cible effectué **ou** indiqué explicitement comme non exécuté, avec logs.
- [ ] Accès en lecture aux marts testé pour le responsable.
- [ ] Résultats, anomalies, coûts et sauvegarde des archives documentés.

### Prévol avant exécution réelle

1. Lire le fichier de sélection `config/geography.lyon.example.json` et vérifier que la liste affichée par `check_archives.py --selection-file config/geography.lyon.example.json --hash` correspond exclusivement à la ville attendue ; le moteur de sélection combine les inclusions par OU.
2. Confirmer la cible Snowflake via `SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE()` dans le worksheet ; le rôle utilisé par Python peut être différent du rôle courant du worksheet.
3. Prévisualiser les lots RAW avec `--dry-run` et vérifier le nombre de lots `À charger` ; sur le compte source déjà chargé, il doit être nul si journal et RAW sont cohérents.
4. N'utiliser `--execute`, `--sync`, le loader sans `--dry-run` ou `dbt build` qu'après accord explicite du propriétaire du compte cible.
5. Ne pas considérer une commande `dbt parse` réussie comme preuve que les données et les droits de création sont valides ; `dbt debug` teste la connexion, `dbt build` écrit des objets.

**État au 12/10/2026 :** RAW Lyon du compte source contrôlé (5 dates, 15 lots, 17 692 229 lignes) ; build V1.3 antérieur validé ; **pas de preuve de build sur compte manager ni de bootstrap sur compte vierge**. La livraison doit conserver cette distinction.
