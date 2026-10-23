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

import http.client
import io
import json
import logging
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger("pipelines")

USER_AGENT = "dataset-alltheplaces (+https://github.com/queria-io/dataset-alltheplaces)"
LATEST_URL = "https://data.alltheplaces.xyz/runs/latest.json"

OUTPUT_DIR = Path("data/places")

# 日本の外接矩形。端は沖ノ鳥島 北緯 20.42 / 択捉島 北緯 45.55 /
# 与那国島 東経 122.93 / 南鳥島 東経 153.98
JAPAN_BBOX = {"xmin": 122.0, "xmax": 154.5, "ymin": 20.0, "ymax": 46.0}

REQUEST_TIMEOUT = 120
# 一時的な失敗（5xx・接続断・タイムアウト）で取得全体を落とさないための再試行。
# 待ち時間は 5, 10, 20, 40 秒
REQUEST_RETRIES = 4
RETRY_BACKOFF = 5


def _request(request: Request, read):
    url = request.full_url
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return read(response)
        except HTTPError as error:
            if error.code < 500 or attempt == REQUEST_RETRIES:
                raise
            reason = error
        # 本文の途中で切れたとき（IncompleteRead）や TLS の失敗も一時的なものとして扱う
        except (OSError, http.client.HTTPException) as error:
            if attempt == REQUEST_RETRIES:
                raise
            reason = error
        wait = RETRY_BACKOFF * 2**attempt
        logger.warning("retry in %ds: %s (%s)", wait, url, reason)
        time.sleep(wait)
    raise AssertionError("unreachable")


def _open(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return _request(request, lambda response: response.read())


def _content_length(url: str) -> int:
    request = Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    return _request(request, lambda response: int(response.headers["Content-Length"]))


class _RangeFile(io.RawIOBase):
    """HTTP の Range で読む、シーク可能な読み取り専用ファイル。zipfile に渡す。"""

    def __init__(self, url: str, size: int) -> None:
        self.url = url
        self.size = size
        self.position = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self.position = offset
        elif whence == io.SEEK_CUR:
            self.position += offset
        else:
            self.position = self.size + offset
        return self.position

    def readinto(self, buffer) -> int:
        if self.position >= self.size or len(buffer) == 0:
            return 0
        end = min(self.size, self.position + len(buffer)) - 1
        request = Request(
            self.url,
            headers={"User-Agent": USER_AGENT, "Range": f"bytes={self.position}-{end}"},
        )
        data = _request(request, self._read_partial)
        buffer[: len(data)] = data
        self.position += len(data)
        return len(data)

    def _read_partial(self, response) -> bytes:
        # Range を無視して 200 で返されると、全世界の zip（約2.7GB）を丸ごと読むことになる
        if response.status != 206:
            raise RuntimeError(f"{self.url}: Range が効かない (HTTP {response.status})")
        return response.read()


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


def _features(archive: zipfile.ZipFile, spider: str) -> list[dict]:
    data = json.loads(archive.read(f"output/{spider}.geojson"))
    return data.get("features") or []


def download_places(run: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "place.ndjson"

    size = _content_length(run["output_url"])
    # 読むたびにバッファの大きさまで先読みする。日本向けのスパイダーのファイルは
    # 9割が 1MB 未満なので、大きく取ると隣のファイルまで取って転送量が数倍になる
    archive = zipfile.ZipFile(io.BufferedReader(_RangeFile(run["output_url"], size), 1 << 16))
    in_archive = {
        Path(name).stem for name in archive.namelist() if name.endswith(".geojson")
    }

    domestic = sorted(name for name in in_archive if name.endswith("_jp"))
    international = sorted(japan_spiders(run["insights_url"]) - set(domestic))
    logger.info("spiders: %d _jp, %d international", len(domestic), len(international))

    rows = 0
    seen: set[tuple[str, str]] = set()
    dropped = {"country": 0, "geometry": 0, "outside": 0, "duplicate": 0}
    partial = output.with_name(output.name + ".part")
    with partial.open("w", encoding="utf-8") as handle:
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
        # 前回の place.ndjson を空のファイルで置き換えない
        partial.unlink()
        raise RuntimeError(f"run {run['run_id']} has no place in Japan")
    partial.replace(output)
