# V1.3 — Certification des empreintes historiques

## État initial vérifié

- `AIRBNB.RAW.INGESTION_LOG` contient 1 629 entrées historiques.
- `SOURCE_SHA256` est NULL sur les 1 629 entrées.
- Le dry-run du loader trouve 1 629 fichiers dans `data_manifest.csv` et zéro fichier à charger.
- Les inventaires RAW et le journal ont été rapprochés sur les clés de lot et les nombres de lignes.
- Aucun de ces contrôles ne prouve une égalité de contenu.

## Limite cryptographique

Le SHA-256 du manifeste est calculé sur les **octets du fichier CSV.GZ**.
Le loader transforme les lignes CSV en objets JSON avant `COPY INTO`, puis les conserve en `RAW_DATA VARIANT`.
Les octets d'origine (en-têtes, ordre des champs, représentation CSV, compression) ne sont pas préservés dans RAW.
**Il est impossible de reconstruire et de certifier le SHA-256 du CSV.GZ d'origine à partir du seul RAW_DATA.**

Même une comparaison parfaite des lignes normalisées prouve seulement une équivalence logique de contenu,
pas l'identité des octets du fichier CSV.GZ historiquement ingéré.

## Stratégie sûre

1. **Conserver les SHA historiques NULL** jusqu'à ce qu'une preuve indépendante existe.
2. Vérifier la présence, l'unicité et les comptes de lignes du journal contre RAW (déjà fait).
3. Développer un audit **lecture seule** par lot qui compare un multiensemble canonique de lignes
   obtenu depuis le CSV.GZ local au multiensemble de `RAW_DATA` Snowflake.
   La comparaison doit préserver les doublons et le nombre de lignes, et utiliser la même
   sémantique CSV/JSON que `csv_gz_to_json_gz`.
4. Tester l'audit sur quelques lots de tailles différentes (listings, reviews, calendar)
   et évaluer le coût avant une exécution globale.
5. Si le contenu logique correspond, produire un rapport de certification explicite
   (`MATCH`, `MISMATCH`, `UNVERIFIABLE`) avec clé du lot, SHA local, méthode, date et métriques.
6. Ne pas transformer automatiquement un résultat `MATCH` en preuve de l'empreinte
   **historique** du CSV.GZ. Pour un backfill dans `SOURCE_SHA256`, prévoir soit
   une colonne de provenance/statut (`VERIFIED_LOGICAL_EQUIVALENCE` vs `RECORDED_AT_INGESTION`),
   soit un journal de certification distinct.
7. Les nouvelles ingestions enregistrent leur SHA-256 directement au chargement.
8. Les rechargements corrigés devront avoir un protocole de sauvegarde, de vérification,
   de commit et de reprise testé séparément avant activation.

## Règles de sécurité

- Aucune mise à jour massive de `SOURCE_SHA256` depuis le manifeste.
- Aucun `DELETE`, `TRUNCATE`, `COPY INTO` ou `UPDATE` dans un audit de certification.
- Aucun rechargement des 1 629 fichiers pour fabriquer artificiellement une empreinte historique.
- Conserver les données RAW et les alertes de qualité existantes, y compris les orphelins calendar.
- Ne pas toucher au `data_manifest.csv` local non commité.
