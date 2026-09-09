"""
코스 주변 시설 스코어. course.py 의 coords 만 소비한다.
data/배포/서울_시설데이터_통합.csv (유형/명칭/위도/경도/...) 한 파일을 유형별로 나눠 쓴다.
버퍼/거리는 반드시 미터 좌표(EPSG:5179)에서. (기존 step9 포팅 + 시설 확장)
"""

import numpy as np
import pandas as pd
from shapely import LineString, contains_xy, distance, points as sh_points

from algo.utils.geo import to_5179
from algo._datapaths import FACIL_CSV as FACILITY_DATASET_PATH  # 배포 패키지 datasets/ 또는 RUNSTOP_DATA_DIR
from algo import config

# 유형(한글, CSV) -> 결과 키(영문)
FACILITY_TYPE_TO_KEY = {"화장실": "toilet", "편의점": "store", "도시공원": "park",
         "가로등": "light", "보안등": "security", "보행등": "walklight",
         "CCTV": "cctv"}

_FACILITY_COORDINATES_CACHE = {}


def _load_facility_coordinates():
    """통합 CSV를 한 번만 읽어 유형별 (N,2) 미터좌표 배열로 캐시."""
    if _FACILITY_COORDINATES_CACHE:
        return _FACILITY_COORDINATES_CACHE
    facility_df = pd.read_csv(FACILITY_DATASET_PATH, low_memory=False).dropna(subset=["위도", "경도"])
    for facility_type, facility_group_df in facility_df.groupby("유형"):
        projected_x, projected_y = to_5179.transform(facility_group_df["경도"].to_numpy(), facility_group_df["위도"].to_numpy())
        _FACILITY_COORDINATES_CACHE[facility_type] = np.column_stack([projected_x, projected_y])
    return _FACILITY_COORDINATES_CACHE


def _create_projected_route_line(route_coordinates):
    return LineString([to_5179.transform(lon, lat) for lat, lon in route_coordinates])


def analyze_nearby_facilities(route_coordinates, buffer_distance_m=None):
    if buffer_distance_m is None:
        buffer_distance_m = config.BUFFER_M
    route_line = _create_projected_route_line(route_coordinates)
    route_buffer = route_line.buffer(buffer_distance_m)
    route_length_km = route_line.length / 1000
    facility_coordinates_by_type = _load_facility_coordinates()

    metrics = {"route_length_km": round(route_length_km, 2), "buffer_m": buffer_distance_m}
    min_x, min_y, max_x, max_y = route_buffer.bounds

    for facility_type, key in FACILITY_TYPE_TO_KEY.items():
        facility_points_xy = facility_coordinates_by_type.get(facility_type)
        if facility_points_xy is None or len(facility_points_xy) == 0:
            metrics[f"{key}_count"], metrics[f"{key}_per_km"], metrics[f"{key}_nearest_m"] = 0, 0.0, None
            continue

        # 1차: 버퍼 bounding box 안의 점만 추림
        bounding_box_mask = ((facility_points_xy[:, 0] >= min_x) & (facility_points_xy[:, 0] <= max_x) &
             (facility_points_xy[:, 1] >= min_y) & (facility_points_xy[:, 1] <= max_y))
        nearby_points_xy = facility_points_xy[bounding_box_mask]
        if len(nearby_points_xy) == 0:
            metrics[f"{key}_count"], metrics[f"{key}_per_km"], metrics[f"{key}_nearest_m"] = 0, 0.0, None
            continue

        # 2차: 버퍼 폴리곤 안 개수 + 코스 선까지 최근접 거리 (벡터 연산)
        nearby_facility_count = int(contains_xy(route_buffer, nearby_points_xy[:, 0], nearby_points_xy[:, 1]).sum())
        nearest_distance_m = float(distance(route_line, sh_points(nearby_points_xy[:, 0], nearby_points_xy[:, 1])).min())

        metrics[f"{key}_count"] = nearby_facility_count
        metrics[f"{key}_per_km"] = round(nearby_facility_count / route_length_km, 2) if route_length_km else 0.0
        metrics[f"{key}_nearest_m"] = round(nearest_distance_m, 1)

    return metrics


if __name__ == "__main__":
    from pprint import pprint
    route = [(37.4979, 127.0276), (37.5020, 127.0276),
             (37.5020, 127.0330), (37.4979, 127.0330), (37.4979, 127.0276)]
    pprint(analyze_nearby_facilities(route))
