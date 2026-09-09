"""
노면·흐름 프로파일 — 코스가 어떤 길로 이뤄졌는지.
course 가 넘겨준 노드 경로(nodes)와 그래프 G 의 OSM 엣지/노드 속성을 읽는다.

- walkable_ratio : footway/path/pedestrian/living_street 등 보행자 친화 길이 비율
- bigroad_ratio  : primary/secondary/tertiary/trunk 등 큰길 길이 비율 (낮을수록 좋음)
- stairs_count   : highway=steps 세그먼트 수
- signal_per_km  : 경로가 지나는 traffic_signals 노드 / km
- crossing_per_km: 횡단보도 노드 / km

격자 그래프(속성 없음)면 전부 None / 0 을 돌려준다.
"""

import ast

_WALKABLE_HIGHWAY_TYPES = {"footway", "path", "pedestrian", "living_street", "track",
             "steps", "corridor", "cycleway",
             "residential", "unclassified", "service"}   # 주택가 이면도로 = 러닝 무난
_MAJOR_ROAD_HIGHWAY_TYPES = {"primary", "secondary", "tertiary", "trunk", "motorway",
            "primary_link", "secondary_link", "tertiary_link",
            "trunk_link", "motorway_link", "busway"}


def _parse_highway_tags(raw_highway_value):
    """highway 원형(문자열 'steps' 또는 "['steps','footway']") -> 태그 집합."""
    if raw_highway_value is None:
        return set()
    if isinstance(raw_highway_value, (list, set, tuple)):
        return set(raw_highway_value)
    serialized_value = str(raw_highway_value)
    if serialized_value.startswith("["):
        try:
            return set(ast.literal_eval(serialized_value))
        except (ValueError, SyntaxError):
            return {serialized_value}
    return {serialized_value}


def _select_shortest_edge_data(graph, from_node_id, to_node_id):
    """u->v 평행 엣지 중 최단 길이 하나의 속성 dict."""
    parallel_edges = graph.get_edge_data(from_node_id, to_node_id) or graph.get_edge_data(to_node_id, from_node_id)
    if not parallel_edges:
        return None
    return min(parallel_edges.values(), key=lambda edge_data: float(edge_data.get("length", 1e18)))


def analyze_surface_profile(graph, route_node_ids):
    total_length_m = walkable_length_m = major_road_length_m = 0.0
    stairs_segment_count = 0
    has_highway_data = False

    for from_node_id, to_node_id in zip(route_node_ids[:-1], route_node_ids[1:]):
        edge_data = _select_shortest_edge_data(graph, from_node_id, to_node_id)
        if not edge_data:
            continue
        edge_length_m = float(edge_data.get("length", 0.0))
        total_length_m += edge_length_m
        raw_highway_value = edge_data.get("highway")
        if raw_highway_value is None:
            continue
        has_highway_data = True
        highway_tags = _parse_highway_tags(raw_highway_value)
        if "steps" in highway_tags:
            stairs_segment_count += 1
        if highway_tags & _WALKABLE_HIGHWAY_TYPES:
            walkable_length_m += edge_length_m
        if highway_tags & _MAJOR_ROAD_HIGHWAY_TYPES:
            major_road_length_m += edge_length_m

    route_length_km = (total_length_m / 1000) or 1e-9
    traffic_signal_count = crossing_count = 0
    for node_id in route_node_ids:
        node_highway_type = str(graph.nodes[node_id].get("highway") or "")
        if "traffic_signals" in node_highway_type:
            traffic_signal_count += 1
        elif "crossing" in node_highway_type:
            crossing_count += 1

    if not has_highway_data:                       # 격자 등 속성 없는 그래프
        return {"length_m": round(total_length_m), "walkable_ratio": None,
                "bigroad_ratio": None, "stairs_count": 0,
                "signal_per_km": None, "crossing_per_km": None}

    return {
        "length_m": round(total_length_m),
        "walkable_ratio": round(walkable_length_m / total_length_m, 3) if total_length_m else None,
        "bigroad_ratio": round(major_road_length_m / total_length_m, 3) if total_length_m else None,
        "stairs_count": stairs_segment_count,
        "signal_per_km": round(traffic_signal_count / route_length_km, 2),
        "crossing_per_km": round(crossing_count / route_length_km, 2),
    }


if __name__ == "__main__":
    from pathlib import Path
    from algo.utils.graph import load_graph, NodeIndex
    from algo.routing.course import generate_course

    G = load_graph(str(Path(__file__).resolve().parent.parent / "data" / "서울_보행네트워크.graphml"))
    idx = NodeIndex(G)
    r = generate_course(G, idx, "loop", (37.4979, 127.0276), 3000)
    from pprint import pprint
    pprint(analyze_surface_profile(G, r["nodes"]))
