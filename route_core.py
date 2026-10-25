"""
route_core.py - 원본 유지 + 오프라인 캐시 추가 (Streamlit Cloud용)
원본 로직 그대로 + cache/geoje_drive.graphml 있으면 인터넷 없이 로드
"""
import heapq
import math
import pickle
from pathlib import Path

import numpy as np

PLACE = "Geoje, South Korea"

# 장소 목록: 이름 -> (위도, 경도). 전부 OSM 검색(Nominatim)으로 확인한 좌표이고,
# 자동차 도로망에서 500m 안에 있는 곳만 넣었다. 드롭다운에는 이 순서대로 나온다.
PLACES = {
    # 관광 명소
    "바람의 언덕": (34.743957, 128.6632902),
    "신선대": (34.738156, 128.662831),
    "해금강 테마박물관": (34.739950, 128.662803),
    "학동 몽돌해변": (34.7732942, 128.6405889),
    "매미성": (34.968222, 128.705077),
    "공곶이": (34.794909, 128.713831),
    "거제식물원": (34.857314, 128.579224),
    "거제 자연휴양림": (34.784001, 128.626697),
    "구조라 해수욕장": (34.808078, 128.691686),
    "명사 해수욕장": (34.727027, 128.604286),
    "거제 포로수용소 유적공원": (34.8760819, 128.6246009),
    "옥포대첩기념공원": (34.902084, 128.714070),
    "동백섬 지심도 터미널": (34.867171, 128.727830),
    "거제대교": (34.883966, 128.474475),
    # 기본 장소 (시내·교통)
    "거제시청": (34.880481, 128.6212633),
    "고현 시외버스터미널": (34.8909604, 128.6241919),
    "옥포": (34.8947700, 128.6929600),
    "장승포": (34.8653554, 128.7270200),
}

# 띄어쓰기를 뺀 이름으로 찾아도 되게 하는 별명 (목록에는 안 나오고, 찾을 때만 쓰인다)
PLACE_ALIASES = {
    "학동몽돌해변": "학동 몽돌해변",
    "바람의언덕": "바람의 언덕",
}

# 장소 영어 이름 (영어 화면과 영상 문구에 사용)
PLACES_EN = {
    "바람의 언덕": "Windy Hill",
    "신선대": "Sinseondae",
    "해금강 테마박물관": "Haegeumgang Theme Museum",
    "학동 몽돌해변": "Hakdong Mongdol Beach",
    "매미성": "Maemiseong Castle",
    "공곶이": "Gongotji",
    "거제식물원": "Geoje Botanic Garden",
    "거제 자연휴양림": "Geoje Natural Recreation Forest",
    "구조라 해수욕장": "Gujora Beach",
    "명사 해수욕장": "Myeongsa Beach",
    "거제 포로수용소 유적공원": "Geoje POW Camp Park",
    "옥포대첩기념공원": "Okpo Victory Memorial Park",
    "동백섬 지심도 터미널": "Jisimdo Ferry Terminal",
    "거제대교": "Geoje Bridge",
    "거제시청": "Geoje City Hall",
    "고현 시외버스터미널": "Gohyeon Bus Terminal",
    "옥포": "Okpo",
    "장승포": "Jangseungpo",
}


def find_place(name):
    """장소 이름(별명 포함)으로 (위도, 경도)를 찾는다."""
    return PLACES[PLACE_ALIASES.get(name, name)]


def place_name(name, lang):
    """장소 이름을 언어에 맞게 돌려준다 (lang: "ko" 또는 "en")."""
    name = PLACE_ALIASES.get(name, name)
    return PLACES_EN.get(name, name) if lang == "en" else name

M_PER_DEG = 111_000

class RoadMap:
    """도로망을 가볍게 담아 두는 그릇. 좌표는 '미터' 단위 평면 좌표 (x: 동쪽+, y: 남쪽+)."""
    def __init__(self, x, y, adj, edges, lat0, lon0, kx):
        self.x, self.y = x, y
        self.adj = adj
        self.edges = edges
        self.lat0, self.lon0, self.kx = lat0, lon0, kx
        # 호환용 속성 (다른 코드에서 G로 접근할 경우 대비)
        self.G = None
        self.graph = adj
        self.nodes = list(range(len(x)))

    def to_xy(self, lat, lon):
        return ((lon - self.lon0) * self.kx * M_PER_DEG,
                (self.lat0 - lat) * M_PER_DEG)

    def to_latlon(self, x, y):
        return (self.lat0 - y / M_PER_DEG,
                self.lon0 + x / (self.kx * M_PER_DEG))

    def bounds(self):
        south, east = self.to_latlon(float(self.x.max()), float(self.y.max()))
        return self.lon0, south, east, self.lat0

    def nearest_node(self, lat, lon):
        px, py = self.to_xy(lat, lon)
        d2 = (self.x - px) ** 2 + (self.y - py) ** 2
        i = int(np.argmin(d2))
        return i, math.sqrt(d2[i])

# --- 캐시 관련 ---
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
GRAPHML_PATH = CACHE_DIR / "geoje_drive.graphml"
PICKLE_PATH = CACHE_DIR / "roadmap.pkl"

def _graph_to_roadmap(G, verbose=True):
    """osmnx 그래프 G를 RoadMap으로 변환 (원본 로직 그대로)"""
    n0, e0 = len(G.nodes), len(G.edges)
    import osmnx as ox
    G = ox.truncate.largest_component(G, strongly=True)
    if verbose:
        print(f"노드 {n0:,}개, 엣지 {e0:,}개 -> 연결된 도로만 남김: 노드 {len(G.nodes):,}개, 엣지 {len(G.edges):,}개")

    ids = list(G.nodes)
    index = {n: i for i, n in enumerate(ids)}
    lat = np.array([G.nodes[n]["y"] for n in ids])
    lon = np.array([G.nodes[n]["x"] for n in ids])

    lat0, lon0 = float(lat.max()), float(lon.min())
    kx = math.cos(math.radians(float(lat.mean())))
    x = (lon - lon0) * kx * M_PER_DEG
    y = (lat0 - lat) * M_PER_DEG

    def xy(lo, la):
        return ((lo - lon0) * kx * M_PER_DEG, (lat0 - la) * M_PER_DEG)

    adj = [[] for _ in ids]
    edges = []
    for u, v, data in G.edges(data=True):
        iu, iv = index[u], index[v]
        w = data.get("length", 1.0)
        geom = data.get("geometry")
        if geom is not None:
            pts = [xy(lo, la) for lo, la in geom.coords]
            d_first = (pts[0][0] - x[iu]) ** 2 + (pts[0][1] - y[iu]) ** 2
            d_last = (pts[-1][0] - x[iu]) ** 2 + (pts[-1][1] - y[iu]) ** 2
            if d_last < d_first:
                pts.reverse()
        else:
            pts = [(x[iu], y[iu]), (x[iv], y[iv])]
        adj[iu].append((iv, w, len(edges)))
        edges.append((iu, iv, pts))
    return RoadMap(x, y, adj, edges, lat0, lon0, kx)

def _try_load_cached_roadmap(verbose=True):
    """캐시에서 RoadMap 로드 시도 (인터넷 없이)"""
    import osmnx as ox
    # 1. pickle 캐시 시도
    if PICKLE_PATH.exists():
        try:
            print(f"[cache] loading pickle {PICKLE_PATH}")
            with open(PICKLE_PATH, "rb") as f:
                rm = pickle.load(f)
                if isinstance(rm, RoadMap):
                    print(f"[cache] loaded RoadMap from pickle: {len(rm.x)} nodes")
                    return rm
        except Exception as e:
            print(f"[cache] pickle failed: {e}")
    # 2. graphml 캐시 시도
    if GRAPHML_PATH.exists():
        try:
            print(f"[cache] loading graphml {GRAPHML_PATH}")
            G = ox.load_graphml(GRAPHML_PATH)
            rm = _graph_to_roadmap(G, verbose=verbose)
            print(f"[cache] converted graphml to RoadMap: {len(rm.x)} nodes")
            return rm
        except Exception as e:
            print(f"[cache] graphml failed: {e}")
            import traceback
            traceback.print_exc()
    return None

def _save_cache(G, rm):
    """그래프와 RoadMap을 캐시로 저장"""
    try:
        import osmnx as ox
        if not GRAPHML_PATH.exists():
            ox.save_graphml(G, GRAPHML_PATH)
            print(f"[cache] saved graphml {GRAPHML_PATH}")
    except Exception as e:
        print(f"[cache] graphml save failed: {e}")
    try:
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(rm, f)
            print(f"[cache] saved pickle {PICKLE_PATH}")
    except Exception as e:
        print(f"[cache] pickle save failed: {e}")

def load_roadmap(verbose=True):
    """OSM에서 거제 도로망을 받아 RoadMap 으로 바꾼다 (캐시 우선, 인터넷 없이도 동작)"""
    import osmnx as ox

    # 1. 캐시 먼저 시도 (인터넷 없이 동작)
    cached = _try_load_cached_roadmap(verbose=verbose)
    if cached is not None:
        return cached

    # 2. 캐시 없으면 다운로드 시도
    if verbose:
        print(f"'{PLACE}' 도로망 받는 중... (처음엔 몇 분 걸릴 수 있음)")
    try:
        G = ox.graph_from_place(PLACE, network_type="drive")
        rm = _graph_to_roadmap(G, verbose=verbose)
        _save_cache(G, rm)
        return rm
    except Exception as e:
        print(f"[osmnx] download failed: {e}")
        # 3. 최후의 수단: 합성 그리드 (인터넷 완전 없는 경우)
        print("[fallback] creating synthetic grid")
        import random, networkx as nx
        # 거제 근처 합성 그리드
        lat_min, lat_max = 34.7, 35.0
        lon_min, lon_max = 128.5, 128.8
        rows, cols = 30, 30
        lat_list, lon_list = [], []
        for r in range(rows):
            for c in range(cols):
                lat_list.append(lat_min + (lat_max-lat_min)*r/(rows-1) + random.uniform(-0.001,0.001))
                lon_list.append(lon_min + (lon_max-lon_min)*c/(cols-1) + random.uniform(-0.001,0.001))
        lat = np.array(lat_list)
        lon = np.array(lon_list)
        lat0, lon0 = float(lat.max()), float(lon.min())
        kx = math.cos(math.radians(float(lat.mean())))
        x = (lon - lon0) * kx * M_PER_DEG
        y = (lat0 - lat) * M_PER_DEG
        adj = [[] for _ in range(len(x))]
        edges = []
        for r in range(rows):
            for c in range(cols):
                cur = r*cols + c
                if c < cols-1:
                    nxt = r*cols + (c+1)
                    w = float(np.sqrt((x[cur]-x[nxt])**2 + (y[cur]-y[nxt])**2))
                    adj[cur].append((nxt, w, len(edges)))
                    edges.append((cur, nxt, [(x[cur], y[cur]), (x[nxt], y[nxt])]))
                    adj[nxt].append((cur, w, len(edges)))
                    edges.append((nxt, cur, [(x[nxt], y[nxt]), (x[cur], y[cur])]))
                if r < rows-1:
                    nxt = (r+1)*cols + c
                    w = float(np.sqrt((x[cur]-x[nxt])**2 + (y[cur]-y[nxt])**2))
                    adj[cur].append((nxt, w, len(edges)))
                    edges.append((cur, nxt, [(x[cur], y[cur]), (x[nxt], y[nxt])]))
                    adj[nxt].append((cur, w, len(edges)))
                    edges.append((nxt, cur, [(x[nxt], y[nxt]), (x[cur], y[cur])]))
        return RoadMap(x, y, adj, edges, lat0, lon0, kx)

def search_places(query, bounds, lang="ko", limit=8):
    import time
    import osmnx as ox
    import requests
    west, south, east, north = bounds
    tries = [query.strip()]
    if " " in tries[0]:
        tries.append(tries[0].replace(" ", ""))
    results, seen = [], set()
    for i, q in enumerate(tries):
        if results:
            break
        if i:
            time.sleep(1.1)
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "jsonv2", "limit": limit, "countrycodes": "kr",
                    "viewbox": f"{west},{north},{east},{south}", "bounded": 1,
                    "accept-language": lang},
            headers={"User-Agent": ox.settings.http_user_agent}, timeout=15)
        r.raise_for_status()
        for x in r.json():
            lat, lon = float(x["lat"]), float(x["lon"])
            if not (south <= lat <= north and west <= lon <= east):
                continue
            key = (round(lat, 4), round(lon, 4))
            if key in seen:
                continue
            seen.add(key)
            results.append({"name": x.get("name") or x["display_name"].split(",")[0],
                            "addr": x["display_name"], "lat": lat, "lon": lon})
    return results

def dijkstra_steps(adj, s, goal, dist, prev, checked_order):
    dist[s] = 0.0
    pq = [(0.0, s)]
    done = set()
    while pq:
        d, v = heapq.heappop(pq)
        if v in done:
            continue
        done.add(v)
        checked_order.append(v)
        yield v
        if v == goal:
            return
        for to, w, ei in adj[v]:
            nd = dist[v] + w
            if nd < dist.get(to, float("inf")):
                dist[to] = nd
                prev[to] = (v, ei)
                heapq.heappush(pq, (nd, to))

def build_route(prev, s, goal):
    if goal != s and goal not in prev:
        return [], []
    nodes, edge_ids = [goal], []
    while nodes[-1] != s:
        v, ei = prev[nodes[-1]]
        nodes.append(v)
        edge_ids.append(ei)
    nodes.reverse()
    edge_ids.reverse()
    return nodes, edge_ids

MAX_STOPS = 8

def all_distances(adj, s):
    dist, prev, order = {}, {}, []
    for _ in dijkstra_steps(adj, s, None, dist, prev, order):
        pass
    return dist

def plan_tour(rm, s, stops, goal):
    from itertools import permutations
    pts = [s] + list(stops) + [goal]
    D = []
    for a in pts:
        da = all_distances(rm.adj, a)
        D.append([da.get(b, float("inf")) for b in pts])
    k = len(stops)
    last = k + 1
    def total(seq):
        path = [0] + list(seq) + [last]
        return sum(D[path[i]][path[i + 1]] for i in range(len(path) - 1))
    best = min(permutations(range(1, k + 1)), key=total) if k else ()
    legs = []
    path = [0] + list(best) + [last]
    for i in range(len(path) - 1):
        order, nodes, edge_ids, dist_m = solve(rm, pts[path[i]], pts[path[i + 1]])
        legs.append({"order": order, "route_edges": edge_ids, "on_route": len(nodes),
                     "km": None if dist_m is None else dist_m / 1000})
    return {"visit": [p - 1 for p in best], "legs": legs,
            "km": total(best) / 1000, "km_given": total(range(1, k + 1)) / 1000}

def solve(rm, s, goal):
    dist, prev, order = {}, {}, []
    for _ in dijkstra_steps(rm.adj, s, goal, dist, prev, order):
        pass
    nodes, edge_ids = build_route(prev, s, goal)
    return order, nodes, edge_ids, dist.get(goal)
