"""Tests hors réseau des protections du chargeur Snowflake RAW."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "load_raw_to_snowflake.py"


def load_module():
    # Ne requiert pas snowflake-connector-python sur la CI.
    snowflake = types.ModuleType("snowflake")
    connector = types.ModuleType("snowflake.connector")
    snowflake.connector = connector
    with patch.dict(sys.modules, {"snowflake": snowflake, "snowflake.connector": connector}):
        spec = importlib.util.spec_from_file_location("loader_raw_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = []

    def execute(self, statement, parameters=None):
        self.sql.append((statement, parameters))

    def fetchall(self):
        return self.rows


class LoaderRawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = load_module()

    def item(self):
        return {
            "country": "france",
            "location": "lyon",
            "snapshot_date": "2026-10-01",
            "filename": "listings.csv.gz",
            "target_table": "RAW_LISTINGS",
            "relative_path": "data/raw/france/lyon/2026-10-01/listings.csv.gz",
            "sha256": "a" * 64,
        }

    def test_journal_lit_empreinte(self):
        item = self.item()
        key = self.loader.ingestion_key(item)
        cursor = FakeCursor([(*key[:4], key[4], 17, item["sha256"])])
        log = self.loader.get_ingestion_log(cursor)
        self.assertEqual(log[key], {"row_count": 17, "sha256": item["sha256"]})
        self.assertIn("SOURCE_SHA256", cursor.sql[0][0])

    def test_lot_charge_identique_est_ignore(self):
        item = self.item()
        key = self.loader.ingestion_key(item)
        log = {key: {"row_count": 17, "sha256": item["sha256"]}}
        with patch.object(self.loader, "get_raw_inventory", return_value={key: 17}):
            pending, skipped = self.loader.classify_files(None, [item], log)
        self.assertEqual(pending, [])
        self.assertEqual(skipped[0]["status"], "LOADED")

    def test_empreinte_divergente_bloque(self):
        item = self.item()
        key = self.loader.ingestion_key(item)
        log = {key: {"row_count": 17, "sha256": "b" * 64}}
        with patch.object(self.loader, "get_raw_inventory", return_value={key: 17}):
            with self.assertRaisesRegex(RuntimeError, "Empreinte source différente"):
                self.loader.classify_files(None, [item], log)

    def test_ancien_journal_sans_empreinte_reste_compatible(self):
        item = self.item()
        key = self.loader.ingestion_key(item)
        log = {key: {"row_count": 17, "sha256": None}}
        with patch.object(self.loader, "get_raw_inventory", return_value={key: 17}):
            pending, skipped = self.loader.classify_files(None, [item], log)
        self.assertEqual(len(skipped), 1)
        self.assertFalse(pending)

    def test_ecart_de_lignes_bloque(self):
        item = self.item()
        key = self.loader.ingestion_key(item)
        log = {key: {"row_count": 17, "sha256": item["sha256"]}}
        with patch.object(self.loader, "get_raw_inventory", return_value={key: 16}):
            with self.assertRaisesRegex(RuntimeError, "Incohérence RAW / INGESTION_LOG"):
                self.loader.classify_files(None, [item], log)

    def test_lot_raw_sans_journal_bloque(self):
        item = self.item()
        key = self.loader.ingestion_key(item)
        with patch.object(self.loader, "get_raw_inventory", return_value={key: 17}):
            with self.assertRaisesRegex(RuntimeError, "absents de INGESTION_LOG"):
                self.loader.classify_files(None, [item], {})

    def test_lot_nouveau_est_planifie(self):
        item = self.item()
        with patch.object(self.loader, "get_raw_inventory", return_value={}):
            pending, skipped = self.loader.classify_files(None, [item], {})
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["status"], "NEW")
        self.assertFalse(skipped)

    def test_journal_doublon_bloque(self):
        item = self.item()
        key = self.loader.ingestion_key(item)
        row = (*key[:4], key[4], 17, item["sha256"])
        with self.assertRaisesRegex(RuntimeError, "Doublon détecté"):
            self.loader.get_ingestion_log(FakeCursor([row, row]))


if __name__ == "__main__":
    unittest.main()
