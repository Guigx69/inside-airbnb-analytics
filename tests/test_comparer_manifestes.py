"""Tests de comparaison de manifestes : aucun accès Git, réseau ou Snowflake."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from comparer_manifestes import compare, parse_manifest


class ComparaisonManifestesTests(unittest.TestCase):
    def test_diff_ajout_suppression_et_modification(self):
        old = {"a": ("1", "aaa"), "b": ("2", "bbb"), "c": ("3", "ccc")}
        new = {"a": ("1", "aaa"), "b": ("4", "bbb"), "d": ("5", "ddd")}
        self.assertEqual(compare(old, new), (["d"], ["c"], ["b"]))

    def test_normalisation_et_colonnes(self):
        rows = "path,size,sha256\na,1,ABC\n"
        self.assertEqual(parse_manifest(rows, "test"), {"a": ("1", "abc")})

    def test_doublons_rejetes(self):
        with self.assertRaisesRegex(ValueError, "doublon"):
            parse_manifest("path,size,sha256\na,1,x\na,2,y\n", "test")


if __name__ == "__main__":
    unittest.main()
