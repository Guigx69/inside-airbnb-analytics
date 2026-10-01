from __future__ import annotations

import argparse
import csv
import hashlib
import gzip
import json
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import requests


BASE_URL = "https://insideairbnb.com"
PAGE_DATA_URL = f"{BASE_URL}/page-data/get-the-data/page-data.json"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"
MANIFEST_PATH = PROJECT_ROOT / "data_manifest.csv"

SOURCE_FILES = (
    "listings.csv.gz",
    "calendar.csv.gz",
    "reviews.csv.gz",
)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "inside-airbnb-analytics/1.0 "
            "(reproducible analytics project)"
        )
    }
)


@dataclass(frozen=True)
class Dataset:
    country: str
    region: str
    location: str
    location_slug: str
    snapshot_date: str
    data_root: str
    filename: str

    @property
    def url(self) -> str:
        return (
            f"{self.data_root.rstrip('/')}/"
            f"{self.snapshot_date}/data/{self.filename}"
        )

    @property
    def local_path(self) -> Path:
        return (
            RAW_ROOT
            / slugify(self.country)
            / self.location_slug
            / self.snapshot_date
            / self.filename
        )

    @property
    def manifest_path(self) -> str:
        return self.local_path.relative_to(PROJECT_ROOT).as_posix()

def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )
    value = value.lower().strip()
    value = "".join(
        character if character.isalnum() else "-"
        for character in value
    )

    while "--" in value:
        value = value.replace("--", "-")

    return value.strip("-")

def discover_catalog_url(session: requests.Session) -> str:
    """
    Discover dynamically the Gatsby static query containing
    the Inside Airbnb dataset catalog.

    Gatsby exposes the static query hashes required by the page
    through /page-data/get-the-data/page-data.json.
    """

    print("[INFO] Discovering Inside Airbnb catalog")

    try:
        response = session.get(
            PAGE_DATA_URL,
            timeout=30,
        )
        response.raise_for_status()
        page_data = response.json()

    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(
            "Unable to read Inside Airbnb Gatsby page-data."
        ) from exc

    query_hashes = page_data.get("staticQueryHashes", [])

    if not query_hashes:
        raise RuntimeError(
            "No Gatsby static query hashes found "
            "for the Inside Airbnb data page."
        )

    print(
        f"[INFO] Gatsby static queries discovered: "
        f"{len(query_hashes)}"
    )

    for query_hash in query_hashes:

        catalog_url = (
            f"{BASE_URL}/page-data/sq/d/"
            f"{query_hash}.json"
        )

        try:
            response = session.get(
                catalog_url,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()

        except (
            requests.RequestException,
            ValueError,
        ):
            continue

        datasets = (
            payload
            .get("data", {})
            .get("allData", {})
            .get("datasets")
        )

        if isinstance(datasets, list) and datasets:

            print("[INFO] Dataset catalog discovered")
            print(f"       {catalog_url}")
            print(
                f"[INFO] Catalog records: "
                f"{len(datasets)}"
            )

            return catalog_url

    raise RuntimeError(
        "None of the Gatsby static queries contains "
        "data.allData.datasets."
    )

def get_catalog() -> list[dict]:
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "inside-airbnb-analytics/1.0 "
                "(dataset synchronization)"
            )
        }
    )

    catalog_url = discover_catalog_url(session)

    print("[INFO] Reading Inside Airbnb catalog")
    print(f"       {catalog_url}")

    response = session.get(
        catalog_url,
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json()

    try:
        datasets = payload["data"]["allData"]["datasets"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "Unexpected Inside Airbnb catalog structure."
        ) from exc

    if not isinstance(datasets, list):
        raise RuntimeError(
            "Inside Airbnb catalog does not contain a dataset list."
        )

    if not datasets:
        raise RuntimeError(
            "Inside Airbnb catalog is empty."
        )

    return datasets

def build_inventory(catalog: list[dict]) -> list[Dataset]:
    inventory: list[Dataset] = []

    for record in catalog:
        country = record.get("country")
        region = record.get("region") or ""
        city = record.get("city")
        link = record.get("link")
        publish_date = record.get("publishDate")
        data_root = record.get("dataRoot")

        if not all(
            [
                country,
                city,
                link,
                publish_date,
                data_root,
            ]
        ):
            continue

        for filename in SOURCE_FILES:
            inventory.append(
                Dataset(
                    country=country,
                    region=region,
                    location=city,
                    location_slug=slugify(link),
                    snapshot_date=publish_date,
                    data_root=data_root,
                    filename=filename,
                )
            )

    return inventory

def filter_inventory(
    inventory: list[Dataset],
    location: str | None,
    country: str | None,
    all_locations: bool,
    snapshot: str | None = None,
    files: list[str] | None = None,
) -> list[Dataset]:

    if all_locations:
        selected = inventory
    else:
        selected = inventory

        if location:
            target = slugify(location)

            selected = [
                item
                for item in selected
                if (
                    slugify(item.location) == target
                    or item.location_slug == target
                )
            ]

        if country:
            target = slugify(country)

            selected = [
                item
                for item in selected
                if slugify(item.country) == target
            ]

    if snapshot:
        selected = [
            item
            for item in selected
            if item.snapshot_date == snapshot
        ]

    if files:
        wanted_files = {
            f"{file_type}.csv.gz"
            for file_type in files
        }

        selected = [
            item
            for item in selected
            if item.filename in wanted_files
        ]

    return selected

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()

def validate_gzip(path: Path) -> None:
    """
    Validate that the downloaded file is a readable gzip stream.

    Reading the complete stream also validates its CRC.
    """
    try:
        with gzip.open(path, "rb") as handle:
            while handle.read(1024 * 1024):
                pass
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise RuntimeError(
            f"Invalid gzip file: {path}"
        ) from exc

def load_manifest() -> dict[str, dict]:
    if not MANIFEST_PATH.exists():
        return {}

    entries: dict[str, dict] = {}

    with MANIFEST_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            entries[row["path"]] = row

    return entries


def write_manifest(entries: dict[str, dict]) -> None:
    with MANIFEST_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "size", "sha256"],
        )

        writer.writeheader()

        for path in sorted(entries):
            writer.writerow(entries[path])


def inspect_status(
    dataset: Dataset,
    manifest: dict[str, dict],
    verify: bool,
) -> str:

    path = dataset.local_path
    manifest_entry = manifest.get(dataset.manifest_path)

    if not path.exists():
        return "NEW"

    if not verify:
        return "LOCAL"

    if not manifest_entry:
        return "UNTRACKED"

    expected_size = int(manifest_entry["size"])

    if path.stat().st_size != expected_size:
        return "INVALID"

    actual_sha = sha256_file(path)

    if actual_sha.lower() != manifest_entry["sha256"].lower():
        return "INVALID"

    return "VERIFIED"


def download_file(
    dataset: Dataset,
    overwrite: bool,
) -> None:

    destination = dataset.local_path

    if destination.exists() and not overwrite:
        return

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = destination.with_suffix(
        destination.suffix + ".part"
    )

    print(f"[DOWNLOAD] {dataset.url}")

    try:
        with SESSION.get(
            dataset.url,
            stream=True,
            timeout=(30, 300),
        ) as response:

            response.raise_for_status()

            with temporary.open("wb") as handle:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        handle.write(chunk)

        if temporary.stat().st_size == 0:
            raise RuntimeError(
                f"Downloaded file is empty: {dataset.url}"
            )

        validate_gzip(temporary)

        temporary.replace(destination)

    except Exception:
        if temporary.exists():
            temporary.unlink()

        raise


def update_manifest(
    dataset: Dataset,
    manifest: dict[str, dict],
) -> None:

    path = dataset.local_path
    manifest_key = dataset.manifest_path

    size = path.stat().st_size
    sha256 = sha256_file(path)

    existing = manifest.get(manifest_key)

    if existing:
        existing_size = int(existing["size"])
        existing_sha256 = existing["sha256"].lower()

        if (
            existing_size != size
            or existing_sha256 != sha256.lower()
        ):
            raise RuntimeError(
                "Manifest integrity violation: "
                f"{manifest_key} already exists with a "
                "different size or SHA-256. "
                "The existing manifest entry was NOT modified."
            )

        return

    manifest[manifest_key] = {
        "path": manifest_key,
        "size": str(size),
        "sha256": sha256,
    }

def print_summary(
    datasets: list[Dataset],
    manifest: dict[str, dict],
    verify: bool,
) -> dict[str, int]:

    counts = {
        "NEW": 0,
        "LOCAL": 0,
        "VERIFIED": 0,
        "UNTRACKED": 0,
        "INVALID": 0,
    }

    current_snapshot = None

    print()
    print("=" * 100)
    print("INSIDE AIRBNB INVENTORY")
    print("=" * 100)

    for dataset in sorted(
        datasets,
        key=lambda item: (
            slugify(item.country),
            item.location_slug,
            item.snapshot_date,
            item.filename,
        ),
    ):
        snapshot = (
            dataset.country,
            dataset.location,
            dataset.snapshot_date,
        )

        if snapshot != current_snapshot:
            print()
            print(
                f"{dataset.country} / "
                f"{dataset.location} / "
                f"{dataset.snapshot_date}"
            )
            current_snapshot = snapshot

        status = inspect_status(
            dataset,
            manifest,
            verify,
        )

        counts[status] += 1

        print(
            f"  [{status:<9}] "
            f"{dataset.filename}"
        )

    locations = {
        (
            slugify(item.country),
            item.location_slug,
        )
        for item in datasets
    }

    snapshots = {
        (
            slugify(item.country),
            item.location_slug,
            item.snapshot_date,
        )
        for item in datasets
    }

    print()
    print("-" * 100)
    print(f"Locations : {len(locations)}")
    print(f"Snapshots : {len(snapshots)}")
    print(f"Files     : {len(datasets)}")

    for status, count in counts.items():
        if count:
            print(f"{status:<9} : {count}")

    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and synchronize Inside Airbnb datasets."
        )
    )

    scope = parser.add_mutually_exclusive_group(
        required=True
    )

    scope.add_argument(
        "--location",
        help="Location, for example: lyon",
    )

    scope.add_argument(
        "--country",
        help="Country, for example: france",
    )

    scope.add_argument(
        "--all",
        action="store_true",
        help="All locations in the Inside Airbnb catalog",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not download anything",
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify local files against data_manifest.csv",
    )

    parser.add_argument(
        "--sync",
        action="store_true",
        help="Download missing datasets and update manifest",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing local files",
    )

    parser.add_argument(
        "--snapshot",
        help="Only one snapshot date, for example: 2026-06-22",
    )

    parser.add_argument(
        "--files",
        nargs="+",
        choices=["listings", "calendar", "reviews"],
        help=(
            "Only selected dataset types, for example: "
            "--files listings or --files listings reviews"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        catalog = get_catalog()
        inventory = build_inventory(catalog)

        selected = filter_inventory(
            inventory,
            location=args.location,
            country=args.country,
            all_locations=args.all,
            snapshot=args.snapshot,
            files=args.files,
        )

        if not selected:
            print("[ERROR] No matching datasets.")
            return 1

        manifest = load_manifest()

        print_summary(
            selected,
            manifest,
            args.verify,
        )

        if args.dry_run:
            print()
            print("[DRY-RUN] No file was downloaded.")
            return 0

        if not args.sync:
            return 0

        downloaded = 0

        for dataset in selected:
            status = inspect_status(
                dataset,
                manifest,
                args.verify,
            )

            should_download = (
                status == "NEW"
                or (
                    args.overwrite
                    and status in {
                        "LOCAL",
                        "INVALID",
                        "UNTRACKED",
                    }
                )
            )

            if should_download:
                download_file(
                    dataset,
                    overwrite=args.overwrite,
                )

                update_manifest(
                    dataset,
                    manifest,
                )

                downloaded += 1

        if downloaded:
            write_manifest(manifest)

        print()
        print("=" * 100)
        print("SYNCHRONIZATION COMPLETE")
        print("=" * 100)
        print(f"Downloaded : {downloaded}")

        print_summary(
            selected,
            manifest,
            verify=True,
        )

        return 0

    except requests.RequestException as exc:
        print(f"[ERROR] HTTP error: {exc}")
        return 1

    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())