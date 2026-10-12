"""Comparer les chemins du catalogue Inside Airbnb sélectionnés à ceux du manifeste local.

Lecture seule : récupère les métadonnées du catalogue, sans téléchargement d'archives ni connexion Snowflake.
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from download_inside_airbnb import build_inventory, get_catalog
from geography_selection import select_datasets, select_manifest_paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-file", required=True)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit doit être supérieur ou égal à 0")

    live = select_datasets(build_inventory(get_catalog()), args.selection_file)
    live_paths = {item.manifest_path for item in live}
    manifest_path = ROOT / "data_manifest.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    manifest_paths = select_manifest_paths(rows, args.selection_file)

    only_live = sorted(live_paths - manifest_paths)
    only_manifest = sorted(manifest_paths - live_paths)
    print(f"Catalogue en ligne :        {len(live_paths)} unique paths ({len(live)} records)")
    print(f"Manifeste sélectionné :   {len(manifest_paths)} unique paths")
    print(f"Chemins communs :        {len(live_paths & manifest_paths)}")
    print(f"Uniquement en ligne :        {len(only_live)}")
    print(f"Uniquement dans le manifeste :    {len(only_manifest)}")
    for title, paths in (("EN LIGNE UNIQUEMENT", only_live), ("MANIFESTE UNIQUEMENT", only_manifest)):
        print(f"\\n{title} (first {args.limit}):")
        for path in paths[:args.limit]:
            print("  " + path)
    print("\\n[LECTURE SEULE] Aucune archive téléchargée ; manifeste et Snowflake inchangés.")


if __name__ == "__main__":
    main()
