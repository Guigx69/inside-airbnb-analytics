"""Resolve inclusive/exclusive geographic scopes against the live Inside Airbnb catalog.

Selection JSON example:
{"include":{"continents":["Europe"],"countries":["Japan"],"cities":["Sydney"]},
 "exclude":{"cities":["Paris"]}}
Unknown geographic names fail closed rather than silently selecting the world.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    return "".join(c for c in text if not unicodedata.combining(c)).casefold().strip()


def _names(block: dict, key: str) -> set[str]:
    values = block.get(key, [])
    if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError(f"{key} must be a list of nonempty strings")
    return {normalize(v) for v in values}


def select_datasets(inventory: list, selection_path: str | Path) -> list:
    try:
        import country_converter as coco
    except ImportError as exc:
        raise RuntimeError("Install project dependencies: country_converter is required") from exc

    payload = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) - {"include", "exclude"}:
        raise ValueError("Selection must contain only include/exclude objects")
    include = payload.get("include", {})
    exclude = payload.get("exclude", {})
    if not isinstance(include, dict) or not isinstance(exclude, dict):
        raise ValueError("include and exclude must be objects")
    allowed = {"continents", "countries", "cities"}
    if set(include) - allowed or set(exclude) - allowed:
        raise ValueError("Unknown geography field; use continents, countries, cities")

    requested = {mode: {key: _names(block, key) for key in allowed}
                 for mode, block in (("include", include), ("exclude", exclude))}
    if not any(requested["include"].values()):
        raise ValueError("At least one inclusion is required; use explicit world selection instead")

    # Resolve the continent of each catalog country once. The converter's
    # 'not found' result is never accepted as a selectable continent.
    countries = {item.country for item in inventory}
    converter = coco.CountryConverter()
    continent_by_country = {}
    for country in countries:
        result = converter.convert(names=country, to="continent", not_found=None)
        continent_by_country[country] = normalize(result) if isinstance(result, str) else None

    def fields(item):
        return {
            "continents": continent_by_country[item.country],
            "countries": normalize(item.country),
            "cities": normalize(item.location),
        }

    available = {key: {fields(item)[key] for item in inventory if fields(item)[key]}
                 for key in allowed}
    for mode in ("include", "exclude"):
        for key in allowed:
            unknown = requested[mode][key] - available[key]
            if unknown:
                raise ValueError(f"Unknown {key} in {mode}: {', '.join(sorted(unknown))}")

    def matches(item, mode):
        actual = fields(item)
        return any(actual[key] in requested[mode][key] for key in allowed)

    return [item for item in inventory
            if matches(item, "include") and not matches(item, "exclude")]


def select_manifest_paths(rows: list[dict], selection_path: str | Path) -> set[str]:
    """Apply the same geographic rules to local manifest entries, without HTTP."""
    from types import SimpleNamespace

    inventory = []
    for row in rows:
        parts = Path(row["path"]).parts
        if len(parts) != 6 or parts[:2] != ("data", "raw"):
            raise ValueError(f"Unexpected manifest path: {row['path']}")
        inventory.append(SimpleNamespace(
            country=parts[2], location=parts[3], manifest_path=row["path"]
        ))
    return {item.manifest_path for item in select_datasets(inventory, selection_path)}
