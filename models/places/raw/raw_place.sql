{# AllThePlaces の日本の施設。GeoJSON の properties（OpenStreetMap のタグ）をそのまま JSON で持つ。
   pipelines/alltheplaces.py が最新の実行から取り出して data/places/place.ndjson に保存する。
   近い場所の行が同じ行グループに入るよう、ヒルベルト曲線の順に並べて書く。 #}

select
    id,
    spider,
    lon,
    lat,
    properties,
    run_id
from read_json(
    'data/places/place.ndjson',
    format = 'newline_delimited',
    columns = {
        'id': 'VARCHAR',
        'spider': 'VARCHAR',
        'lon': 'DOUBLE',
        'lat': 'DOUBLE',
        'properties': 'JSON',
        'run_id': 'VARCHAR'
    }
)
order by st_hilbert(lon, lat, {'min_x': 122.0, 'min_y': 20.0, 'max_x': 154.5, 'max_y': 46.0}::box_2d)
