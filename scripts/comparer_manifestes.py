"""Comparer sans modifier le manifeste local à une révision Git connue.

Exemple : python scripts/comparer_manifestes.py --reference origin/main
La commande est en lecture seule et n'accède ni à Snowflake ni au réseau.
"""
from __future__ import annotations

import argparse
import csv
import io
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data_manifest.csv"
COLS = ("path", "size", "sha256")


def parse_manifest(content: str, source: str) -> dict[str, tuple[str, str]]:
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None or not set(COLS).issubset(reader.fieldnames):
        raise ValueError(f"Colonnes invalides dans {source} ; attendu : {', '.join(COLS)}")
    result = {}
    for row in reader:
        path = row["path"].strip()
        if not path or path in result:
            raise ValueError(f"Chemin vide ou doublon dans {source} : {path!r}")
        result[path] = (row["size"].strip(), row["sha256"].strip().lower())
    return result


def compare(reference: dict, local: dict) -> tuple[list, list, list]:
    added = sorted(local.keys() - reference.keys())
    removed = sorted(reference.keys() - local.keys())
    changed = sorted(p for p in local.keys() & reference.keys() if local[p] != reference[p])
    return added, removed, changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default="origin/main", help="Révision Git locale existante, défaut origin/main")
    args = parser.parse_args(argv)
    try:
        completed = subprocess.run(
            ["git", "show", f"{args.reference}:data_manifest.csv"],
            cwd=ROOT, capture_output=True, check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        parser.error(f"Révision {args.reference!r} introuvable. Exécuter 'git fetch origin' puis réessayer : {exc}")
    reference = parse_manifest(completed.stdout.decode("utf-8-sig"), args.reference)
    local = parse_manifest(MANIFEST.read_text(encoding="utf-8-sig"), str(MANIFEST))
    added, removed, changed = compare(reference, local)
    print(f"Référence {args.reference} : {len(reference)} entrées ; local : {len(local)} entrées")
    print(f"Ajoutées localement : {len(added)} ; absentes localement : {len(removed)} ; modifiées : {len(changed)}")
    for title, entries in (("AJOUT", added), ("ABSENT", removed), ("MODIFIÉ", changed)):
        for path in entries:
            print(f"[{title}] {path}")
    print("Lecture seule : aucun fichier modifié.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
