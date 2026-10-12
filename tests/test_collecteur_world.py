"""Tests hors réseau du collecteur Inside Airbnb."""
import gzip
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "download_inside_airbnb.py"
spec = importlib.util.spec_from_file_location("download_inside_airbnb", SCRIPT)
import sys
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TestCollecteur(unittest.TestCase):
    def test_inventaire_trois_archives(self):
        catalog = [{"country": "France", "region": "", "city": "Lyon",
                    "link": "lyon", "publishDate": "2026-09-17",
                    "dataRoot": "https://example.org"}]
        files = module.build_inventory(catalog)
        self.assertEqual(len(files), 3)
        self.assertEqual({f.filename for f in files}, set(module.SOURCE_FILES))

    def test_archive_locale_non_referencee(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = module.Dataset("France", "", "Lyon", "lyon",
                                     "2026-09-17", "https://example.org",
                                     "listings.csv.gz")
            with patch.object(module, "RAW_ROOT", root / "data" / "raw"), \
                 patch.object(module, "PROJECT_ROOT", root), \
                 patch.object(module, "MANIFEST_PATH", root / "data_manifest.csv"):
                path = dataset.local_path
                path.parent.mkdir(parents=True)
                with gzip.open(path, "wb") as stream:
                    stream.write(b"test")
                manifest = {}
                self.assertEqual(module.inspect_status(dataset, manifest, True), "UNTRACKED")
                module.validate_gzip(path)
                module.update_manifest(dataset, manifest)
                module.write_manifest(manifest)
                self.assertEqual(module.inspect_status(dataset, manifest, True), "VERIFIED")
                self.assertEqual(len(module.load_manifest()), 1)

    def test_manifeste_protege_contre_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = module.Dataset("France", "", "Lyon", "lyon",
                                     "2026-09-17", "https://example.org",
                                     "listings.csv.gz")
            with patch.object(module, "RAW_ROOT", root / "data" / "raw"), \
                 patch.object(module, "PROJECT_ROOT", root):
                path = dataset.local_path
                path.parent.mkdir(parents=True)
                with gzip.open(path, "wb") as stream:
                    stream.write(b"test")
                manifest = {dataset.manifest_path: {
                    "path": dataset.manifest_path, "size": "1", "sha256": "0" * 64}}
                with self.assertRaises(RuntimeError):
                    module.update_manifest(dataset, manifest)


if __name__ == "__main__":
    unittest.main()
