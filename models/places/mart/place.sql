{# raw_place のタグを平坦化した日本の施設。列の選び方は place.table.yml。 #}

with tagged as (
    select
        *,
        -- OpenStreetMap で施設の種類を表す主なキー。先に見つかったものを種類とする
        case
            when properties->>'shop' is not null then 'shop'
            when properties->>'amenity' is not null then 'amenity'
            when properties->>'leisure' is not null then 'leisure'
            when properties->>'tourism' is not null then 'tourism'
            when properties->>'office' is not null then 'office'
            when properties->>'healthcare' is not null then 'healthcare'
            when properties->>'craft' is not null then 'craft'
            when properties->>'emergency' is not null then 'emergency'
        end as category_key,
        -- addr:state に都道府県を入れるスパイダーもある。番号を入れるもの（nissan）は使わない
        coalesce(
            properties->>'addr:province',
            case
                when regexp_matches(properties->>'addr:state', '[都道府県]$')
                    then properties->>'addr:state'
            end
        ) as province
    from {{ ref('raw_place') }}
)

select
    spider || '/' || id as place_id,
    spider,
    coalesce(properties->>'brand:ja', properties->>'brand') as brand,
    properties->>'brand:en' as brand_en,
    properties->>'brand:wikidata' as brand_wikidata,
    coalesce(properties->>'name:ja', properties->>'name') as name,
    coalesce(properties->>'branch:ja', properties->>'branch') as branch,
    properties->>'ref' as ref,
    category_key,
    properties->>category_key as category,
    -- 無人の設備。店舗として数えるときは除く
    coalesce(category_key || '=' || (properties->>category_key) in (
        'amenity=vending_machine',
        'amenity=post_box',
        'amenity=atm',
        'amenity=telephone',
        'emergency=defibrillator',
        'amenity=bicycle_rental',
        'amenity=bicycle_parking',
        'amenity=parking',
        'amenity=photo_booth',
        'amenity=parcel_locker',
        'amenity=luggage_locker',
        'amenity=charging_station'
    ), false) as is_unattended,
    coalesce(
        properties->>'addr:full',
        nullif(concat_ws(' ',
            province,
            properties->>'addr:city',
            properties->>'addr:street_address'
        ), '')
    ) as address,
    properties->>'addr:postcode' as postcode,
    province,
    properties->>'addr:city' as city,
    properties->>'phone' as phone,
    properties->>'website' as website,
    properties->>'opening_hours' as opening_hours,
    coalesce(properties->>'operator:ja', properties->>'operator') as operator,
    lat,
    lon,
    st_point(lon, lat) as geometry,
    run_id,
    cast(strptime(left(run_id, 10), '%Y-%m-%d') as date) as run_date
from tagged
