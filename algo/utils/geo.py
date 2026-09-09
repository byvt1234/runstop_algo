"""
좌표 유틸 — 다른 모든 모듈의 공통 기반.

- 외부 좌표는 EPSG:4326 (위도, 경도) 순서.
- 거리/기하 계산이 필요하면 EPSG:5179 (미터)로 투영해서 한다.
- "방향 + 거리 -> 지점" 은 지구 타원체를 반영한 측지선 계산(pyproj.Geod)을 쓴다.
"""

from pyproj import Geod, Transformer

CRS_WGS84  = 4326   # 외부 좌표 (위도, 경도)
CRS_METRIC = 5179   # 거리/면적 계산용 미터 좌표 (Korea 2000 / Central Belt)

_geod = Geod(ellps="WGS84")
to_5179 = Transformer.from_crs(f"EPSG:{CRS_WGS84}", f"EPSG:{CRS_METRIC}", always_xy=True)  # 위경도 -> 미터
to_4326 = Transformer.from_crs(f"EPSG:{CRS_METRIC}", f"EPSG:{CRS_WGS84}", always_xy=True)  # 미터 -> 위경도


def point_at_bearing(lat, lon, bearing_deg, distance_m):
    """(lat, lon)에서 방위각(북=0, 시계방향)으로 distance_m 간 지점의 (lat, lon)."""
    lon2, lat2, _ = _geod.fwd(lon, lat, bearing_deg, distance_m)
    return lat2, lon2


def haversine_m(a, b):
    """두 (lat, lon) 사이 지표면 거리(m)."""
    (lat1, lon1), (lat2, lon2) = a, b
    _, _, dist = _geod.inv(lon1, lat1, lon2, lat2)
    return dist


def bearing_deg(a, b):
    """a -> b 방위각(도, 0~360)."""
    (lat1, lon1), (lat2, lon2) = a, b
    fwd_az, _, _ = _geod.inv(lon1, lat1, lon2, lat2)
    return fwd_az % 360

if __name__ == "__main__":
    gangnam = (37.4979, 127.0276)
    print("북 500m:", point_at_bearing(*gangnam, 0, 500))    # 위도 커짐
    print("동 500m:", point_at_bearing(*gangnam, 90, 500))   # 경도 커짐
    print("두 점 거리:", round(haversine_m(gangnam, (37.5013, 127.0396)), 1), "m")
