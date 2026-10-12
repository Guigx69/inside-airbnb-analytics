# Maintenance autonome World — Inside Airbnb Analytics

**Dernière mise à jour : 13 octobre 2026.** Exécuter toutes les commandes dans **PowerShell VS Code**, depuis `C:\Projects\inside_airbnb`. Le dépôt peut être installé ailleurs : adapter uniquement le chemin racine. Ce guide distingue explicitement inventaire, téléchargement, ingestion et transformation.

## 1. État de référence et preuves

| Indicateur | État observé |
|---|---:|
| Zones géographiques du catalogue courant | 120 |
| Snapshots du catalogue courant | 553 |
| Archives du catalogue courant | 1 659 |
| Archives courantes contrôlées (`VERIFIED`) | 1 659 |
| Archives ajoutées lors de la synchronisation | 360 |
| Entrées du manifeste avant / après | 1 629 / 1 989 |
| Entrées historiques hors catalogue courant | 330 |
| Dernier snapshot observé | Vaud, 2026-10-05 |

L'audit différentiel a trouvé 120 nouveaux snapshots pour 119 zones (Vaud : deux dates). La comparaison `comparer_manifestes.py --reference origin/main` avant publication indiquait **360 ajouts, 0 suppression, 0 modification**. L'opérateur a ensuite indiqué avoir publié le manifeste. **Le contrôle SHA-256 exhaustif des 1 989 archives n'est pas attesté par la sortie transmise**, contrairement au contrôle des 1 659 archives courantes.

Les 25 modèles dbt et 456 tests du build précédent concernent **l'état antérieur** aux nouveaux snapshots. Les neuf pages Streamlit ont été parcourues sur le compte source avant la synchronisation. **Aucune ingestion World ni reconstruction dbt post-synchronisation n'est établie.**

## 2. Prévol (lecture seule)

```powershell
git status --short
git pull origin main
.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --help
.\.venv\Scripts\python.exe .\scripts\check_archives.py --help
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --help
```

Ne pas faire `git reset --hard` ou `git clean`. En présence de modifications locales, les examiner avant `git pull`. Les secrets Snowflake restent dans les variables d'environnement, le profil dbt utilisateur et les secrets Streamlit locaux ; **jamais dans Git**.

## 3. Inventaire du catalogue officiel sans téléchargement

```powershell
.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --all --dry-run > audit_world.txt 2>&1
Get-Content .\audit_world.txt -Tail 20
```

`NEW` signifie **absent du disque local** ; ce n'est pas une preuve que le fichier est absent du manifeste. `LOCAL` signifie présent, **sans vérification SHA-256**. `VERIFIED` signifie taille et SHA-256 cohérents avec le manifeste.

Pour comparer le catalogue actuel au manifeste par **chemin exact** (sans modifier les données) :

```powershell
@'
import csv
from collections import defaultdict
from scripts.download_inside_airbnb import get_catalog, build_inventory

with open("data_manifest.csv", newline="", encoding="utf-8-sig") as f:
    known = {row["path"] for row in csv.DictReader(f)}
missing = [item for item in build_inventory(get_catalog()) if item.manifest_path not in known]
grouped = defaultdict(list)
for item in missing:
    grouped[(item.country, item.location, item.snapshot_date)].append(item.filename)
for (country, city, date), names in sorted(grouped.items()):
    print(f"{country} / {city} / {date} : {', '.join(sorted(names))}")
print(f"Snapshots à référencer : {len(grouped)} ; archives à référencer : {len(missing)}")
'@ | .\.venv\Scripts\python.exe -
```

**Contrôle de cohérence :** si le catalogue est indisponible, si sa structure change ou si les résultats semblent incomplets, **arrêter la procédure**. Ne pas considérer une liste vide comme une preuve de fraîcheur avant d'avoir vérifié que le catalogue a bien été chargé.

## 4. Synchronisation du disque et du manifeste

Prévoir l'espace disque et une sauvegarde indépendante des CSV.GZ. Ne pas exécuter `--overwrite` sans diagnostic.

```powershell
.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --all --sync
```

Le script télécharge les fichiers manquants, vérifie leur intégrité gzip et inscrit taille et SHA-256 dans `data_manifest.csv`. Il n'écrit pas dans Snowflake. Après téléchargement :

```powershell
.\.venv\Scripts\python.exe .\scripts\download_inside_airbnb.py --all --dry-run --verify > verification_catalogue.txt 2>&1
Get-Content .\verification_catalogue.txt -Tail 15
.\.venv\Scripts\python.exe .\scripts\check_archives.py --hash > verification_manifeste.txt 2>&1
Get-Content .\verification_manifeste.txt -Tail 25
```

**Deux contrôles distincts :** le premier couvre le **catalogue courant** ; le second couvre **tout le manifeste**, y compris les archives historiques absentes du catalogue. Examiner les codes retour PowerShell via `$LASTEXITCODE` après chaque exécution avant de passer à la suivante. En cas d'échec, ne pas publier un état prétendument validé.

Calculer la taille totale depuis le manifeste :

```powershell
@'
import csv
with open("data_manifest.csv", newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
print("Archives :", len(rows))
print("Taille :", round(sum(int(r["size"]) for r in rows) / 1024**3, 2), "Gio")
'@ | .\.venv\Scripts\python.exe -
```

## 5. Vérification Git et publication

```powershell
git fetch origin
.\.venv\Scripts\python.exe .\scripts\comparer_manifestes.py --reference origin/main
git status --short
git diff -- data_manifest.csv
```

Le comparateur ne contacte **pas Inside Airbnb** ; il compare le manifeste local à une référence Git. Après revue des ajouts :

```powershell
git add data_manifest.csv
git commit -m "data: actualiser le manifeste World"
git push origin main
git status --short
git log -1 --oneline
```

Ne jamais faire `git add .` sans examiner les changements : les archives, secrets, logs volumineux et fichiers temporaires ne doivent pas être publiés. Si le manifeste est déjà committé, ne pas recréer un commit vide.

## 6. Passage à Snowflake : porte de validation séparée

**Ne pas lancer l'ingestion mondiale immédiatement après un téléchargement.** Confirmer : compte, rôle, warehouse, budget, capacité disque, sauvegarde, droits, journal d'ingestion, nombre de lots nouveaux et état du compte d'essai. Le journal `AIRBNB.RAW.INGESTION_LOG` et les tables RAW doivent être contrôlés ensemble.

```powershell
# Lecture seule côté RAW (mais connexion Snowflake et éventuels coûts de requête)
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --dry-run
```

Le loader réel utilise des opérations modifiantes (PUT, DELETE ciblé, COPY INTO, journalisation). **Faire d'abord un pilote sur une seule ville/date** et examiner les volumes, le journal et les erreurs. Exemple **à n'exécuter qu'après autorisation** :

```powershell
.\.venv\Scripts\python.exe .\scripts\load_raw_to_snowflake.py --country switzerland --location vaud --snapshot 2026-10-05
```

Avant toute extension mondiale, vérifier l'idempotence des lots, la correspondance exacte des dates et les crédits consommés. Une relance ne doit pas écraser aveuglément des lots déjà chargés.

## 7. dbt et Streamlit : validation après ingestion

```powershell
.\.venv\Scripts\dbt.exe debug
.\.venv\Scripts\dbt.exe parse
.\.venv\Scripts\dbt.exe ls
```

Ces commandes ne prouvent **pas** que les marts ont été reconstruits. Le build écrit des objets et peut consommer des crédits :

```powershell
# Uniquement après validation du périmètre et du budget
.\.venv\Scripts\dbt.exe build --threads 4
```

Archiver `target/run_results.json`, les logs et les comptages RAW avant/après. Comparer les 456 tests de référence et documenter tout nouvel avertissement. Le WARN historique `assert_stg_calendar_listing_exists` (3 163 références orphelines) reste à qualifier ; ne pas le masquer.

Démarrer ensuite Streamlit :

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit\streamlit_app.py
```

Vérifier les neuf pages : Vue d'ensemble, Marché, Quartiers, Cartographie, Prix, Disponibilité, Hôtes, Comparateur temporel et Méthodologie. Contrôler **les dates et volumes affichés**, pas seulement la navigation. Les secrets de connexion sont locaux dans `$HOME\.streamlit\secrets.toml`. Ne pas les copier dans le dépôt.

## 8. Incidents, reprise et limites

- **Catalogue indisponible / Gatsby modifié :** conserver le dernier manifeste, investiguer la source, ne pas exécuter de synchronisation aveugle.
- **`NEW` alors que l'archive est dans le manifeste :** restaurer le fichier physique depuis la sauvegarde ou la source officielle ; `git pull` ne le récupère pas.
- **`INVALID` / hash différent :** isoler le fichier, vérifier l'origine et les sauvegardes ; ne pas utiliser `--overwrite` sans analyse.
- **Téléchargement interrompu :** inspecter les `.part`, relancer l'inventaire, puis reprendre uniquement les manquants.
- **Journal RAW incohérent :** arrêter les écritures ; comparer `INGESTION_LOG` et les tables, sans suppression massive.
- **Essai Snowflake expiré ou crédits insuffisants :** ne pas tenter de build ; conserver les archives et preuves hors Snowflake.
- **Sélection JSON :** inclusions combinées par **OU**, pas par ET. L'orchestrateur `run_pipeline.py` exige `--selection-file` ; il n'accepte pas directement `--all`. Pour World, utiliser les étapes séparées.
- **Limites :** pas de garantie de rollback inter-étapes, de reprise transactionnelle globale, de déploiement vierge validé, ni de synchronisation automatique planifiée.

## 9. Critères de réception d'une mise à jour

- [ ] Catalogue chargé et différentiel par chemin calculé.
- [ ] Périmètre et taille estimés ; espace disque suffisant.
- [ ] Archives téléchargées et manifeste mis à jour sans altérer l'historique.
- [ ] Catalogue courant vérifié ; **manifeste entier vérifié** si livraison exhaustive.
- [ ] Git propre ; commit et push contrôlés.
- [ ] Copie indépendante des CSV.GZ et secrets hors Git.
- [ ] Dry-run RAW, budget et droits validés.
- [ ] Ingestion RAW réalisée **ou explicitement notée non exécutée**.
- [ ] Build dbt et tests réalisés **ou explicitement notés non exécutés**.
- [ ] Pages Streamlit, dates et volumes vérifiés **après** ingestion/build si applicable.
- [ ] Logs, résultats et anomalies archivés.

**Règle de publication :** utiliser « validé » uniquement pour les opérations effectivement exécutées avec une preuve ; « non testé » pour le reste.
