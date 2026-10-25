import math
import random

import networkx as nx
import numpy as np
import pytest

from algorithms import (NoPathError, astar, dijkstra, judge, make_heuristic, path_length_m,
                        run_battle, search_recorded)
from map_loader import RoadGraph, make_grid_graph, pick_endpoints


def test_both_find_optimal_path_on_grid(grid, grid_cfg):
    g, s, t = grid
    b = run_battle(g, s, t, grid_cfg)
    ref = nx.dijkstra_path_length(g.to_networkx(), s, t, weight="length")
    assert b["dijkstra"].cost_m == pytest.approx(ref)
    assert b["astar"].cost_m == pytest.approx(ref)
    assert all(b["optimal"].values())
    # 경로 길이는 실제 간선 길이의 합과 같아야 한다
    assert b["path_km"]["A*"] * 1000 == pytest.approx(b["astar"].cost_m)
    assert b["astar"].path[0] == s and b["astar"].path[-1] == t


def test_astar_expands_no_more_than_dijkstra(grid):
    g, s, t = grid
    d = dijkstra(g.adj, s, t)
    a = astar(g.adj, s, t, make_heuristic(g, t))
    assert a.expanded <= d.expanded
    assert d.found and a.found
    assert d.expanded >= len(d.path)


def test_recorded_run_matches_timed_run(grid):
    g, s, t = grid
    h = make_heuristic(g, t)
    for rec, pure in ((search_recorded("Dijkstra", g.adj, s, t), dijkstra(g.adj, s, t)),
                      (search_recorded("A*", g.adj, s, t, h), astar(g.adj, s, t, h))):
        assert rec.expanded == pure.expanded == len(rec.trace)
        assert rec.path == pure.path
        assert rec.edges_scanned == pure.edges_scanned
        # 기록된 확장 노드는 모두 고유해야 한다
        assert len({u for u, _, _ in rec.trace}) == rec.expanded


def test_euclid_heuristic_is_admissible(grid):
    g, s, t = grid
    h = make_heuristic(g, t)
    true = nx.single_source_dijkstra_path_length(g.to_networkx().reverse(), t, weight="length")
    assert all(h(v) <= dist + 1e-9 for v, dist in true.items())


def make_latlon_graph(seed=1, n=400):
    """위경도 좌표의 무작위 도로망. 간선 길이 = 대원 거리 x (1~1.4) 이므로 실제 도로처럼 직선보다 길다."""
    rng = random.Random(seed)
    lat = np.array([37.45 + rng.random() * 0.15 for _ in range(n)])
    lon = np.array([126.9 + rng.random() * 0.2 for _ in range(n)])
    from map_loader import haversine_np
    pts = np.radians(np.c_[lat, lon])
    adj = [[] for _ in range(n)]
    for u in range(n):
        d = haversine_np(pts[u, 0], pts[u, 1], pts[:, 0], pts[:, 1])
        for v in np.argsort(d)[1:6]:
            w = float(d[v]) * rng.uniform(1.0, 1.4)
            adj[u].append((int(v), w))
            if rng.random() < 0.8:      # 나머지는 일방통행
                adj[int(v)].append((u, w))
    return RoadGraph(mode="seoul", x=lon, y=lat, lat=lat, lon=lon, adj=adj, heuristic="haversine")


@pytest.mark.parametrize("seed", range(5))
def test_haversine_astar_is_optimal_on_random_road_graphs(seed):
    g = make_latlon_graph(seed)
    G = g.to_networkx()
    rng = random.Random(seed)
    for _ in range(10):
        s, t = rng.sample(range(g.n_nodes), 2)
        try:
            ref = nx.dijkstra_path_length(G, s, t, weight="length")
        except nx.NetworkXNoPath:
            assert not astar(g.adj, s, t, make_heuristic(g, t)).found
            continue
        a = astar(g.adj, s, t, make_heuristic(g, t))
        d = dijkstra(g.adj, s, t)
        assert a.cost_m == pytest.approx(ref, rel=1e-9)
        assert d.cost_m == pytest.approx(ref, rel=1e-9)
        assert path_length_m(g, a.path) == pytest.approx(ref, rel=1e-9)


def test_one_way_is_respected():
    # 0 -> 1 -> 2 만 있고 되돌아가는 길은 없다
    g = RoadGraph(mode="grid", x=np.array([0.0, 1, 2]), y=np.zeros(3),
                  adj=[[(1, 1.0)], [(2, 1.0)], []], heuristic="euclid")
    assert dijkstra(g.adj, 0, 2).found
    assert not dijkstra(g.adj, 2, 0).found
    assert not astar(g.adj, 2, 0, make_heuristic(g, 0)).found


def test_no_path_gives_clear_error(grid_cfg):
    g = RoadGraph(mode="grid", x=np.array([0.0, 1, 2]), y=np.zeros(3),
                  adj=[[(1, 1.0)], [(0, 1.0)], []], heuristic="euclid")
    with pytest.raises(NoPathError, match="경로가 없습니다"):
        run_battle(g, 0, 2, grid_cfg)


def test_judge_rules():
    from algorithms import SearchResult
    d = SearchResult("Dijkstra", True, [0, 1], 1000.0, 500, 0, 0)
    a = SearchResult("A*", True, [0, 1], 1000.0, 100, 0, 0)
    v = judge(d, a, td=10.0, ta=5.0, tie_percent=10)
    assert v["winner"] == "A*" and v["score"] == {"Dijkstra": 0, "A*": 2}
    v = judge(d, a, td=5.0, ta=5.2, tie_percent=10)       # 4% 차이 → 시간은 무승부
    assert [r["winner"] for r in v["rows"]] == ["tie", "A*", "tie"]
    v = judge(d, a, td=3.0, ta=6.0, tie_percent=10)       # 1:1 → 종합 무승부
    assert v["winner"] == "DRAW"


def test_grid_is_deterministic(grid_cfg):
    a, b = make_grid_graph(grid_cfg), make_grid_graph(grid_cfg)
    assert a.adj == b.adj
    assert pick_endpoints(a, grid_cfg) == pick_endpoints(b, grid_cfg)
