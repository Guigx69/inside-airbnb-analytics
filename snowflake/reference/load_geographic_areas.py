from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

import snowflake.connector

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / ".geo_cache"

SNOWFLAKE_DATABASE = os.getenv(
    "SNOWFLAKE_DATABASE"
)

SNOWFLAKE_MARTS_SCHEMA = os.getenv(
    "SNOWFLAKE_MARTS_SCHEMA"
)

if not SNOWFLAKE_DATABASE:
    raise RuntimeError(
        "SNOWFLAKE_DATABASE est obligatoire."
    )

if not SNOWFLAKE_MARTS_SCHEMA:
    raise RuntimeError(
        "SNOWFLAKE_MARTS_SCHEMA est obligatoire."
    )


FCT_LISTING_SNAPSHOT = (
    f"{SNOWFLAKE_DATABASE}."
    f"{SNOWFLAKE_MARTS_SCHEMA}."
    "FCT_LISTING_SNAPSHOT"
)

REF_GEOGRAPHIC_AREAS = (
    f"{SNOWFLAKE_DATABASE}."
    f"{SNOWFLAKE_MARTS_SCHEMA}."
    "REF_GEOGRAPHIC_AREAS"
)

FRANCE_COMMUNES_URL = (
    "https://etalab-datasets.geo.data.gouv.fr/"
    "contours-administratifs/latest/geojson/"
    "communes-100m.geojson.gz"
)

PARIS_URL = (
    "https://opendata.paris.fr/api/explore/v2.1/catalog/"
    "datasets/arrondissements/exports/geojson"
)

BRUSSELS_URL = (
    "https://opendata.brussels.be/api/explore/v2.1/catalog/"
    "datasets/limites-administratives-des-communes-en-region-de-bruxelles-capitale/"
    "exports/geojson"
)

BORDEAUX_COMMUNES_URL = (
    "https://opendata.bordeaux-metropole.fr/api/explore/v2.1/catalog/"
    "datasets/fv_commu_s/exports/geojson"
)

BORDEAUX_QUARTIERS_URL = (
    "https://opendata.bordeaux-metropole.fr/api/explore/v2.1/catalog/"
    "datasets/se_quart_s/exports/geojson"
)


# ============================================================
# Normalisation
# ============================================================


def normalize(value: object) -> str:
    """Normalize a geographic label for deterministic matching."""

    if value is None:
        return ""

    text = str(value).strip().lower()

    text = text.replace("œ", "oe")
    text = text.replace("æ", "ae")
    text = text.replace("’", "'")

    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(text.split())

def repair_mojibake(value: object) -> str:
    """
    Repair common UTF-8 text accidentally decoded as latin-1/cp1252.

    Example:
        GuÃ©thary -> Guéthary
    """

    if value is None:
        return ""

    text = str(value)

    if not any(
        marker in text
        for marker in ("Ã", "Â", "â", "ð")
    ):
        return text

    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def geographic_key(value: object) -> str:
    """Canonical key used for geographic matching."""

    return normalize(
        repair_mojibake(value)
    )

def paris_name(value: object) -> str:
    """
    Paris Data may expose labels such as:
    '1er Arrondissement' / 'Louvre'.

    Inside Airbnb uses the arrondissement names:
    Louvre, Bourse, Temple...
    """

    return normalize(value)


# ============================================================
# Files / GeoJSON
# ============================================================


def download(
    url: str,
    filename: str,
) -> Path:

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    target = CACHE_DIR / filename

    if target.exists():
        print(f"[CACHE] {target.name}")
        return target

    print(f"[DOWNLOAD] {url}")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "inside-airbnb-analytics/1.0"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=120,
    ) as response:

        target.write_bytes(
            response.read()
        )

    print(
        f"[OK] {target.name} "
        f"({target.stat().st_size / 1024 / 1024:.1f} MB)"
    )

    return target


def load_geojson(path: Path) -> dict:

    if path.suffix == ".gz":

        with gzip.open(
            path,
            "rt",
            encoding="utf-8",
        ) as handle:

            return json.load(handle)

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(handle)


def load_source(
    url: str,
    filename: str,
) -> dict:

    return load_geojson(
        download(
            url,
            filename,
        )
    )


# ============================================================
# Snowflake
# ============================================================


def connect():

    required = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "DBT_SNOWFLAKE_PASSWORD",
    ]

    missing = [
        variable
        for variable in required
        if not os.getenv(variable)
    ]

    if missing:
        raise RuntimeError(
            "Variables d'environnement absentes : "
            + ", ".join(missing)
        )

    return snowflake.connector.connect(
        account=os.environ[
            "SNOWFLAKE_ACCOUNT"
        ],
        user=os.environ[
            "SNOWFLAKE_USER"
        ],
        password=os.environ[
            "DBT_SNOWFLAKE_PASSWORD"
        ],
        role=os.getenv(
            "SNOWFLAKE_ROLE",
            "DBT_ROLE",
        ),
        warehouse=os.getenv(
            "SNOWFLAKE_WAREHOUSE",
            "DBT_WH",
        ),
        database=os.getenv(
            "SNOWFLAKE_DATABASE",
            "AIRBNB",
        ),
    )


def load_neighbourhoods(connection):

    sql = f"""
        SELECT DISTINCT
            LOWER(SOURCE_COUNTRY),
            LOWER(SOURCE_CITY),
            NEIGHBOURHOOD
        FROM {FCT_LISTING_SNAPSHOT}
        WHERE NEIGHBOURHOOD IS NOT NULL
        ORDER BY 1, 2, 3
    """

    cursor = connection.cursor()

    try:

        cursor.execute(sql)

        return [
            {
                "source_country": row[0],
                "source_city": row[1],
                "neighbourhood": row[2],
            }
            for row in cursor.fetchall()
        ]

    finally:
        cursor.close()


# ============================================================
# Geographic records
# ============================================================


def record(
    country,
    city,
    area_code,
    area_name,
    area_level,
    geometry,
    source,
):

    return {
        "source_country": country,
        "source_city": city,
        "area_code": str(area_code),
        "area_name": str(area_name),
        "area_level": area_level,
        "geometry": geometry,
        "source": source,
    }


def build_paris(data):

    rows = []

    for feature in data["features"]:

        props = feature["properties"]

        rows.append(
            record(
                "france",
                "paris",
                props["c_arinsee"],
                props["l_aroff"],
                "arrondissement",
                feature["geometry"],
                "Paris Data",
            )
        )

    return rows


def build_brussels(data):

    rows = []

    for feature in data["features"]:

        props = feature["properties"]

        rows.append(
            record(
                "belgium",
                "brussels",
                props["national_code"],
                props["name_fr"],
                "municipality",
                feature["geometry"],
                "Brussels UrbIS",
            )
        )

    return rows


def build_france_communes(data):

    rows = []

    for feature in data["features"]:

        props = feature["properties"]

        rows.append(
            {
                "code": str(
                    props["code"]
                ),
                "department": str(
                    props["departement"]
                ),
                "name": str(
                    props["nom"]
                ),
                "normalized_name":
                    geographic_key(
                        props["nom"]
                    ),
                "geometry":
                    feature["geometry"],
            }
        )

    return rows


def build_bordeaux_communes(data):

    rows = []

    for feature in data["features"]:

        props = feature["properties"]

        rows.append(
            record(
                "france",
                "bordeaux",
                props["insee"],
                props["nom"],
                "municipality",
                feature["geometry"],
                "Bordeaux Métropole",
            )
        )

    return rows


def build_bordeaux_quarters(data):

    rows = []

    for feature in data["features"]:

        props = feature["properties"]

        row = record(
            "france",
            "bordeaux",
            f"Q-{props['gid']}",
            props["nom"],
            "neighbourhood",
            feature["geometry"],
            "Bordeaux Métropole",
        )

        row["insee"] = (
            str(props["insee"])
            if props.get("insee") is not None
            else None
        )

        row["quarpoli"] = (
            str(props["quarpoli"])
            if props.get("quarpoli") is not None
            else None
        )

        rows.append(row)

    return rows


# ============================================================
# Matching
# ============================================================


def index_by_name(rows):

    index = defaultdict(list)

    for row in rows:

        index[
            geographic_key(
                row["area_name"]
            )
        ].append(row)

    return index


def match_exact(
    neighbourhoods,
    geographic_rows,
):

    index = index_by_name(
        geographic_rows
    )

    matches = []
    missing = []
    ambiguous = []

    for neighbourhood in neighbourhoods:

        key = geographic_key(
            neighbourhood
        )

        candidates = index.get(
            key,
            [],
        )

        if len(candidates) == 1:

            matches.append(
                {
                    "neighbourhood":
                        neighbourhood,
                    "area":
                        candidates[0],
                }
            )

        elif len(candidates) > 1:

            ambiguous.append(
                {
                    "neighbourhood":
                        neighbourhood,
                    "candidates":
                        candidates,
                }
            )

        else:

            missing.append(
                neighbourhood
            )

    return (
        matches,
        missing,
        ambiguous,
    )


def build_pays_basque(
    neighbourhoods,
    france_communes,
):

    index = defaultdict(list)

    for commune in france_communes:

        index[
            commune[
                "normalized_name"
            ]
        ].append(
            commune
        )

    rows = []
    missing = []
    ambiguous = []

    for neighbourhood in neighbourhoods:

        key = geographic_key(
            neighbourhood
        )

        candidates = [
            candidate
            for candidate in index.get(key, [])
            if candidate["department"] == "64"
        ]

        if len(candidates) == 1:

            commune = candidates[0]

            rows.append(
                record(
                    "france",
                    "pays-basque",
                    commune["code"],
                    neighbourhood,
                    "municipality",
                    commune["geometry"],
                    "Contours administratifs France",
                )
            )

        elif len(candidates) > 1:

            ambiguous.append(
                (
                    neighbourhood,
                    [
                        candidate["code"]
                        for candidate
                        in candidates
                    ],
                )
            )

        else:

            missing.append(
                neighbourhood
            )

    return (
        rows,
        missing,
        ambiguous,
    )

BORDEAUX_ALIASES = {
    geographic_key("Ambars-et-Lagrave"):
        geographic_key("Ambarès-et-Lagrave"),

    geographic_key("Ambs"):
        geographic_key("Ambès"),

    geographic_key("Artigues-Prs-Bordeaux"):
        geographic_key("Artigues-près-Bordeaux"),

    geographic_key("Beaudsert"):
        geographic_key("Beaudésert"),

    geographic_key("Bgles"):
        geographic_key("Bègles"),

    geographic_key("Caudran"):
        geographic_key("Caudéran"),

    geographic_key("La Glacire"):
        geographic_key("La Glacière"),

    geographic_key("La Paillre-Compostelle"):
        geographic_key("La Paillère-Compostelle"),

    geographic_key("Le Taillan-Mdoc"):
        geographic_key("Le Taillan-Médoc"),

    geographic_key("Nansouty - Saint Gens"):
        geographic_key("Nansouty - Saint-Genès"),

    geographic_key("Nos"):
        geographic_key("Noès"),

    geographic_key("Palmer-Gravires-Cavailles"):
        geographic_key("Palmer-Gravières-Cavailles"),

    geographic_key("Saint-Aubin-de-Mdoc"):
        geographic_key("Saint-Aubin-de-Médoc"),

    geographic_key("Saint-Mdard-en-Jalles"):
        geographic_key("Saint-Médard-en-Jalles"),
}

BORDEAUX_CONTEXT_RULES = {
    geographic_key(
        "Centre ville (Bordeaux)"
    ): {
        "target_name":
            geographic_key("Centre ville"),
        "insee": "33063",
    },

    geographic_key(
        "Centre ville (Merignac)"
    ): {
        "target_name":
            geographic_key("Centre ville"),
        "insee": "33281",
    },
}

def build_bordeaux_hybrid(
    neighbourhoods,
    municipality_rows,
    quarter_rows,
):

    municipality_index = (
        index_by_name(
            municipality_rows
        )
    )

    quarter_index = (
        index_by_name(
            quarter_rows
        )
    )

    rows = []
    missing = []
    ambiguous = []

    for neighbourhood in neighbourhoods:

        original_key = geographic_key(
            neighbourhood
        )

        # ----------------------------------------------------
        # Explicit contextual rules
        # ----------------------------------------------------

        context_rule = (
            BORDEAUX_CONTEXT_RULES.get(
                original_key
            )
        )

        if context_rule:

            candidates = [
                candidate
                for candidate
                in quarter_index.get(
                    context_rule[
                        "target_name"
                    ],
                    [],
                )
                if candidate.get("insee")
                == context_rule["insee"]
            ]

            if len(candidates) == 1:

                source = candidates[0]

                rows.append(
                    {
                        **source,
                        "area_name":
                            neighbourhood,
                    }
                )

                continue

            if len(candidates) > 1:

                ambiguous.append(
                    (
                        neighbourhood,
                        [
                            (
                                candidate[
                                    "area_name"
                                ],
                                candidate[
                                    "area_level"
                                ],
                                candidate.get(
                                    "insee"
                                ),
                                candidate.get(
                                    "quarpoli"
                                ),
                            )
                            for candidate
                            in candidates
                        ],
                    )
                )

            else:

                missing.append(
                    neighbourhood
                )

            continue

        # ----------------------------------------------------
        # Standard aliases
        # ----------------------------------------------------

        key = BORDEAUX_ALIASES.get(
            original_key,
            original_key,
        )

        quarter_candidates = (
            quarter_index.get(
                key,
                [],
            )
        )

        municipality_candidates = (
            municipality_index.get(
                key,
                [],
            )
        )

        # Prefer the finer geographic grain.
        if len(quarter_candidates) == 1:

            source = quarter_candidates[0]

        elif (
            not quarter_candidates
            and len(
                municipality_candidates
            ) == 1
        ):

            source = (
                municipality_candidates[0]
            )

        else:

            candidates = (
                quarter_candidates
                + municipality_candidates
            )

            if candidates:

                ambiguous.append(
                    (
                        neighbourhood,
                        [
                            (
                                candidate[
                                    "area_name"
                                ],
                                candidate[
                                    "area_level"
                                ],
                                candidate.get(
                                    "insee"
                                ),
                                candidate.get(
                                    "quarpoli"
                                ),
                            )
                            for candidate
                            in candidates
                        ],
                    )
                )

            else:

                missing.append(
                    neighbourhood
                )

            continue

        rows.append(
            {
                **source,
                "area_name":
                    neighbourhood,
            }
        )

    return (
        rows,
        missing,
        ambiguous,
    )

def extract_matched_rows(matches):
    return [
        {
            **match["area"],
            "area_name": match["neighbourhood"],
        }
        for match in matches
    ]

# ============================================================
# Reporting
# ============================================================


def report(
    location,
    expected,
    matched,
    missing,
    ambiguous,
):

    total = len(expected)

    matched_count = len(matched)

    coverage = (
        matched_count / total * 100
        if total
        else 0
    )

    print()
    print(
        "=" * 68
    )

    print(
        location.upper()
    )

    print(
        "=" * 68
    )

    print(
        f"Zones Inside Airbnb : {total}"
    )

    print(
        f"Matchées            : {matched_count}"
    )

    print(
        f"Manquantes          : {len(missing)}"
    )

    print(
        f"Ambiguës            : {len(ambiguous)}"
    )

    print(
        f"Couverture          : {coverage:.2f} %"
    )

    if missing:

        print()
        print("MANQUANTES")

        for value in missing:
            print(
                f"  - {value}"
            )

    if ambiguous:

        print()
        print("AMBIGUËS")

        for value in ambiguous:
            print(
                f"  - {value}"
            )

def inspect_bordeaux_missing(
    missing,
    municipality_rows,
    quarter_rows,
):

    if not missing:
        return

    print()
    print("=" * 68)
    print("DIAGNOSTIC BORDEAUX")
    print("=" * 68)

    all_rows = (
        municipality_rows
        + quarter_rows
    )

    for neighbourhood in missing:

        key = geographic_key(
            neighbourhood
        )

        print()
        print(
            f"Recherche : {neighbourhood!r} "
            f"-> clé={key!r}"
        )

        # Display potentially useful records.
        # We deliberately do not fuzzy-match automatically.
        for row in all_rows:

            candidate_key = (
                geographic_key(
                    row["area_name"]
                )
            )

            if (
                key in candidate_key
                or candidate_key in key
                or (
                    key
                    and candidate_key
                    and key[0]
                    == candidate_key[0]
                )
            ):

                print(
                    "  - "
                    f"{row['area_name']!r} | "
                    f"{row['area_level']} | "
                    f"code={row['area_code']} | "
                    f"insee={row.get('insee')} | "
                    f"quarpoli={row.get('quarpoli')}"
                )

def assert_full_coverage(
    location,
    expected,
    matched,
    missing,
    ambiguous,
):
    if (
        len(matched) != len(expected)
        or missing
        or ambiguous
    ):
        raise RuntimeError(
            f"{location}: couverture géographique incomplète "
            f"({len(matched)}/{len(expected)}, "
            f"{len(missing)} manquante(s), "
            f"{len(ambiguous)} ambiguë(s))."
        )

def apply_geographic_rows(connection, rows):

    cursor = connection.cursor()

    try:
        cursor.execute("BEGIN")

        locations = sorted(
            {
                (
                    row["source_country"],
                    row["source_city"],
                )
                for row in rows
            }
        )

        # Remplace uniquement les 4 localisations gérées
        # par ce loader. Lyon reste intact.
        for country, city in locations:

            cursor.execute(
                f"""
                DELETE FROM {REF_GEOGRAPHIC_AREAS}
                WHERE LOWER(SOURCE_COUNTRY) = %s
                  AND LOWER(SOURCE_CITY) = %s
                """,
                (
                    country.lower(),
                    city.lower(),
                ),
            )

        insert_sql = f"""
            INSERT INTO {REF_GEOGRAPHIC_AREAS}
            (
                SOURCE_COUNTRY,
                SOURCE_CITY,
                AREA_CODE,
                AREA_NAME,
                AREA_LEVEL,
                GEOMETRY,
                SOURCE,
                LOADED_AT
            )
            SELECT
                %s,
                %s,
                %s,
                %s,
                %s,
                TO_GEOGRAPHY(PARSE_JSON(%s)),
                %s,
                CURRENT_TIMESTAMP()
        """

        payload = [
            (
                row["source_country"],
                row["source_city"],
                row["area_code"],
                row["area_name"],
                row["area_level"],
                json.dumps(
                    row["geometry"],
                    ensure_ascii=False,
                ),
                row["source"],
            )
            for row in rows
        ]

        for values in payload:
            cursor.execute(
                insert_sql,
                values,
            )

        cursor.execute("COMMIT")

        print()
        print(
            f"[OK] {len(rows)} zones chargées "
            f"dans {REF_GEOGRAPHIC_AREAS}"
        )

    except Exception:

        try:
            cursor.execute("ROLLBACK")
        finally:
            raise

    finally:
        cursor.close()


def verify_loaded_reference(connection):

    cursor = connection.cursor()

    try:
        cursor.execute(
            f"""
            SELECT
                LOWER(SOURCE_COUNTRY) AS SOURCE_COUNTRY,
                LOWER(SOURCE_CITY) AS SOURCE_CITY,
                COUNT(*) AS AREA_COUNT,
                COUNT_IF(GEOMETRY IS NULL) AS NULL_GEOMETRY,
                COUNT(DISTINCT AREA_CODE) AS DISTINCT_CODES
            FROM {REF_GEOGRAPHIC_AREAS}
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        )

        rows = cursor.fetchall()

        print()
        print("=" * 68)
        print("REF_GEOGRAPHIC_AREAS - CONTRÔLE FINAL")
        print("=" * 68)

        for row in rows:
            print(
                f"{row[0]}/{row[1]} : "
                f"{row[2]} zones | "
                f"geometry NULL={row[3]} | "
                f"codes distincts={row[4]}"
            )

    finally:
        cursor.close()

# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Valide le matching sans modifier Snowflake.",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Valide puis charge REF_GEOGRAPHIC_AREAS.",
    )

    args = parser.parse_args()

    if args.validate == args.apply:
        parser.error(
            "Utilise exactement une option parmi --validate ou --apply."
        )

    connection = connect()

    try:

        source_rows = (
            load_neighbourhoods(
                connection
            )
        )

    finally:

        connection.close()

    neighbourhoods = defaultdict(list)

    for row in source_rows:

        neighbourhoods[
            (
                row[
                    "source_country"
                ],
                row[
                    "source_city"
                ],
            )
        ].append(
            row[
                "neighbourhood"
            ]
        )

    print(
        "Chargement des référentiels..."
    )

    france_data = load_source(
        FRANCE_COMMUNES_URL,
        "france_communes_100m.geojson.gz",
    )

    paris_data = load_source(
        PARIS_URL,
        "paris_arrondissements.geojson",
    )

    brussels_data = load_source(
        BRUSSELS_URL,
        "brussels_municipalities.geojson",
    )

    bordeaux_communes_data = (
        load_source(
            BORDEAUX_COMMUNES_URL,
            "bordeaux_communes.geojson",
        )
    )

    bordeaux_quarters_data = (
        load_source(
            BORDEAUX_QUARTIERS_URL,
            "bordeaux_quartiers.geojson",
        )
    )

    france_communes = (
        build_france_communes(
            france_data
        )
    )

    paris_rows = build_paris(
        paris_data
    )

    brussels_rows = (
        build_brussels(
            brussels_data
        )
    )

    bordeaux_municipalities = (
        build_bordeaux_communes(
            bordeaux_communes_data
        )
    )

    bordeaux_quarters = (
        build_bordeaux_quarters(
            bordeaux_quarters_data
        )
    )

    # --------------------------------------------------------
    # Paris
    # --------------------------------------------------------

    paris_expected = neighbourhoods[
        ("france", "paris")
    ]

    (
        paris_matches,
        paris_missing,
        paris_ambiguous,
    ) = match_exact(
        paris_expected,
        paris_rows,
    )

    report(
        "france/paris",
        paris_expected,
        paris_matches,
        paris_missing,
        paris_ambiguous,
    )

    assert_full_coverage(
        "france/paris",
        paris_expected,
        paris_matches,
        paris_missing,
        paris_ambiguous,
    )
    
    # --------------------------------------------------------
    # Brussels
    # --------------------------------------------------------

    brussels_expected = (
        neighbourhoods[
            (
                "belgium",
                "brussels",
            )
        ]
    )

    (
        brussels_matches,
        brussels_missing,
        brussels_ambiguous,
    ) = match_exact(
        brussels_expected,
        brussels_rows,
    )

    report(
        "belgium/brussels",
        brussels_expected,
        brussels_matches,
        brussels_missing,
        brussels_ambiguous,
    )

    assert_full_coverage(
        "belgium/brussels",
        brussels_expected,
        brussels_matches,
        brussels_missing,
        brussels_ambiguous,
    )

    # --------------------------------------------------------
    # Pays Basque
    # --------------------------------------------------------

    basque_expected = (
        neighbourhoods[
            (
                "france",
                "pays-basque",
            )
        ]
    )

    (
        basque_rows,
        basque_missing,
        basque_ambiguous,
    ) = build_pays_basque(
        basque_expected,
        france_communes,
    )

    report(
        "france/pays-basque",
        basque_expected,
        basque_rows,
        basque_missing,
        basque_ambiguous,
    )

    assert_full_coverage(
        "france/pays-basque",
        basque_expected,
        basque_rows,
        basque_missing,
        basque_ambiguous,
    )

    # --------------------------------------------------------
    # Bordeaux
    # --------------------------------------------------------

    bordeaux_expected = (
        neighbourhoods[
            (
                "france",
                "bordeaux",
            )
        ]
    )

    (
        bordeaux_rows,
        bordeaux_missing,
        bordeaux_ambiguous,
    ) = build_bordeaux_hybrid(
        bordeaux_expected,
        bordeaux_municipalities,
        bordeaux_quarters,
    )

    report(
        "france/bordeaux",
        bordeaux_expected,
        bordeaux_rows,
        bordeaux_missing,
        bordeaux_ambiguous,
    )

    assert_full_coverage(
        "france/bordeaux",
        bordeaux_expected,
        bordeaux_rows,
        bordeaux_missing,
        bordeaux_ambiguous,
    )

    inspect_bordeaux_missing(
        bordeaux_missing,
        bordeaux_municipalities,
        bordeaux_quarters,
    )

    paris_load_rows = extract_matched_rows(
        paris_matches
    )

    brussels_load_rows = extract_matched_rows(
        brussels_matches
    )

    load_rows = (
        paris_load_rows
        + brussels_load_rows
        + basque_rows
        + bordeaux_rows
    )

    print()
    print(
        f"Zones prêtes au chargement : {len(load_rows)}"
    )

    if args.apply:

        print()
        print(
            f"Chargement de {len(load_rows)} zones dans Snowflake..."
        )

        connection = connect()

        try:
            apply_geographic_rows(
                connection,
                load_rows,
            )

            verify_loaded_reference(
                connection
            )

        finally:
            connection.close()


if __name__ == "__main__":
    main()