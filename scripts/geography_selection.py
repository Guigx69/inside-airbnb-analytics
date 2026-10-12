"""Résoudre les inclusions et exclusions géographiques du catalogue Inside Airbnb.

Exemple de sélection JSON :
{"include":{"continents":["Europe"],"countries":["Japan"],"cities":["Sydney"]},
 "exclude":{"cities":["Paris"]}}
Un nom géographique inconnu provoque une erreur, jamais une sélection mondiale.
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
        raise ValueError(f"{key} doit être une liste de chaînes non vides")
    return {normalize(v) for v in values}


def select_datasets(inventory: list, selection_path: str | Path) -> list:
    try:
        import country_converter as coco
    except ImportError as exc:
        raise RuntimeError("Installer les dépendances : country_converter est nécessaire") from exc

    payload = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) - {"include", "exclude"}:
        raise ValueError("La sélection doit contenir uniquement include/exclude")
    include = payload.get("include", {})
    exclude = payload.get("exclude", {})
    if not isinstance(include, dict) or not isinstance(exclude, dict):
        raise ValueError("include et exclude doivent être des objets")
    allowed = {"continents", "countries", "cities"}
    if set(include) - allowed or set(exclude) - allowed:
        raise ValueError("Champ inconnu ; utiliser continents, countries, cities")

    requested = {mode: {key: _names(block, key) for key in allowed}
                 for mode, block in (("include", include), ("exclude", exclude))}
    if not any(requested["include"].values()):
        raise ValueError("Au moins une inclusion est nécessaire ; utiliser --all dans le collecteur pour le monde")

    # Déterminer le continent de chaque pays une seule fois.
    # Une conversion inconnue n'est pas un continent sélectionnable.
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
                raise ValueError(f"Valeur {key} inconnue dans {mode} : {', '.join(sorted(unknown))}")

    def matches(item, mode):
        actual = fields(item)
        return any(actual[key] in requested[mode][key] for key in allowed)

    return [item for item in inventory
            if matches(item, "include") and not matches(item, "exclude")]


def select_manifest_paths(rows: list[dict], selection_path: str | Path) -> set[str]:
    """Appliquer les mêmes règles géographiques au manifeste local, sans HTTP."""
    from types import SimpleNamespace

    inventory = []
    for row in rows:
        parts = Path(row["path"]).parts
        if len(parts) != 6 or parts[:2] != ("data", "raw"):
            raise ValueError(f"Chemin inattendu dans le manifeste : {row['path']}")
        inventory.append(SimpleNamespace(
            country=parts[2], location=parts[3], manifest_path=row["path"]
        ))
    return {item.manifest_path for item in select_datasets(inventory, selection_path)}
