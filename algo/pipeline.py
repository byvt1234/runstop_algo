"""
전체 파이프라인 — 요청 1건 -> 추천 코스 목록.

candidates(후보 풀) -> 각 후보에 elevation(경사) + scoring(시설)
+ nature(녹지·하천 인접률) + surface(노면·흐름) 부착 -> weighting(conditionScore)
-> 상위 top_k 반환.

routeType 매핑:  LOOP -> loop  |  ONE_WAY -> point_to_point  |  ROUND_TRIP -> out_and_back
API 서버는 다음 단계 (이 recommend() 를 HTTP 로 감싸면 됨).
"""

import networkx as nx

from algo.routing.candidates import generate_candidates, drop_near_duplicate_courses
from algo.routing.course import generate_course_via
from algo.features.elevation import analyze_elevation_profile
from algo.features.facilities import analyze_nearby_facilities
from algo.features.nature import analyze_nature_adjacency
from algo.features.surface import analyze_surface_profile
from algo.scoring.weighting import score_candidate
_MODE = {
    "LOOP": "loop",
    "ONE_WAY": "point_to_point",
    "ROUND_TRIP": "out_and_back",
}


def _generate_via_candidates(
    G, idx, mode, start, target_m, end, vias, n_directions,
    pool=8, weights=None, requirements=None,
):
    """사용자 경유지가 있을 때: 우회점 방향(bearing)만 바꿔가며 후보 풀 생성.
    상위 3개 컷은 안 함 — recommend 가 conditionScore 매긴 뒤 자른다."""
    tail = end if mode == "point_to_point" else None   # LOOP/ROUND_TRIP 는 시작점 복귀
    out = []
    for k in range(n_directions):
        try:
            r = generate_course_via(G, idx, start, vias, target_m, end=tail,
                                    bearing=360.0 * k / n_directions,
                                    weights=weights, requirements=requirements)
        except (ValueError, nx.NetworkXException):
            continue
        if r["distance_error_pct"] <= 10:
            out.append(r)
    out.sort(key=lambda r: (r["overlap_ratio"], r["distance_error_pct"]))
    return drop_near_duplicate_courses(out)[:pool]


def recommend(G, idx, route_type, start, target_km, end=None, vias=None,
              weights=None, requirements=None, n_directions=12, top_k=3):
    mode = _MODE.get(route_type)
    if mode is None:
        raise ValueError(f"route_type 은 {list(_MODE)} 중 하나 (받음: {route_type})")
    if mode == "point_to_point" and end is None:
        raise ValueError("ONE_WAY 는 end 좌표가 필요합니다")

    target_m = target_km * 1000
    if vias:
        # [가중치 설계 변경] 후보 생성 단계부터 선호도와 필수조건을 경로 탐색에 반영한다.
        cands = _generate_via_candidates(
            G, idx, mode, start, target_m, end, vias, n_directions,
            weights=weights, requirements=requirements,
        )
    else:
        cands = generate_candidates(G, idx, mode, start, target_m,
                                    end=end, n_directions=n_directions,
                                    weights=weights, requirements=requirements)

    for c in cands:
        c["slope"] = analyze_elevation_profile(c["coords"])          # 경사 (DEM)
        c["facilities"] = analyze_nearby_facilities(c["coords"])        # 시설 (CSV)
        c["nature"] = analyze_nature_adjacency(c["coords"])       # 녹지·하천 인접률 (OSM 폴리곤)
        c["surface"] = analyze_surface_profile(G, c["nodes"])     # 노면·흐름 (OSM 엣지/노드)
        score_candidate(c, weights, requirements)         # sub_scores + conditionScore
        c.pop("nodes", None)                              # 내부용, 응답엔 불필요

    cands.sort(key=lambda c: c["condition_score"], reverse=True)
    return cands[:top_k]          # 풀에 점수 매긴 뒤 상위 top_k 만

if __name__ == "__main__":
    from pathlib import Path
    from algo.utils.graph import NodeIndex

    graphml = Path(__file__).parent / "data" / "서울_보행네트워크.graphml"
    if graphml.exists():
        from algo.utils.graph import load_graph
        print(f"[그래프] 실제 서울 도로망: {graphml.name}")
        G = load_graph(str(graphml))
    else:
        from algo.utils.graph import grid_graph
        print("[그래프] 격자 (build_graph.py 로 실제 그래프 빌드 가능)")
        G = grid_graph(90, 90, 100, origin=(37.475, 126.985))
    idx = NodeIndex(G)

    # start = (37.4979, 127.0276)   # 강남역
    start = (37.571806, 127.011287)  # 동대문역
    # end = (37.5045, 127.0400)     # 역삼 방향, 직선 약 1.3km (ONE_WAY 용, 목표 3km 보다 짧아야 함)
    end = (37.571153, 127.009639)  # 흥인지문(동대문)

    weights = {
        "distance": 5,    # 짧고 목표 거리에 가까운 경로
        "elevation": 4,   # 낮은 경사 선호
        "toilet": 5,      # 화장실 선호
        "store": 2,       # 편의점 선호
        "park": 3,        # 공원·하천 선호
        "night": 5,       # 조명·CCTV 선호
        "surface": 3,     # 보행 친화 노면 선호
        "flow": 2,        # 신호등이 적은 길 선호
        "overlap": 5,     # 같은 길 반복 억제
    }
    requirements = {
        "toilet": True,
        "store": False,
        "park": False,
        "no_stairs": True,
        "max_slope_pct": 8,
    }

    cases = [
        ("LOOP", 3.0, {}),
        ("ONE_WAY", 3.0, {"end": end}),
        ("ROUND_TRIP", 3.0, {}),
        ("LOOP", 5.0, {"vias": [(37.5045, 127.0490)]}),   # 선릉역 경유 순환 5km
    ]
    for rt, km, kw in cases:
        label = rt + (f" +경유지{len(kw['vias'])}" if kw.get("vias") else "")
        print(f"\n== {label} {km}km ==")
        cands = recommend(G, idx, rt, start, km, weights=weights,
                          requirements=requirements, **kw)
        if not cands:
            print("  (후보 없음)")
        for i, c in enumerate(cands, 1):
            ss = c["sub_scores"]
            print(f" {i}. conditionScore {c['condition_score']}  "
                  f"({c['actual_distance_m']}m, {c['estimated_minutes']}분, "
                  f"exact={c['exact_match']})")
            print("    소점수:", {k: v for k, v in ss.items() if v is not None})
            if c["failed_conditions"]:
                print("    미충족:", c["failed_conditions"])
