"""AllThePlaces（日本分）のデータパイプライン。

1. places: 最新の実行から日本の施設を取り出す
2. dbt:    dbt ビルド
"""

import logging

from dbt.cli.main import dbtRunner

from pipelines.alltheplaces import download_places, latest_run

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("pipelines")


def dbt_build():
    dbt = dbtRunner()
    for command in (["deps"], ["build"]):
        result = dbt.invoke(command)
        if not result.success:
            raise SystemExit(f"dbt {' '.join(command)} failed")


def main():
    logger.info("1/2: places (AllThePlaces 日本の施設)")
    download_places(latest_run())

    logger.info("2/2: dbt build")
    dbt_build()


if __name__ == "__main__":
    main()
