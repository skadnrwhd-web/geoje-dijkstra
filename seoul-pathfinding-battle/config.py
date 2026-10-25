"""
config.py
설정 파일(config.json)을 읽고 저장한다.

- DEFAULTS 에 모든 기본값이 있다. config.json 에는 바꾸고 싶은 값만 적어도 된다.
- load_config() 는 기본값 위에 config.json 값을 덮어써서 돌려준다.
"""

import copy
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.json"

# 영상 속 지도 패널 하나의 모양(가로/세로). animation.py 의 화면 배치와 같은 값
PANEL_ASPECT = 500 / 1230

DEFAULTS = {
    # "seoul" = 실제 서울 도로망(OpenStreetMap), "grid" = 인터넷 없이 쓰는 가상 격자 도시
    "map_mode": "seoul",

    "start": {"name": "광화문", "name_en": "Gwanghwamun", "lat": 37.5716, "lon": 126.9769},
    "goal": {"name": "사당역", "name_en": "Sadang Stn", "lat": 37.4765, "lon": 126.9816},

    "seoul_map": {
        # 출발지·목적지를 감싸는 사각형에 이만큼(km) 여유를 더해 도로망을 받는다
        "margin_km": 1.0,
        # 화면 패널 모양(가로/세로)에 맞춰 영역을 넓힌다. 0 이면 넓히지 않는다
        "fit_panel_aspect": True,
        # 직접 영역을 정하고 싶으면 [서쪽 경도, 남쪽 위도, 동쪽 경도, 북쪽 위도] 를 넣는다
        "bbox": None,
        # OSMnx 도로 종류: drive(자동차), walk(보행), bike(자전거)
        "network_type": "drive",
        "cache_dir": "maps",
        # 비우면 OSMnx 기본 Overpass 서버(overpass-api.de). 붐비면 다른 공개 서버 주소를 넣는다
        "overpass_url": "",
        "download_retries": 3,
    },

    "grid_map": {
        "cols": 34,
        "rows": 80,
        "spacing_m": 120,
        "jitter": 0.28,          # 교차로 위치를 흔드는 정도 (간격 대비 비율)
        "remove_ratio": 0.12,    # 끊어진 도로 비율
        "oneway_ratio": 0.08,    # 일방통행 비율
        "river": True,           # 가운데 강 + 다리 몇 개
        "bridges": 4,
        "seed": 7,
        # 격자 모드의 출발지·목적지 위치 (지도 가로·세로 대비 비율, 0~1)
        "start_frac": [0.45, 0.04],
        "goal_frac": [0.55, 0.96],
    },

    "benchmark": {
        "repeats": 7,                 # 실행 시간 측정 반복 횟수 (중앙값 사용)
        "time_tie_percent": 10.0,     # 실행 시간 차이가 이 % 이내면 무승부
    },

    "video": {
        "title": "DIJKSTRA vs A* | SEOUL ESCAPE",
        "subtitle": "같은 지도 · 같은 출발지 · 같은 목적지",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_sec": 25,           # 전체 영상 길이(초). speed 가 0 일 때 이 길이에 맞춘다
        "intro_sec": 3.0,
        "path_sec": 1.5,
        "result_sec": 6.0,
        "nodes_per_frame": 0,         # 애니메이션 속도: 한 프레임에 확장하는 노드 수 (0 = 자동)
        "output_dir": "output",
        "filename": "",               # 비우면 날짜_시간 으로 자동 이름
        "crf": 20,
        "disclaimer": "※ 실행 시간은 PC 성능·실행 환경에 따라 달라질 수 있습니다",
    },

    "style": {
        "background": "#05070d",
        "road": "#1d2a3e",
        "road_major": "#2c3f5c",
        "dijkstra": "#00e5ff",
        "astar": "#ff2bd6",
        "path": "#ffe600",
        "start": "#39ff88",
        "goal": "#ff3b3b",
        "text": "#e8f1ff",
        "muted": "#7f8ea8",
        # 비우면 시스템 글꼴을 자동으로 찾는다 (Windows: 맑은 고딕)
        "font": "",
        "font_bold": "",
    },
}


def deep_merge(base, extra):
    """base 사전 위에 extra 사전을 겹쳐 새 사전을 만든다 (하위 사전도 합친다)."""
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_config(path=CONFIG_PATH):
    """config.json 을 읽어 기본값과 합친 설정을 돌려준다. 파일이 없으면 기본값."""
    path = Path(path)
    user = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
    cfg = deep_merge(DEFAULTS, user)
    validate(cfg)
    return cfg


def save_config(cfg, path=CONFIG_PATH):
    validate(cfg)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def validate(cfg):
    """흔한 설정 실수를 알아보기 쉬운 메시지로 알려 준다."""
    if cfg["map_mode"] not in ("seoul", "grid"):
        raise ValueError(f"map_mode 는 'seoul' 또는 'grid' 여야 합니다: {cfg['map_mode']!r}")
    for key in ("start", "goal"):
        p = cfg[key]
        if not (-90 <= float(p["lat"]) <= 90 and -180 <= float(p["lon"]) <= 180):
            raise ValueError(f"{key} 좌표가 올바르지 않습니다: {p}")
    v = cfg["video"]
    if v["width"] % 2 or v["height"] % 2:
        raise ValueError("영상 가로·세로 크기는 짝수여야 합니다 (MP4 인코딩 조건)")
    if v["fps"] <= 0 or v["duration_sec"] <= 0:
        raise ValueError("fps 와 duration_sec 는 0보다 커야 합니다")
    if v["intro_sec"] + v["path_sec"] + v["result_sec"] >= v["duration_sec"]:
        raise ValueError("duration_sec 가 intro_sec + path_sec + result_sec 보다 길어야 합니다")


def resolve_path(p):
    """설정의 상대 경로를 프로젝트 폴더 기준 절대 경로로 바꾼다."""
    p = Path(p)
    return p if p.is_absolute() else PROJECT_DIR / p
