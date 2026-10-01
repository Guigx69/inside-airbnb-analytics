/* ============================================================================
   Inside Airbnb Analytics
   Snowflake Roles
   File: snowflake/setup/02_roles.sql

   Purpose:
     - Create DBT_ROLE
     - Create INGESTION_ROLE
     - Grant the infrastructure-level privileges required by each role

   Run with:
     ACCOUNTADMIN

   Important:
     User-specific role assignments are intentionally NOT included here.
     This keeps the project portable across Snowflake accounts.

   After running this script on a new account, execute:

       GRANT ROLE DBT_ROLE TO USER <YOUR_USER>;
       GRANT ROLE INGESTION_ROLE TO USER <YOUR_USER>;

   ============================================================================ */


/* ============================================================================
   1. ROLES
   ============================================================================ */

CREATE ROLE IF NOT EXISTS DBT_ROLE
    COMMENT = 'Role used by dbt Core for Inside Airbnb Analytics';

CREATE ROLE IF NOT EXISTS INGESTION_ROLE
    COMMENT = 'Role used to ingest Inside Airbnb source files into RAW';


/* ============================================================================
   2. DBT_ROLE - COMPUTE
   ============================================================================ */

GRANT USAGE
    ON WAREHOUSE DBT_WH
    TO ROLE DBT_ROLE;


/* ============================================================================
   3. DBT_ROLE - DATABASE

   dbt needs:
     - USAGE to access AIRBNB
     - CREATE SCHEMA because dbt creates target schemas such as:
         DBT_<USER>_STAGING
         DBT_<USER>_INTERMEDIATE
         DBT_<USER>_MARTS
   ============================================================================ */

GRANT USAGE
    ON DATABASE AIRBNB
    TO ROLE DBT_ROLE;

GRANT CREATE SCHEMA
    ON DATABASE AIRBNB
    TO ROLE DBT_ROLE;


/* ============================================================================
   4. INGESTION_ROLE - COMPUTE

   Object-level RAW privileges are intentionally applied later by
   04_grants.sql, after the RAW schema/tables/stage have been created.
   ============================================================================ */

GRANT USAGE
    ON WAREHOUSE DBT_WH
    TO ROLE INGESTION_ROLE;

GRANT USAGE
    ON DATABASE AIRBNB
    TO ROLE INGESTION_ROLE;


/* ============================================================================
   5. VALIDATION
   ============================================================================ */

SHOW ROLES LIKE 'DBT_ROLE';

SHOW ROLES LIKE 'INGESTION_ROLE';

SHOW GRANTS TO ROLE DBT_ROLE;

SHOW GRANTS TO ROLE INGESTION_ROLE;