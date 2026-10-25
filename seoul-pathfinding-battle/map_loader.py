"""
map_loader.py
알고리즘이 달릴 도로 그래프를 만든다.

- load_seoul_graph(): OpenStreetMap 서울 도로망을 OSMnx 로 받아 maps/ 폴더에 저장(캐시)한다.
  두 번째 실행부터는 저장된 파일을 읽으므로 인터넷이 필요 없다.
- make_grid_graph(): 인터넷 없이 테스트하는 가상 격자 도시를 만든다.

어느 쪽이든 결과는 같은 RoadGraph 형태이고, 다익스트라와 A* 는 이 하나의 그래프를 함께 쓴다.
"""

import hashlib
import math
import random
import time
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from config import PANEL_ASPECT, resolve_path

# OSMnx 가 도로 길이를 계산할 때 쓰는 지구 반지름과 같은 값 (A* 휴리스틱도 이 값을 쓴다)
EARTH_RADIUS_M = 6_371_009
OSM_ATTRIBUTION = "Map data © OpenStreetMap contributors (ODbL)"
MAJOR_HIGHWAYS = {"motorway", "trunk", "primary", "secondary",
                  "motorway_link", "trunk_link", "primary_link", "secondary_link"}


class MapLoadError(RuntimeError):
    """지도를 만들 수 없을 때 사용자에게 보여 줄 메시지를 담는 오류."""


@dataclass
class RoadGraph:
    mode: str                    # "seoul" 또는 "grid"
    x: np.ndarray                # 노드 화면용 좌표 (미터, 동쪽 +)
    y: np.ndarray                # 노드 화면용 좌표 (미터, 북쪽 +)
    adj: list                    # adj[u] = [(v, 길이m), ...]  방향 있는 간선
    heuristic: str               # "haversine"(위경도) 또는 "euclid"(평면 미터)
    lat: np.ndarray | None = None
    lon: np.ndarray | None = None
    geom: dict = field(default_factory=dict)    # (u, v) -> 곡선 점들 [(x, y), ...]
    major: set = field(default_factory=set)     # 큰길 간선 (그림용)
    water: list = field(default_factory=list)   # 강 사각형 [(x0, y0, x1, y1)] (격자 모드 그림용)
    source: str = ""
    info: dict = field(default_factory=dict)

    @property
    def n_nodes(self):
        return len(self.adj)

    @property
    def n_edges(self):
        return sum(len(a) for a in self.adj)

    def to_networkx(self):
        """검증용: 같은 간선·비용으로 networkx 방향 그래프를 만든다."""
        g = nx.DiGraph()
        g.add_nodes_from(range(self.n_nodes))
        for u, nbrs in enumerate(self.adj):
            for v, w in nbrs:
                if not g.has_edge(u, v) or w < g[u][v]["length"]:   # 평행 간선은 가장 짧은 것
                    g.add_edge(u, v, length=w)
        return g

    def edge_points(self, u, v):
        pts = self.geom.get((u, v))
        if pts is not None:
            return pts
        return [(self.x[u], self.y[u]), (self.x[v], self.y[v])]

    def nearest_node(self, lat=None, lon=None, x=None, y=None):
        """가장 가까운 노드 번호와 그 거리(m)를 돌려준다."""
        if lat is not None:
            if self.lat is None:
                raise ValueError("이 지도에는 위경도가 없습니다")
            d = haversine_np(np.radians(lat), np.radians(lon),
                             np.radians(self.lat), np.radians(self.lon))
        else:
            d = np.hypot(self.x - x, self.y - y)
        i = int(np.argmin(d))
        return i, float(d[i])


def haversine_np(lat1, lon1, lat2, lon2):
    """대원 거리(m). 입력은 라디안."""
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ---------------------------------------------------------------- 서울 (OSM)

def seoul_bbox(cfg):
    """[서, 남, 동, 북] 영역. 직접 정한 bbox 가 없으면 출발지·목적지 + 여유로 계산."""
    sm = cfg["seoul_map"]
    if sm.get("bbox"):
        w, s, e, n = map(float, sm["bbox"])
        return w, s, e, n
    a, b = cfg["start"], cfg["goal"]
    lat_c = (a["lat"] + b["lat"]) / 2
    km_per_lat = math.pi * EARTH_RADIUS_M / 180 / 1000
    km_per_lon = km_per_lat * math.cos(math.radians(lat_c))
    m = float(sm["margin_km"])
    w_km = abs(a["lon"] - b["lon"]) * km_per_lon + 2 * m
    h_km = abs(a["lat"] - b["lat"]) * km_per_lat + 2 * m
    if sm.get("fit_panel_aspect"):
        # 영상 패널을 꽉 채우도록 좁은 쪽을 넓힌다
        if w_km / h_km < PANEL_ASPECT:
            w_km = h_km * PANEL_ASPECT
        else:
            h_km = w_km / PANEL_ASPECT
    lon_c = (a["lon"] + b["lon"]) / 2
    dlon = w_km / 2 / km_per_lon
    dlat = h_km / 2 / km_per_lat
    return (round(lon_c - dlon, 5), round(lat_c - dlat, 5),
            round(lon_c + dlon, 5), round(lat_c + dlat, 5))


def seoul_cache_file(cfg):
    bbox = seoul_bbox(cfg)
    net = cfg["seoul_map"]["network_type"]
    key = hashlib.sha1(f"{net}{bbox}".encode()).hexdigest()[:10]
    return resolve_path(cfg["seoul_map"]["cache_dir"]) / f"seoul_{net}_{key}.graphml"


def load_seoul_graph(cfg, allow_download=True, progress=print):
    try:
        import osmnx as ox
    except ImportError as e:
        raise MapLoadError("osmnx 가 설치되어 있지 않습니다. `pip install -r requirements.txt` "
                           "를 실행하거나 map_mode 를 'grid' 로 바꾸세요.") from e

    bbox = seoul_bbox(cfg)
    path = seoul_cache_file(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        progress(f"저장된 지도 읽는 중: {path.name}")
        G = ox.load_graphml(path)
    else:
        if not allow_download:
            raise MapLoadError(f"저장된 지도가 없습니다 ({path.name}). 인터넷에 연결해 한 번 받거나 "
                               "가상 격자 모드(grid)를 쓰세요.")
        progress(f"OpenStreetMap 에서 도로망 받는 중... 영역 {bbox}")
        sm = cfg["seoul_map"]
        ox.settings.use_cache = True
        ox.settings.cache_folder = str(path.parent / "http_cache")
        ox.settings.requests_timeout = 300
        if sm.get("overpass_url"):
            ox.settings.overpass_url = sm["overpass_url"].rstrip("/")
        tries = max(1, int(sm.get("download_retries", 3)))
        for attempt in range(1, tries + 1):
            try:
                G = ox.graph_from_bbox(bbox, network_type=sm["network_type"], simplify=True)
                break
            except Exception as e:
                # 공개 Overpass 서버는 자주 붐빈다 → 잠시 기다렸다 다시 시도
                if attempt == tries:
                    raise MapLoadError(
                        f"도로망을 받지 못했습니다 ({tries}회 시도): {e}\n"
                        "OpenStreetMap 의 Overpass 서버가 붐비거나 인터넷이 끊겼을 수 있습니다. "
                        "잠시 뒤 다시 시도하거나, config.json 의 seoul_map.overpass_url 을 다른 서버로 바꾸거나, "
                        "map_mode 를 'grid' 로 바꾸세요.") from e
                wait = 30 * attempt
                progress(f"다운로드 실패 ({attempt}/{tries}), {wait}초 뒤 다시 시도: {str(e)[:120]}")
                time.sleep(wait)
        # 일방통행 때문에 들어가기만 하고 나올 수 없는 곳을 없애려고 '강한 연결' 최대 덩어리만 남긴다
        G = ox.truncate.largest_component(G, strongly=True)
        ox.save_graphml(G, path)
        progress(f"저장 완료: {path}")

    rg = graph_from_osmnx(G)
    rg.info.update(bbox=bbox, cache_file=str(path))
    return rg


def graph_from_osmnx(G):
    """OSMnx MultiDiGraph -> RoadGraph. 같은 두 점 사이 평행 간선은 가장 짧은 것만 쓴다."""
    ids = list(G.nodes)
    index = {n: i for i, n in enumerate(ids)}
    lat = np.array([G.nodes[n]["y"] for n in ids], dtype=float)
    lon = np.array([G.nodes[n]["x"] for n in ids], dtype=float)
    lat0, lon0 = lat.mean(), lon.mean()
    k = math.pi * EARTH_RADIUS_M / 180

    def proj(lo, la):
        return (lo - lon0) * k * math.cos(math.radians(lat0)), (la - lat0) * k

    x, y = proj(lon, lat)

    best = {}
    for u, v, data in G.edges(data=True):
        a, b = index[u], index[v]
        if a == b:
            continue
        w = float(data["length"])
        if (a, b) not in best or w < best[(a, b)][0]:
            best[(a, b)] = (w, data)

    adj = [[] for _ in ids]
    geom, major = {}, set()
    for (a, b), (w, data) in best.items():
        adj[a].append((b, w))
        g = data.get("geometry")
        if g is not None:
            xs, ys = proj(np.array(g.xy[0]), np.array(g.xy[1]))
            geom[(a, b)] = list(zip(xs, ys))
        hw = data.get("highway", "")
        hw = hw if isinstance(hw, str) else (hw[0] if hw else "")
        if hw in MAJOR_HIGHWAYS:
            major.add((a, b))
    return RoadGraph(mode="seoul", x=x, y=y, lat=lat, lon=lon, adj=adj,
                     heuristic="haversine", geom=geom, major=major,
                     source=OSM_ATTRIBUTION, info={"osm_ids": ids})


# ---------------------------------------------------------------- 가상 격자 도시

def make_grid_graph(cfg):
    gc = cfg["grid_map"]
    rows, cols, sp = int(gc["rows"]), int(gc["cols"]), float(gc["spacing_m"])
    rng = random.Random(gc["seed"])

    def nid(r, c):
        return r * cols + c

    xs = np.zeros(rows * cols)
    ys = np.zeros(rows * cols)
    for r in range(rows):
        for c in range(cols):
            j = gc["jitter"] * sp
            xs[nid(r, c)] = c * sp + rng.uniform(-j, j)
            ys[nid(r, c)] = (rows - 1 - r) * sp + rng.uniform(-j, j)

    river_row = rows // 2 if gc.get("river") else None
    bridges = set()
    if river_row is not None:
        n = max(1, int(gc["bridges"]))
        bridges = {int((i + 0.5) * cols / n + rng.randint(-2, 2)) for i in range(n)}

    pairs = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                pairs.append(((r, c), (r, c + 1)))
            if r + 1 < rows:
                if river_row is not None and r == river_row and c not in bridges:
                    continue   # 강을 건너는 길은 다리에서만
                pairs.append(((r, c), (r + 1, c)))

    g = nx.DiGraph()
    g.add_nodes_from(range(rows * cols))
    major = set()
    for (r1, c1), (r2, c2) in pairs:
        is_bridge = river_row is not None and r1 == river_row and r2 == river_row + 1
        if not is_bridge and rng.random() < gc["remove_ratio"]:
            continue
        a, b = nid(r1, c1), nid(r2, c2)
        w = float(math.hypot(xs[a] - xs[b], ys[a] - ys[b]))
        both = is_bridge or rng.random() >= gc["oneway_ratio"]
        first = rng.random() < 0.5
        if both or first:
            g.add_edge(a, b, length=w)
        if both or not first:
            g.add_edge(b, a, length=w)
        if is_bridge or (r1 == r2 and r1 % 8 == 0) or (c1 == c2 and c1 % 6 == 0):
            major.update({(a, b), (b, a)})

    keep = max(nx.strongly_connected_components(g), key=len)
    old = sorted(keep)
    index = {o: i for i, o in enumerate(old)}
    adj = [[] for _ in old]
    for a, b, d in g.edges(data=True):
        if a in index and b in index:
            adj[index[a]].append((index[b], d["length"]))
    major = {(index[a], index[b]) for a, b in major if a in index and b in index}

    water = []
    if river_row is not None:
        y_top = (rows - 1 - river_row) * sp
        water.append((-sp, y_top - sp * 0.78, cols * sp, y_top - sp * 0.22))

    rg = RoadGraph(mode="grid", x=xs[old], y=ys[old], adj=adj, heuristic="euclid",
                   major=major, water=water,
                   source="Synthetic grid city (no external data)")
    rg.info["bbox"] = (float(rg.x.min()), float(rg.y.min()), float(rg.x.max()), float(rg.y.max()))
    return rg


# ---------------------------------------------------------------- 공통 진입점

def load_graph(cfg, allow_download=True, progress=print):
    if cfg["map_mode"] == "grid":
        return make_grid_graph(cfg)
    return load_seoul_graph(cfg, allow_download=allow_download, progress=progress)


def pick_endpoints(graph, cfg, max_snap_m=1500):
    """설정의 출발지·목적지를 그래프의 가장 가까운 교차로 번호로 바꾼다."""
    if graph.mode == "grid":
        x0, y0, x1, y1 = graph.info["bbox"]
        pts = []
        for key in ("start_frac", "goal_frac"):
            fx, fy = cfg["grid_map"][key]
            pts.append(graph.nearest_node(x=x0 + fx * (x1 - x0), y=y1 - fy * (y1 - y0))[0])
        s, t = pts
    else:
        s, ds = graph.nearest_node(lat=cfg["start"]["lat"], lon=cfg["start"]["lon"])
        t, dt = graph.nearest_node(lat=cfg["goal"]["lat"], lon=cfg["goal"]["lon"])
        for name, d in (("출발지", ds), ("목적지", dt)):
            if d > max_snap_m:
                raise MapLoadError(f"{name} 에서 가장 가까운 도로가 {d:.0f}m 떨어져 있습니다. "
                                   "좌표가 지도 영역 안에 있는지 확인하세요.")
    if s == t:
        raise MapLoadError("출발지와 목적지가 같은 교차로입니다. 좌표를 더 떨어뜨려 주세요.")
    return s, t
