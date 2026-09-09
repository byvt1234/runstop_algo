"""
서울 DEM(격자 고도 데이터) 조회 유틸리티

build_dem.py로 만든 서울_DEM_10m.npy / 서울_DEM_10m_meta.json을 읽어서,
위경도(WGS84) 좌표 하나를 넣으면 고도(m)를 반환한다.
경로 위 두 지점의 고도 차이로 경사(%)를 계산하는 예시도 포함.
"""

import numpy as np
import json
import os
from pyproj import Transformer

DEM_DIR = os.path.dirname(os.path.abspath(__file__))

_to_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

with open(f"{DEM_DIR}/서울_DEM_10m_meta.json", encoding="utf-8") as f:
    _meta = json.load(f)
_dem = np.load(f"{DEM_DIR}/서울_DEM_10m.npy")


def get_elevation(lat: float, lon: float) -> float:
    """위경도(WGS84) -> 고도(m). 격자 범위 밖이면 None."""
    x, y = _to_5179.transform(lon, lat)
    col = int((x - _meta["x_min"]) / _meta["resolution_m"])
    row = int((y - _meta["y_min"]) / _meta["resolution_m"])
    if 0 <= row < _meta["shape"][0] and 0 <= col < _meta["shape"][1]:
        return float(_dem[row, col])
    return None


def slope_percent(lat1, lon1, lat2, lon2) -> float:
    """두 지점 간 경사(%) = 고도차 / 수평거리 * 100"""
    e1, e2 = get_elevation(lat1, lon1), get_elevation(lat2, lon2)
    if e1 is None or e2 is None:
        return None
    x1, y1 = _to_5179.transform(lon1, lat1)
    x2, y2 = _to_5179.transform(lon2, lat2)
    horiz_dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if horiz_dist == 0:
        return 0.0
    return abs(e2 - e1) / horiz_dist * 100


if __name__ == "__main__":
    # 예시: 남산(고지대)과 근처 평지 한 지점 비교
    namsan = (37.5512, 126.9882)
    myeongdong = (37.5636, 126.9850)
    print("남산 고도:", get_elevation(*namsan), "m")
    print("명동 고도:", get_elevation(*myeongdong), "m")
    print("두 지점 간 경사:", round(slope_percent(*namsan, *myeongdong), 2), "%")
