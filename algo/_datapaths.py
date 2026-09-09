"""
배포 패키지가 쓰는 데이터셋 위치를 한 곳에서 해석한다.

DATA_ROOT 우선순위
  1) 환경변수 RUNSTOP_DATA_DIR   (도커/서버 배포 시 마운트 경로)
  2) 이 패키지에 동봉된 deploy/datasets/
  3) (개발 환경 폴백) /Users/user/Desktop/runstop/data

어느 경우든 하위 레이아웃은 동일하다:
  <DATA_ROOT>/배포/query_elevation.py, 서울_DEM_10m.npy, 서울_DEM_10m_meta.json
  <DATA_ROOT>/배포/서울_시설데이터_통합.csv
  <DATA_ROOT>/osm/out/서울_공원.geojson, 서울_하천_polygon.geojson

elevation.py · scoring.py · nature.py 가 이 모듈만 바라본다.
"""

import os
from pathlib import Path

_BUNDLED = Path(__file__).resolve().parent.parent / "datasets"
_LEGACY = Path("/Users/user/Desktop/runstop/data")


def _resolve_root() -> Path:
    env = os.environ.get("RUNSTOP_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    if _BUNDLED.is_dir():
        return _BUNDLED
    return _LEGACY


DATA_ROOT = _resolve_root()

DEM_DIR = DATA_ROOT / "배포"
FACIL_CSV = DATA_ROOT / "배포" / "서울_시설데이터_통합.csv"
OSM_OUT = DATA_ROOT / "osm" / "out"
