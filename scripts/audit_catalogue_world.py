"""Audit du catalogue World, sans téléchargement ni accès Snowflake.

Code retour : 0 si le catalogue est couvert par le manifeste, 2 si de
nouvelles archives sont détectées, 1 en cas d'erreur de lecture.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from download_inside_airbnb import MANIFEST_PATH, build_inventory, get_catalog


def audit(catalogue, manifest_path: Path) -> dict:
    inventory = build_inventory(catalogue)
    if not inventory:
        raise ValueError("Le catalogue ne contient aucune archive exploitable.")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifeste introuvable : {manifest_path}")
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "path" not in reader.fieldnames:
            raise ValueError("Colonne 'path' absente du manifeste.")
        known = {row["path"] for row in reader}
    missing = [item for item in inventory if item.manifest_path not in known]
    groups = defaultdict(list)
    for item in missing:
        groups[(item.country, item.location, item.snapshot_date)].append(item.filename)
    return {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "zones": len({(item.country, item.location_slug) for item in inventory}),
        "snapshots": len({(item.country, item.location_slug, item.snapshot_date) for item in inventory}),
        "archives_catalogue": len(inventory),
        "archives_manifeste": len(known),
        "archives_nouvelles": len(missing),
        "nouveaux_snapshots": [
            {"pays": country, "ville": city, "date": date, "fichiers": sorted(files)}
            for (country, city, date), files in sorted(groups.items())
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rapport", type=Path, help="Fichier JSON local de sortie")
    args = parser.parse_args(argv)
    try:
        result = audit(get_catalog(), MANIFEST_PATH)
        output = json.dumps(result, ensure_ascii=False, indent=2)
        print(output)
        if args.rapport:
            args.rapport.parent.mkdir(parents=True, exist_ok=True)
            args.rapport.write_text(output + "\n", encoding="utf-8")
        return 2 if result["archives_nouvelles"] else 0
    except Exception as exc:
        print(f"[ERREUR] Audit du catalogue impossible : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
