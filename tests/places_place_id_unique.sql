-- place_id は spider と AllThePlaces の ID の組。重なればスパイダーの取り込みを二重にしている。
SELECT place_id, count(*) AS n
FROM {{ ref('place') }}
GROUP BY place_id
HAVING count(*) > 1
