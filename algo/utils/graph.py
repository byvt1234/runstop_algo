"""
도로 그래프 로드 + 좌표 -> 노드 스냅.

TMAP(블랙박스) 대신 OSM 보행 네트워크를 networkx 그래프로 직접 들고 다닌다.
그래야 routing.py 에서 "이미 지나온 엣지에 벌점" 조작이 가능하다.

그래프 스키마 (osmnx 와 동일):
  노드: x=경도, y=위도   |   엣지: length=미터   |   타입: MultiDiGraph

실제 서울 그래프는 build_graph.py 로 만든 graphml 을 load_graphml() 로 읽는다.
그게 없을 때 개발/테스트용으로 grid_graph() 를 쓴다.
"""

import pickle
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

from algo.utils.geo import point_at_bearing, to_5179


def load_graphml(path):
    """osmnx graphml -> MultiDiGraph. 문자열로 저장된 좌표/길이를 float 로 복원."""
    G = nx.read_graphml(path, force_multigraph=True)
    for _, d in G.nodes(data=True):
        d["x"] = float(d["x"])
        d["y"] = float(d["y"])
    for _, _, d in G.edges(data=True):
        d["length"] = float(d.get("length", 1.0))
    return G


def load_graph(graphml_path):
    """graphml 로드 + pickle 캐시. 두 번째 실행부터 훨씬 빠름 (~19s -> ~3s).
    .pkl 이 graphml 보다 최신일 때만 사용 (build_graph 재실행 시 자동 무효화).
    networkx 버전을 올린 뒤 이상하면 .pkl 을 지우면 다음 실행에 새로 만든다."""
    p = Path(graphml_path)
    cache = p.with_suffix(".pkl")
    if cache.exists() and cache.stat().st_mtime >= p.stat().st_mtime:
        with open(cache, "rb") as f:
            return pickle.load(f)
    G = load_graphml(str(p))
    with open(cache, "wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
    return G
 

class NodeIndex:
    """(lat, lon) -> 가장 가까운 그래프 노드 id. EPSG:5179 평면에서 KD-tree 최근접."""

    def __init__(self, G):
        self.ids = list(G.nodes)
        xy = np.array([
            to_5179.transform(G.nodes[n]["x"], G.nodes[n]["y"])
            for n in self.ids
        ])
        self._tree = cKDTree(xy)

    def snap(self, lat, lon):
        x, y = to_5179.transform(lon, lat)
        _, i = self._tree.query([x, y])
        return self.ids[i]


def grid_graph(rows=80, cols=80, spacing_m=100.0, origin=(37.50, 127.02)):
    """테스트용 격자 도로망. 실제 OSM 그래프와 같은 스키마(x, y, length).
    r 증가 = 북쪽, c 증가 = 동쪽. 모든 엣지 양방향."""
    G = nx.MultiDiGraph()
    lat0, lon0 = origin

    for r in range(rows):
        lat_r, lon_r = point_at_bearing(lat0, lon0, 0, r * spacing_m)
        for c in range(cols):
            lat, lon = point_at_bearing(lat_r, lon_r, 90, c * spacing_m)
            G.add_node((r, c), x=lon, y=lat)

    for r in range(rows):
        for c in range(cols):
            for dr, dc in ((1, 0), (0, 1)):
                r2, c2 = r + dr, c + dc
                if r2 < rows and c2 < cols:
                    G.add_edge((r, c), (r2, c2), length=spacing_m)
                    G.add_edge((r2, c2), (r, c), length=spacing_m)
    return G


if __name__ == "__main__":
    G = grid_graph(rows=10, cols=10, spacing_m=100)
    print("노드:", G.number_of_nodes(), "엣지:", G.number_of_edges())
    print("(9,9) 좌표:", G.nodes[(9, 9)])
    print("연결됨?", nx.is_strongly_connected(G))

    idx = NodeIndex(G)
    t = G.nodes[(5, 5)]
    print("스냅:", idx.snap(t["y"], t["x"]), "(→ (5,5) 기대)")
