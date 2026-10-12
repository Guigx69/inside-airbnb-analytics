-- Initialisation RAW Inside Airbnb pour un environnement Snowflake NEUF et dédié.
-- VÉRIFIER les identifiants et privilèges avant exécution : ce script exécute du DDL.
-- Exécuter avec un rôle autorisé à créer des schémas, tables et stages.
-- Ce script ne crée volontairement aucun rôle, entrepôt ni base de données.
-- Ne pas exécuter sur le projet existant sans examiner chaque instruction.
USE DATABASE AIRBNB;
CREATE SCHEMA IF NOT EXISTS RAW;
USE SCHEMA RAW;

CREATE TABLE IF NOT EXISTS RAW_LISTINGS (
  SOURCE_COUNTRY VARCHAR NOT NULL,
  SOURCE_CITY VARCHAR NOT NULL,
  SNAPSHOT_DATE DATE NOT NULL,
  SOURCE_FILE VARCHAR NOT NULL,
  LOADED_AT TIMESTAMP_LTZ NOT NULL,
  RAW_DATA VARIANT
);
CREATE TABLE IF NOT EXISTS RAW_CALENDAR (
  SOURCE_COUNTRY VARCHAR NOT NULL,
  SOURCE_CITY VARCHAR NOT NULL,
  SNAPSHOT_DATE DATE NOT NULL,
  SOURCE_FILE VARCHAR NOT NULL,
  LOADED_AT TIMESTAMP_LTZ NOT NULL,
  RAW_DATA VARIANT
);
CREATE TABLE IF NOT EXISTS RAW_REVIEWS (
  SOURCE_COUNTRY VARCHAR NOT NULL,
  SOURCE_CITY VARCHAR NOT NULL,
  SNAPSHOT_DATE DATE NOT NULL,
  SOURCE_FILE VARCHAR NOT NULL,
  LOADED_AT TIMESTAMP_LTZ NOT NULL,
  RAW_DATA VARIANT
);
CREATE TABLE IF NOT EXISTS INGESTION_LOG (
  SOURCE_COUNTRY VARCHAR NOT NULL,
  SOURCE_CITY VARCHAR NOT NULL,
  SNAPSHOT_DATE DATE NOT NULL,
  SOURCE_FILE VARCHAR NOT NULL,
  TARGET_TABLE VARCHAR NOT NULL,
  ROW_COUNT NUMBER(38,0) NOT NULL,
  LOADED_AT TIMESTAMP_LTZ NOT NULL
);
CREATE STAGE IF NOT EXISTS INSIDE_AIRBNB_STAGE;

-- Après préparation, autoriser INGESTION_ROLE à accéder au schéma,
-- aux tables et au stage (dont READ/WRITE sur le stage interne) selon
-- la politique de privilèges approuvée par l'organisation. Attribuer à DBT_ROLE
-- SELECT sur les trois tables RAW et USAGE sur la base et le schéma.
-- Snowflake CREATE ... IF NOT EXISTS ne vérifie pas la structure des objets existants.
-- Contrôler DESCRIBE TABLE / DESCRIBE STAGE avant ingestion.
