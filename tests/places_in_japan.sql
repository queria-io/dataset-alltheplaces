-- 日本の外接矩形（沖ノ鳥島・択捉島・与那国島・南鳥島を含む）から外れる施設は、
-- 国コードの絞り込みが漏れているか、緯度と経度が入れ替わっている。
SELECT place_id, lat, lon
FROM {{ ref('place') }}
WHERE lat NOT BETWEEN 20.0 AND 46.0
   OR lon NOT BETWEEN 122.0 AND 154.5
