"""
코스(coords)의 경사 프로파일. course.py 의 coords 만 소비한다.
고도값은 data/배포/query_elevation.py 의 DEM 조회(get_elevation)를 그대로 쓴다.
(기존 step8_slope_profile.py 포팅 + None 방어)
"""

import sys

# query_elevation.py + 서울_DEM_10m.npy + _meta.json 이 있는 폴더 (배포 패키지 기준)
from algo._datapaths import DEM_DIR
sys.path.insert(0, str(DEM_DIR))
from query_elevation import get_elevation                  # noqa: E402

from algo.utils.geo import haversine_m
from algo import config


def sample_route_coordinates(route_coordinates, sampling_interval_m=None):
    """폴리라인에서 대략 interval_m 간격으로 점을 뽑는다. None 이면 config.SLOPE_SAMPLE_M."""
    if sampling_interval_m is None:
        sampling_interval_m = config.SLOPE_SAMPLE_M
    if not route_coordinates:
        return []
    sampled_coordinates = [route_coordinates[0]]
    accumulated_distance_m = 0.0
    for start_coordinate, end_coordinate in zip(route_coordinates[:-1], route_coordinates[1:]):
        accumulated_distance_m += haversine_m(start_coordinate, end_coordinate)
        if accumulated_distance_m >= sampling_interval_m:
            sampled_coordinates.append(end_coordinate)
            accumulated_distance_m = 0.0
    if sampled_coordinates[-1] != route_coordinates[-1]:
        sampled_coordinates.append(route_coordinates[-1])
    return sampled_coordinates


def analyze_elevation_profile(route_coordinates, sampling_interval_m=None):
    if sampling_interval_m is None:
        sampling_interval_m = config.SLOPE_SAMPLE_M
    sampled_coordinates = sample_route_coordinates(route_coordinates, sampling_interval_m)
    elevations_m = [get_elevation(lat, lon) for lat, lon in sampled_coordinates]

    slope_percentages, total_elevation_gain_m = [], 0.0
    for start_coordinate, end_coordinate, start_elevation_m, end_elevation_m in zip(sampled_coordinates[:-1], sampled_coordinates[1:], elevations_m[:-1], elevations_m[1:]):
        if start_elevation_m is None or end_elevation_m is None:      # DEM 범위 밖 구간은 건너뜀
            continue
        segment_distance_m = haversine_m(start_coordinate, end_coordinate)
        if segment_distance_m < config.MIN_SEGMENT_M:      # 0 나눗셈 방지
            continue
        slope_percentages.append(abs(end_elevation_m - start_elevation_m) / segment_distance_m * 100)
        if end_elevation_m > start_elevation_m:
            total_elevation_gain_m += end_elevation_m - start_elevation_m

    if not slope_percentages:                        # 전 구간 DEM 없음
        return {"avg_slope_pct": None, "max_slope_pct": None,
                "elevation_gain_m": None, "sample_count": len(sampled_coordinates)}

    return {
        "avg_slope_pct": round(sum(slope_percentages) / len(slope_percentages), 2),
        "max_slope_pct": round(max(slope_percentages), 2),
        "elevation_gain_m": round(total_elevation_gain_m, 1),
        "sample_count": len(sampled_coordinates),
    }


if __name__ == "__main__":
    # 남산(고지대) 넘어가는 가상 코스
    example_route_coordinates  = [
        (37.5512, 126.9882),   # 남산 정상 부근 ~253m
        (37.5563, 126.9723),   # 회현동 쪽 내리막
        (37.5636, 126.9850),   # 명동 ~30m
    ]
    print(analyze_elevation_profile(example_route_coordinates))
