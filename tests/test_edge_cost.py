"""사용자 가중치가 실제 최단경로 선택에 반영되는지 검증한다."""

import unittest

import networkx as nx

from algo.routing.shortest_path import path_to_edge_set, shortest_path


def _add_bidirectional_edge(graph, start, end, **attributes):
    # [가중치 설계 추가] 테스트 그래프의 양방향 도로를 간단히 구성한다.
    graph.add_edge(start, end, **attributes)
    graph.add_edge(end, start, **attributes)


class WeightedEdgeCostTests(unittest.TestCase):
    def setUp(self):
        # [가중치 설계 추가] 모든 테스트가 공유하는 최소 OSM 형태의 그래프다.
        self.graph = nx.MultiDiGraph()
        for node_id in ("start", "major", "walk", "end"):
            self.graph.add_node(node_id, highway=None)

    def test_surface_preference_changes_selected_route(self):
        _add_bidirectional_edge(
            self.graph,
            "start",
            "major",
            length=100,
            highway="primary",
        )
        _add_bidirectional_edge(
            self.graph,
            "major",
            "end",
            length=100,
            highway="primary",
        )
        _add_bidirectional_edge(
            self.graph,
            "start",
            "walk",
            length=115,
            highway="footway",
        )
        _add_bidirectional_edge(
            self.graph,
            "walk",
            "end",
            length=115,
            highway="footway",
        )

        distance_only_weights = {
            "distance": 5,
            "elevation": 0,
            "safety": 0,
            "nature": 0,
            "surface": 0,
            "flow": 0,
            "overlap": 0,
        }
        surface_first_weights = {**distance_only_weights, "distance": 3, "surface": 5}

        shortest_nodes, _ = shortest_path(
            self.graph,
            "start",
            "end",
            weights=distance_only_weights,
        )
        walkable_nodes, _ = shortest_path(
            self.graph,
            "start",
            "end",
            weights=surface_first_weights,
        )

        self.assertEqual(shortest_nodes, ["start", "major", "end"])
        self.assertEqual(walkable_nodes, ["start", "walk", "end"])

    def test_no_stairs_requirement_excludes_steps(self):
        _add_bidirectional_edge(
            self.graph,
            "start",
            "major",
            length=50,
            highway="steps",
        )
        _add_bidirectional_edge(
            self.graph,
            "major",
            "end",
            length=50,
            highway="steps",
        )
        _add_bidirectional_edge(
            self.graph,
            "start",
            "walk",
            length=100,
            highway="footway",
        )
        _add_bidirectional_edge(
            self.graph,
            "walk",
            "end",
            length=100,
            highway="footway",
        )

        route_nodes, _ = shortest_path(
            self.graph,
            "start",
            "end",
            requirements={"no_stairs": True},
        )

        self.assertEqual(route_nodes, ["start", "walk", "end"])

    def test_no_stairs_requirement_reports_no_path_when_only_steps_exist(self):
        # [가중치 설계 추가] 필수 조건은 단순 감점이 아니라 도로를 완전히 제외해야 한다.
        _add_bidirectional_edge(
            self.graph,
            "start",
            "major",
            length=50,
            highway="steps",
        )
        _add_bidirectional_edge(
            self.graph,
            "major",
            "end",
            length=50,
            highway="steps",
        )

        with self.assertRaises(nx.NetworkXNoPath):
            shortest_path(
                self.graph,
                "start",
                "end",
                requirements={"no_stairs": True},
            )

    def test_used_edge_penalty_selects_alternative_route(self):
        _add_bidirectional_edge(
            self.graph,
            "start",
            "major",
            length=100,
            highway="footway",
        )
        _add_bidirectional_edge(
            self.graph,
            "major",
            "end",
            length=100,
            highway="footway",
        )
        _add_bidirectional_edge(
            self.graph,
            "start",
            "walk",
            length=110,
            highway="footway",
        )
        _add_bidirectional_edge(
            self.graph,
            "walk",
            "end",
            length=110,
            highway="footway",
        )

        first_route, _ = shortest_path(self.graph, "start", "end")
        alternative_route, _ = shortest_path(
            self.graph,
            "start",
            "end",
            # [가중치 설계 변경] 최신 함수명 path_to_edge_set에 맞춘다.
            penalty_edges=path_to_edge_set(first_route),
            factor=5.0,
            weights={"overlap": 5},
        )

        self.assertEqual(first_route, ["start", "major", "end"])
        self.assertEqual(alternative_route, ["start", "walk", "end"])


if __name__ == "__main__":
    unittest.main()
