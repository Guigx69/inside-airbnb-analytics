# Qualité des données — couverture calendrier/annonces

## Diagnostic confirmé le 08/10/2026

Le test dbt `tests/assert_stg_calendar_listing_exists.sql` identifie les clés distinctes `(source_country, source_city, snapshot_date, listing_id)` présentes dans `stg_calendar`, mais absentes de `stg_listings` au même snapshot.

Résultats observés dans l'environnement Snowflake existant :

- **3 163 clés calendrier/annonce sans correspondance**.
- **0** de ces clés retrouvées dans `AIRBNB.RAW.RAW_LISTINGS` avec les mêmes pays, ville, date et identifiant numérique.
- Les **3 163** sont absentes de `RAW_LISTINGS`.
- Le test dbt conserve volontairement la sévérité `warn`. Ne pas masquer l'avertissement ni inventer des annonces pour obtenir une suite entièrement verte.

L'écart est déjà présent au niveau RAW, et non uniquement introduit par la transformation `stg_listings`. Sa cause exacte en amont (exports source, décalage temporel ou couverture incomplète) **n'est pas établie**.

## Conséquences

Les lignes de calendrier sans annonce correspondante ne possèdent pas d'attributs d'annonce vérifiables. Une jointure interne entre calendrier et annonces exclut ces clés : certaines mesures peuvent donc couvrir moins d'observations que le calendrier RAW. Vérifier chaque métrique en aval avant de quantifier l'impact.

## Reproduire le diagnostic — lecture seule

```sql
WITH orphan_calendar AS (
    SELECT DISTINCT c.source_country, c.source_city, c.snapshot_date, c.listing_id
    FROM AIRBNB.DBT_GGILLET_STAGING.STG_CALENDAR c
    LEFT JOIN AIRBNB.DBT_GGILLET_STAGING.STG_LISTINGS l
      ON c.source_country = l.source_country
     AND c.source_city = l.source_city
     AND c.snapshot_date = l.snapshot_date
     AND c.listing_id = l.listing_id
    WHERE l.listing_id IS NULL
),
raw_listing_keys AS (
    SELECT DISTINCT source_country, source_city, snapshot_date,
           TRY_TO_NUMBER(raw_data:id::VARCHAR) AS listing_id
    FROM AIRBNB.RAW.RAW_LISTINGS
)
SELECT COUNT(*) AS total_orphan_listings,
       COUNT_IF(r.listing_id IS NOT NULL) AS found_in_raw,
       COUNT_IF(r.listing_id IS NULL) AS absent_from_raw
FROM orphan_calendar o
LEFT JOIN raw_listing_keys r
  ON o.source_country = r.source_country
 AND o.source_city = r.source_city
 AND o.snapshot_date = r.snapshot_date
 AND o.listing_id = r.listing_id;
```

Adapter les identifiants de base et de schéma pour un autre compte. Cette requête peut analyser un grand volume RAW et entraîner des coûts Snowflake.

## État des vérifications

`dbt parse`, `dbt compile` et `dbt test --threads 4` ont été exécutés dans un environnement Snowflake existant, avec un avertissement sur cette relation. Cela **ne démontre pas** qu'un compte neuf peut reconstruire automatiquement les données historiques. L'approvisionnement du compte, la récupération des archives et la reconstruction de bout en bout restent à valider.
