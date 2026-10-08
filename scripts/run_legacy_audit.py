"""Resumable, bounded, read-only legacy RAW audit orchestrator.

Run from repository root:
  python scripts/run_legacy_audit.py --files listings --batch-size 5 --max-batches 1
Resume with exactly the same arguments. Snowflake access is SELECT-only.
"""
import argparse
import csv
import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from load_raw_to_snowflake import PROJECT_ROOT, MANIFEST_PATH, FILE_TO_TABLE


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def exclusive_lock(state_path):
    """Exclusive lock held for the whole campaign; stale locks require manual review."""
    lock = state_path.with_name(state_path.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(
            f"Audit déjà en cours ou verrou abandonné : {lock}. "
            "Vérifier qu'aucun processus n'est actif avant de retirer manuellement le verrou."
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()} started_utc={datetime.now(timezone.utc).isoformat()}\\n")
        yield
    finally:
        lock.unlink(missing_ok=True)


def manifest_digest():
    digest = hashlib.sha256()
    with MANIFEST_PATH.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_paths(args):
    with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"path", "size", "sha256"}.issubset(reader.fieldnames):
            raise RuntimeError("Manifest invalide")
        paths = []
        seen = set()
        for row in reader:
            path = Path(row["path"]).as_posix()
            if path in seen:
                raise RuntimeError(f"Doublon manifeste : {path}")
            seen.add(path)
            parts = Path(path).parts
            if len(parts) != 6 or parts[:2] != ("data", "raw"):
                continue
            _, _, country, city, snapshot, filename = parts
            if filename not in FILE_TO_TABLE:
                continue
            if args.country and country.lower() != args.country.lower():
                continue
            if args.location and city.lower() != args.location.lower():
                continue
            if args.snapshot and snapshot != args.snapshot:
                continue
            if args.files and filename not in {name + ".csv.gz" for name in args.files}:
                continue
            paths.append(path)
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description="Audit RAW progressif, reprenable, sans écriture Snowflake")
    parser.add_argument("--files", nargs="+", choices=("listings", "reviews", "calendar"))
    parser.add_argument("--country")
    parser.add_argument("--location")
    parser.add_argument("--snapshot")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--state", type=Path, default=PROJECT_ROOT / "target" / "legacy_audit_state.json")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 50:
        parser.error("--batch-size doit être compris entre 1 et 50")
    if not 1 <= args.max_batches <= 100:
        parser.error("--max-batches doit être compris entre 1 et 100")

    selection = {name: getattr(args, name) for name in ("files", "country", "location", "snapshot")}
    identity = {"manifest_sha256": manifest_digest(), "selection": selection,
                "batch_size": args.batch_size}
    paths = selected_paths(args)
    with exclusive_lock(args.state):
        return run_campaign(args, identity, paths)


def run_campaign(args, identity, paths):
    if args.state.exists():
        state = json.loads(args.state.read_text(encoding="utf-8"))
        if state.get("identity") != identity:
            raise RuntimeError("État incompatible (manifest, sélection ou taille de lot modifiés). "
                               "Utiliser un autre --state ; ne pas effacer le checkpoint.")
        results = state["results"]
        if len(results) > len(paths) or any(
            result["path"] != paths[i] for i, result in enumerate(results)
        ):
            raise RuntimeError("État incohérent avec l'ordre du manifeste.")
        print(f"Reprise : {len(results)}/{len(paths)} lots déjà certifiés")
    else:
        state = {"identity": identity, "results": []}
        results = state["results"]
        print(f"Nouvelle campagne : {len(paths)} lots sélectionnés")
    if any(r["status"] != "MATCH" for r in results):
        raise RuntimeError("Checkpoint avec anomalie ; investigation nécessaire avant reprise.")

    script = Path(__file__).with_name("audit_legacy_raw.py")
    for _ in range(args.max_batches):
        offset = len(results)
        if offset >= len(paths):
            break
        count = min(args.batch_size, len(paths) - offset)
        batch_report = args.state.with_name(args.state.stem + "_current_batch.json")
        # A prior interrupted process may have left a complete-looking stale report.
        # Never accept it as evidence of the current subprocess.
        batch_report.unlink(missing_ok=True)
        command = [sys.executable, str(script), "--all", "--limit", str(count),
                   "--output", str(batch_report)]
        for name in ("country", "location", "snapshot"):
            value = getattr(args, name)
            if value:
                command.extend(["--" + name, value])
        if args.files:
            command.extend(["--files", *args.files])
        if offset:
            command.extend(["--start-after", paths[offset - 1]])
        print(f"Audit lot {offset + 1} à {offset + count}/{len(paths)}", flush=True)
        started_ns = time.time_ns()
        process = subprocess.run(command, check=False)
        if not batch_report.exists():
            raise RuntimeError("Rapport de lot absent ; aucun avancement enregistré.")
        if batch_report.stat().st_mtime_ns < started_ns - 2_000_000_000:
            raise RuntimeError("Rapport de lot trop ancien ; checkpoint inchangé.")
        batch = json.loads(batch_report.read_text(encoding="utf-8"))
        batch_results = batch.get("results", [])
        expected = paths[offset:offset + count]
        if batch.get("method") != "canonical_json_multiset_sha256_v1":
            raise RuntimeError("Méthode d'audit inconnue ; checkpoint inchangé.")
        if [r.get("path") for r in batch_results] != expected:
            raise RuntimeError("Résultats de lot inattendus ; checkpoint inchangé.")
        # Do not advance on a failed or interrupted subprocess.
        if process.returncode != 0 or any(r.get("status") != "MATCH" for r in batch_results):
            failure_report = args.state.with_name(args.state.stem + "_failure.json")
            atomic_json(failure_report, {"results": batch_results, "returncode": process.returncode})
            raise RuntimeError(f"Audit non conforme ; checkpoint inchangé. Détails : {failure_report}")
        results.extend(batch_results)
        state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        atomic_json(args.state, state)
        batch_report.unlink(missing_ok=True)

    summary = {status: sum(r["status"] == status for r in results)
               for status in ("MATCH", "MISMATCH", "UNVERIFIABLE")}
    print(f"BILAN GLOBAL : {summary} ; progression {len(results)}/{len(paths)}")
    print(f"Checkpoint / rapport consolidé : {args.state}")
    print("Campagne terminée." if len(results) == len(paths) else
          "Campagne partielle ; relancer la même commande pour reprendre.")
    return 0 if len(results) == len(paths) else 0


if __name__ == "__main__":
    raise SystemExit(main())
