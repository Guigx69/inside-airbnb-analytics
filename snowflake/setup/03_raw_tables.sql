/* ============================================================================
   Inside Airbnb Analytics
   RAW layer bootstrap

   Recreates the RAW schema and the four physical ingestion tables.
   No source data is stored in Git: RAW data is reloaded from Inside Airbnb
   source snapshots by the project ingestion script.
   ============================================================================ */

CREATE SCHEMA IF NOT EXISTS AIRBNB.RAW;


/* ---------------------------------------------------------------------------
   RAW_LISTINGS
   --------------------------------------------------------------------------- */

CREATE TABLE IF NOT EXISTS AIRBNB.RAW.RAW_LISTINGS (
    SOURCE_COUNTRY VARCHAR NOT NULL,
    SOURCE_CITY    VARCHAR NOT NULL,
    SNAPSHOT_DATE  DATE NOT NULL,
    SOURCE_FILE    VARCHAR NOT NULL,
    LOADED_AT      TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    RAW_DATA       VARIANT NOT NULL
);


/* ---------------------------------------------------------------------------
   RAW_CALENDAR
   --------------------------------------------------------------------------- */

CREATE TABLE IF NOT EXISTS AIRBNB.RAW.RAW_CALENDAR (
    SOURCE_COUNTRY VARCHAR NOT NULL,
    SOURCE_CITY    VARCHAR NOT NULL,
    SNAPSHOT_DATE  DATE NOT NULL,
    SOURCE_FILE    VARCHAR NOT NULL,
    LOADED_AT      TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    RAW_DATA       VARIANT NOT NULL
);


/* ---------------------------------------------------------------------------
   RAW_REVIEWS
   --------------------------------------------------------------------------- */

CREATE TABLE IF NOT EXISTS AIRBNB.RAW.RAW_REVIEWS (
    SOURCE_COUNTRY VARCHAR NOT NULL,
    SOURCE_CITY    VARCHAR NOT NULL,
    SNAPSHOT_DATE  DATE NOT NULL,
    SOURCE_FILE    VARCHAR NOT NULL,
    LOADED_AT      TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    RAW_DATA       VARIANT NOT NULL
);


/* ---------------------------------------------------------------------------
   INGESTION_LOG
   --------------------------------------------------------------------------- */

CREATE TABLE IF NOT EXISTS AIRBNB.RAW.INGESTION_LOG (
    SOURCE_COUNTRY VARCHAR NOT NULL,
    SOURCE_CITY    VARCHAR NOT NULL,
    SNAPSHOT_DATE  DATE NOT NULL,
    SOURCE_FILE    VARCHAR NOT NULL,
    TARGET_TABLE   VARCHAR NOT NULL,
    ROW_COUNT      NUMBER(38,0),
    LOADED_AT      TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);


/* ---------------------------------------------------------------------------
   Validation
   --------------------------------------------------------------------------- */

SELECT
    TABLE_NAME,
    ROW_COUNT
FROM AIRBNB.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'RAW'
  AND TABLE_NAME IN (
      'RAW_LISTINGS',
      'RAW_CALENDAR',
      'RAW_REVIEWS',
      'INGESTION_LOG'
  )
ORDER BY TABLE_NAME;