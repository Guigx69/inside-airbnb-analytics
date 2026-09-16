from pathlib import Path
import csv
import gzip


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "france"
    / "lyon"
    / "2025-09-18"
)

FILES = [
    "listings.csv.gz",
    "calendar.csv.gz",
    "reviews.csv.gz",
]


def profile_csv_gz(file_path: Path) -> None:
    print("\n" + "=" * 100)
    print(f"FILE : {file_path.name}")
    print("=" * 100)

    compressed_size_mb = file_path.stat().st_size / (1024 * 1024)

    with gzip.open(file_path, mode="rt", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)

        try:
            header = next(reader)
        except StopIteration:
            print("Fichier vide.")
            return

        row_count = 0
        invalid_column_count = 0
        null_counts = [0] * len(header)
        sample_rows = []

        for row in reader:
            row_count += 1

            if len(row) != len(header):
                invalid_column_count += 1
                continue

            for i, value in enumerate(row):
                if value is None or value.strip() == "":
                    null_counts[i] += 1

            if len(sample_rows) < 3:
                sample_rows.append(row)

    print(f"Taille compressee : {compressed_size_mb:,.2f} MB")
    print(f"Nombre de lignes  : {row_count:,}")
    print(f"Nombre de colonnes: {len(header)}")
    print(f"Lignes invalides  : {invalid_column_count:,}")

    print("\nCOLONNES")
    print("-" * 100)

    for i, column in enumerate(header, start=1):
        null_count = null_counts[i - 1]

        null_pct = (
            (null_count / row_count) * 100
            if row_count > 0
            else 0
        )

        print(
            f"{i:>3}. "
            f"{column:<40} "
            f"NULL/VIDE={null_count:>10,} "
            f"({null_pct:>6.2f}%)"
        )

    print("\nAPERÇU DES 3 PREMIERES LIGNES")
    print("-" * 100)

    for row_number, row in enumerate(sample_rows, start=1):
        print(f"\nLigne {row_number}")

        for column, value in zip(header, row):
            display_value = value.replace("\n", " ").replace("\r", " ")

            if len(display_value) > 100:
                display_value = display_value[:97] + "..."

            print(f"  {column}: {display_value}")


def main() -> None:
    print(f"Snapshot analyse : {SNAPSHOT_PATH}")

    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(
            f"Le dossier du snapshot n'existe pas : {SNAPSHOT_PATH}"
        )

    for filename in FILES:
        file_path = SNAPSHOT_PATH / filename

        if not file_path.exists():
            print(f"\n[ERREUR] Fichier introuvable : {file_path}")
            continue

        profile_csv_gz(file_path)


if __name__ == "__main__":
    main()