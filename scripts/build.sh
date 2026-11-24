#!/usr/bin/env bash
set -euo pipefail
# 説明 (<model>.tabledoc.yml) の無いテーブルは Queria の一覧と検索に出さない
export FDL_UNDESCRIBED="${FDL_UNDESCRIBED:-hidden}"
exec "$(dirname "$0")/../shared/scripts/build-fdl.sh" "$@"
