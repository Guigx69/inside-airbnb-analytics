# Sélection géographique — collecte, vérification des archives et chargement RAW

Le sélecteur géographique prend un fichier JSON explicite. Les inclusions sont réunies par **OU** entre continents, pays et villes. Les exclusions sont appliquées ensuite. Une inclusion répétée ne duplique pas les fichiers du catalogue.

Exemple `config/geography.example.json` :

```json
{"include":{"continents":["Europe"],"countries":["Japan"],"cities":["Sydney"]},"exclude":{"cities":["Paris"]}}
```

Après `git pull` et `./scripts/setup.ps1`, prévisualiser dans PowerShell :

```powershell
.\.venv\Scripts\python.exe scripts\download_inside_airbnb.py --selection-file config/geography.example.json --dry-run
```

Pour télécharger, remplacer explicitement `--dry-run` par `--sync --verify`. **Ne pas lancer une collecte multirégionale sans examiner l'inventaire et estimer les besoins réseau et disque.**

Les continents sont déduits des pays du catalogue via `country_converter`. Un nom inconnu provoque une erreur. Les villes sont recherchées mondialement : un nom présent dans plusieurs pays sélectionne toutes les occurrences. Les exclusions de ville sont également globales. Seuls les jeux de données du catalogue Inside Airbnb **actuellement publié** sont sélectionnables.

Le même fichier sert au manifeste local :

```powershell
.\.venv\Scripts\python.exe scripts\check_archives.py --selection-file config/geography.example.json --hash
.\.venv\Scripts\python.exe scripts\load_raw_to_snowflake.py --selection-file config/geography.example.json --dry-run
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_geography_selection.py" -v
```

**Contrôles historiques du 08/10/2026 sous Windows :** 864 archives du manifeste validées par SHA-256 ; simulation RAW : 864 fichiers déjà chargés et aucun en attente ; six tests de régression géographique réussis. Ces chiffres ne représentent pas l'état actuel du catalogue.

**Différence entre les inventaires :** le collecteur lit le catalogue en ligne ; le contrôle d'archives et le chargeur RAW lisent uniquement le manifeste local. Lors du contrôle historique : 870 fichiers visibles en ligne (159 nouveaux) et 864 dans le manifeste ; 711 communs, 159 uniquement en ligne et 153 uniquement dans le manifeste. Les snapshots historiques sortis du catalogue doivent être conservés, jamais supprimés automatiquement.

**Limite :** `run_pipeline.py` orchestre une sélection JSON explicite ; il n'offre pas d'option `--all` pour le monde en une seule commande. Voir [Guide géographique A à Z](GUIDE_GEOGRAPHIE_A_Z.md).
