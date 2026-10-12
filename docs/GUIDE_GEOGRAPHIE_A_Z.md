# Guide opérationnel A à Z — ville, pays, continent, multi-zones et monde

**Point d'entrée :** [manuel manager](MANUEL_MANAGER_A_Z.md). Ce guide couvre les sélections géographiques, l'inventaire, les téléchargements, la vérification, l'ingestion et le lancement dbt. Les commandes sont conçues pour **Windows PowerShell** depuis la racine du dépôt, après installation du venv et configuration des accès Snowflake.

> **Ne pas confondre les périmètres.** `download_inside_airbnb.py` parcourt le **catalogue public courant** Inside Airbnb ; `check_archives.py` et `load_raw_to_snowflake.py` travaillent sur le **manifeste local**. Un fichier absent du manifeste ne sera pas ingéré même s'il apparaît dans le catalogue. `dbt build` transforme les données présentes dans RAW, sans filtre géographique implicite lié au dernier téléchargement.

## 1. Sécurité : prévol obligatoire

```powershell
.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --help
.\.venv\Scripts\python.exe .\scripts\check_archives.py --help
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --help
.\.venv\Scripts\python.exe .\scripts\run_pipeline.py --help
.\.venv\Scripts\dbt.exe debug
```

Avant toute écriture : confirmer le compte Snowflake, le rôle d'ingestion, le warehouse, les droits, les crédits et le disque disponible ; sauvegarder les archives et le manifeste ; **ne jamais** utiliser `--overwrite` sans investigation. Les opérations `--sync`, ingestion réelle et `dbt build` modifient l'état ; les commandes d'inventaire `--dry-run` n'écrivent pas d'archives mais consultent le catalogue en ligne.

## 2. Choisir un périmètre : commandes de découverte sans écriture

| Besoin | Commande PowerShell | Remarque |
|---|---|---|
| Une ville | `.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --location lyon --dry-run` | Nom de ville ; vérifier qu'il n'existe pas d'homonyme |
| Un pays | `.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --country france --dry-run` | Toutes les villes de ce pays dans le catalogue |
| Un continent | `.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --selection-file config/geography.europe.example.json --dry-run` | Sélection JSON, exemple ci-dessous |
| Plusieurs pays | `.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --selection-file config/geography.multi.example.json --dry-run` | Union des pays indiqués |
| Monde entier | `.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --all --dry-run` | **Inventaire uniquement** ; pas de `--all` dans l'orchestrateur |
| Une date | `.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --location lyon --snapshot 2026-09-17 --dry-run` | Date exacte disponible au catalogue |
| Un type de fichier | `.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --country france --files listings --dry-run` | Valeurs : listings, calendar, reviews |

Le catalogue est susceptible de changer : **les nombres de villes/fichiers du résultat de prévisualisation font foi**, pas une estimation figée dans le guide. Si un nom n'existe pas dans le catalogue, le programme doit signaler l'absence de correspondance.

## 3. Sélections JSON reproductibles

Le JSON utilise deux blocs facultatifs `include` et `exclude`, avec les tableaux `continents`, `countries`, `cities`. Au moins **une inclusion non vide** est obligatoire. Les inclusions sont combinées par **OU** ; les exclusions retirent toute entrée qui correspond à **l'un quelconque** des critères d'exclusion. La casse et les accents sont normalisés.

**Une ville, Lyon** — `config/geography.lyon.example.json` :

```json
{"include":{"cities":["Lyon"]},"exclude":{}}
```

**Un pays, France** — créer `config/geography.france.example.json` (exemple fourni dans le dépôt) :

```json
{"include":{"countries":["France"]},"exclude":{}}
```

**Un continent, Europe** — créer `config/geography.europe.example.json` (exemple fourni dans le dépôt) :

```json
{"include":{"continents":["Europe"]},"exclude":{}}
```

**Deux pays** — créer `config/geography.multi.example.json` (exemple fourni dans le dépôt) :

```json
{"include":{"countries":["France","Spain"]},"exclude":{}}
```

**Europe sauf Paris** :

```json
{"include":{"continents":["Europe"]},"exclude":{"cities":["Paris"]}}
```

**France + Sydney** (union volontaire, **pas** intersection) :

```json
{"include":{"countries":["France"],"cities":["Sydney"]},"exclude":{}}
```

**ATTENTION :** `{"include":{"countries":["France"],"cities":["Lyon"]}}` sélectionne **toute la France**, pas seulement Lyon. Pour une ville homonyme dans plusieurs pays, ce moteur ne sait pas exprimer `pays ET ville` dans un même fichier JSON : inspecter le résultat, et utiliser le filtre `--country` du collecteur séparément si nécessaire. Ne pas supposer qu'un nom de ville est mondialement unique.

**Monde entier :** le collecteur sait faire `--all`, mais le sélecteur JSON actuel n'a **pas** de mot-clé `world` ni de sélection universelle vide. Ne pas inventer un JSON `world`. Pour l'ingestion mondiale, le loader sait travailler sur tout le manifeste **sans `--selection-file`** (sous réserve de ses autres options et des ressources) ; l'orchestrateur, lui, impose une sélection JSON. Le monde entier **en une commande orchestrée** n'est donc pas une fonctionnalité actuellement validée.

## 4. Télécharger les fichiers (modifie le disque et le manifeste)

D'abord inventorier :

```powershell
.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --country france --dry-run --verify
```

Après validation du périmètre et de l'espace disque :

```powershell
.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --country france --sync --verify
```

Pour un continent, remplacer `--country france` par `--selection-file config/geography.europe.example.json`. Pour un fichier ou une date, ajouter `--files listings` ou `--snapshot AAAA-MM-JJ` au **collecteur**. Pour le monde, remplacer par `--all` **uniquement après un inventaire et une estimation de capacité**. Le téléchargement met à jour `data_manifest.csv` ; les archives physiques restent hors GitHub. Ne pas utiliser `--overwrite` par défaut.

## 5. Vérifier les archives du périmètre

```powershell
# Lyon
.\.venv\Scripts\python.exe .\scripts\check_archives.py --location lyon --hash
# France
.\.venv\Scripts\python.exe .\scripts\check_archives.py --country france --hash
# Europe : le JSON doit exister
.\.venv\Scripts\python.exe .\scripts\check_archives.py --selection-file config/geography.europe.example.json --hash
# Monde : totalité du manifeste, potentiellement très long
.\.venv\Scripts\python.exe .\scripts\check_archives.py --hash
```

Attendu : aucun fichier manquant ni hash incorrect. Vérifier les compteurs de fichiers et les pays/villes affichés avant d'aller plus loin.

## 6. Prévisualiser puis ingérer RAW

```powershell
# Lyon
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --location lyon --dry-run
# France
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country france --dry-run
# Europe
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --selection-file config/geography.europe.example.json --dry-run
# Monde : toutes les entrées du manifeste ; ATTENTION au coût
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --dry-run
```

L'ingestion réelle reprend **la même commande sans `--dry-run`**, après contrôle de la liste des lots, du journal et des coûts. Exemple ciblé :

```powershell
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --location lyon --snapshot 2026-09-17
```

Le loader écrit dans RAW et le journal. Ne pas l'utiliser comme vérification neutre. Sur le compte source V1.3, les cinq snapshots Lyon sont déjà présents en RAW : **ne pas les recharger**.

## 7. Orchestrateur : ce qu'il automatise réellement

```powershell
# Prévisualisation du périmètre JSON, puis vérification des archives et RAW
.\.venv\Scripts\python.exe .\scripts\run_pipeline.py --selection-file config/geography.lyon.example.json
# Exécution réelle : après prévol et approbation des coûts
.\.venv\Scripts\python.exe .\scripts\run_pipeline.py --selection-file config/geography.lyon.example.json --execute --sync --dbt-build
```

Les mêmes commandes fonctionnent avec `config/geography.europe.example.json` ou `config/geography.multi.example.json` après vérification du catalogue et des archives. `--sync` autorise le téléchargement, `--execute` autorise les écritures RAW, `--dbt-build` lance dbt ; le pipeline s'arrête au premier échec, **sans rollback inter-étapes**. Pour le monde, utiliser **les étapes séparées** : inventaire `--all`, téléchargement `--all --sync`, vérification globale, loader global et dbt. **Ne pas utiliser l'exemple générique mélangeant Europe/Japon/Sydney comme configuration de production.**

## 8. Construire et consulter dbt

```powershell
.\.venv\Scripts\dbt.exe debug
.\.venv\Scripts\dbt.exe parse
.\.venv\Scripts\dbt.exe ls
# Écriture Snowflake et consommation de crédits : uniquement après validation
.\.venv\Scripts\dbt.exe build --threads 4
.\.venv\Scripts\dbt.exe docs generate
.\.venv\Scripts\dbt.exe docs serve
```

`dbt build` traite le périmètre disponible en RAW selon les modèles SQL ; il **n'est pas automatiquement limité** à la ville/pays du dernier `--selection-file`. Pour une isolation stricte par zone, utiliser une base ou un environnement RAW dédié et vérifier les modèles. `dbt docs serve` ouvre un serveur local à arrêter avec Ctrl+C.

## 9. Dimensionnement, reprise et critères d'acceptation

**Avant un pays/continent/monde :** inventorier le nombre de fichiers et snapshots ; calculer les tailles depuis `data_manifest.csv` et prévoir une marge disque ; estimer le stockage Snowflake, le temps et les crédits ; vérifier la limite d'essai et la suspension automatique du warehouse ; commencer par **une ville et une date**, puis élargir par lots. Après synchronisation d'octobre, le manifeste comporte 1 989 entrées ; les 1 659 archives du catalogue courant ont été vérifiées. La volumétrie exacte doit être recalculée depuis le manifeste ; les 330 archives historiques supplémentaires exigent un contrôle global distinct.

**Après interruption :** inspecter les fichiers `.part`, le manifeste, les SHA-256, `INGESTION_LOG` et les volumes RAW ; relancer d'abord le `--dry-run`. Ne pas supposer qu'un journal suffit à prouver la complétude, ni supprimer/recharger des lots sans diagnostic. Conserver les logs et `target/run_results.json` après build.

**Réception par le manager :** le périmètre choisi correspond aux fichiers inventoriés ; archives disponibles et intègres ; journal/RAW cohérents ; `dbt debug` et `dbt parse` OK ; build réellement exécuté si requis et résultats archivés ; droits de lecture des marts vérifiés ; anomalies et coûts documentés. Si l'une de ces étapes n'a pas été réalisée, noter **« non testé »**, pas « validé ».

## 10. Limites explicites de la version actuelle

- Pas de filtre composé `pays ET ville` dans le JSON.
- Pas de `--all` direct dans `run_pipeline.py`.
- Pas de `world` universel dans le sélecteur JSON.
- Pas de pilotage automatique des coûts, de reprise transactionnelle globale ni de preuve de déploiement sur compte vierge.
- Les commandes monde/continent ne sont **pas** garanties sur la volumétrie cible tant qu'elles n'ont pas été testées sur cet environnement.

Ces limites sont des contraintes du **code existant**, pas des omissions à contourner en inventant des commandes.
