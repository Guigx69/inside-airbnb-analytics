"""Orchestration sécurisée de la collecte, des contrôles, du chargement RAW et de dbt.

Par défaut, prévisualisation sans écriture. --execute autorise les écritures RAW ;
--sync ajoute le téléchargement et --dbt-build lance dbt sur demande.
Aucune réinitialisation destructive automatique.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands(selection_file: str, execute: bool, sync: bool, dbt_build: bool,
             python_executable: str = sys.executable) -> list[tuple[str, list[str]]]:
    collector = [python_executable, str(ROOT / "scripts" / "download_inside_airbnb.py"),
                 "--selection-file", selection_file]
    if execute and sync:
        collector += ["--sync", "--verify"]
    else:
        collector += ["--dry-run", "--verify"]

    steps = [("collector", collector)]
    steps.append(("archives", [python_executable, str(ROOT / "scripts" / "check_archives.py"),
                               "--selection-file", selection_file, "--hash"]))
    raw = [python_executable, str(ROOT / "scripts" / "load_raw_to_snowflake.py"),
           "--selection-file", selection_file]
    if not execute:
        raw.append("--dry-run")
    steps.append(("raw", raw))
    if execute and dbt_build:
        dbt_exe = ROOT / ".venv" / "Scripts" / "dbt.exe"
        dbt_command = str(dbt_exe) if dbt_exe.is_file() else "dbt"
        steps.append(("dbt", [dbt_command, "build", "--project-dir", str(ROOT)]))
    return steps


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-file", default=None)
    parser.add_argument("--execute", action="store_true", help="Autoriser les écritures dans RAW")
    parser.add_argument("--sync", action="store_true", help="Télécharger les archives manquantes (nécessite --execute)")
    parser.add_argument("--dbt-build", action="store_true", help="Lancer dbt build (nécessite --execute)")
    args = parser.parse_args(argv)
    if (args.sync or args.dbt_build) and not args.execute:
        parser.error("--sync et --dbt-build nécessitent --execute")
    if not args.selection_file:
        parser.error("Préciser --selection-file ; consulter docs/GUIDE_GEOGRAPHIE_A_Z.md")
    selection = Path(args.selection_file)
    if not selection.is_absolute():
        selection = ROOT / selection
    if not selection.is_file():
        parser.error(f"Fichier de sélection introuvable : {selection}")
    args.selection_file = str(selection)
    return args


def main(argv=None, runner=subprocess.run):
    args = parse_args(argv)
    steps = commands(args.selection_file, args.execute, args.sync, args.dbt_build)
    print("Mode :", "EXÉCUTION" if args.execute else "PRÉVISUALISATION (sans écriture)", flush=True)
    print("Synchronisation :", args.sync, "dbt build :", args.dbt_build, flush=True)
    for index, (name, cmd) in enumerate(steps, 1):
        print(f"[{index}/{len(steps)}] {name}: {' '.join(cmd)}", flush=True)
        result = runner(cmd, cwd=ROOT, check=False)
        if result.returncode:
            print(f"[ÉCHEC] {name} : code {result.returncode} ; arrêt du pipeline", file=sys.stderr)
            return result.returncode
    print("[OK] Toutes les étapes demandées sont terminées", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
