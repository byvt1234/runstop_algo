"""
"최단경로 버튼" 하나 + 이미 지나온 엣지에 벌점.

course.py 가 모드마다 이 함수를 2~3번 호출해 경로를 조립한다.
TMAP(블랙박스)로는 불가능했던 것: penalty_edges 를 넘기면 그 도로의 가중치를
factor 배로 쳐서, 복귀 경로가 자연히 다른 길로 가도록 유도한다.
"""

import networkx as nx

from algo import config
from algo.scoring.edge_cost import create_edge_cost_function


def _edge_len(data):
    """엣지 길이(m). MultiDiGraph면 data={key: 속성}, 단순 그래프면 속성 dict 자체."""
    if data is None:
        return float("inf")
    if "length" in data:
        return float(data["length"])
    return min(float(a.get("length", 1.0)) for a in data.values())


def path_to_edge_set(nodes):
    """경로 노드열 -> 방향 무시한 엣지 집합 {frozenset({u, v}), ...}."""
    return {frozenset((u, v)) for u, v in zip(nodes[:-1], nodes[1:])}


def shortest_path(
    G,
    src,
    dst,
    penalty_edges=None,
    factor=None,
    weights=None,
    requirements=None,
):
    """src, dst = 노드 id. penalty_edges = {frozenset({u,v}), ...} (이미 쓴 도로).
    factor=None 이면 config.LOOP_PENALTY_FACTOR.
    반환: (노드 리스트, 실제 거리_m). 경로 없으면 nx.NetworkXNoPath 발생."""
    if factor is None:
        factor = config.LOOP_PENALTY_FACTOR
    # [가중치 설계 변경] 거리만 보던 weight 함수를 요청별 선호도·필수조건 비용으로 교체한다.
    edge_cost = create_edge_cost_function(
        G,
        weights=weights,
        requirements=requirements,
        used_edges=penalty_edges,
        reuse_factor=factor,
    )
    nodes = nx.shortest_path(G, src, dst, weight=edge_cost)
    length = sum(
        _edge_len(G.get_edge_data(a, b))
        for a, b in zip(nodes[:-1], nodes[1:])
    )
    return nodes, length


if __name__ == "__main__":
    from algo.utils.graph import grid_graph

    G = grid_graph(10, 10, 100)
    nodes, dist = shortest_path(G, (0, 0), (0, 4))
    print("벌점 없음:", nodes, "->", dist, "m")

    used = path_to_edge_set(nodes)
    nodes2, dist2 = shortest_path(G, (0, 0), (0, 4), penalty_edges=used)
    print("벌점 있음:", nodes2, "->", dist2, "m  (우회로 더 길어야 정상)")
    print("겹친 도로:", len(used & path_to_edge_set(nodes2)), "/", len(used))
