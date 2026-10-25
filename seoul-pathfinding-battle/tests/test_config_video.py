import json
import subprocess

import pytest

from algorithms import run_battle
from animation import BattleRenderer, map_preview
from config import DEFAULTS, deep_merge, load_config, validate
from video_export import find_ffmpeg, make_video


def test_config_merges_partial_file(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"video": {"title": "TEST"}, "map_mode": "grid"}), encoding="utf-8")
    cfg = load_config(p)
    assert cfg["video"]["title"] == "TEST"
    assert cfg["video"]["fps"] == DEFAULTS["video"]["fps"]    # 나머지는 기본값
    assert cfg["map_mode"] == "grid"


def test_config_validation():
    bad = deep_merge(DEFAULTS, {"map_mode": "mars"})
    with pytest.raises(ValueError):
        validate(bad)
    bad = deep_merge(DEFAULTS, {"video": {"width": 1081}})
    with pytest.raises(ValueError):
        validate(bad)


def test_project_config_json_is_valid():
    load_config()   # 저장된 config.json 이 깨지지 않았는지


def test_timeline_fits_requested_duration(grid, grid_cfg):
    g, s, t = grid
    b = run_battle(g, s, t, grid_cfg)
    r = BattleRenderer(g, b, grid_cfg)
    v = grid_cfg["video"]
    assert abs(r.duration_sec - v["duration_sec"]) < 1.0
    assert r.done_at["A*"] <= r.done_at["Dijkstra"]          # 같은 속도 → 적게 탐색한 쪽이 먼저 끝남
    assert r.npf * r.search_n >= max(b["dijkstra"].expanded, b["astar"].expanded)


def test_key_frames_and_map_preview(grid, grid_cfg):
    g, s, t = grid
    b = run_battle(g, s, t, grid_cfg)
    frames = BattleRenderer(g, b, grid_cfg, width=540, height=960).key_frames()
    assert len(frames) == 4
    assert all(im.size == (540, 960) for im in frames.values())
    assert map_preview(g, s, t, grid_cfg).size[0] > 100


def test_short_mp4_export(grid_cfg, tmp_path):
    grid_cfg["video"].update(duration_sec=4, intro_sec=0.5, path_sec=0.5, result_sec=1.0)
    out = tmp_path / "t.mp4"
    res = make_video(grid_cfg, preview=True, out_path=out, log=lambda m: None)
    assert out.exists() and out.stat().st_size > 10_000
    assert res["json"].exists()
    probe = subprocess.run([find_ffmpeg(), "-i", str(out)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stderr
    assert "540x960" in probe and "h264" in probe
    log = json.loads(res["json"].read_text(encoding="utf-8"))
    assert log["results"]["A*"]["expanded"] == res["battle"]["astar"].expanded
