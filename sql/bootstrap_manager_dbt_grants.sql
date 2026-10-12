-- Préparation administrateur pour dbt sur un compte Snowflake NEUF.
-- Nécessite DBT_ROLE, DBT_WH, la base AIRBNB et les tables RAW préexistants.
-- Vérifier le préfixe des schémas et utiliser un rôle autorisé à attribuer les privilèges.
-- Aucun DROP, REVOKE, transfert de propriété ni modification des données existantes.

GRANT USAGE ON WAREHOUSE DBT_WH TO ROLE DBT_ROLE;
GRANT USAGE, CREATE SCHEMA ON DATABASE AIRBNB TO ROLE DBT_ROLE;
GRANT USAGE ON SCHEMA AIRBNB.RAW TO ROLE DBT_ROLE;
GRANT SELECT ON TABLE AIRBNB.RAW.RAW_LISTINGS TO ROLE DBT_ROLE;
GRANT SELECT ON TABLE AIRBNB.RAW.RAW_CALENDAR TO ROLE DBT_ROLE;
GRANT SELECT ON TABLE AIRBNB.RAW.RAW_REVIEWS TO ROLE DBT_ROLE;
GRANT SELECT ON TABLE AIRBNB.RAW.INGESTION_LOG TO ROLE DBT_ROLE;

-- DBT_ROLE crée et possède les schémas et objets générés.
-- Exécuter les instructions suivantes avec DBT_ROLE, APRÈS les autorisations ci-dessus :
-- USE ROLE DBT_ROLE;
-- CREATE SCHEMA IF NOT EXISTS AIRBNB.DBT_XXX_STAGING;
-- CREATE SCHEMA IF NOT EXISTS AIRBNB.DBT_XXX_INTERMEDIATE;
-- CREATE SCHEMA IF NOT EXISTS AIRBNB.DBT_XXX_MARTS;
-- DBT_XXX est un paramètre fictif : remplacer XXX par l'identifiant du responsable ou de l'environnement.
-- Le schéma cible dbt doit correspondre à DBT_SNOWFLAKE_SCHEMA=DBT_XXX
-- si la convention de nommage dbt ajoute _STAGING/_INTERMEDIATE/_MARTS.
-- Vérifier le comportement de generate_schema_name avant d'exécuter dbt build.

SHOW GRANTS TO ROLE DBT_ROLE;
