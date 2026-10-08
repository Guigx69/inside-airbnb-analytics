#!/usr/bin/env python3

"""V14.2: Validate and insert Inside Airbnb World neighbourhood polygons without overwriting existing keys.



Run from project root:

  python snowflake/reference/load_world_geographic_areas.py --validate

  python snowflake/reference/load_world_geographic_areas.py --apply
  python snowflake/reference/load_world_geographic_areas.py --diagnose



Optional fallback geojson_world_matching.csv; pip install requests shapely snowflake-connector-python.

"""

from __future__ import annotations

from shapely import set_precision



import argparse

import csv

import hashlib

import json

import os

import sys

from collections import Counter, defaultdict

from pathlib import Path

from urllib.parse import urlparse, unquote
import unicodedata



import requests

import snowflake.connector

from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape

from shapely.ops import unary_union

from shapely.validation import make_valid



def precision_candidates(geom):

    """

    Génère des réparations candidates sans modifier la géométrie source.

    Les surfaces sont comparées en coordonnées projetées approximatives

    uniquement pour détecter une altération excessive.

    """

    for grid_size in (1e-8, 1e-7, 1e-6, 1e-5):

        try:

            repaired = set_precision(

                geom,

                grid_size=grid_size,

                mode="valid_output",

            )



            if repaired.is_empty or not repaired.is_valid:

                continue



            if repaired.geom_type not in ("Polygon", "MultiPolygon"):

                continue



            original_area = geom.area

            if original_area <= 0:

                continue



            area_delta = abs(repaired.area - original_area) / original_area



            if area_delta > 0.001:

                continue



            yield grid_size, repaired, area_delta



        except Exception:

            continue



def identifier(value, label):

    if not value or not (value[0].isalpha() or value[0] == "_") or not all(c.isalnum() or c == "_" for c in value):

        raise ValueError(f"Invalid Snowflake identifier {label}: {value!r}")

    return value.upper()





def connect():

    required = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "DBT_SNOWFLAKE_PASSWORD",

                "SNOWFLAKE_DATABASE", "SNOWFLAKE_MARTS_SCHEMA")

    missing = [x for x in required if not os.getenv(x)]

    if missing:

        raise RuntimeError("Missing environment variables: " + ", ".join(missing))

    return snowflake.connector.connect(

        account=os.environ["SNOWFLAKE_ACCOUNT"],

        user=os.environ["SNOWFLAKE_USER"],

        password=os.environ["DBT_SNOWFLAKE_PASSWORD"],

        authenticator="snowflake",

        role=os.getenv("SNOWFLAKE_ROLE", "DBT_ROLE"),

        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "DBT_WH"),

        database=os.environ["SNOWFLAKE_DATABASE"],

        schema=os.environ["SNOWFLAKE_MARTS_SCHEMA"],

        autocommit=False,

    )





def inventory(path):

    with path.open(encoding="utf-8-sig", newline="") as f:

        rows = list(csv.DictReader(f))

    if not rows or not {"source_country", "source_city", "in_fct", "url"}.issubset(rows[0]):

        raise ValueError(f"Invalid inventory: {path}")

    result = {}

    for r in rows:

        if str(r["in_fct"]).strip() != "1":

            continue

        key = (r["source_country"], r["source_city"])

        if key in result:

            raise ValueError(f"Duplicate inventory key: {key}")

        url = r["url"]

        parsed = urlparse(url)

        if (parsed.scheme != "https" or parsed.hostname != "data.insideairbnb.com"

                or not parsed.path.endswith("/visualisations/neighbourhoods.geojson")):

            raise ValueError(f"Unexpected URL: {url}")

        result[key] = url

    return result






CATALOG_URL = "https://insideairbnb.com/page-data/sq/d/3176684073.json"


def catalog_slug(value):
    """Normalize Unicode/percent-encoded destination path to FCT ASCII slug."""
    decoded = unquote(value)
    ascii_text = unicodedata.normalize("NFKD", decoded)
    ascii_text = "".join(ch for ch in ascii_text if not unicodedata.combining(ch))
    return ascii_text.casefold()


def discover_catalog(session, url=CATALOG_URL):
    """Choose latest dated official publication per destination.

    Repeated historical snapshots are normal. A same-date disagreement remains
    ambiguous and is excluded individually (allowing inventory fallback).
    """
    from datetime import date
    response = session.get(url, timeout=45)
    response.raise_for_status()
    root = response.json()
    records = {}

    def walk(node):
        if isinstance(node, dict):
            data_root = node.get("dataRoot")
            publish_date = node.get("publishDate")
            if isinstance(data_root, str) and isinstance(publish_date, str):
                parsed = urlparse(data_root)
                parts = [part for part in parsed.path.split("/") if part]
                if (parsed.scheme == "https" and parsed.hostname == "data.insideairbnb.com"
                        and not parsed.username and not parsed.password and not parsed.port
                        and len(parts) >= 2 and not parsed.query and not parsed.fragment):
                    try:
                        day = date.fromisoformat(publish_date)
                        if day.isoformat() != publish_date:
                            raise ValueError("noncanonical date")
                    except ValueError:
                        pass
                    else:
                        key = (catalog_slug(parts[0]), catalog_slug(parts[-1]))
                        geo_url = data_root.rstrip("/") + "/" + publish_date + "/visualisations/neighbourhoods.geojson"
                        records.setdefault(key, {}).setdefault(day, set()).add(geo_url)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(root)
    discovered = {}
    ambiguous = []
    for key, by_date in records.items():
        latest = max(by_date)
        urls = by_date[latest]
        if len(urls) == 1:
            discovered[key] = next(iter(urls))
        else:
            ambiguous.append(key)
    if ambiguous:
        print(f"[CATALOG WARNING] ambiguous latest publications={len(ambiguous)}; excluded individually", file=sys.stderr)
    if not discovered:
        raise RuntimeError("No unambiguous Inside Airbnb destination GeoJSON URLs found in catalog")
    return discovered


def destination_complete(country, city, expected_names, existing_keys):
    """True only if at least one named FCT area exists and all named keys are in reference."""
    return bool(expected_names) and all((country, city, name) in existing_keys for name in expected_names)


def resolve_sources(destinations, csv_sources, catalog_sources, catalog_error=None):
    """Catalog-first resolution; CSV fallback; unresolved destinations remain quarantined."""
    result, origin, unresolved = {}, {}, {}
    for key in sorted(destinations):
        if key in catalog_sources:
            result[key] = catalog_sources[key]
            origin[key] = "CATALOG"
        elif key in csv_sources:
            result[key] = csv_sources[key]
            origin[key] = "INVENTORY_FALLBACK"
        else:
            unresolved[key] = "Catalog unavailable: " + str(catalog_error) if catalog_error else "Destination absent from catalog and inventory"
    return result, origin, unresolved


def polygon_only(geom):

    """Keep polygonal components of make_valid results, excluding lines and points."""

    if geom.is_empty:

        return None

    if isinstance(geom, Polygon):

        return geom if geom.area > 0 else None

    if isinstance(geom, MultiPolygon):

        parts = [g for g in geom.geoms if not g.is_empty and g.area > 0]

    elif isinstance(geom, GeometryCollection):

        parts = []

        for g in geom.geoms:

            poly = polygon_only(g)

            if poly is not None:

                parts.extend(poly.geoms if isinstance(poly, MultiPolygon) else [poly])

    else:

        return None

    if not parts:

        return None

    return parts[0] if len(parts) == 1 else MultiPolygon(parts)





def repair_polygon(geom, max_area_change):

    """Return (polygon, repaired, relative area change); reject excessive changes."""

    raw = shape(geom)

    if raw.is_empty or raw.geom_type not in ("Polygon", "MultiPolygon"):

        raise ValueError(f"Empty or nonpolygon source geometry: {raw.geom_type}")

    before = raw.area

    repaired = not raw.is_valid

    fixed = make_valid(raw) if repaired else raw

    fixed = polygon_only(fixed)

    if fixed is None:

        raise ValueError("No polygonal components after make_valid")

    if not fixed.is_valid:

        fixed = polygon_only(make_valid(fixed))

    if fixed is None or not fixed.is_valid or fixed.is_empty:

        raise ValueError("Invalid geometry after repair")

    after = fixed.area

    delta = abs(after - before) / before if before > 0 else (0 if after == 0 else float("inf"))

    if delta > max_area_change:

        raise ValueError(f"Area change {delta:.6%} exceeds {max_area_change:.2%}")

    return fixed, repaired, delta





def area_code(country, city, name):

    digest = hashlib.sha256(json.dumps([country, city, name], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:24].upper()

    return "IA_" + digest





def write_csv(path, header, rows):

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as f:

        w = csv.writer(f)

        w.writerow(header)

        w.writerows(rows)





DIAGNOSTIC_TARGETS = {
    ("united-states", "portland"): "Pleasant Valley",
    ("united-states", "san-mateo-county"): "Unincorporated Areas",
    ("united-states", "santa-cruz-county"): "Unincorporated Areas",
}


def snowflake_valid(cur, geom):
    geojson = json.dumps(mapping(geom), ensure_ascii=False, separators=(",", ":"))
    cur.execute("SELECT TRY_TO_GEOGRAPHY(%s) IS NOT NULL", (geojson,))
    return bool(cur.fetchone()[0])


def component_variants(part):
    """Conservative local repairs; leave all other components byte-for-byte unchanged."""
    yield "original", part
    operations = [
        ("make_valid", lambda g: polygon_only(make_valid(g))),
        ("buffer_0", lambda g: polygon_only(g.buffer(0))),
    ]
    for grid in (1e-9, 1e-8, 1e-7, 1e-6, 1e-5):
        operations.append((f"precision_{grid:g}",
                           lambda g, grid=grid: polygon_only(set_precision(g, grid, mode="valid_output"))))
    for name, operation in operations:
        try:
            candidate = operation(part)
            if candidate is not None and not candidate.is_empty and candidate.is_valid:
                yield name, candidate
        except Exception:
            continue


def ring_diagnostics(part):
    """Describe local ring defects without modifying source coordinates."""
    from shapely.validation import explain_validity
    from shapely.geometry import LinearRing
    rings = [("exterior", part.exterior)] + [(f"hole_{i}", r) for i, r in enumerate(part.interiors)]
    output = []
    for label, ring in rings:
        coords = list(ring.coords)
        consecutive_duplicates = sum(a == b for a, b in zip(coords, coords[1:]))
        output.append((label, len(coords), consecutive_duplicates,
                       LinearRing(coords).is_simple if len(coords) >= 4 else False))
    return explain_validity(part), output


def local_ring_variants(part):
    """Attempt localized fixes to rings and tiny coordinate defects, not other components."""
    from shapely.geometry.polygon import orient
    from shapely.ops import snap
    from shapely import remove_repeated_points
    operations = [
        ("orient_ccw", lambda g: orient(g, sign=1.0)),
        ("orient_cw", lambda g: orient(g, sign=-1.0)),
        ("remove_repeated_0", lambda g: remove_repeated_points(g, tolerance=0)),
        ("make_valid", lambda g: make_valid(g)),
        ("buffer_0", lambda g: g.buffer(0)),
    ]
    for tolerance in (1e-12, 1e-11, 1e-10, 1e-9, 1e-8):
        operations.extend([
            (f"remove_repeated_{tolerance:g}",
             lambda g, t=tolerance: remove_repeated_points(g, tolerance=t)),
            (f"buffer_{tolerance:g}", lambda g, t=tolerance: g.buffer(t)),
            (f"buffer_minus_{tolerance:g}", lambda g, t=tolerance: g.buffer(-t)),
            (f"buffer_out_in_{tolerance:g}", lambda g, t=tolerance: g.buffer(t).buffer(-t)),
        ])
    for method, fn in operations:
        try:
            candidate = polygon_only(fn(part))
            if candidate is not None and not candidate.is_empty and candidate.is_valid:
                yield method, candidate
        except Exception:
            continue
    yield from ((m, g) for m, g in component_variants(part) if m != "original")


def geographic_component_diagnostic(cur, part, index):
    """Snowflake geodesic diagnostics; no invalid geography is inserted."""
    coords = list(part.exterior.coords)
    edges = [((a[0]-b[0])**2 + (a[1]-b[1])**2)**0.5
             for a, b in zip(coords, coords[1:])]
    print(f"  [GEO] component={index} bounds={part.bounds} "
          f"planar_area={part.area:.16g} min_edge_deg={min(edges):.12g} "
          f"max_edge_deg={max(edges):.12g}")
    print(f"  [COORDS] component={index} exterior={coords!r}")
    geojson = json.dumps(mapping(part), separators=(",", ":"))
    cur.execute("SELECT ST_AREA(TRY_TO_GEOGRAPHY(%s, TRUE))", (geojson,))
    print(f"  [GEODESIC] component={index} allow_invalid_area_m2={cur.fetchone()[0]}")
    from shapely import force_2d
    flat = force_2d(part)
    print(f"  [DIMENSIONS] component={index} has_z={part.has_z} "
          f"xy_unchanged={flat.equals(part)} "
          f"2d_snowflake_valid={snowflake_valid(cur, flat)}")
    # Check each edge's spherical interpretation without mutating the geometry.
    from shapely.geometry import LineString
    coords2d = [(c[0], c[1]) for c in part.exterior.coords]
    for edge_index, (a, b) in enumerate(zip(coords2d, coords2d[1:])):
        line = LineString([a, b])
        print(f"  [EDGE] component={index} edge={edge_index} "
              f"snowflake_valid={snowflake_valid(cur, line)}")


def dimensional_variants(part):
    """Remove Z without changing XY, then test geodesic ring interpretation.

    A 2D conversion preserves the footprint exactly. Triangulation is only
    diagnostic: it never silently replaces a source component.
    """
    from shapely import force_2d
    from shapely.geometry.polygon import orient
    from shapely.ops import triangulate
    flat = force_2d(part)
    yield "force_2d", flat
    yield "force_2d_ccw", orient(flat, sign=1)
    yield "force_2d_cw", orient(flat, sign=-1)
    if len(flat.interiors) == 0 and len(flat.exterior.coords) <= 12:
        triangles = [g for g in triangulate(flat) if flat.covers(g.representative_point())]
        for i, tri in enumerate(triangles):
            yield f"triangle_{i}_diagnostic_only", tri


def vertex_variants(part):
    """Move one vertex by sub-millimetre-to-centimetre offsets; diagnostic only.

    Reject any variant that changes ring count, validity or planar area > 0.1%.
    The complete MultiPolygon still must pass strict Snowflake validation.
    """
    if len(part.interiors) or len(part.exterior.coords) > 12:
        return
    coords = list(part.exterior.coords[:-1])
    for magnitude in (1e-11, 1e-10, 1e-9, 1e-8, 1e-7):
        for idx in range(len(coords)):
            for dx, dy in ((magnitude, 0), (-magnitude, 0),
                           (0, magnitude), (0, -magnitude),
                           (magnitude, magnitude), (-magnitude, -magnitude)):
                moved = [(float(p[0]), float(p[1])) for p in coords]
                x, y = moved[idx]
                moved[idx] = (x + dx, y + dy)
                candidate = Polygon(moved)
                if candidate.is_valid and not candidate.is_empty and candidate.area > 0:
                    yield f"vertex_{idx}_{dx:+.0e}_{dy:+.0e}", candidate


def topology_component_diagnostic(cur, original, index, label):
    """Read-only component topology. Never drop or replace source polygons."""
    from shapely import force_2d
    from shapely.ops import unary_union

    parts = list(original.geoms) if isinstance(original, MultiPolygon) else [original]
    target = force_2d(parts[index])
    others = [force_2d(p) for j, p in enumerate(parts) if j != index]
    if not others:
        print(f"  [TOPOLOGY] component={index} isolated_only_component=True")
        return
    remaining = unary_union(others)
    covered = remaining.covers(target)
    overlap = target.intersection(remaining)
    overlap_area = overlap.area
    uncovered = target.difference(remaining)
    uncovered_area = uncovered.area
    overlap_ratio = overlap_area / target.area if target.area else 0.0
    uncovered_ratio = uncovered_area / target.area if target.area else 0.0
    distance = target.distance(remaining)
    print(f"  [TOPOLOGY] component={index} covered_by_others={covered} "
          f"overlap_ratio={overlap_ratio:.12g} uncovered_ratio={uncovered_ratio:.12g} "
          f"nearest_distance_deg={distance:.12g}")
    contacts = []
    for j, other in enumerate(parts):
        if j == index:
            continue
        other = force_2d(other)
        d = target.distance(other)
        if d == 0 or len(contacts) < 5:
            shared = target.boundary.intersection(other.boundary)
            contacts.append((j, d, target.intersection(other).area, shared.length))
    contacts.sort(key=lambda item: (item[1], -item[2], item[0]))
    for j, d, intersection_area, shared_boundary in contacts[:10]:
        print(f"  [NEIGHBOR] component={index} other={j} distance_deg={d:.12g} "
              f"intersection_area_deg2={intersection_area:.12g} "
              f"shared_boundary_deg={shared_boundary:.12g}")
    remaining_valid = snowflake_valid(cur, remaining)
    print(f"  [EXCLUSION TEST] component={index} remaining_components={len(others)} "
          f"remaining_snowflake_valid={remaining_valid} "
          f"lost_area_deg2={uncovered_area:.16g} "
          f"lost_fraction_of_component={uncovered_ratio:.12g} "
          "diagnostic_only=True")
    print(f"  [POLICY] component={index} excluded=False; "
          "no automatic geometry deletion or replacement")


def contact_fusion_diagnostic(cur, original, index, label):
    """Read-only test of lossless fusion with touching components; no fallback deletion."""
    from shapely import force_2d
    from shapely.ops import unary_union

    parts = list(original.geoms) if isinstance(original, MultiPolygon) else [original]
    target = force_2d(parts[index])
    touching = []
    for j, part in enumerate(parts):
        if j == index:
            continue
        neighbor = force_2d(part)
        if target.distance(neighbor) <= 1e-12:
            touching.append((j, neighbor))
    print(f"  [FUSION] component={index} touching_neighbors={[j for j, _ in touching]}")
    for j, neighbor in touching:
        source_union = unary_union([target, neighbor])
        fused = []
        if source_union.geom_type == "Polygon":
            fused.append(("unary_union", source_union))
        elif source_union.geom_type == "MultiPolygon":
            print(f"  [FUSION] neighbor={j} unary_union_disconnected=True "
                  f"result_components={len(source_union.geoms)}")
        try:
            buffered = unary_union([target, neighbor]).buffer(0)
            if buffered.geom_type == "Polygon":
                fused.append(("buffer_zero", buffered))
        except Exception as exc:
            print(f"  [FUSION ERROR] neighbor={j} operation=buffer_zero error={exc}")
        for method, candidate in fused:
            original_pair = unary_union([target, neighbor])
            loss = original_pair.difference(candidate).area
            gain = candidate.difference(original_pair).area
            tolerance = max(original_pair.area * 1e-12, 1e-18)
            lossless = loss <= tolerance and gain <= tolerance
            candidate_valid = candidate.is_valid and snowflake_valid(cur, candidate)
            rebuilt = [force_2d(p) for k, p in enumerate(parts) if k not in (index, j)] + [candidate]
            whole = MultiPolygon(rebuilt) if len(rebuilt) > 1 else rebuilt[0]
            whole_valid = whole.is_valid and snowflake_valid(cur, whole)
            print(f"  [FUSION TEST] component={index} neighbor={j} method={method} "
                  f"loss_deg2={loss:.16g} gain_deg2={gain:.16g} "
                  f"lossless={lossless} pair_valid={candidate_valid} "
                  f"whole_valid={whole_valid} resulting_components={len(rebuilt)} "
                  "diagnostic_only=True")
    print(f"  [FUSION POLICY] component={index} applied=False; "
          "no automatic topology changes")


def contour_reconstruction_diagnostic(cur, original, index, label):
    """Read-only reconstruction trials. No source component is ever discarded."""
    from shapely import force_2d
    from shapely.ops import triangulate, unary_union
    from shapely.geometry import Polygon

    parts = list(original.geoms) if isinstance(original, MultiPolygon) else [original]
    target = force_2d(parts[index])
    coords = list(target.exterior.coords[:-1])
    if target.interiors or len(coords) > 10 or target.area <= 0:
        print(f"  [CONTOUR] component={index} unsupported_rings=True diagnostic_only=True")
        return
    trials = []
    for i in range(len(coords)):
        reduced = coords[:i] + coords[i+1:]
        if len(reduced) >= 3:
            trials.append((f"remove_vertex_{i}", Polygon(reduced)))
    for tolerance in (1e-12, 1e-10, 1e-9, 1e-8, 1e-7):
        trials.append((f"simplify_{tolerance:.0e}", target.simplify(tolerance, preserve_topology=True)))
    trials.append(("convex_hull", target.convex_hull))
    # Triangulation is tested both individually and as a union, with coverage metrics.
    triangles = [t for t in triangulate(target) if target.covers(t.representative_point())]
    for i, tri in enumerate(triangles):
        trials.append((f"triangle_{i}", tri))
    if triangles:
        trials.append(("triangle_union", unary_union(triangles)))
    print(f"  [CONTOUR] component={index} original_area_deg2={target.area:.16g} "
          f"vertices={len(coords)} trials={len(trials)} diagnostic_only=True")
    for method, candidate in trials:
        if candidate.geom_type != "Polygon" or candidate.is_empty or not candidate.is_valid:
            print(f"  [CONTOUR SKIP] component={index} method={method} "
                  f"geometry_type={candidate.geom_type} valid={candidate.is_valid}")
            continue
        lost = target.difference(candidate).area
        gained = candidate.difference(target).area
        loss_ratio = lost / target.area
        gain_ratio = gained / target.area
        component_valid = snowflake_valid(cur, candidate)
        # Avoid querying a large assembled geometry for invalid candidates.
        whole_valid = False
        if component_valid:
            rebuilt = parts.copy()
            rebuilt[index] = candidate
            assembled = MultiPolygon(rebuilt) if len(rebuilt) > 1 else rebuilt[0]
            whole_valid = assembled.is_valid and snowflake_valid(cur, assembled)
        # Strict preservation: neither losing nor adding more than one millionth
        # of the component's area. Never authorize automatic use in this version.
        coverage_preserved = loss_ratio <= 1e-6 and gain_ratio <= 1e-6
        print(f"  [CONTOUR TEST] component={index} method={method} "
              f"lost_deg2={lost:.16g} gained_deg2={gained:.16g} "
              f"loss_ratio={loss_ratio:.9g} gain_ratio={gain_ratio:.9g} "
              f"component_valid={component_valid} whole_valid={whole_valid} "
              f"coverage_preserved={coverage_preserved} diagnostic_only=True")
    print(f"  [CONTOUR POLICY] component={index} applied=False; "
          "no automatic simplification, triangulation or component exclusion")


def triangle_partition_diagnostic(cur, original, index, label):
    """Read-only exact partition tests; never authorizes replacement or writes REF."""
    from shapely import force_2d
    from shapely.ops import triangulate, unary_union

    parts = list(original.geoms) if isinstance(original, MultiPolygon) else [original]
    target = force_2d(parts[index])
    if target.interiors or len(target.exterior.coords) != 5:
        print(f"  [PARTITION SKIP] component={index} non_quadrilateral=True")
        return

    coords = list(target.exterior.coords[:-1])
    partitions = []
    # Both diagonals of the source quadrilateral. Triangles must lie inside it.
    for diagonal in ((0, 2), (1, 3)):
        a, b = diagonal
        i, j = sorted(diagonal)
        chain1 = coords[i:j+1]
        chain2 = coords[j:] + coords[:i+1]
        try:
            pair = (Polygon(chain1), Polygon(chain2))
            partitions.append((f"diagonal_{a}_{b}", pair))
        except Exception as exc:
            print(f"  [PARTITION ERROR] diagonal={a}_{b} error={exc}")
    triangles = triangulate(target)
    inside = [t for t in triangles if target.covers(t.representative_point())]
    if len(inside) == 2:
        partitions.append(("shapely_triangulate", tuple(inside)))

    print(f"  [PARTITION] component={index} partitions={len(partitions)} "
          f"original_area_deg2={target.area:.16g} diagnostic_only=True")
    for method, pair in partitions:
        if any(p.is_empty or p.area <= 0 or not p.is_valid for p in pair):
            print(f"  [PARTITION SKIP] method={method} degenerate_or_invalid_triangle=True")
            continue
        pair_union = unary_union(pair)
        lost = target.difference(pair_union).area
        gained = pair_union.difference(target).area
        loss_ratio = lost / target.area
        gain_ratio = gained / target.area
        overlap = pair[0].intersection(pair[1]).area
        shared = pair[0].boundary.intersection(pair[1].boundary).length
        exact = loss_ratio <= 1e-10 and gain_ratio <= 1e-10 and overlap <= target.area * 1e-10
        individually_valid = [snowflake_valid(cur, p) for p in pair]
        multipolygon = MultiPolygon(pair)
        multi_shapely_valid = multipolygon.is_valid
        multi_snowflake_valid = snowflake_valid(cur, multipolygon)
        # Snowflake's native spherical union is a separate diagnostic: it is
        # not equivalent to Shapely's planar union or a lossless replacement.
        native_union_valid = False
        native_union_area_m2 = None
        native_union_error = None
        if all(individually_valid):
            try:
                j0 = json.dumps(mapping(pair[0]), separators=(",", ":"))
                j1 = json.dumps(mapping(pair[1]), separators=(",", ":"))
                cur.execute("SELECT ST_ISVALID(ST_UNION(TO_GEOGRAPHY(%s), TO_GEOGRAPHY(%s))), "
                            "ST_AREA(ST_UNION(TO_GEOGRAPHY(%s), TO_GEOGRAPHY(%s)))",
                            (j0, j1, j0, j1))
                result = cur.fetchone()
                native_union_valid = bool(result[0])
                native_union_area_m2 = result[1]
            except Exception as exc:
                native_union_error = str(exc).replace("\n", " ")[:250]
        print(f"  [PARTITION TEST] component={index} method={method} "
              f"loss_ratio={loss_ratio:.12g} gain_ratio={gain_ratio:.12g} "
              f"overlap_deg2={overlap:.16g} shared_boundary_deg={shared:.16g} "
              f"exact_coverage={exact} triangles_valid={individually_valid} "
              f"multi_shapely_valid={multi_shapely_valid} "
              f"multi_snowflake_valid={multi_snowflake_valid} "
              f"native_union_valid={native_union_valid} "
              f"native_union_area_m2={native_union_area_m2} "
              f"native_union_error={native_union_error} diagnostic_only=True")
        # The full geometry test is meaningful only for a strict MultiPolygon.
        if multi_shapely_valid and multi_snowflake_valid:
            rebuilt = [force_2d(p) for k, p in enumerate(parts) if k != index] + list(pair)
            whole = MultiPolygon(rebuilt)
            whole_valid = whole.is_valid and snowflake_valid(cur, whole)
            print(f"  [PARTITION WHOLE] method={method} whole_valid={whole_valid} "
                  "diagnostic_only=True")
    print(f"  [PARTITION POLICY] component={index} applied=False; "
          "no automatic partition or area loss")


def generic_exact_partition_repair(cur, original, label):
    """Repair a single invalid quadrilateral component with exact-cover triangles.

    Shapely considers edge-sharing MultiPolygons invalid, but Snowflake's
    GEOGRAPHY parser can accept this representation. Never relax source
    coverage checks or use allow_invalid=TRUE.
    """
    from shapely import force_2d
    from shapely.ops import unary_union, triangulate

    parts = list(original.geoms) if isinstance(original, MultiPolygon) else [original]
    bad = [i for i, p in enumerate(parts) if not snowflake_valid(cur, p)]
    if len(bad) != 1:
        print(f"  [PARTITION INTEGRATION] blocked: invalid_indices={bad}")
        return None
    index = bad[0]
    target = force_2d(parts[index])
    if target.interiors or len(target.exterior.coords) != 5 or target.area <= 0:
        print("  [PARTITION INTEGRATION] blocked: target is not a simple quadrilateral")
        return None
    coords = list(target.exterior.coords[:-1])
    variants = [
        ("diagonal_0_2", (Polygon(coords[0:3]), Polygon(coords[2:] + coords[:1]))),
    ]
    tris = [t for t in triangulate(target) if target.covers(t.representative_point())]
    if len(tris) == 2:
        variants.append(("shapely_triangulate", tuple(tris)))

    for method, pair in variants:
        if any(t.is_empty or not t.is_valid or t.area <= 0 for t in pair):
            continue
        union = unary_union(pair)
        lost = target.difference(union).area / target.area
        gained = union.difference(target).area / target.area
        overlap = pair[0].intersection(pair[1]).area / target.area
        if max(lost, gained, overlap) > 1e-10:
            print(f"  [PARTITION INTEGRATION] method={method} rejected: "
                  f"loss={lost:.12g} gain={gained:.12g} overlap={overlap:.12g}")
            continue
        if not all(snowflake_valid(cur, t) for t in pair):
            continue
        # Retain all other source components, changing only the one bad sliver.
        rebuilt = [force_2d(p) for j, p in enumerate(parts) if j != index] + list(pair)
        candidate = MultiPolygon(rebuilt)
        # Shapely validity is deliberately not required: the triangles share an
        # internal edge. Snowflake must accept the COMPLETE geography instead.
        whole_valid = snowflake_valid(cur, candidate)
        print(f"  [PARTITION INTEGRATION] method={method} component={index} "
              f"loss_ratio={lost:.12g} gain_ratio={gained:.12g} "
              f"overlap_ratio={overlap:.12g} whole_snowflake_valid={whole_valid} "
              f"parts_before={len(parts)} parts_after={len(rebuilt)}")
        if whole_valid:
            # Check whole-neighbourhood planar coverage as a second safeguard.
            original_cover = unary_union([force_2d(p) for p in parts])
            rebuilt_cover = unary_union(rebuilt)
            denom = original_cover.area
            if denom <= 0:
                continue
            total_loss = original_cover.difference(rebuilt_cover).area / denom
            total_gain = rebuilt_cover.difference(original_cover).area / denom
            if max(total_loss, total_gain) <= 1e-10:
                print(f"  [PARTITION FIXED] {label}: method={method} "
                      f"whole_loss_ratio={total_loss:.12g} "
                      f"whole_gain_ratio={total_gain:.12g}")
                return candidate
            print(f"  [PARTITION INTEGRATION] rejected whole coverage "
                  f"loss={total_loss:.12g} gain={total_gain:.12g}")
    print(f"  [PARTITION BLOCKED] {label}: no valid exact-cover whole geography")
    return None


def targeted_repair(cur, original, label, max_delta=0.001):
    """Diagnose every invalid component; attempt local variants, then validate assembled shape."""
    from itertools import product
    parts = list(original.geoms) if isinstance(original, MultiPolygon) else [original]
    bad = [i for i, part in enumerate(parts) if not snowflake_valid(cur, part)]
    print(f"[TARGET] {label}: components={len(parts)} invalid={bad}")
    if not bad:
        return original if snowflake_valid(cur, original) else None
    replacements = {}
    for index in bad:
        part = parts[index]
        reason, rings = ring_diagnostics(part)
        print(f"  [RINGS] component={index} reason={reason} "
              f"holes={len(part.interiors)} vertices={sum(r[1] for r in rings)}")
        for ring_name, vertices, duplicates, simple in rings[:8]:
            print(f"    [RING] {ring_name} vertices={vertices} duplicates={duplicates} simple={simple}")
        geographic_component_diagnostic(cur, part, index)
        topology_component_diagnostic(cur, original, index, label)
        if label == "united-states/portland/Pleasant Valley":
            contact_fusion_diagnostic(cur, original, index, label)
            contour_reconstruction_diagnostic(cur, original, index, label)
            triangle_partition_diagnostic(cur, original, index, label)
        viable = []
        tested = 0
        from itertools import chain
        variants = chain(dimensional_variants(part), local_ring_variants(part), vertex_variants(part))
        for method, candidate in variants:
            tested += 1
            if candidate.geom_type != "Polygon":
                print(f"  [SKIP] component={index} method={method}: changes component count")
                continue
            delta = abs(candidate.area - part.area) / part.area if part.area > 0 else float("inf")
            if delta > max_delta:
                continue
            if snowflake_valid(cur, candidate):
                if method.endswith("_diagnostic_only"):
                    print(f"  [TRIANGLE] component={index} {method} accepted separately; "
                          "not eligible for replacement")
                    continue
                viable.append((method, candidate, delta))
                print(f"  [CANDIDATE] component={index} method={method} area_delta={delta:.8%}")
                if len(viable) >= 12:
                    break
        if not viable:
            print(f"  [UNRESOLVED] component={index}: {tested} local variants tested")
        else:
            replacements[index] = viable[:12]
    if len(replacements) != len(bad):
        partitioned = generic_exact_partition_repair(cur, original, label)
        if partitioned is not None:
            return partitioned
        print(f"  [REPAIR TEST] {label}: unresolved_components={sorted(set(bad)-set(replacements))}")
        return None
    attempts = 0
    for combination in product(*(replacements[i] for i in bad)):
        attempts += 1
        if attempts > 144:
            print("  [LIMIT] Maximum 144 assembled combinations")
            break
        newparts = parts.copy()
        for i, (_, candidate, _) in zip(bad, combination):
            newparts[i] = candidate
        assembled = MultiPolygon(newparts) if len(newparts) > 1 else newparts[0]
        if not assembled.is_valid:
            continue
        delta = abs(assembled.area - original.area) / original.area if original.area else float("inf")
        if delta > max_delta:
            continue
        if snowflake_valid(cur, assembled):
            methods = {i: item[0] for i, item in zip(bad, combination)}
            print(f"  [FIXED] {label}: methods={methods} area_delta={delta:.8%}")
            return assembled
    print(f"  [UNRESOLVED] {label}: no Snowflake-valid complete geometry ({attempts} attempts)")
    return None


def diagnose_components(conn, session, sources, names, report_path, max_area_change):
    """Read-only topology and local-ring diagnosis; never updates REF."""
    rows = []
    cur = conn.cursor()
    cur.execute("CREATE OR REPLACE TEMPORARY TABLE WORLD_GEO_DIAG ("
                "TARGET VARCHAR, COMPONENT_INDEX NUMBER, GEOJSON VARCHAR)")
    for (country, city), area_name in DIAGNOSTIC_TARGETS.items():
        if area_name not in names[(country, city)]:
            raise RuntimeError(f"Missing FCT neighbourhood: {country}/{city}/{area_name}")
        url = sources[(country, city)]
        response = session.get(url, timeout=(20, 120))
        response.raise_for_status()
        payload = response.json()
        if payload.get("type") != "FeatureCollection":
            raise ValueError(f"Invalid GeoJSON for {country}/{city}")
        polys = []
        rejected = []
        for index, feature in enumerate(payload.get("features", [])):
            if (feature.get("properties") or {}).get("neighbourhood") != area_name:
                continue
            try:
                poly, _, _ = repair_polygon(feature["geometry"], max_area_change)
                polys.append(poly)
            except Exception as exc:
                rejected.append((index, str(exc)))
        if not polys:
            raise RuntimeError(f"No usable polygons: {country}/{city}/{area_name}")
        combined = unary_union(polys) if len(polys) > 1 else polys[0]
        if not combined.is_valid:
            combined = make_valid(combined)
        combined = polygon_only(combined)
        if combined is None or combined.is_empty or not combined.is_valid:
            raise RuntimeError(f"Invalid combined polygon: {country}/{city}/{area_name}")
        parts = list(combined.geoms) if isinstance(combined, MultiPolygon) else [combined]
        target = f"{country}/{city}/{area_name}"
        cur.execute("DELETE FROM WORLD_GEO_DIAG")
        batch = [
            (target, idx, json.dumps(mapping(part), separators=(",", ":")))
            for idx, part in enumerate(parts)
        ]
        cur.executemany("INSERT INTO WORLD_GEO_DIAG VALUES (%s,%s,%s)", batch)
        cur.execute("""SELECT COMPONENT_INDEX, LENGTH(GEOJSON),
                             TRY_TO_GEOGRAPHY(GEOJSON) IS NOT NULL
                       FROM WORLD_GEO_DIAG ORDER BY COMPONENT_INDEX""")
        component_results = cur.fetchall()
        invalid_indices = []
        for idx, length, valid in component_results:
            status = "VALID" if valid else "INVALID"
            if not valid:
                invalid_indices.append(idx)
            rows.append((country, city, area_name, idx, status, length,
                         f"area={parts[idx].area:.15g};bounds={parts[idx].bounds}"))
        full_json = json.dumps(mapping(combined), separators=(",", ":"))
        cur.execute("SELECT TRY_TO_GEOGRAPHY(%s) IS NOT NULL", (full_json,))
        whole_valid = cur.fetchone()[0]
        print(f"[DIAG] {target}: components={len(parts)} "
              f"individually_invalid={len(invalid_indices)} "
              f"whole_valid={whole_valid} rejected_features={len(rejected)}")
        print(f"       invalid component indices (first 30): {invalid_indices[:30]}")
        if not invalid_indices and not whole_valid:
            print("       [INTERACTION] Components individually valid but combined "
                  "geography invalid; investigate geodesic overlaps/ring orientation.")
        if invalid_indices:
            repaired = targeted_repair(cur, combined, target)
            print(f"       [REPAIR TEST] whole_valid_after={bool(repaired is not None)}")
        if rejected:
            print(f"       rejected feature examples: {rejected[:5]}")
    write_csv(report_path,
              ("source_country", "source_city", "area_name", "component_index",
               "snowflake_status", "geojson_length", "geometry_details"), rows)
    print(f"[DIAG REPORT] {report_path} ({len(rows)} components)")
    print("[READ-ONLY] Permanent reference table unchanged; no repair applied.")
    return 0


def main():

    parser = argparse.ArgumentParser(description=__doc__)

    mode = parser.add_mutually_exclusive_group(required=True)

    mode.add_argument("--validate", action="store_true")

    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--diagnose", action="store_true", help="Read-only targeted Snowflake component diagnosis")

    parser.add_argument("--diagnostic-report", type=Path, default=Path("geojson_world_component_diagnostic.csv"))
    parser.add_argument("--inventory", type=Path, default=Path("geojson_world_matching.csv"),
                        help="Optional CSV fallback for destinations missing from live catalog")
    parser.add_argument("--catalog-url", default=CATALOG_URL,
                        help="Inside Airbnb Gatsby catalog endpoint")
    parser.add_argument("--incremental", action="store_true",
                        help="Skip destinations with all named FCT areas already in reference; does not detect geometry changes")
    parser.add_argument("--inventory-only", action="store_true",
                        help="Disable live discovery (useful for regression and controlled tests)")

    parser.add_argument("--report", type=Path, default=Path("geojson_world_load_report.csv"))

    parser.add_argument("--issues-report", type=Path, default=Path("geojson_world_geometry_issues.csv"))

    parser.add_argument("--quarantine-report", type=Path, default=Path("geojson_world_quarantine.csv"))
    parser.add_argument("--run-summary", type=Path, default=Path("geojson_world_run_summary.json"))
    parser.add_argument("--fail-on-quarantine", action="store_true",
                        help="Block the entire load if any expected neighbourhood is unresolved")
    parser.add_argument("--max-area-change", type=float, default=0.01,

                        help="Maximum relative planar area change per repaired feature (default: 1%%)")

    args = parser.parse_args()

    if not 0 <= args.max_area_change <= 1:

        parser.error("--max-area-change must be between 0 and 1")



    db = identifier(os.getenv("SNOWFLAKE_DATABASE", ""), "database")

    schema = identifier(os.getenv("SNOWFLAKE_MARTS_SCHEMA", ""), "schema")

    fct = f"{db}.{schema}.FCT_LISTING_SNAPSHOT"

    ref = f"{db}.{schema}.REF_GEOGRAPHIC_AREAS"

    csv_sources = inventory(args.inventory) if args.inventory.exists() else {}
    if args.inventory_only and not csv_sources:
        raise RuntimeError("--inventory-only requires a readable non-empty inventory")



    report, issues, candidates = [], [], []
    quarantine = []

    stats = Counter()

    conn = connect()

    session = requests.Session()
    catalog_sources, catalog_error = {}, None
    if not args.inventory_only:
        try:
            catalog_sources = discover_catalog(session, args.catalog_url)
            print(f"[CATALOG] discovered={len(catalog_sources)} destinations")
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            catalog_error = str(exc)
            print(f"[CATALOG WARNING] {catalog_error}; using inventory fallback where available", file=sys.stderr)

    try:

        cur = conn.cursor()

        cur.execute(f"SELECT SOURCE_COUNTRY, SOURCE_CITY, NEIGHBOURHOOD FROM {fct} GROUP BY 1,2,3")

        names = defaultdict(set)

        destinations = set()

        for country, city, name in cur:

            destinations.add((country, city))

            if isinstance(name, str) and name.strip():

                names[(country, city)].add(name)

        sources, source_origin, absent_sources = resolve_sources(
            destinations, csv_sources, catalog_sources, catalog_error)
        for (country, city), reason in sorted(absent_sources.items()):
            for area in sorted(names[(country, city)]):
                quarantine.append((country, city, area, "SOURCE_UNAVAILABLE", reason))
        print(f"[DISCOVERY] fct={len(destinations)} resolved={len(sources)} "
              f"catalog={sum(v == 'CATALOG' for v in source_origin.values())} "
              f"fallback={sum(v == 'INVENTORY_FALLBACK' for v in source_origin.values())} "
              f"unresolved={len(absent_sources)}")

        for country, city in sorted(destinations):
            if source_origin.get((country, city)) == "INVENTORY_FALLBACK":
                reason = ("not present in unambiguous catalog results" if catalog_error is None
                          else "catalog unavailable: " + str(catalog_error))
                print(f"[FALLBACK] {country}/{city}: {reason}; inventory_url={sources[(country, city)]}")
        for (country, city), reason in sorted(absent_sources.items()):
            print(f"[UNRESOLVED] {country}/{city}: {reason}")

        cur.execute(f"SELECT SOURCE_COUNTRY, SOURCE_CITY, AREA_NAME FROM {ref}")

        existing = {(country, city, name) for country, city, name in cur}

        print(f"[INFO] World destinations={len(sources)} existing reference keys={len(existing)}")
        if args.diagnose:
            return diagnose_components(conn, session, sources, names,
                                       args.diagnostic_report, args.max_area_change)



        incremental_skipped = 0
        incremental_checked = 0
        if args.incremental:
            print("[INCREMENTAL] Enabled: existing area keys are treated as complete; geometry updates will NOT be detected")
        for i, ((country, city), url) in enumerate(sorted(sources.items()), 1):
            if args.incremental and not args.diagnose:
                expected_keys = names[(country, city)]
                if destination_complete(country, city, expected_keys, existing):
                    incremental_skipped += 1
                    print(f"[{i:3}/{len(sources)}] {country}/{city}: SKIPPED_COMPLETE areas={len(expected_keys)}")
                    continue
                incremental_checked += 1


            expected = names[(country, city)]

            groups = defaultdict(list)

            skipped = repaired_count = duplicate_count = 0

            try:

                response = session.get(url, timeout=(20, 120))

                response.raise_for_status()

                payload = response.json()

                if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):

                    raise ValueError("Expected FeatureCollection")

                for feature_index, feature in enumerate(payload["features"]):

                    name = (feature.get("properties") or {}).get("neighbourhood")

                    geom = feature.get("geometry")

                    if not isinstance(name, str) or not name.strip() or not geom:

                        skipped += 1

                        continue

                    if name not in expected:

                        continue

                    try:

                        poly, repaired, delta = repair_polygon(geom, args.max_area_change)

                        groups[name].append(poly)

                        if repaired:

                            repaired_count += 1

                            issues.append((country, city, name, feature_index, "REPAIRED", f"area_change={delta:.8%}"))

                    except Exception as exc:

                        issues.append((country, city, name, feature_index, "REJECTED", str(exc)))

                missing = expected - set(groups)

                for name in sorted(missing):

                    issues.append((country, city, name, "", "MISSING", "No usable polygon"))
                    if (country, city, name) not in existing:
                        quarantine.append((country, city, name, "MISSING", "No usable polygon"))

                new_count = 0

                for name, polys in groups.items():

                    duplicate_count += len(polys) - 1

                    if (country, city, name) in existing:

                        continue

                    try:

                        combined = unary_union(polys) if len(polys) > 1 else polys[0]

                        if not combined.is_valid:

                            combined = make_valid(combined)

                        combined = polygon_only(combined)

                        if combined is None or not combined.is_valid or combined.is_empty:

                            raise ValueError("Invalid polygon after union")

                        geojson = json.dumps(mapping(combined), ensure_ascii=False, separators=(",", ":"))

                        candidates.append((country, city, area_code(country, city, name), name,

                                           "NEIGHBOURHOOD", geojson, "INSIDE_AIRBNB_GEOJSON"))

                        new_count += 1

                    except Exception as exc:

                        issues.append((country, city, name, "", "REJECTED_UNION", str(exc)))
                        quarantine.append((country, city, name, "REJECTED_UNION", str(exc)))

                report.append((country, city, len(expected), len(groups), new_count, skipped,

                               duplicate_count, repaired_count, len(missing), "OK" if not missing else "MISSING"))

                stats["repaired"] += repaired_count

                stats["skipped"] += skipped

                print(f"[{i:3}/{len(sources)}] {country}/{city}: FCT={len(expected)} matched={len(groups)} new={new_count} repaired={repaired_count} missing={len(missing)}")

            except Exception as exc:

                issues.append((country, city, "", "", "DOWNLOAD_ERROR", str(exc)))

                report.append((country, city, len(expected), 0, 0, 0, 0, 0, len(expected), "ERROR"))

                print(f"[ERROR] {country}/{city}: {exc}", file=sys.stderr)
                for area in sorted(expected):
                    if (country, city, area) not in existing:
                        quarantine.append((country, city, area, "DOWNLOAD_ERROR", str(exc)))



        write_csv(args.report, ("source_country", "source_city", "fct_named_areas", "matched_geojson_areas",

                                "new_candidates", "skipped_features", "duplicate_extra_features",

                                "repaired_features", "missing_areas", "status"), report)

        write_csv(args.issues_report, ("source_country", "source_city", "area_name", "feature_index",

                                       "status", "detail"), issues)

        # Quartiers réellement prêts à être insérés dans Snowflake.

        # On utilise les candidats finaux, après réparation et union,

        # et non simplement les noms présents dans la FCT.

        valid_candidate_keys = {

            (country, city, area_name)

            for country, city, _, area_name, _, _, _ in candidates

        }



        # Les quartiers déjà présents dans le référentiel sont également couverts.

        covered_keys = valid_candidate_keys | existing



        blockers = []



        for issue in issues:

            country, city, area_name, feature_index, status, detail = issue

            key = (country, city, area_name)



            if status == "REPAIRED":

                continue



            if status == "REJECTED" and key in covered_keys:

                # Une autre géométrie valide a été conservée pour ce quartier,

                # ou le quartier dispose déjà d'un polygone de référence.

                continue



            blockers.append(issue)



        # A rejected source feature is nonblocking when another valid feature
        # covers the same neighbourhood. All other unresolved keys are quarantined.
        for country, city, area, _, status, detail in blockers:
            if area and (country, city, area) not in existing:
                quarantine.append((country, city, area, status, detail))
        if blockers:
            print(f"[QUARANTINE] {len(blockers)} unresolved source issues; continuing safe candidates.")
        if args.fail_on_quarantine and quarantine:
            write_csv(args.quarantine_report,
                      ("source_country", "source_city", "area_name", "status", "detail"),
                      sorted(set(quarantine)))
            print("[BLOCKED] --fail-on-quarantine: no permanent changes.", file=sys.stderr)
            return 2


        # Temporary staging is session-scoped; it does not modify the permanent reference table.

        cur.execute("CREATE OR REPLACE TEMPORARY TABLE WORLD_GEO_STAGE ("

                    "SOURCE_COUNTRY VARCHAR, SOURCE_CITY VARCHAR, AREA_CODE VARCHAR, "

                    "AREA_NAME VARCHAR, AREA_LEVEL VARCHAR, GEOJSON VARCHAR, SOURCE VARCHAR)")

        if candidates:

            cur.executemany("INSERT INTO WORLD_GEO_STAGE VALUES (%s,%s,%s,%s,%s,%s,%s)", candidates)

        conn.commit()

        cur.execute("SELECT SOURCE_COUNTRY, SOURCE_CITY, AREA_NAME FROM WORLD_GEO_STAGE "

                    "WHERE TRY_TO_GEOGRAPHY(GEOJSON) IS NULL")

        bad = cur.fetchall()

        if bad:
            print(f"[REPAIR] {len(bad)} Snowflake-invalid neighbourhood geometries")
            for country, city, area_name in bad:
                cur.execute(
                    """SELECT GEOJSON FROM WORLD_GEO_STAGE
                       WHERE SOURCE_COUNTRY=%s AND SOURCE_CITY=%s AND AREA_NAME=%s""",
                    (country, city, area_name),
                )
                geom = shape(json.loads(cur.fetchone()[0]))
                fixed = targeted_repair(cur, geom, f"{country}/{city}/{area_name}")
                if fixed is None:
                    quarantine.append((country, city, area_name, "SNOWFLAKE_INVALID",
                                       "No safe repair found"))
                    cur.execute("DELETE FROM WORLD_GEO_STAGE WHERE SOURCE_COUNTRY=%s AND SOURCE_CITY=%s AND AREA_NAME=%s",
                                (country, city, area_name))
                    print(f"[QUARANTINE] {country}/{city}/{area_name}: no safe repair")
                    continue
                cur.execute(
                    """UPDATE WORLD_GEO_STAGE SET GEOJSON=%s
                       WHERE SOURCE_COUNTRY=%s AND SOURCE_CITY=%s AND AREA_NAME=%s""",
                    (json.dumps(mapping(fixed), ensure_ascii=False, separators=(",", ":")),
                     country, city, area_name),
                )
            cur.execute("SELECT COUNT(*) FROM WORLD_GEO_STAGE WHERE TRY_TO_GEOGRAPHY(GEOJSON) IS NULL")
            if cur.fetchone()[0]:
                raise RuntimeError("Invalid geography remained after targeted repair")
            print("[REPAIR] All repaired neighbourhoods valid in Snowflake.")
        cur.execute(f"SELECT COUNT(*) FROM WORLD_GEO_STAGE s JOIN {ref} r "

                    "ON s.SOURCE_COUNTRY=r.SOURCE_COUNTRY AND s.SOURCE_CITY=r.SOURCE_CITY "

                    "AND s.AREA_NAME=r.AREA_NAME")

        already = cur.fetchone()[0]

        if already:

            print(f"[BLOCKED] {already} candidate keys already exist in reference.", file=sys.stderr)

            return 2

        cur.execute("SELECT COUNT(*) FROM WORLD_GEO_STAGE")
        ready = cur.fetchone()[0]
        quarantine = sorted(set(quarantine))
        write_csv(args.quarantine_report,
                  ("source_country", "source_city", "area_name", "status", "detail"), quarantine)
        summary = {"mode": "validate" if args.validate else "apply",
                   "destinations_in_fct": len(destinations),
                   "destinations_in_inventory": len(csv_sources),
                   "destinations_resolved": len(sources),
                   "destinations_from_catalog": sum(v == "CATALOG" for v in source_origin.values()),
                   "destinations_from_inventory_fallback": sum(v == "INVENTORY_FALLBACK" for v in source_origin.values()),
                   "destinations_unresolved": len(absent_sources),
                   "existing_reference_keys": len(existing),
                   "incremental_enabled": args.incremental,
                   "incremental_skipped_destinations": incremental_skipped,
                   "incremental_checked_destinations": incremental_checked,
                   "candidates_discovered": len(candidates), "candidates_ready": ready,
                   "repaired_features": stats["repaired"],
                   "quarantined_areas": len({(c, t, n) for c, t, n, _, _ in quarantine}),
                   "quarantine_events": len(quarantine)}
        if args.incremental:
            print(f"[INCREMENTAL] skipped={incremental_skipped} checked={incremental_checked}")
        print(f"[VALIDATED] destinations={len(destinations)} candidates_ready={ready} "
              f"repaired_features={stats['repaired']} quarantined={summary['quarantined_areas']} "
              f"existing_reference_keys={len(existing)}")
        print(f"[QUARANTINE REPORT] {args.quarantine_report}")
        if args.fail_on_quarantine and quarantine:
            print("[BLOCKED] --fail-on-quarantine: no permanent changes.", file=sys.stderr)
            return 2

        print(f"[REPORT] {args.report} | {args.issues_report}")

        if args.validate:
            args.run_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print("[READ-ONLY] Reference table unchanged.")

            return 0



        try:

            cur.execute("BEGIN")

            cur.execute(f"""MERGE INTO {ref} r

                USING (SELECT SOURCE_COUNTRY, SOURCE_CITY, AREA_CODE, AREA_NAME,

                              AREA_LEVEL, TO_GEOGRAPHY(GEOJSON) AS GEOMETRY, SOURCE

                       FROM WORLD_GEO_STAGE) s

                ON r.SOURCE_COUNTRY=s.SOURCE_COUNTRY

                   AND r.SOURCE_CITY=s.SOURCE_CITY AND r.AREA_NAME=s.AREA_NAME

                WHEN NOT MATCHED THEN INSERT

                  (SOURCE_COUNTRY, SOURCE_CITY, AREA_CODE, AREA_NAME, AREA_LEVEL, GEOMETRY, SOURCE)

                  VALUES (s.SOURCE_COUNTRY, s.SOURCE_CITY, s.AREA_CODE, s.AREA_NAME,

                          s.AREA_LEVEL, s.GEOMETRY, s.SOURCE)""")

            affected = cur.rowcount

            cur.execute("COMMIT")

            summary["inserted"] = affected
            args.run_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(f"[APPLIED] merged_insert_count={affected}; existing polygons preserved; "
                  f"quarantined={summary['quarantined_areas']}.")

        except Exception:

            cur.execute("ROLLBACK")

            raise

        return 0

    finally:

        session.close()

        conn.close()





if __name__ == "__main__":

    sys.exit(main())
