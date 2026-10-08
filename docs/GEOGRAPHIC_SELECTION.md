# Geographic selection (collector, initial implementation)

The geographic selector accepts an explicit JSON file. Inclusion and exclusion
sets are unions across continents, countries and cities. Exclusions are applied
last. Overlapping inclusions never duplicate catalog datasets.

Example `config/geography.example.json`:
```json
{
  "include": {
    "continents": ["Europe"],
    "countries": ["Japan"],
    "cities": ["Sydney"]
  },
  "exclude": {
    "cities": ["Paris"]
  }
}
```

After `git pull` and `./scripts/setup.ps1`, preview the selection in PowerShell:
```powershell
.\.venv\Scripts\python.exe scripts\download_inside_airbnb.py --selection-file config/geography.example.json --dry-run
```

To download, explicitly replace `--dry-run` with `--sync --verify`.
Never run an unreviewed multi-continent download: inspect the printed inventory
and anticipated storage/network requirements first.

Continents are derived from catalog country names using `country_converter`.
Unknown names cause an error instead of silently broadening the selection.
City names are matched globally: if a city name occurs in multiple countries,
all matches are selected. Use an exclusion carefully for the same reason.
Only datasets in the **currently published** Inside Airbnb catalog are selectable.

Current limits: JSON selection is integrated into the **collector only**.
The RAW loader and archive preflight do not yet accept this selection file;
there is no integrated end-to-end geographic orchestration yet.
This feature has not been validated on the user's Windows environment.
