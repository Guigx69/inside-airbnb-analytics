# Geographic selection (collector, archive preflight and RAW loader)

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

The same selection file can be applied to local manifest entries:

```powershell
.\.venv\Scripts\python.exe scripts\check_archives.py --selection-file config/geography.example.json --hash
.\.venv\Scripts\python.exe scripts\load_raw_to_snowflake.py --selection-file config/geography.example.json --dry-run
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_geography_selection.py" -v
```

Validated on Windows (2026-10-08): 864 manifest archives passed SHA-256;
RAW dry-run classified 864 already loaded and 0 pending; all six offline
selection regression tests passed.

**Inventory semantics:** the collector selects snapshots from the live Inside
Airbnb catalog; archive preflight and RAW loader select only existing local
manifest entries. The observed live preview (870 files, including 159 NEW)
and local manifest (864 files) therefore are not directly interchangeable.
Path-level reconciliation on Windows confirmed 711 shared files, 159 live-only files, and 153 manifest-only files (870 = 711 + 159; 864 = 711 + 153). Examples show September 2026 snapshots in the live catalog and September 2025 snapshots retained only in the local manifest. Preserve historical manifest entries; do not delete them when catalog entries rotate.

**Limit:** full collector-to-dbt orchestration is not implemented yet.

