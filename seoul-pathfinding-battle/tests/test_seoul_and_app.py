"""서울 지도 테스트는 maps/ 에 저장된 지도가 있을 때만 돈다 (인터넷 없이 실행 가능하게)."""

import pytest

from algorithms import run_battle
from config import load_config
from map_loader import load_graph, pick_endpoints, seoul_cache_file


def seoul_cfg():
    cfg = load_config()
    cfg["map_mode"] = "seoul"
    cfg["benchmark"]["repeats"] = 3
    return cfg


@pytest.mark.skipif(not seoul_cache_file(seoul_cfg()).exists(), reason="저장된 서울 지도 없음")
def test_seoul_battle_is_optimal_and_respects_direction():
    cfg = seoul_cfg()
    g = load_graph(cfg, allow_download=False)
    s, t = pick_endpoints(g, cfg)
    b = run_battle(g, s, t, cfg)
    assert all(b["optimal"].values())
    assert b["astar"].expanded < b["dijkstra"].expanded
    # 직선 거리보다 도로 거리가 길어야 한다
    from map_loader import haversine_np
    import numpy as np
    straight = haversine_np(*np.radians([g.lat[s], g.lon[s], g.lat[t], g.lon[t]]))
    assert b["path_km"]["A*"] * 1000 > straight
    # 일방통행: 반대 방향 간선이 없는 간선이 존재해야 한다
    one_way = sum(1 for u, nb in enumerate(g.adj) for v, _ in nb if all(x != u for x, _ in g.adj[v]))
    assert one_way > 0


def test_app_starts_without_errors():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("../app.py", default_timeout=120).run()
    assert not at.exception
    assert any("Seoul Pathfinding Battle" in t.value for t in at.title)


def test_app_grid_battle_flow():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("../app.py", default_timeout=180).run()
    at.session_state.cfg["map_mode"] = "grid"
    at.session_state.cfg["benchmark"]["repeats"] = 3
    at.run()
    [b for b in at.button if b.label == "배틀 시작"][0].click().run()
    assert not at.exception
    assert at.session_state.battle is not None
    assert all(at.session_state.battle["optimal"].values())
