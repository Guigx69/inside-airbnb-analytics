#!/usr/bin/env python3
"""Read-only comparison of Inside Airbnb GeoJSON with Snowflake FCT neighbourhoods."""
import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
import snowflake.connector

import requests


def canonical(value):
    return unicodedata.normalize('NFC', str(value or '')).strip().casefold()


def slug(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', text.lower())).strip('-')


def connect_snowflake():
    required = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "DBT_SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_MARTS_SCHEMA",
    ]

    missing = [
        name for name in required
        if not os.getenv(name)
    ]

    if missing:
        raise RuntimeError(
            "Variables d'environnement absentes : "
            + ", ".join(missing)
        )

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["DBT_SNOWFLAKE_PASSWORD"],
        authenticator="snowflake",
        role=os.getenv("SNOWFLAKE_ROLE", "DBT_ROLE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "DBT_WH"),
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_MARTS_SCHEMA"],
    )

def read_fct(table):
    # Identifier-only interpolation: never interpolate untrusted SQL fragments.
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', table):
        raise ValueError('Invalid FCT table identifier')
    conn = connect_snowflake()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f'''SELECT SOURCE_COUNTRY, SOURCE_CITY, NEIGHBOURHOOD,
                               COUNT(*) AS OBSERVATIONS
                               FROM {table}
                               WHERE NEIGHBOURHOOD IS NOT NULL
                               GROUP BY 1, 2, 3''')
            return cursor.fetchall()
    finally:
        conn.close()


def fetch_geojson(session, url):
    response = session.get(url, timeout=(15, 120))
    response.raise_for_status()
    obj = response.json()
    if obj.get('type') != 'FeatureCollection' or not isinstance(obj.get('features'), list):
        raise ValueError('Not a GeoJSON FeatureCollection')
    names = []
    invalid = 0
    for feature in obj['features']:
        if not isinstance(feature, dict):
            invalid += 1
            continue
        geometry = feature.get('geometry') or {}
        if geometry.get('type') not in ('Polygon', 'MultiPolygon') or not geometry.get('coordinates'):
            invalid += 1
        props = feature.get('properties') or {}
        name = props.get('neighbourhood')
        if not isinstance(name, str) or not name.strip():
            invalid += 1
        else:
            names.append(name)
    return names, len(obj['features']), invalid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=Path('geojson_world_inventory.csv'))
    parser.add_argument('--output', type=Path, default=Path('geojson_world_matching.csv'))
    parser.add_argument('--fct-table', default='FCT_LISTING_SNAPSHOT')
    parser.add_argument('--limit', type=int, default=0, help='Test first N destinations (0 = all)')
    args = parser.parse_args()
    with args.inventory.open(encoding='utf-8-sig', newline='') as handle:
        inventory = list(csv.DictReader(handle))
    if not inventory:
        raise RuntimeError('Inventory is empty')
    fct = defaultdict(lambda: defaultdict(int))
    fct_destinations = set()
    for country, city, name, observations in read_fct(args.fct_table):
        key = (slug(country), slug(city))
        fct_destinations.add(key)
        fct[key][canonical(name)] += int(observations)
    print(f'[INFO] FCT destinations: {len(fct_destinations)}', flush=True)
    session = requests.Session()
    session.headers['User-Agent'] = 'inside-airbnb-analytics/1.0 (read-only geojson audit)'
    rows = []
    inventory_keys = set()
    selected = inventory[:args.limit] if args.limit else inventory
    for index, item in enumerate(selected, 1):
        key = (slug(item['source_country']), slug(item['source_city']))
        inventory_keys.add(key)
        fct_names = fct.get(key, {})
        row = {
            'source_country': item['source_country'],
            'source_city': item['source_city'],
            'snapshot_date': item['snapshot_date'],
            'in_fct': int(key in fct_destinations),
            'fct_neighbourhoods': len(fct_names),
            'geojson_features': 0,
            'geojson_neighbourhoods': 0,
            'matched': 0,
            'missing': len(fct_names),
            'coverage_pct': 0.0,
            'observation_coverage_pct': 0.0,
            'duplicate_geojson_names': 0,
            'invalid_features': 0,
            'missing_examples': '',
            'status': 'ERROR',
            'error': '',
            'url': item['url'],
        }
        try:
            names, count, invalid = fetch_geojson(session, item['url'])
            geo_counts = Counter(canonical(name) for name in names)
            geo_names = set(geo_counts)
            matches = set(fct_names) & geo_names
            missing = set(fct_names) - geo_names
            total_observations = sum(fct_names.values())
            covered_observations = sum(fct_names[name] for name in matches)
            row.update({
                'geojson_features': count,
                'geojson_neighbourhoods': len(geo_names),
                'matched': len(matches),
                'missing': len(missing),
                'coverage_pct': round(100 * len(matches) / len(fct_names), 2) if fct_names else 0.0,
                'observation_coverage_pct': round(100 * covered_observations / total_observations, 2) if total_observations else 0.0,
                'duplicate_geojson_names': sum(n - 1 for n in geo_counts.values() if n > 1),
                'invalid_features': invalid,
                'missing_examples': ' | '.join(sorted(missing)[:8]),
                'status': 'OK' if not invalid else 'INVALID_FEATURES',
            })
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'[:300]
        rows.append(row)
        print(f"[{index:3}/{len(selected)}] {key[0]}/{key[1]} "
              f"FCT={row['fct_neighbourhoods']} GEO={row['geojson_neighbourhoods']} "
              f"MATCH={row['matched']} COVER={row['coverage_pct']}% {row['status']}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print('\n=== WORLD MATCHING ===')
    print('Catalog destinations audited:', len(rows))
    print('Catalog destinations present in FCT:', sum(r['in_fct'] for r in rows))
    print('FCT destinations absent from audited catalog:', len(fct_destinations - inventory_keys))
    if fct_destinations - inventory_keys:
        print('Absent:', ', '.join('/'.join(key) for key in sorted(fct_destinations - inventory_keys)))
    print('Exact-name matched neighbourhoods:', sum(r['matched'] for r in rows))
    print('FCT neighbourhoods:', sum(r['fct_neighbourhoods'] for r in rows))
    print('GeoJSON duplicate-name extra features:', sum(r['duplicate_geojson_names'] for r in rows))
    print('GeoJSON invalid features:', sum(r['invalid_features'] for r in rows))
    print('Failed downloads/parses:', sum(r['status'] == 'ERROR' for r in rows))
    print('CSV:', args.output.resolve())
    print('[READ-ONLY] Snowflake data unchanged.')
    return 0 if all(r['status'] == 'OK' for r in rows) else 1


if __name__ == '__main__':
    sys.exit(main())