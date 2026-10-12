"""Tests hors ligne de découverte V14.2. Aucun accès réseau ou Snowflake, aucune écriture permanente."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

path = Path(__file__).resolve().parent.parent / 'snowflake' / 'reference' / 'load_world_geographic_areas.py'
if not path.is_file():
    raise FileNotFoundError(f'Chargeur introuvable : {path}')
spec = importlib.util.spec_from_file_location('geo_v143', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def catalog(rows):
    response = Mock()
    response.json.return_value = {'nodes': rows}
    session = Mock()
    session.get.return_value = response
    return mod.discover_catalog(session)

def row(country, city, date, region='region', host='data.insideairbnb.com'):
    return {'dataRoot': f'https://{host}/{country}/{region}/{city}', 'publishDate': date}

old = row('france', 'paris', '2024-01-01')
new = row('france', 'paris', '2026-09-01')
result = catalog([old, new, old, row('test', 'new-city', '2026-09-30'), row('evil', 'fake', '2026-09-30', host='evil.example')])
assert len(result) == 2 and '/2026-09-01/' in result[('france', 'paris')]
print('[RÉUSSI] historiques : la publication récente prévaut ; doublons et hôtes non sûrs ignorés')

result = catalog([row('france','paris','2026-09-01'), row('france','paris','2026-09-01',region='different'), row('test','new-city','2026-09-30')])
assert ('france','paris') not in result and ('test','new-city') in result
resolved, origin, missing = mod.resolve_sources({('france','paris'),('test','new-city')}, {('france','paris'):'csv-url'}, result)
assert not missing and origin[('france','paris')] == 'INVENTORY_FALLBACK' and origin[('test','new-city')] == 'CATALOG'
print('[RÉUSSI] conflit réel de date récente isolé ; repli CSV par destination')

try:
    catalog([row('evil','fake','2026-09-30',host='evil.example')])
except RuntimeError:
    print('[RÉUSSI] le catalogue inutilisable entraîne un refus sécurisé')
else:
    raise AssertionError('catalogue inutilisable accepté')
print('[RÉUSSI] trois scénarios V14.2 hors ligne ; aucune écriture permanente')

# Décisions de complétude incrémentale (sans appel à la base ni requête HTTP).
assert mod.destination_complete('france', 'paris', {'A','B'}, {('france','paris','A'),('france','paris','B')})
assert not mod.destination_complete('france', 'paris', {'A','B'}, {('france','paris','A')})
assert not mod.destination_complete('france', 'paris', set(), set())
assert not mod.destination_complete('france', 'paris', {'A'}, {('france','lyon','A')})
print('[RÉUSSI] complétude incrémentale : cas complets, manquants, vides et inter-villes')

# Clés de destination Unicode : les URL conservent l'orthographe source d'origine.
result = catalog([
    row('brazil', 'são-paulo', '2026-06-14', region='sp'),
    row('colombia', 'bogotá', '2026-06-21', region='dc'),
])
assert ('brazil', 'sao-paulo') in result
assert ('colombia', 'bogota') in result
assert '/são-paulo/' in result[('brazil', 'sao-paulo')]
assert '/bogotá/' in result[('colombia', 'bogota')]
print('[RÉUSSI] São Paulo et Bogotá associés aux identifiants ASCII de FCT')

result = catalog([
    row('brazil', 's%C3%A3o-paulo', '2026-06-14', region='sp'),
    row('colombia', 'bogot%C3%A1', '2026-06-21', region='dc'),
])
assert ('brazil', 'sao-paulo') in result and ('colombia', 'bogota') in result
print('[RÉUSSI] chemins de destinations Unicode encodés en pourcentage correctement associés')