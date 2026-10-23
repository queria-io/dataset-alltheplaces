-- 大手コンビニ3社は全国で1万店を超える。下回れば、スパイダーのファイルを取り損ねたか、
-- 相手のサイトの変更でスパイダーが壊れている。部分的な取得で公開しないための検査。
WITH expected(spider) AS (
    VALUES ('seven_eleven_jp'), ('familymart_jp'), ('lawson_jp')
)
SELECT e.spider, count(p.place_id) AS n
FROM expected AS e
LEFT JOIN {{ ref('place') }} AS p ON p.spider = e.spider
GROUP BY e.spider
HAVING count(p.place_id) < 10000
