# Manager quickstart (Windows / Snowflake)

## Prerequisites
- Git, Python (compatible with dbt-core 1.12), PowerShell and access to a Snowflake account.
- Snowflake database/RAW tables, roles, warehouse and privileges must be provisioned separately.
- Never share personal passwords or commit credentials.

## Clone and prepare
```powershell
git clone https://github.com/Guigx69/inside-airbnb-analytics.git
cd inside-airbnb-analytics
.\scripts\setup.ps1
```

## Configure
- Copy `.env.example` to a local `.env` for reference; `.env` is intentionally ignored by Git and **not loaded automatically**.
- Create `$HOME\.dbt\profiles.yml` using your own Snowflake account, role, warehouse, database and schema.
- The dbt project expects a profile named `inside_airbnb`. Use environment variables or a secure authenticator; do not commit secrets.
- RAW ingestion uses `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `DBT_SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`.

## Validate (no data modifications)
```powershell
.\scripts\check_environment.ps1
```

## Mode A: existing Snowflake RAW data
Confirm your own Snowflake role can read `AIRBNB.RAW` and write to your dbt target schema.
Review the target configuration before running:
```powershell
.\.venv\Scripts\dbt.exe build
```
This command **writes** dbt objects and runs tests.

## Mode B: rebuild from source (not yet one-click)
The repository excludes `data/raw/`. The collector `scripts/download_inside_airbnb.py` can retrieve snapshots currently available in the public catalog; historical snapshots missing from that catalog require an authorized archive transfer. The ingestion loader filters the manifest before validating archives, so only files in the selected city/snapshot scope are required. A Lyon 2026-09-17 collection, SHA-256 check, RAW ingestion, dbt run and targeted dbt tests succeeded on the development account.
For a small-city pilot, use `python scripts/download_inside_airbnb.py --location lyon --dry-run --verify`, then an explicitly approved scoped `--sync --verify`, `python scripts/check_archives.py --country france --location lyon --hash`, and `python scripts/load_raw_to_snowflake.py --dry-run --country france --location lyon` before authorizing a real ingestion. Snowflake RAW tables, `INGESTION_LOG` and `INSIDE_AIRBNB_STAGE` must already exist. Do not run ingestion until the target environment and expected data volumes have been reviewed.

## Streamlit in Snowflake
The deployment manifest is `streamlit/snowflake.yml`. It currently contains development-specific Snowflake identifiers, so deploying in another account requires adapting the identifiers and privileges. Do not deploy it unchanged to a production environment.

## Current limits
- This quickstart provides a reproducible local toolchain and a read-only connection check, not a full Snowflake infrastructure bootstrap.
- The current catalog download path is validated for Lyon; replay of the entire historical manifest remains unverified.
- There is no demonstrated scheduled end-to-end orchestration in this repository.
