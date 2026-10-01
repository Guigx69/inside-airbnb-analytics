/* ============================================================================
   Inside Airbnb Analytics
   Snowflake Core Infrastructure
   File: snowflake/setup/01_database.sql

   Purpose:
     - Create the AIRBNB database
     - Create the DBT_WH warehouse

   Run with:
     ACCOUNTADMIN

   This script is idempotent and can safely be executed multiple times.
   ============================================================================ */


/* ============================================================================
   1. DATABASE
   ============================================================================ */

CREATE DATABASE IF NOT EXISTS AIRBNB;


/* ============================================================================
   2. COMPUTE WAREHOUSE

   Configuration reproduced from the validated POC environment:
     Type                       STANDARD
     Size                       X-Small
     Min clusters               1
     Max clusters               1
     Auto suspend               60 seconds
     Auto resume                TRUE
     Scaling policy             STANDARD
     Resource constraint        STANDARD_GEN_2
     Query acceleration         TRUE
     Query acceleration scale   8
   ============================================================================ */

CREATE WAREHOUSE IF NOT EXISTS DBT_WH
    WAREHOUSE_TYPE = STANDARD
    WAREHOUSE_SIZE = 'XSMALL'
    MIN_CLUSTER_COUNT = 1
    MAX_CLUSTER_COUNT = 1
    SCALING_POLICY = STANDARD
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    ENABLE_QUERY_ACCELERATION = TRUE
    QUERY_ACCELERATION_MAX_SCALE_FACTOR = 8
    RESOURCE_CONSTRAINT = STANDARD_GEN_2
    COMMENT = 'Warehouse dédié à dbt Core pour le POC Inside Airbnb';


/* ============================================================================
   3. VALIDATION
   ============================================================================ */

SHOW DATABASES LIKE 'AIRBNB';

SHOW WAREHOUSES LIKE 'DBT_WH';