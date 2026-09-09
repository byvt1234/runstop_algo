"""
추천 코스를 HTML 지도로 그린다 (folium).

    python -m algo.draw_map LOOP 3
    python -m algo.draw_map ONE_WAY 3 --end 37.5045 127.0400
    python -m algo.draw_map ROUND_TRIP 5 --start 37.5563 126.9723
    python -m algo.draw_map LOOP 5 --via 37.5045 127.0490       # 경유지 (여러 번 가능)

결과: routes_map.html  (브라우저로 열기)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import folium

from algo.pipeline import recommend
from algo.utils.graph import NodeIndex, grid_graph, load_graph

ALGO_DIRECTORY = Path(__file__).resolve().parent
GRAPHML_PATH = ALGO_DIRECTORY / "data" / "서울_보행네트워크.graphml"
ROUTE_COLORS = ["#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#d62728"]


def _load_routing_graph():
    """도로망 GraphML을 로드하고, 파일이 없으면 테스트 격자를 생성한다."""
    # [draw_map 변경] 현재 algo 패키지 경로와 일치하는 유틸리티를 사용한다.
    if GRAPHML_PATH.exists():
        print(f"[그래프] {GRAPHML_PATH.name} 로드 중...")
        return load_graph(str(GRAPHML_PATH))
    print("[그래프] graphml 없음 -> 격자")
    return grid_graph(90, 90, 100, origin=(37.475, 126.985))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("route_type", nargs="?", default="LOOP",
                        choices=["LOOP", "ONE_WAY", "ROUND_TRIP"])
    parser.add_argument("target_km", nargs="?", type=float, default=3.0)
    parser.add_argument("--start", nargs=2, type=float, default=[37.571806, 127.011287],
                        metavar=("LAT", "LON"), help="기본: 강남역")
    parser.add_argument("--end", nargs=2, type=float, default=[37.571806, 127.011287],
                        metavar=("LAT", "LON"),
                        help="ONE_WAY 도착지. 기본: 역삼 방향(직선 ~1.3km). LOOP/ROUND_TRIP 은 무시")
    parser.add_argument("--via", action="append", nargs=2, type=float,
                        metavar=("LAT", "LON"),
                        help="반드시 지날 경유지 (여러 번 지정 가능)")
    parser.add_argument("--out", type=Path, default=ALGO_DIRECTORY / "routes_map.html")
    args = parser.parse_args()

    start_coordinates = tuple(args.start)
    end_coordinates = (
        tuple(args.end) if args.end and args.route_type == "ONE_WAY" else None
    )
    via_coordinates = [tuple(via) for via in args.via] if args.via else None

    # [draw_map 변경] 축약 변수를 도메인 의미가 드러나는 이름으로 통일했다.
    graph = _load_routing_graph()
    node_index = NodeIndex(graph)
    print(f"[추천] {args.route_type} {args.target_km}km"
          + (f"  경유지 {len(via_coordinates)}개" if via_coordinates else "") + " ...")
    candidates = recommend(
        graph,
        node_index,
        args.route_type,
        start_coordinates,
        args.target_km,
        end=end_coordinates,
        vias=via_coordinates,
    )
    if not candidates:
        raise SystemExit("후보 없음 (ONE_WAY 는 목표거리 > 직선거리 여야 함)")

    route_map = folium.Map(location=start_coordinates, zoom_start=15, tiles="OpenStreetMap")
    folium.Marker(start_coordinates, tooltip="출발",
                  icon=folium.Icon(color="green")).add_to(route_map)
    if end_coordinates:
        folium.Marker(end_coordinates, tooltip="도착",
                      icon=folium.Icon(color="red")).add_to(route_map)
    for waypoint_number, waypoint in enumerate(via_coordinates or [], 1):
        folium.Marker(waypoint, tooltip=f"경유지 {waypoint_number}",
                      icon=folium.Icon(color="orange", icon="flag")).add_to(route_map)

    all_route_coordinates = []
    for candidate_index, candidate in enumerate(candidates, 1):
        slope_metrics = candidate["slope"]
        facility_metrics = candidate["facilities"]
        tooltip_html = (
            f"#{candidate_index}  {candidate['actual_distance_m']}m "
            f"(오차 {candidate['distance_error_pct']}%)  "
            f"겹침 {candidate['overlap_ratio']}<br>"
            f"경사 avg {slope_metrics['avg_slope_pct']}% / "
            f"오르막 {slope_metrics['elevation_gain_m']}m<br>"
            f"화장실 {facility_metrics['toilet_count']} · "
            f"편의점 {facility_metrics['store_count']} · "
            f"공원 {facility_metrics['park_count']} · "
            f"CCTV {facility_metrics['cctv_count']}"
        )
        folium.PolyLine(
            candidate["coords"],
            color=ROUTE_COLORS[(candidate_index - 1) % len(ROUTE_COLORS)],
            weight=5,
            opacity=0.8,
            tooltip=tooltip_html,
        ).add_to(route_map)
        all_route_coordinates.extend(candidate["coords"])

    route_map.fit_bounds([
        [
            min(coordinate[0] for coordinate in all_route_coordinates),
            min(coordinate[1] for coordinate in all_route_coordinates),
        ],
        [
            max(coordinate[0] for coordinate in all_route_coordinates),
            max(coordinate[1] for coordinate in all_route_coordinates),
        ],
    ])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    route_map.save(str(args.out))
    # [draw_map 변경] Windows CP949 터미널에서도 출력되도록 ASCII 하이픈을 사용한다.
    print(f"[저장] {args.out} - 브라우저로 여세요")


if __name__ == "__main__":
    main()
