select
    source_country,
    source_city,
    snapshot_date,
    price_band,
    price_band_order

from {{ ref('mart_price_distribution_snapshot') }}

where
    case price_band
        when 'NO_PRICE'      then 0
        when '01_<50'        then 1
        when '02_50_99'      then 2
        when '03_100_149'    then 3
        when '04_150_199'    then 4
        when '05_200_299'    then 5
        when '06_300_PLUS'   then 6
        else -1
    end <> price_band_order