"""Weighted Dijkstra에서 사용할 사용자 맞춤형 도로 구간 비용."""

from algo import config
from algo.scoring.constraints import (
    extract_slope_pct,
    parse_osm_tags,
    violates_edge_requirements,
)
from algo.scoring.normalization import (
    increasing_penalty,
    normalize_preference_weight,
)


# [가중치 설계 추가] 기능별 최대 영향력. 튜닝 시 이 값만 조정하면 된다.
FEATURE_COST_SCALES = {
    "elevation": config.EDGE_COST_SCALE_ELEVATION,
    "safety": config.EDGE_COST_SCALE_SAFETY,
    "nature": config.EDGE_COST_SCALE_NATURE,
    "surface": config.EDGE_COST_SCALE_SURFACE,
    "flow": config.EDGE_COST_SCALE_FLOW,
}

_WALKABLE_HIGHWAY_TYPES = {
    "footway", "path", "pedestrian", "living_street", "track",
    "corridor", "cycleway", "residential", "unclassified", "service",
}
_MAJOR_ROAD_HIGHWAY_TYPES = {
    "primary", "secondary", "tertiary", "trunk", "motorway",
    "primary_link", "secondary_link", "tertiary_link",
    "trunk_link", "motorway_link", "busway",
}
_POOR_SURFACES = {"unpaved", "gravel", "ground", "dirt", "sand", "mud"}
_NATURE_VALUES = {"park", "garden", "nature_reserve", "forest", "wood", "water"}


def _as_bool(value):
    """OSM yes/no 계열 속성을 bool 또는 None으로 변환한다."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"yes", "true", "1", "designated"}:
        return True
    if normalized in {"no", "false", "0"}:
        return False
    return None


def _surface_penalty(edge_data, highway_tags):
    # [가중치 설계 추가] 계단·큰길·비포장도로를 높게, 보행 친화 도로를 낮게 평가한다.
    if "steps" in highway_tags:
        return 1.0
    if highway_tags & _MAJOR_ROAD_HIGHWAY_TYPES:
        return 1.0
    surface_tags = parse_osm_tags(edge_data.get("surface"))
    if surface_tags & _POOR_SURFACES:
        return 0.8
    if highway_tags & _WALKABLE_HIGHWAY_TYPES:
        return 0.0
    return 0.4


def _safety_penalty(edge_data):
    # [가중치 설계 추가] 엣지에 조명 정보가 없으면 중립값을 적용한다.
    is_lit = _as_bool(edge_data.get("lit"))
    if is_lit is True:
        return 0.0
    if is_lit is False:
        return 1.0
    return 0.5


def _nature_penalty(edge_data):
    # [가중치 설계 추가] 공원·숲·하천 속성이 있는 도로는 자연 선호 벌점이 없다.
    nature_tags = set()
    for attribute in ("leisure", "natural", "landuse", "waterway"):
        nature_tags |= parse_osm_tags(edge_data.get(attribute))
    return 0.0 if nature_tags & _NATURE_VALUES else 0.5


def _flow_penalty(graph, to_node_id):
    # [가중치 설계 추가] 신호등은 최대 벌점, 일반 횡단보도는 절반 벌점을 적용한다.
    node_highway = str(graph.nodes[to_node_id].get("highway") or "")
    if "traffic_signals" in node_highway:
        return 1.0
    if "crossing" in node_highway:
        return 0.5
    return 0.0


def _single_edge_cost(
    graph,
    from_node_id,
    to_node_id,
    edge_data,
    weights,
    requirements,
    used_edges,
    reuse_factor,
):
    if violates_edge_requirements(edge_data, requirements):
        # [가중치 설계 변경] 무한대 비용이 아니라 None을 반환해 NetworkX 탐색에서 완전히 제외한다.
        return None

    try:
        edge_length_m = max(float(edge_data.get("length", 1.0)), 0.01)
    except (TypeError, ValueError):
        edge_length_m = 1.0

    highway_tags = parse_osm_tags(edge_data.get("highway"))
    slope_penalty = increasing_penalty(
        extract_slope_pct(edge_data),
        good=config.EDGE_SLOPE_GOOD_PCT,
        bad=config.EDGE_SLOPE_BAD_PCT,
    )

    # [가중치 설계 추가] 거리를 기본 비용으로 두고 모든 선호 요소를 비음수 벌점으로 합산한다.
    distance_priority = 0.5 + normalize_preference_weight(weights, "distance")
    cost_multiplier = distance_priority
    cost_multiplier += (
        FEATURE_COST_SCALES["elevation"]
        * normalize_preference_weight(weights, "elevation")
        * slope_penalty
    )
    cost_multiplier += (
        FEATURE_COST_SCALES["safety"]
        * normalize_preference_weight(weights, "safety")
        * _safety_penalty(edge_data)
    )
    cost_multiplier += (
        FEATURE_COST_SCALES["nature"]
        * normalize_preference_weight(weights, "nature")
        * _nature_penalty(edge_data)
    )
    cost_multiplier += (
        FEATURE_COST_SCALES["surface"]
        * normalize_preference_weight(weights, "surface")
        * _surface_penalty(edge_data, highway_tags)
    )
    cost_multiplier += (
        FEATURE_COST_SCALES["flow"]
        * normalize_preference_weight(weights, "flow")
        * _flow_penalty(graph, to_node_id)
    )

    undirected_edge = frozenset((from_node_id, to_node_id))
    if undirected_edge in used_edges:
        # [가중치 설계 변경] 기존 factor 벌점을 overlap 선호도 0~5로 조절 가능하게 만든다.
        overlap_weight = normalize_preference_weight(
            weights,
            "overlap",
            default=5.0,
        )
        cost_multiplier *= 1.0 + max(reuse_factor - 1.0, 0.0) * overlap_weight

    return edge_length_m * cost_multiplier


def create_edge_cost_function(
    graph,
    weights=None,
    requirements=None,
    used_edges=None,
    reuse_factor=5.0,
):
    """NetworkX shortest_path의 weight 인자로 사용할 함수를 생성한다."""
    # [가중치 설계 추가] 요청별 설정을 클로저에 고정해 탐색 중 반복 준비 비용을 줄인다.
    used_edge_set = used_edges or set()

    def calculate_edge_cost(from_node_id, to_node_id, edge_payload):
        # MultiDiGraph는 {edge_key: edge_data}, 단순 그래프는 edge_data를 전달한다.
        if "length" in edge_payload:
            candidate_edges = (edge_payload,)
        else:
            candidate_edges = tuple(edge_payload.values())

        weighted_edges = [
            _single_edge_cost(
                graph,
                from_node_id,
                to_node_id,
                edge_data,
                weights,
                requirements,
                used_edge_set,
                reuse_factor,
            )
            for edge_data in candidate_edges
        ]
        # [가중치 설계 추가] 평행 엣지 중 조건을 만족하는 도로만 비용 비교 대상으로 삼는다.
        allowed_costs = [cost for cost in weighted_edges if cost is not None]
        return min(allowed_costs) if allowed_costs else None

    return calculate_edge_cost
