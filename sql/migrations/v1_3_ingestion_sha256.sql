-- V1.3 migration — execute once, manually, before running the updated RAW loader.
-- Existing rows retain NULL SOURCE_SHA256: the historical source hash is unknown.
-- Do NOT populate hashes from the current local manifest without verifying RAW contents.
ALTER TABLE AIRBNB.RAW.INGESTION_LOG
ADD COLUMN IF NOT EXISTS SOURCE_SHA256 VARCHAR(64);

-- Read-only validation:
-- SELECT COUNT(*) AS total_rows,
--        COUNT_IF(SOURCE_SHA256 IS NULL) AS legacy_rows,
--        COUNT_IF(SOURCE_SHA256 IS NOT NULL) AS hashed_rows
-- FROM AIRBNB.RAW.INGESTION_LOG;
