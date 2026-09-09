"""
심장 — geo/graph/routing/waypoints 를 엮어 3가지 모드의 코스를 만든다.

세 모드의 차이는 _build() 안의 분기뿐:
  out_and_back  : 경유지 1개, 갔던 길 뒤집기 (벌점 없음)
  loop          : 경유지 1개, 나간 길에 벌점 -> 다른 길로 복귀
  point_to_point: 타원 경유지 1개, S->W->E (약한 벌점)

거리는 한 번에 못 맞추므로, 실제거리를 재고 scale 을 보정해 재시도한다
(오차 5% 이내 또는 6회).
"""

from algo.utils.geo import haversine_m
from algo.routing.shortest_path import shortest_path, path_to_edge_set
from algo.routing.waypoints import circle_waypoints, ellipse_waypoints
from algo import config


def _overlap_ratio(nodes):
    """방향 무시, 이미 지난 도로 재방문 비율. 순환 품질 지표."""
    seen, reused, total = set(), 0, 0
    for u, v in zip(nodes[:-1], nodes[1:]):
        e = frozenset((u, v))
        total += 1
        if e in seen:
            reused += 1
        else:
            seen.add(e)
    return reused / total if total else 0.0


def _build(G, idx, mode, start, end, scale, bearing, weights=None, requirements=None):
    s = idx.snap(*start)

    if mode == "out_and_back":
        w = circle_waypoints(*start, radius_m=scale, n=1, start_bearing=bearing)[0]
        wn = idx.snap(*w)
        # [가중치 설계 변경] 모든 구간 탐색에 동일한 사용자 설정을 전달한다.
        out, out_len = shortest_path(G, s, wn, weights=weights, requirements=requirements)
        return out + out[-2::-1], out_len * 2

    if mode == "loop":
        w = circle_waypoints(*start, radius_m=scale, n=1, start_bearing=bearing)[0]
        wn = idx.snap(*w)
        out, out_len = shortest_path(G, s, wn, weights=weights, requirements=requirements)
        back, back_len = shortest_path(G, wn, s, penalty_edges=path_to_edge_set(out),
                                       factor=config.LOOP_PENALTY_FACTOR,
                                       weights=weights, requirements=requirements)
        return out + back[1:], out_len + back_len

    if mode == "point_to_point":
        e = idx.snap(*end)
        ws = ellipse_waypoints(start, end, target_sum_m=scale, n=8)
        w = ws[int(round(bearing / 45.0)) % 8]
        wn = idx.snap(*w)
        a, a_len = shortest_path(G, s, wn, weights=weights, requirements=requirements)
        b, b_len = shortest_path(G, wn, e, penalty_edges=path_to_edge_set(a),
                                 factor=config.P2P_PENALTY_FACTOR,
                                 weights=weights, requirements=requirements)
        return a + b[1:], a_len + b_len

    raise ValueError(f"unknown mode: {mode}")


def generate_course(G, idx, mode, start, target_distance_m, end=None,
                    bearing=0.0, max_iter=None, tol=None,
                    weights=None, requirements=None):
    if mode == "point_to_point" and end is None:
        raise ValueError("point_to_point 모드는 end 좌표가 필요합니다")
    if max_iter is None:
        max_iter = config.DIST_FIT_MAX_ITER
    if tol is None:
        tol = config.DIST_FIT_TOL

    scale = target_distance_m / 2 if mode in ("loop", "out_and_back") else target_distance_m

    best = None
    for _ in range(max_iter):
        nodes, dist = _build(
            G, idx, mode, start, end, scale, bearing,
            weights=weights, requirements=requirements,
        )
        if dist <= 0:
            scale *= 2
            continue
        err = abs(dist - target_distance_m) / target_distance_m
        if best is None or err < best[0]:
            best = (err, nodes, dist, scale)
        if err <= tol:
            break
        scale *= target_distance_m / dist       # 스케일 피드백 보정

    if best is None:                     # 모든 시도에서 경로 실패 (start 가 그래프 밖 / target 과다)
        raise ValueError(
            f"경로 생성 실패: start={start} 가 그래프 범위 밖이거나 "
            f"target_distance_m={target_distance_m} 가 부적절 (bearing={bearing})")

    err, nodes, dist, scale = best
    return _pack(mode, nodes, dist, target_distance_m, G, round(scale))


def _pack(mode, nodes, dist, target_m, G, scale_m):
    """course 결과 dict. generate_course / generate_course_via 공통.
    nodes: OSM 엣지 속성(노면·계단·신호등)을 읽으려면 노드 경로가 필요해 함께 넘긴다."""
    err = abs(dist - target_m) / target_m
    return {
        "mode": mode,
        "target_distance_m": target_m,
        "actual_distance_m": round(dist),
        "distance_error_pct": round(err * 100, 1),
        "overlap_ratio": round(_overlap_ratio(nodes), 3),
        "scale_m": scale_m,
        "coords": [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in nodes],
        "nodes": nodes,
    }


def _route_chain(G, node_chain, penalty=None, weights=None, requirements=None):
    """연속한 노드쌍을 최단경로로 잇되, 앞 구간에서 쓴 엣지엔 벌점 (왕복 억제).
    penalty=None 이면 config.VIA_PENALTY_FACTOR. 반환: (전체 노드열, 총 길이 m)."""
    if penalty is None:
        penalty = config.VIA_PENALTY_FACTOR
    full, total, used = [], 0.0, set()
    for a, b in zip(node_chain[:-1], node_chain[1:]):
        seg, seg_len = shortest_path(
            G, a, b, penalty_edges=used, factor=penalty,
            weights=weights, requirements=requirements,
        )
        used |= path_to_edge_set(seg)
        full = seg if not full else full + seg[1:]
        total += seg_len
    return full, total


def generate_course_via(G, idx, start, vias, target_distance_m, end=None,
                        bearing=0.0, max_iter=None, tol=None, penalty=None,
                        weights=None, requirements=None):
    """사용자가 지정한 경유지(vias, 순서대로 반드시 통과)를 지나는 코스.
    end=None 이면 시작점으로 복귀(순환). 목표거리에 모자라면 마지막 구간에
    우회점 하나를 끼워 채운다. max_iter/tol/penalty=None 이면 config 값."""
    if max_iter is None:
        max_iter = config.DIST_FIT_MAX_ITER
    if tol is None:
        tol = config.DIST_FIT_TOL
    if penalty is None:
        penalty = config.VIA_PENALTY_FACTOR
    tail = end if end is not None else start
    anchors = [start] + list(vias) + [tail]
    anchor_nodes = [idx.snap(*a) for a in anchors]

    fixed_nodes, fixed_len = _route_chain(
        G, anchor_nodes, penalty, weights=weights, requirements=requirements,
    )
    if fixed_len > target_distance_m * (1 + tol):
        raise ValueError(
            f"경유지를 다 지나면 최소 {fixed_len/1000:.2f}km 라서 "
            f"목표 {target_distance_m/1000:.2f}km 보다 깁니다"
        )
    if fixed_len >= target_distance_m * (1 - tol):
        return _pack("via", fixed_nodes, fixed_len, target_distance_m, G,
                     scale_m=round(fixed_len))

    # 마지막 구간(마지막 경유지 -> tail)에 우회점 P 하나 끼워 부족분 채우기
    a_last, b_last = anchors[-2], anchors[-1]
    scale = haversine_m(a_last, b_last) + (target_distance_m - fixed_len)  # 타원 target_sum 초기값

    best = None
    for _ in range(max_iter):
        try:
            cand_pts = ellipse_waypoints(a_last, b_last, target_sum_m=scale, n=8)
        except ValueError:
            scale *= 1.1
            continue
        pn = idx.snap(*cand_pts[int(round(bearing / 45.0)) % 8])
        nodes, length = _route_chain(
            G,
            anchor_nodes[:-1] + [pn, anchor_nodes[-1]],
            penalty,
            weights=weights,
            requirements=requirements,
        )
        if length <= 0:
            scale *= 2
            continue
        err = abs(length - target_distance_m) / target_distance_m
        if best is None or err < best[0]:
            best = (err, nodes, length, scale)
        if err <= tol:
            break
        scale *= target_distance_m / length

    if best is None:                     # 경유지 체인을 목표 거리로 못 맞춤
        raise ValueError(
            f"경유지 경로 생성 실패: start={start}, vias={vias}, "
            f"target_distance_m={target_distance_m} (bearing={bearing})")

    err, nodes, length, scale = best
    return _pack("via", nodes, length, target_distance_m, G, scale_m=round(scale))


if __name__ == "__main__":
    from algo.utils.graph import grid_graph, NodeIndex

    G = grid_graph(60, 60, 100)
    idx = NodeIndex(G)
    start = (G.nodes[(30, 30)]["y"], G.nodes[(30, 30)]["x"])
    end = (G.nodes[(30, 40)]["y"], G.nodes[(30, 40)]["x"])
    via = (G.nodes[(45, 30)]["y"], G.nodes[(45, 30)]["x"])

    for mode in ("out_and_back", "loop"):
        r = generate_course(G, idx, mode, start, 3000, bearing=0.0)
        print(mode, "->", r["actual_distance_m"], "m  err", r["distance_error_pct"],
              "%  overlap", r["overlap_ratio"])
    r = generate_course(G, idx, "point_to_point", start, 3000, end=end, bearing=90.0)
    print("point_to_point ->", r["actual_distance_m"], "m  err", r["distance_error_pct"], "%")

    r = generate_course_via(G, idx, start, [via], 4000, bearing=90.0)
    print("via (순환, 경유지 1개) ->", r["actual_distance_m"], "m  err",
          r["distance_error_pct"], "%  overlap", r["overlap_ratio"])
