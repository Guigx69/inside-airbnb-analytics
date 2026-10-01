/* ============================================================================
   Inside Airbnb Analytics
   Snowflake Object Grants
   File: snowflake/setup/04_grants.sql

   Purpose:
     - Grant INGESTION_ROLE the privileges required to load Inside Airbnb
       source files into the RAW layer.
     - Grant DBT_ROLE read access to the RAW layer used as dbt sources.

   Prerequisites:
     - AIRBNB database exists
     - DBT_WH warehouse exists
     - DBT_ROLE exists
     - INGESTION_ROLE exists
     - AIRBNB.RAW schema exists
     - AIRBNB.RAW.INSIDE_AIRBNB_STAGE exists
     - RAW tables exist

   Execution order:
     01_database.sql
     02_roles.sql
     03_raw_tables.sql
     04_grants.sql

   Run with:
     ACCOUNTADMIN

   This script is idempotent and can safely be executed multiple times.
   ============================================================================ */


/* ============================================================================
   1. INGESTION_ROLE - WAREHOUSE
   ============================================================================ */

GRANT USAGE
    ON WAREHOUSE DBT_WH
    TO ROLE INGESTION_ROLE;


/* ============================================================================
   2. INGESTION_ROLE - DATABASE AND RAW SCHEMA
   ============================================================================ */

GRANT USAGE
    ON DATABASE AIRBNB
    TO ROLE INGESTION_ROLE;

GRANT USAGE
    ON SCHEMA AIRBNB.RAW
    TO ROLE INGESTION_ROLE;


/* ============================================================================
   3. INGESTION_ROLE - INTERNAL STAGE

   READ:
     Required to read staged JSON.GZ files during COPY INTO.

   WRITE:
     Required to upload local JSON.GZ files with PUT.

   Stage:
     AIRBNB.RAW.INSIDE_AIRBNB_STAGE
   ============================================================================ */

GRANT READ
    ON STAGE AIRBNB.RAW.INSIDE_AIRBNB_STAGE
    TO ROLE INGESTION_ROLE;

GRANT WRITE
    ON STAGE AIRBNB.RAW.INSIDE_AIRBNB_STAGE
    TO ROLE INGESTION_ROLE;


/* ============================================================================
   4. INGESTION_ROLE - RAW_LISTINGS

   SELECT:
     Required for post-load row-count validation.

   INSERT:
     Required by COPY INTO.

   DELETE:
     Required to replace an existing source batch before reloading it.
   ============================================================================ */

GRANT SELECT, INSERT, DELETE
    ON TABLE AIRBNB.RAW.RAW_LISTINGS
    TO ROLE INGESTION_ROLE;


/* ============================================================================
   5. INGESTION_ROLE - RAW_CALENDAR
   ============================================================================ */

GRANT SELECT, INSERT, DELETE
    ON TABLE AIRBNB.RAW.RAW_CALENDAR
    TO ROLE INGESTION_ROLE;


/* ============================================================================
   6. INGESTION_ROLE - RAW_REVIEWS
   ============================================================================ */

GRANT SELECT, INSERT, DELETE
    ON TABLE AIRBNB.RAW.RAW_REVIEWS
    TO ROLE INGESTION_ROLE;


/* ============================================================================
   7. INGESTION_ROLE - INGESTION_LOG

   SELECT:
     Allows validation and inspection of ingestion history.

   INSERT:
     Records a successfully loaded source file.

   DELETE:
     Removes the previous log entry before replacing it.
   ============================================================================ */

GRANT SELECT, INSERT, DELETE
    ON TABLE AIRBNB.RAW.INGESTION_LOG
    TO ROLE INGESTION_ROLE;


/* ============================================================================
   8. DBT_ROLE - RAW SCHEMA ACCESS

   dbt models use AIRBNB.RAW as their source layer.

   DBT_ROLE therefore requires:
     - USAGE on the RAW schema
     - SELECT on the three source tables
     - SELECT on INGESTION_LOG
   ============================================================================ */

GRANT USAGE
    ON SCHEMA AIRBNB.RAW
    TO ROLE DBT_ROLE;


/* ============================================================================
   9. DBT_ROLE - RAW TABLE READ ACCESS
   ============================================================================ */

GRANT SELECT
    ON TABLE AIRBNB.RAW.RAW_LISTINGS
    TO ROLE DBT_ROLE;

GRANT SELECT
    ON TABLE AIRBNB.RAW.RAW_CALENDAR
    TO ROLE DBT_ROLE;

GRANT SELECT
    ON TABLE AIRBNB.RAW.RAW_REVIEWS
    TO ROLE DBT_ROLE;

GRANT SELECT
    ON TABLE AIRBNB.RAW.INGESTION_LOG
    TO ROLE DBT_ROLE;


/* ============================================================================
   10. VALIDATION - INGESTION_ROLE

   Expected privileges:

     WAREHOUSE
       DBT_WH
         USAGE

     DATABASE
       AIRBNB
         USAGE

     SCHEMA
       AIRBNB.RAW
         USAGE

     STAGE
       AIRBNB.RAW.INSIDE_AIRBNB_STAGE
         READ
         WRITE

     TABLE
       AIRBNB.RAW.RAW_LISTINGS
         SELECT
         INSERT
         DELETE

       AIRBNB.RAW.RAW_CALENDAR
         SELECT
         INSERT
         DELETE

       AIRBNB.RAW.RAW_REVIEWS
         SELECT
         INSERT
         DELETE

       AIRBNB.RAW.INGESTION_LOG
         SELECT
         INSERT
         DELETE

   Expected total:
     17 grants
   ============================================================================ */

SHOW GRANTS TO ROLE INGESTION_ROLE;


/* ============================================================================
   11. VALIDATION - DBT_ROLE

   Relevant bootstrap privileges expected:

     WAREHOUSE
       DBT_WH
         USAGE

     DATABASE
       AIRBNB
         USAGE
         CREATE SCHEMA

     SCHEMA
       AIRBNB.RAW
         USAGE

     TABLE
       AIRBNB.RAW.RAW_LISTINGS
         SELECT

       AIRBNB.RAW.RAW_CALENDAR
         SELECT

       AIRBNB.RAW.RAW_REVIEWS
         SELECT

       AIRBNB.RAW.INGESTION_LOG
         SELECT

   Additional OWNERSHIP grants may already exist on schemas, views,
   tables, Streamlit objects and Git objects created later by DBT_ROLE.
   Those are intentionally NOT recreated by this bootstrap script.
   ============================================================================ */

SHOW GRANTS TO ROLE DBT_ROLE;