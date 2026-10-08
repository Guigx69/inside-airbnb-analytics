# Provisioning a new Snowflake RAW environment

The SQL file `sql/bootstrap_raw.sql` creates the minimum RAW schema,
three VARIANT-backed source tables, ingestion log and internal stage
required by `scripts/load_raw_to_snowflake.py`.

**Not an automatic installer.** It assumes an existing database `AIRBNB`,
an appropriately sized warehouse, and provisioned roles. Change the
database/schema identifiers before running against another account.
Run only on a dedicated new environment with authorized DDL privileges.
It uses `IF NOT EXISTS` and does not delete existing objects, but existing
objects with incompatible structures are not repaired.

The ingestion role needs USAGE on database/schema/warehouse, DML on
the RAW tables and log, and appropriate stage permissions. The dbt role
needs USAGE and SELECT on RAW and privileges to create its output schemas
and models. Privilege grants are environment-specific and are **not**
performed by this script.

## Data dependency

The Git repository does not include `data/raw`. All selected
`data_manifest.csv` archive paths must exist locally with the recorded
size and SHA-256 before ingestion. The collector `scripts/download_inside_airbnb.py` can discover currently
published snapshots and download a selected city/snapshot, validating gzip
and recording SHA-256 in the manifest. Previously published snapshots may
no longer be in the live catalog; preserve historical archives separately.

The loader filters the manifest **before validating archives**. A scoped
city/snapshot ingestion only requires the corresponding local files.
This was validated for Lyon 2026-09-17 on the existing development account;
full historical recovery and fresh-account deployment remain unverified.

## Controlled execution order

1. Review identifiers, roles, warehouse sizing and estimated data volume.
2. Execute `sql/bootstrap_raw.sql` on a new Snowflake database.
3. Grant the necessary privileges and inspect object definitions.
4. Restore and verify source archives in `data/raw`.
5. Export ingestion environment variables securely; a local `.env`
   file is **not** automatically loaded.
6. Run `python scripts/load_raw_to_snowflake.py --dry-run`, review the
   plan, then run without `--dry-run` only after explicit approval.
7. Configure `~/.dbt/profiles.yml` and dbt RAW source variables, run
   `dbt debug`, `dbt parse`, `dbt compile`, then an authorized build.

The RAW bootstrap SQL and ingestion procedure have **not yet been
validated on a fresh Snowflake account**. Do not describe them as a
proven one-click deployment.
