-- V1.3 isolated Snowflake transaction proof.
-- Run in a Snowflake worksheet using a role allowed to create TEMP tables.
-- No references to AIRBNB.RAW; no production data modifications.
-- Execute the whole script in order, in a single session.
-- Expected: all SELECT assertions return PASS.

CREATE OR REPLACE TEMPORARY TABLE V13_TX_RAW_TEST (
    SOURCE_COUNTRY VARCHAR, SOURCE_CITY VARCHAR, SNAPSHOT_DATE DATE,
    SOURCE_FILE VARCHAR, RAW_DATA VARIANT
);
CREATE OR REPLACE TEMPORARY TABLE V13_TX_LOG_TEST (
    SOURCE_COUNTRY VARCHAR, SOURCE_CITY VARCHAR, SNAPSHOT_DATE DATE,
    SOURCE_FILE VARCHAR, TARGET_TABLE VARCHAR, ROW_COUNT NUMBER,
    SOURCE_SHA256 VARCHAR(64)
);
CREATE OR REPLACE TEMPORARY TABLE V13_TX_PREP_TEST LIKE V13_TX_RAW_TEST;

INSERT INTO V13_TX_RAW_TEST
SELECT 'united-states','pacific-grove',TO_DATE('2026-03-31'),'listings.csv.gz',
       PARSE_JSON('{"id":"old-1"}');
INSERT INTO V13_TX_LOG_TEST
VALUES ('united-states','pacific-grove',TO_DATE('2026-03-31'),'listings.csv.gz',
        'RAW_LISTINGS',1,REPEAT('a',64));
INSERT INTO V13_TX_PREP_TEST
SELECT 'united-states','pacific-grove',TO_DATE('2026-03-31'),'listings.csv.gz',
       PARSE_JSON('{"id":"new-1"}')
UNION ALL
SELECT 'united-states','pacific-grove',TO_DATE('2026-03-31'),'listings.csv.gz',
       PARSE_JSON('{"id":"new-2"}');

-- Baseline: old row and old journal.
SELECT 'baseline' AS CHECK_NAME,
       IFF((SELECT COUNT(*) FROM V13_TX_RAW_TEST)=1
         AND (SELECT COUNT(*) FROM V13_TX_LOG_TEST WHERE ROW_COUNT=1 AND SOURCE_SHA256=REPEAT('a',64))=1,
           'PASS','FAIL') AS RESULT;

-- Failure scenario: DML inside explicit transaction, followed by rollback.
BEGIN TRANSACTION;
DELETE FROM V13_TX_RAW_TEST WHERE SOURCE_COUNTRY='united-states'
 AND SOURCE_CITY='pacific-grove' AND SNAPSHOT_DATE=TO_DATE('2026-03-31')
 AND SOURCE_FILE='listings.csv.gz';
INSERT INTO V13_TX_RAW_TEST SELECT * FROM V13_TX_PREP_TEST;
UPDATE V13_TX_LOG_TEST SET ROW_COUNT=2,SOURCE_SHA256=REPEAT('b',64)
 WHERE SOURCE_COUNTRY='united-states' AND SOURCE_CITY='pacific-grove'
 AND SNAPSHOT_DATE=TO_DATE('2026-03-31') AND SOURCE_FILE='listings.csv.gz'
 AND TARGET_TABLE='RAW_LISTINGS';
-- Deliberately abort the replacement. No DDL/COPY between BEGIN and ROLLBACK.
ROLLBACK;

SELECT 'rollback_preserves_old_raw_and_log' AS CHECK_NAME,
       IFF((SELECT COUNT(*) FROM V13_TX_RAW_TEST)=1
         AND (SELECT COUNT(*) FROM V13_TX_RAW_TEST WHERE RAW_DATA:id::STRING='old-1')=1
         AND (SELECT COUNT(*) FROM V13_TX_LOG_TEST WHERE ROW_COUNT=1 AND SOURCE_SHA256=REPEAT('a',64))=1,
           'PASS','FAIL') AS RESULT;

-- Successful scenario: identical DML, then COMMIT.
BEGIN TRANSACTION;
DELETE FROM V13_TX_RAW_TEST WHERE SOURCE_COUNTRY='united-states'
 AND SOURCE_CITY='pacific-grove' AND SNAPSHOT_DATE=TO_DATE('2026-03-31')
 AND SOURCE_FILE='listings.csv.gz';
INSERT INTO V13_TX_RAW_TEST SELECT * FROM V13_TX_PREP_TEST;
UPDATE V13_TX_LOG_TEST SET ROW_COUNT=2,SOURCE_SHA256=REPEAT('b',64)
 WHERE SOURCE_COUNTRY='united-states' AND SOURCE_CITY='pacific-grove'
 AND SNAPSHOT_DATE=TO_DATE('2026-03-31') AND SOURCE_FILE='listings.csv.gz'
 AND TARGET_TABLE='RAW_LISTINGS';
COMMIT;

SELECT 'commit_replaces_raw_and_log' AS CHECK_NAME,
       IFF((SELECT COUNT(*) FROM V13_TX_RAW_TEST)=2
         AND (SELECT COUNT(*) FROM V13_TX_RAW_TEST WHERE RAW_DATA:id::STRING IN ('new-1','new-2'))=2
         AND (SELECT COUNT(*) FROM V13_TX_LOG_TEST WHERE ROW_COUNT=2 AND SOURCE_SHA256=REPEAT('b',64))=1,
           'PASS','FAIL') AS RESULT;

-- Temporary tables disappear at the end of the Snowflake session.
