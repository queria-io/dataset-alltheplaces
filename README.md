## データ出典

[AllThePlaces](https://www.alltheplaces.xyz/) が公開している施設データのうち、日本の施設です。

AllThePlaces は、チェーンごとのスパイダー（各社の公式サイトの店舗検索を読むプログラム）を有志が書き、毎週すべてを実行して結果を配布しているオープンソースのプロジェクトです。元のデータは各社が公式サイトに掲載している店舗情報なので、チェーンの店舗はブランドごとに公式の店舗一覧とほぼ同じ件数がそろいます。

このデータセットは、最新の実行から次の施設を取り出しています。

- 日本向けのスパイダー（名前が `_jp` で終わるもの）の全件
- 複数の国を回るスパイダー（ユニクロ、サイゼリヤ、ツルハドラッグなど）のうち、国コードが JP の施設

全国で約84万件、スパイダーは約270、ブランドは約390です。

## スキーマ: places

### テーブル: place

1行が1施設です。

- place_id: 施設 ID（VARCHAR、spider と AllThePlaces の ID を / でつないだもの。この表で一意）
- spider: スパイダー名（VARCHAR、seven_eleven_jp など）
- brand: ブランド（VARCHAR、brand:ja、無ければ brand。チェーンに属さない施設は NULL）
- brand_en: ブランドの英語名（VARCHAR、brand:en）
- brand_wikidata: ブランドの Wikidata ID（VARCHAR、セブン-イレブンは Q259340）
- name: 名称（VARCHAR、ブランド名だけのことが多い）
- branch: 店舗名（VARCHAR、「日野駅前店」など）
- ref: 店舗番号（VARCHAR、各社が振る店舗コード）
- category_key / category: 施設の種類（VARCHAR、OpenStreetMap のタグのキーと値。shop / convenience、amenity / fast_food など）
- is_unattended: 無人の設備か（BOOLEAN）
- address: 住所（VARCHAR、表記はスパイダーごとに揃っていない）
- postcode / province / city: 郵便番号・都道府県・市区町村（VARCHAR、都道府県と市区町村は入っていないスパイダーが多い）
- phone: 電話番号（VARCHAR）
- website: 店舗ページ（VARCHAR）
- opening_hours: 営業時間（VARCHAR、OpenStreetMap の opening_hours の書式）
- operator: 運営者（VARCHAR）
- lat / lon: 緯度・経度（DOUBLE）
- geometry: 位置（GEOMETRY、POINT）
- run_id / run_date: 取り込んだ実行の ID と開始日（VARCHAR / DATE）

自動販売機・郵便ポスト・ATM・公衆電話・AED・シェアサイクルのポート・駐輪場・駐車場・証明写真機・宅配ロッカー・コインロッカー・充電スタンドは is_unattended が true で、全体の約7割（約60万件）を占めます。店舗として数えるときは `WHERE NOT is_unattended` で除いてください。残る約24万件の上位は、コンビニ（shop=convenience、約5.7万）、郵便局（約2.9万）、薬局（約2.2万）、ファストフード（約1.9万）、ガソリンスタンド（約1.8万）、ドラッグストア（shop=chemist、約1.2万）です。

個人店はほとんど収録されません。調剤薬局のように、チェーンの店舗検索に系列外の店舗が載っている場合だけ入ります。同じ店舗が複数のスパイダーから入ることがあり（コンビニとその中の銀行 ATM など）、その場合は別の行になります。

### テーブル: raw_place

place と同じ施設を、AllThePlaces の GeoJSON の properties（OpenStreetMap のタグ）のまま JSON で持ちます。取扱商品・設備・決済手段・言語別の名前など、place に無いタグはここにあります。

- id: AllThePlaces の ID（VARCHAR、spider と組で一意）
- spider: スパイダー名（VARCHAR）
- lon / lat: 経度・緯度（DOUBLE）
- properties: タグ（JSON）
- run_id: 取り込んだ実行の ID（VARCHAR）

## データ更新手順

main.py が AllThePlaces の[最新の実行](https://data.alltheplaces.xyz/runs/latest.json)を調べ、配布 zip（全世界で約2.7GB）のうち日本の施設を持つスパイダーのファイルだけを HTTP の Range で取ります（約130MB）。複数の国を回るスパイダーのうち日本の施設を持つものは、実行の統計（`stats/_insights.json`）から選びます。そのあと dbt build で各テーブルを作り直します。ビルドは `bash scripts/build.sh` で実行します（Queria に公開する）。

取り込みでは次のものを除いています。

- 国コードが JP 以外の施設（日本向けのスパイダーに混ざる国外の店舗、数十件）
- 位置が点でない施設（座標の無いものなど、約1,200件）
- 座標が日本の外接矩形から外れる施設（数十件）
- 同じスパイダーが同じ ID で2回出した施設の2件目（数件）
- 取得元の API の URL（@source_uri タグ）。サイトに埋め込まれた API キーを含むことがあるため

AllThePlaces は毎週土曜に実行を始め、配布物がそろうのは水曜ごろです。Sync は毎週金曜 04:00（JST）に取り直します。

## ライセンス

AllThePlaces のデータは [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) で提供されています。スパイダーのソースコードは [MIT ライセンス](https://github.com/alltheplaces/alltheplaces/blob/master/LICENSE)です。

出典:
[AllThePlaces](https://www.alltheplaces.xyz/)。元のデータは各社が公式サイトに掲載している店舗情報です。

日本の施設の取り出しと、タグを列に平坦化する加工を行っています。
