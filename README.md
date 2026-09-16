# Inside Airbnb Analytics Platform

Data engineering and analytics Proof of Concept built with **dbt**, **Snowflake** and **Inside Airbnb open data**.

The project transforms historical Airbnb snapshots into a tested and documented analytical layer designed for market, neighbourhood, host, pricing, availability and review analysis.

## Overview

The objective of this POC is to demonstrate an end-to-end modern analytics workflow:

```text
Inside Airbnb
      │
      ▼
Historical CSV snapshots
      │
      ▼
Snowflake RAW
      │
      ▼
dbt STAGING
      │
      ▼
dbt INTERMEDIATE
      │
      ▼
dbt MARTS
      │
      ▼
BI / Analytics
```

The first implementation focuses on **Lyon, France**, while the data model is designed to support future geographical expansion without fundamentally redesigning the transformation layer.

Planned scalability:

```text
V1  Lyon
V2  France
V3  Europe
V4  Global
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Data source | Inside Airbnb Open Data |
| Data warehouse | Snowflake |
| Transformation | dbt |
| Development environment | Visual Studio Code |
| Raw ingestion | Python |
| Data format | CSV / CSV.GZ |
| Version control | Git |
| Analytics | BI layer to be added |

The current development environment has been validated using dbt Fusion.

---

## Data Source

Data is sourced from **Inside Airbnb**, an independent project providing publicly available datasets derived from Airbnb listings.

The POC uses three detailed datasets:

- `listings.csv.gz`
- `calendar.csv.gz`
- `reviews.csv.gz`

Each ingestion also records technical metadata:

- source country
- source city
- snapshot date
- source file
- load timestamp

This allows every analytical record to remain traceable to its source snapshot.

### Historical snapshots

The Lyon V1 currently contains four snapshots:

| Snapshot |
|---|
| 2025-09-18 |
| 2025-12-22 |
| 2026-03-25 |
| 2026-06-22 |

The use of multiple snapshots enables longitudinal analysis rather than limiting the project to the latest state of the market.

---

## Architecture

### RAW

Raw Inside Airbnb files are loaded into Snowflake with the original source row stored as `VARIANT`.

Main raw tables:

```text
AIRBNB.RAW.RAW_LISTINGS
AIRBNB.RAW.RAW_CALENDAR
AIRBNB.RAW.RAW_REVIEWS
```

The RAW layer intentionally performs minimal transformation and preserves source traceability.

### STAGING

The staging layer converts semi-structured RAW records into typed, consistently named analytical columns.

Models:

```text
stg_listings
stg_calendar
stg_reviews
```

Responsibilities include:

- data typing
- field normalization
- source metadata propagation
- basic source quality validation
- definition of stable technical grains

### INTERMEDIATE

The intermediate layer implements reusable analytical business logic.

Models:

```text
int_reviews
int_listing_snapshot
int_listing_snapshot_movement
int_market_snapshot_transition
int_neighbourhood_snapshot_transition
int_listing_calendar_metrics
int_listing_availability_horizon
int_calendar_monthly_metrics
int_listing_review_metrics
int_host_snapshot
```

This layer handles concepts such as:

- historical listing presence
- snapshot sequencing
- listing entry and return
- observation gaps
- market transitions
- neighbourhood transitions
- host portfolio reconstruction
- calendar availability
- availability horizons
- monthly calendar coverage
- reconstructed historical review activity

### MARTS

The marts layer exposes BI-oriented analytical datasets.

Models:

```text
fct_listing_snapshot

mart_market_snapshot
mart_market_transition

mart_neighbourhood_snapshot
mart_neighbourhood_transition

mart_host_snapshot

mart_room_type_snapshot

mart_price_distribution_snapshot
mart_price_transition

mart_availability_snapshot
mart_availability_horizon_snapshot
mart_calendar_month_snapshot
```

The marts are designed around explicit analytical grains and are suitable for direct consumption by a BI layer.

---

## Model Inventory

The current dbt project contains:

| Layer | Models |
|---|---:|
| Staging | 3 |
| Intermediate | 10 |
| Marts / Fact | 12 |
| **Total** | **25** |

All 25 models are documented in dbt YAML metadata.

---

## Main Analytical Capabilities

### Market evolution

The project can measure market evolution between historical snapshots, including:

- listing population
- retained listings
- disappeared listings
- newly observed listings
- listings returning after an observation gap
- net listing change
- retention and disappearance rates

### Neighbourhood dynamics

Neighbourhood models provide:

- listing population by neighbourhood
- entries and disappearances
- movements between neighbourhoods
- returns after observation gaps
- neighbourhood-level net changes

Geographical movement is explicitly separated from listing disappearance.

### Host concentration

Host-level reconstruction enables analysis of:

- number of active hosts
- listings per host
- single-listing versus multi-listing hosts
- host portfolio segments
- superhost share
- identity verification
- top 1%, 5% and 10% listing concentration
- Herfindahl-Hirschman Index (HHI)

### Pricing

Pricing models provide:

- listing-level price
- market price statistics
- price distributions
- price bands
- price changes between observations
- increases, decreases and unchanged prices
- comparable-price coverage

Source price coverage varies by snapshot and is therefore explicitly measured rather than assumed.

### Availability

Availability is reconstructed from the detailed calendar dataset.

Analytics include:

- available and unavailable listing-days
- listing-level availability rates
- market availability rates
- 30-day horizon
- 60-day horizon
- 90-day horizon
- 365-day horizon
- monthly availability
- calendar coverage

Monthly models preserve partial calendar months instead of silently treating them as complete months.

### Reviews

Reviews are deduplicated across historical snapshots using the business grain:

```text
country + city + listing_id + review_id
```

The project reconstructs review activity as of each historical snapshot, including:

- cumulative reviews
- reviews during the previous 30 days
- reviews during the previous 90 days
- reviews during the previous 365 days
- first historical review
- latest review
- recency of review activity

Native Inside Airbnb review indicators are preserved separately from reconstructed metrics.

---

## Historical Snapshot Semantics

A central design principle of this project is the distinction between:

```text
previous snapshot
```

and:

```text
previous observed snapshot for a listing
```

A listing can disappear from one snapshot and reappear later.

The model therefore explicitly tracks:

- first observation
- last observation
- number of observed snapshots
- observation gaps
- missing snapshot count
- immediately preceding market presence
- returns after gaps

This prevents a reappearing listing from being incorrectly classified as a new listing.

---

## Calendar Semantics

Inside Airbnb calendar availability represents **future calendar availability as observed at the snapshot date**.

It must not be interpreted directly as observed historical occupancy.

Therefore:

```text
unavailable day ≠ proven occupied day
```

A date may be unavailable for reasons other than a completed booking.

The project consequently exposes **availability metrics**, not factual occupancy metrics.

Similarly, any occupancy or revenue estimates originating from Inside Airbnb must be treated as estimates rather than observed commercial transactions.

---

## Data Quality

Data quality is enforced through dbt tests covering:

- source metadata completeness
- required fields
- accepted values
- model grains
- historical consistency
- transition consistency
- population reconciliation
- calendar reconciliation
- availability consistency
- review consistency

Latest validated full build:

```text
25 models
445 tests
470 nodes processed

469 success
1 warning
0 failures
0 errors
```

The remaining warning is intentional.

A source-level reconciliation identified **38 listing IDs in the detailed calendar for the 2026-06-22 snapshot that are not present in the corresponding listings dataset**.

The relationship is therefore monitored as a warning rather than forcing the transformation layer to discard valid calendar observations.

---

## Repository Structure

```text
inside_airbnb/
│
├── analyses/
├── data/
├── macros/
├── models/
│   ├── staging/
│   ├── intermediate/
│   └── marts/
│       └── core/
│
├── scripts/
├── seeds/
├── snapshots/
├── tests/
│
├── dbt_project.yml
├── README.md
└── .gitignore
```

### Python utilities

The `scripts` directory contains utilities used to ingest and validate the source data:

```text
check_raw_keys.py
load_raw_to_snowflake.py
profile_raw_data.py
validate_snapshots.py
```

---

## Snowflake Organization

The development environment separates the different transformation layers into dedicated schemas.

Example:

```text
AIRBNB
│
├── RAW
│
├── DBT_<DEVELOPER>_staging
│
├── DBT_<DEVELOPER>_intermediate
│
└── DBT_<DEVELOPER>_marts
```

This keeps raw source data separate from developer-specific transformation objects.

Credentials are not stored in the repository.

The Snowflake password is supplied to dbt through an environment variable.

---

## Running the Project

### Validate dbt configuration

```powershell
dbt debug
```

### Parse the project

```powershell
dbt parse
```

### Build the complete analytical layer

```powershell
dbt build
```

`dbt build` creates the models in dependency order and executes the associated data tests.

### Run models only

```powershell
dbt run
```

### Run tests only

```powershell
dbt test
```

### Run a specific model

```powershell
dbt run --select mart_market_snapshot
```

### Test a specific model

```powershell
dbt test --select mart_market_snapshot
```

---

## Design Principles

The project follows several explicit modelling principles:

1. Preserve source traceability.
2. Never silently remove source anomalies.
3. Define and test the grain of analytical models.
4. Separate staging, reusable business logic and BI-facing marts.
5. Preserve historical snapshot semantics.
6. Distinguish source-native indicators from reconstructed indicators.
7. Measure data coverage instead of assuming completeness.
8. Preserve partial calendar periods.
9. Avoid interpreting availability as observed occupancy.
10. Design geographical dimensions for future expansion.

---

## Current Scope and Limitations

The current POC is intentionally limited to Lyon and four historical snapshots.

Known limitations include:

- source coverage varies between snapshots
- listing prices are unavailable in some source snapshots
- calendar and listings populations can differ slightly
- calendar data represents availability, not observed occupancy
- reconstructed review metrics can differ from native Inside Airbnb counters
- source snapshot intervals are not perfectly regular
- the current project does not infer real Airbnb bookings or actual revenue

These limitations are preserved explicitly in the analytical design rather than hidden by transformations.

---

## Roadmap

### V1 — Lyon

- historical ingestion
- Snowflake RAW layer
- dbt staging
- historical intermediate models
- analytical marts
- automated data quality tests
- project documentation
- BI dashboard

### V2 — France

Extend the ingestion framework to additional French cities while preserving the existing analytical model.

### V3 — Europe

Generalize ingestion and reporting to European markets.

### V4 — Global

Support a broader multi-country analytical platform using the same source metadata and modelling principles.

---

## Status

**Data engineering and dbt modelling: validated**

Current validated build:

```text
25 models
445 tests
469 successful nodes
1 documented source warning
0 failures
0 errors
```

Next milestone:

```text
BI / Analytics layer
```