"""AllThePlaces の最新の実行から、日本の施設を取り出す。

AllThePlaces はチェーンごとの「スパイダー」が各社公式サイトの店舗検索を読み、
毎週まとめて実行した結果をスパイダーごとの GeoJSON にして1つの zip で配る。
zip は全世界で 3GB 近いので、末尾の目次だけを読み、日本の施設を持つスパイダーの
ファイルだけを HTTP の Range で取る。

日本の施設を持つスパイダーは2種類ある。
- 名前が _jp で終わる日本向けのスパイダー。全件を取る
- 複数の国を回るスパイダー（ユニクロ、サイゼリヤなど）。実行の統計
  （stats/_insights.json）で日本の件数を持つものだけ開き、addr:country が JP の施設を取る

出力: data/places/place.ndjson（1行 = 1施設。GeoJSON の properties を @source_uri 以外そのまま持つ）

データソース: AllThePlaces https://www.alltheplaces.xyz/
"""

import io
import json
import logging
import zipfile
from pathlib import Path

from shared.fetch import RangeFile, RangeNotSupported, download, fetch, replacing

logger = logging.getLogger("pipelines")

USER_AGENT = "dataset-alltheplaces (+https://github.com/queria-io/dataset-alltheplaces)"
LATEST_URL = "https://data.alltheplaces.xyz/runs/latest.json"

OUTPUT_DIR = Path("data/places")

# 日本の外接矩形。端は沖ノ鳥島 北緯 20.42 / 択捉島 北緯 45.55 /
# 与那国島 東経 122.93 / 南鳥島 東経 153.98
JAPAN_BBOX = {"xmin": 122.0, "xmax": 154.5, "ymin": 20.0, "ymax": 46.0}

# スパイダーのファイルは大きいもので数十MBある
REQUEST_TIMEOUT = 120


def _open(url: str) -> bytes:
    return fetch(url, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT)


def latest_run() -> dict:
    run = json.loads(_open(LATEST_URL))
    logger.info("AllThePlaces run %s (%d spiders)", run["run_id"], run["spiders"])
    return run


def japan_spiders(insights_url: str) -> set[str]:
    """実行の統計から、日本の施設を持つスパイダーを集める。"""
    insights = json.loads(_open(insights_url))["data"]
    spiders = set()
    for brand in insights:
        spiders.update((brand.get("atp_splits") or {}).get("JP", {}))
    return spiders


def _open_archive(url: str) -> zipfile.ZipFile:
    """配布 zip を開く。Range が効けば目次と要るメンバーだけを読む。

    配信元（Cloudflare）は、要求を送る場所によって Range を無視して全体を返す
    （手元では 206、GitHub のランナーでは 200 だった）。そのときは全体（約2.7GB）を
    data/places/output.zip に落としてから読む。ファイルは次の実行で上書きする。
    """
    try:
        source = RangeFile(url, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT)
        # 読むたびにバッファの大きさまで先読みする。日本向けのスパイダーのファイルは
        # 9割が 1MB 未満なので、大きく取ると隣のファイルまで取って転送量が数倍になる
        return zipfile.ZipFile(io.BufferedReader(source, 1 << 16))
    except RangeNotSupported as error:
        logger.warning("%s; downloading the whole archive", error)
    path = OUTPUT_DIR / "output.zip"
    size = download(url, path, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT)
    logger.info("downloaded %s (%d bytes)", path, size)
    return zipfile.ZipFile(path)


def _features(archive: zipfile.ZipFile, spider: str) -> list[dict]:
    data = json.loads(archive.read(f"output/{spider}.geojson"))
    return data.get("features") or []


def download_places(run: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "place.ndjson"

    archive = _open_archive(run["output_url"])
    in_archive = {
        Path(name).stem for name in archive.namelist() if name.endswith(".geojson")
    }

    domestic = sorted(name for name in in_archive if name.endswith("_jp"))
    international = sorted(japan_spiders(run["insights_url"]) - set(domestic))
    logger.info("spiders: %d _jp, %d international", len(domestic), len(international))

    rows = 0
    seen: set[tuple[str, str]] = set()
    dropped = {"country": 0, "geometry": 0, "outside": 0, "duplicate": 0}
    # 途中で失敗したときと0件のときは、前回の place.ndjson を残す
    with replacing(output) as partial, partial.open("w", encoding="utf-8") as handle:
        for spider in domestic + international:
            if spider not in in_archive:
                logger.warning("%s: not in archive", spider)
                continue
            is_international = not spider.endswith("_jp")
            kept = 0
            for feature in _features(archive, spider):
                properties = feature.get("properties") or {}
                country = properties.get("addr:country")
                if is_international and country != "JP":
                    continue
                # 日本向けのスパイダーにも国外の店舗が混ざることがある
                if country not in (None, "", "JP"):
                    dropped["country"] += 1
                    continue
                geometry = feature.get("geometry") or {}
                if geometry.get("type") != "Point":
                    dropped["geometry"] += 1
                    continue
                lon, lat = geometry["coordinates"][:2]
                # 国コードが JP でも、座標が国外を指しているものがある（数十件）
                if not (
                    JAPAN_BBOX["xmin"] <= lon <= JAPAN_BBOX["xmax"]
                    and JAPAN_BBOX["ymin"] <= lat <= JAPAN_BBOX["ymax"]
                ):
                    dropped["outside"] += 1
                    continue
                # 同じスパイダーが同じ ID を2回出すことがある（数件）。先の1件を残す
                key = (spider, feature.get("id"))
                if key in seen:
                    dropped["duplicate"] += 1
                    continue
                seen.add(key)
                # 取得元の API の URL。サイトに埋め込まれた API キーを含むことがあるので持たない
                properties.pop("@source_uri", None)
                row = {
                    "id": feature.get("id"),
                    "spider": spider,
                    "lon": lon,
                    "lat": lat,
                    "properties": properties,
                    "run_id": run["run_id"],
                }
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                kept += 1
            rows += kept
            logger.info("%s: %d", spider, kept)

        logger.info(
            "places: %d rows (dropped %d other countries, %d non-point, "
            "%d outside Japan, %d duplicates)",
            rows,
            dropped["country"],
            dropped["geometry"],
            dropped["outside"],
            dropped["duplicate"],
        )
        if rows == 0:
            raise RuntimeError(f"run {run['run_id']} has no place in Japan")
