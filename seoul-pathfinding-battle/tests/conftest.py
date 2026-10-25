import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import load_config  # noqa: E402
from map_loader import make_grid_graph, pick_endpoints  # noqa: E402


@pytest.fixture
def grid_cfg():
    cfg = load_config(ROOT / "does_not_exist.json")   # 기본값만 사용
    cfg["map_mode"] = "grid"
    cfg["benchmark"]["repeats"] = 3
    return cfg


@pytest.fixture
def grid(grid_cfg):
    g = make_grid_graph(grid_cfg)
    s, t = pick_endpoints(g, grid_cfg)
    return g, s, t
