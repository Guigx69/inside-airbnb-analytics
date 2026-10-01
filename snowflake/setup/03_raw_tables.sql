/* ============================================================================
   Inside Airbnb Analytics
   Snowflake RAW Layer Bootstrap
   File: snowflake/setup/03_raw_tables.sql

   Purpose:
     - Create the RAW schema
     - Create the internal ingestion stage
     - Create the three RAW source tables
     - Create the ingestion audit table

   Notes:
     - No RAW business data is stored in Git.
     - Source snapshots are loaded by scripts/load_raw_to_snowflake.py.
     - This script is idempotent and can safely be executed multiple times.
   ============================================================================ */


/* ============================================================================
   1. RAW SCHEMA
   ============================================================================ */

CREATE SCHEMA IF NOT EXISTS AIRBNB.RAW;


/* ============================================================================
   2. INTERNAL INGESTION STAGE

   Temporary landing area used by scripts/load_raw_to_snowflake.py.

   The loader:
     1. Reads the source CSV.GZ files locally
     2. Converts them to JSON.GZ
     3. Uploads them to this internal Snowflake stage
     4. Executes COPY INTO the corresponding RAW table

   The stage intentionally uses Snowflake default properties.
   The COPY command defines its own JSON/GZIP file format.
   ============================================================================ */

CREATE STAGE IF NOT EXISTS AIRBNB.RAW.INSIDE_AIRBNB_STAGE
    COMMENT = 'Internal stage for Inside Airbnb source files';


/* ============================================================================
   3. RAW_LISTINGS
   ============================================================================ */

CREATE TABLE IF NOT EXISTS AIRBNB.RAW.RAW_LISTINGS (
    SOURCE_COUNTRY VARCHAR NOT NULL,
    SOURCE_CITY    VARCHAR NOT NULL,
    SNAPSHOT_DATE  DATE NOT NULL,
    SOURCE_FILE    VARCHAR NOT NULL,
    LOADED_AT      TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    RAW_DATA       VARIANT NOT NULL
);


/* ============================================================================
   4. RAW_CALENDAR
   ============================================================================ */

CREATE TABLE IF NOT EXISTS AIRBNB.RAW.RAW_CALENDAR (
    SOURCE_COUNTRY VARCHAR NOT NULL,
    SOURCE_CITY    VARCHAR NOT NULL,
    SNAPSHOT_DATE  DATE NOT NULL,
    SOURCE_FILE    VARCHAR NOT NULL,
    LOADED_AT      TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    RAW_DATA       VARIANT NOT NULL
);


/* ============================================================================
   5. RAW_REVIEWS
   ============================================================================ */

CREATE TABLE IF NOT EXISTS AIRBNB.RAW.RAW_REVIEWS (
    SOURCE_COUNTRY VARCHAR NOT NULL,
    SOURCE_CITY    VARCHAR NOT NULL,
    SNAPSHOT_DATE  DATE NOT NULL,
    SOURCE_FILE    VARCHAR NOT NULL,
    LOADED_AT      TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    RAW_DATA       VARIANT NOT NULL
);


/* ============================================================================
   6. INGESTION_LOG

   One row per successfully loaded source file.

   Used to retain:
     - source location
     - snapshot date
     - source filename
     - target RAW table
     - number of rows loaded
     - ingestion timestamp
   ============================================================================ */

CREATE TABLE IF NOT EXISTS AIRBNB.RAW.INGESTION_LOG (
    SOURCE_COUNTRY VARCHAR NOT NULL,
    SOURCE_CITY    VARCHAR NOT NULL,
    SNAPSHOT_DATE  DATE NOT NULL,
    SOURCE_FILE    VARCHAR NOT NULL,
    TARGET_TABLE   VARCHAR NOT NULL,
    ROW_COUNT      NUMBER(38,0),
    LOADED_AT      TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);


/* ============================================================================
   7. VALIDATION - TABLES

   Expected:
     INGESTION_LOG
     RAW_CALENDAR
     RAW_LISTINGS
     RAW_REVIEWS
   ============================================================================ */

SELECT
    TABLE_NAME,
    ROW_COUNT
FROM AIRBNB.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'RAW'
  AND TABLE_NAME IN (
      'INGESTION_LOG',
      'RAW_CALENDAR',
      'RAW_LISTINGS',
      'RAW_REVIEWS'
  )
ORDER BY TABLE_NAME;


/* ============================================================================
   8. VALIDATION - INTERNAL STAGE

   Expected:
     INSIDE_AIRBNB_STAGE
     TYPE = INTERNAL
   ============================================================================ */

SHOW STAGES IN SCHEMA AIRBNB.RAW;