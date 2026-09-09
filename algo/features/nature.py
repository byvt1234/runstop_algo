"""
녹지·하천 인접률 — course 의 coords(위경도 폴리라인)만 소비.

data/osm/out/ 의 폴리곤 geojson 을 EPSG:5179 로 투영해 GeoDataFrame + 공간인덱스로 캐시.
인접률 = 코스 주변 buffer_m 띠의 면적 중 (공원 / 하천) 폴리곤과 겹치는 비율.

geojson 이 없으면 해당 값은 None (fetch_park_water.py 로 생성).
"""

import geopandas as gpd
from shapely import LineString

from algo.utils.geo import to_5179, CRS_METRIC
from algo._datapaths import OSM_OUT as NATURE_DATA_DIRECTORY   # 배포 패키지 datasets/osm/out 또는 RUNSTOP_DATA_DIR
from algo import config
NATURE_LAYER_PATHS = {
    "park": NATURE_DATA_DIRECTORY / "서울_공원.geojson",
    "water": NATURE_DATA_DIRECTORY / "서울_하천_polygon.geojson",
}

_NATURE_LAYER_CACHE = {}


def _load_nature_layers():
    if _NATURE_LAYER_CACHE:
        return _NATURE_LAYER_CACHE
    for nature_type, geojson_path in NATURE_LAYER_PATHS.items():
        if geojson_path.exists():
            layer_gdf = gpd.read_file(geojson_path).to_crs(CRS_METRIC)
            layer_gdf.sindex  # 공간인덱스 미리 구축
            _NATURE_LAYER_CACHE[nature_type] = layer_gdf
        else:
            _NATURE_LAYER_CACHE[nature_type] = None
    return _NATURE_LAYER_CACHE


def _create_projected_route_line(route_coordinates):
    return LineString([to_5179.transform(lon, lat) for lat, lon in route_coordinates])


def analyze_nature_adjacency(route_coordinates, buffer_distance_m=None):
    if buffer_distance_m is None:
        buffer_distance_m = config.BUFFER_M
    route_line = _create_projected_route_line(route_coordinates)
    route_buffer = route_line.buffer(buffer_distance_m)
    buffer_area_m2 = route_buffer.area or 1e-9
    nature_layers = _load_nature_layers()

    metrics = {}
    for nature_type in NATURE_LAYER_PATHS:
        nature_layer_gdf = nature_layers.get(nature_type)
        if nature_layer_gdf is None:
            metrics[f"{nature_type}_ratio"] = None
            continue
        intersecting_indices = list(nature_layer_gdf.sindex.query(route_buffer, predicate="intersects"))
        if not intersecting_indices:
            metrics[f"{nature_type}_ratio"] = 0.0
            continue
        merged_nature_geometry = nature_layer_gdf.geometry.iloc[intersecting_indices].union_all()
        metrics[f"{nature_type}_ratio"] = round(route_buffer.intersection(merged_nature_geometry).area / buffer_area_m2, 3)
    return metrics


if __name__ == "__main__":
    from pathlib import Path
    from algo.utils.graph import load_graph, NodeIndex
    from algo.routing.course import generate_course

    G = load_graph(str(Path(__file__).resolve().parent.parent / "data" / "서울_보행네트워크.graphml"))
    idx = NodeIndex(G)
    # 한강 가까운 출발점
    r = generate_course(G, idx, "loop", (37.5133, 127.0590), 4000)
    from pprint import pprint
    pprint(analyze_nature_adjacency(r["coords"]))
