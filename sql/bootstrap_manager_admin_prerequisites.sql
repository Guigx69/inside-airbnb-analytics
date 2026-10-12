-- Prérequis administrateur — compte Snowflake cible VIERGE uniquement.
-- À exécuter avec un rôle autorisé à créer des rôles et warehouses.
-- Ne crée aucun utilisateur et n'attribue aucun rôle à un utilisateur.
-- Ne modifie pas les données RAW. Les noms doivent être approuvés avant exécution.
-- Un CREATE IF NOT EXISTS ne modifie pas la configuration d'un warehouse existant.

CREATE ROLE IF NOT EXISTS INGESTION_ROLE
  COMMENT = 'Chargement contrôlé des archives Inside Airbnb dans RAW';
CREATE ROLE IF NOT EXISTS DBT_ROLE
  COMMENT = 'Transformation dbt des données Inside Airbnb';

-- Dimensionnement prudent de départ ; vérifier les coûts et la politique du compte.
-- Suspendre après 60 secondes d'inactivité ; ne pas reprendre automatiquement.
CREATE WAREHOUSE IF NOT EXISTS DBT_WH
  WAREHOUSE_SIZE = 'XSMALL'
  WAREHOUSE_TYPE = 'STANDARD'
  AUTO_SUSPEND = 60
  AUTO_RESUME = FALSE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Warehouse pilote Inside Airbnb ; activation manuelle et budget à valider';

SHOW WAREHOUSES LIKE 'DBT_WH';
SHOW ROLES LIKE 'INGESTION_ROLE';
SHOW ROLES LIKE 'DBT_ROLE';

-- À traiter par l'administrateur selon l'identité du compte cible :
-- GRANT ROLE INGESTION_ROLE TO USER <UTILISATEUR_INGESTION>;
-- GRANT ROLE DBT_ROLE TO USER <UTILISATEUR_DBT>;
--
-- L'usage de DBT_WH requiert une reprise manuelle du warehouse si AUTO_RESUME=FALSE.
-- Ne pas exécuter de chargement ou dbt build sans contrôle des crédits disponibles.
-- Puis exécuter dans cet ordre :
-- 1. sql/bootstrap_manager_empty_raw.sql
-- 2. sql/bootstrap_manager_ingestion_grants.sql
-- 3. sql/bootstrap_manager_dbt_grants.sql
