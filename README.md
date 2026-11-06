# AllThePlaces 日本の施設

チェーン店・郵便局・ATM・自動販売機など、全国約 84 万件の施設の位置を、SQL で集計・地図表示できるテーブルにしたデータセットです。コンビニ・ドラッグストア・ファストフード・ガソリンスタンド・携帯ショップなど、チェーンの店舗はブランドごとに公式の店舗一覧とほぼ同じ件数があります。

## 出典と利用条件

[AllThePlaces](https://www.alltheplaces.xyz/) が公開している施設データのうち、日本の施設を加工しています。AllThePlaces は、チェーンごとのスパイダー（各社の公式サイトの店舗検索を読むプログラム）を有志が書き、毎週すべてを実行して結果を配布しているオープンソースのプロジェクトです。元のデータは各社が公式サイトに掲載している店舗情報です。

- データは [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) で提供されています。スパイダーのソースコードは [MIT ライセンス](https://github.com/alltheplaces/alltheplaces/blob/master/LICENSE)です
- Queria は、日本の施設の取り出しと、タグを列に平坦化する加工を行っています

最新の実行から、次の施設を取り出しています。全国で約 84 万件、スパイダーは約 270、ブランドは約 390 です。

- 日本向けのスパイダー（名前が `_jp` で終わるもの）の全件
- 複数の国を回るスパイダー（ユニクロ、サイゼリヤ、ツルハドラッグなど）のうち、国コードが JP の施設

## テーブル

| テーブル | 内容 |
| --- | --- |
| `places.place` | 1 行が 1 施設。ブランド（名前と Wikidata ID）、店舗名、店舗番号、施設の種類、住所、電話番号、営業時間、位置 |
| `places.raw_place` | `place` と同じ施設を、OpenStreetMap のタグのまま JSON で持つ |

## 使い方

無人の設備を除いて、施設の種類ごとに数える:

```sql
SELECT category_key, category, count(*) AS places
FROM alltheplaces.places.place
WHERE NOT is_unattended
GROUP BY ALL
ORDER BY places DESC
LIMIT 10;
```

## 収録範囲の注意

- 自動販売機・郵便ポスト・ATM・公衆電話・AED・シェアサイクルのポート・駐輪場・駐車場・証明写真機・宅配ロッカー・コインロッカー・充電スタンドは `is_unattended` が true で、全体の約 7 割（約 60 万件）を占めます。店舗として数えるときは `WHERE NOT is_unattended` で除いてください
- 残る約 24 万件の上位は、コンビニ（shop=convenience、約 5.7 万）、郵便局（約 2.9 万）、薬局（約 2.2 万）、ファストフード（約 1.9 万）、ガソリンスタンド（約 1.8 万）、ドラッグストア（shop=chemist、約 1.2 万）です
- 個人店はほとんど収録されていません。調剤薬局のように、チェーンの店舗検索に系列外の店舗が載っている場合だけ入ります
- 同じ店舗が複数のスパイダーから入ることがあり（コンビニとその中の銀行 ATM など）、その場合は別の行になります
- 施設の種類は OpenStreetMap のタグのキー（`category_key`: shop / amenity / leisure / tourism / office / healthcare / craft / emergency）と値（`category`）です。どのキーも無い施設は NULL です
- `place_id` は実行をまたいでも同じ施設に同じ値が付くことが多いですが、保証はありません
- 住所の表記はスパイダーごとに統一されていません。都道府県・市区町村の列は入っていないスパイダーが多くあります

取り込みでは次のものを除いています。

- 国コードが JP 以外の施設（日本向けのスパイダーに混ざる国外の店舗、数十件）
- 位置が点でない施設（座標の無いものなど、約 1,200 件）
- 座標が日本の外接矩形から外れる施設（数十件）
- 同じスパイダーが同じ ID で 2 回出した施設の 2 件目（数件）
- 取得元の API の URL（@source_uri タグ）。サイトに埋め込まれた API キーを含むことがあるため

## ビルド

```bash
git submodule update --init
uv sync
bash scripts/build.sh
```

`main.py` が AllThePlaces の[最新の実行](https://data.alltheplaces.xyz/runs/latest.json)を確認し、配布 zip（全世界で約 2.7GB）のうち日本の施設を持つスパイダーのファイルだけを HTTP の Range で取得します（約 130MB）。配信元が Range を無視して全体を返したとき（GitHub Actions のランナーから取得するとこうなります）は、zip 全体を `data/places/output.zip`（約 2.7GB、次の実行で上書き）にダウンロードしてから読みます。複数の国を回るスパイダーのうち日本の施設を持つものは、実行の統計（`stats/_insights.json`）から選びます。そのあと dbt build で各テーブルを作り直します。

AllThePlaces は毎週土曜に実行を始め、配布物がそろうのは水曜ごろです。Sync は毎週金曜 04:00（JST）に取得し直します。
