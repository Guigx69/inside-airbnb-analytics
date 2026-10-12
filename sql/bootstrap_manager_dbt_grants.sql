-- Administrator provisioning for dbt on a NEW Snowflake account.
-- Requires pre-existing DBT_ROLE, DBT_WH and AIRBNB database/RAW tables.
-- Review schema prefix and execute with a role authorized to grant privileges.
-- No DROP, REVOKE, ownership transfer or modifications to existing data.

GRANT USAGE ON WAREHOUSE DBT_WH TO ROLE DBT_ROLE;
GRANT USAGE, CREATE SCHEMA ON DATABASE AIRBNB TO ROLE DBT_ROLE;
GRANT USAGE ON SCHEMA AIRBNB.RAW TO ROLE DBT_ROLE;
GRANT SELECT ON TABLE AIRBNB.RAW.RAW_LISTINGS TO ROLE DBT_ROLE;
GRANT SELECT ON TABLE AIRBNB.RAW.RAW_CALENDAR TO ROLE DBT_ROLE;
GRANT SELECT ON TABLE AIRBNB.RAW.RAW_REVIEWS TO ROLE DBT_ROLE;
GRANT SELECT ON TABLE AIRBNB.RAW.INGESTION_LOG TO ROLE DBT_ROLE;

-- DBT_ROLE creates and owns the generated schemas and objects.
-- Run the following statements in a DBT_ROLE session, AFTER the grants above:
-- USE ROLE DBT_ROLE;
-- CREATE SCHEMA IF NOT EXISTS AIRBNB.DBT_GGILLET_STAGING;
-- CREATE SCHEMA IF NOT EXISTS AIRBNB.DBT_GGILLET_INTERMEDIATE;
-- CREATE SCHEMA IF NOT EXISTS AIRBNB.DBT_GGILLET_MARTS;
-- The dbt target schema must match DBT_SNOWFLAKE_SCHEMA=DBT_GGILLET
-- if dbt's configured schema naming appends _STAGING/_INTERMEDIATE/_MARTS.
-- Verify the project's generate_schema_name behavior before running dbt build.

SHOW GRANTS TO ROLE DBT_ROLE;
