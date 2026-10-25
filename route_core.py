"""
route_core.py
Streamlit 앱(app.py)과 mp4 저장(route_dijkstra.py)이 같이 쓰는 핵심 로직
  - 거제 도로망 받기 (곡선 모양 포함)
  - 다익스트라 직접 구현
  - 경로 복원
"""

import heapq
import math

import numpy as np

PLACE = "Geoje, South Korea"

# 장소 목록: 이름 -> (위도, 경도). 전부 OSM 검색으로 확인한 좌표
PLACES = {
    "거제시청": (34.880481, 128.6212633),
    "고현 시외버스터미널": (34.8909604, 128.6241919),
    "거제 포로수용소 유적공원": (34.8760819, 128.6246009),
    "옥포": (34.8947700, 128.6929600),
    "장승포": (34.8653554, 128.7270200),
    "학동 몽돌해변": (34.7732942, 128.6405889),
    "바람의 언덕": (34.743957, 128.6632902),
}

# 장소 영어 이름 (영어 화면과 영상 문구에 사용)
PLACES_EN = {
    "거제시청": "Geoje City Hall",
    "고현 시외버스터미널": "Gohyeon Bus Terminal",
    "거제 포로수용소 유적공원": "Geoje POW Camp Park",
    "옥포": "Okpo",
    "장승포": "Jangseungpo",
    "학동 몽돌해변": "Hakdong Mongdol Beach",
    "바람의 언덕": "Windy Hill",
}


def place_name(name, lang):
    """장소 이름을 언어에 맞게 돌려준다 (lang: "ko" 또는 "en")."""
    return PLACES_EN.get(name, name) if lang == "en" else name


M_PER_DEG = 111_000           # 위도 1도 ~ 111km


class RoadMap:
    """도로망을 가볍게 담아 두는 그릇. 좌표는 '미터' 단위 평면 좌표 (x: 동쪽+, y: 남쪽+)."""

    def __init__(self, x, y, adj, edges, lat0, lon0, kx):
        self.x, self.y = x, y        # 교차로(노드) 좌표, numpy 배열
        self.adj = adj               # adj[u] = [(v, 거리m, 엣지번호), ...]
        self.edges = edges           # edges[i] = (u, v, [(x, y), ...] 곡선 점들)
        self.lat0, self.lon0, self.kx = lat0, lon0, kx   # 위경도 -> 미터 변환 기준

    def to_xy(self, lat, lon):
        """위경도 -> 이 지도의 미터 좌표."""
        return ((lon - self.lon0) * self.kx * M_PER_DEG,
                (self.lat0 - lat) * M_PER_DEG)

    def to_latlon(self, x, y):
        """이 지도의 미터 좌표 -> 위경도 (지도 클릭 위치를 바꿀 때 사용)."""
        return (self.lat0 - y / M_PER_DEG,
                self.lon0 + x / (self.kx * M_PER_DEG))

    def bounds(self):
        """도로망을 감싸는 상자 (서, 남, 동, 북) 위경도."""
        south, east = self.to_latlon(float(self.x.max()), float(self.y.max()))
        return self.lon0, south, east, self.lat0

    def nearest_node(self, lat, lon):
        """좌표에서 가장 가까운 교차로 번호와 떨어진 거리(m)."""
        px, py = self.to_xy(lat, lon)
        d2 = (self.x - px) ** 2 + (self.y - py) ** 2
        i = int(np.argmin(d2))
        return i, math.sqrt(d2[i])


def load_roadmap(verbose=True):
    """OSM에서 거제 도로망을 받아 RoadMap 으로 바꾼다 (처음엔 다운로드, 그다음엔 캐시)."""
    import osmnx as ox  # 무거운 import는 필요할 때만

    if verbose:
        print(f"'{PLACE}' 도로망 받는 중... (처음엔 몇 분 걸릴 수 있음)")
    G = ox.graph_from_place(PLACE, network_type="drive")
    n0, e0 = len(G.nodes), len(G.edges)

    # 섬이라 다른 길과 끊긴 짧은 도로 조각이 있다.
    # 서로 오갈 수 있는 가장 큰 도로 덩어리만 남겨서 '경로 없음'을 막는다.
    G = ox.truncate.largest_component(G, strongly=True)
    if verbose:
        print(f"노드 {n0:,}개, 엣지 {e0:,}개 -> 연결된 도로만 남김: "
              f"노드 {len(G.nodes):,}개, 엣지 {len(G.edges):,}개")

    ids = list(G.nodes)                        # 노드 번호 목록
    index = {n: i for i, n in enumerate(ids)}  # 노드 번호 -> 0..N-1
    lat = np.array([G.nodes[n]["y"] for n in ids])
    lon = np.array([G.nodes[n]["x"] for n in ids])

    # 위경도를 미터 평면으로: 왼쪽 위(서북쪽) 모서리를 (0,0)으로
    lat0, lon0 = float(lat.max()), float(lon.min())
    kx = math.cos(math.radians(float(lat.mean())))   # 경도 보정
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
            # 실제 도로 모양(곡선)을 이루는 점들
            pts = [xy(lo, la) for lo, la in geom.coords]
            # 점 순서가 u->v 방향과 반대면 뒤집는다
            d_first = (pts[0][0] - x[iu]) ** 2 + (pts[0][1] - y[iu]) ** 2
            d_last = (pts[-1][0] - x[iu]) ** 2 + (pts[-1][1] - y[iu]) ** 2
            if d_last < d_first:
                pts.reverse()
        else:
            pts = [(x[iu], y[iu]), (x[iv], y[iv])]   # 곡선 정보 없으면 직선
        adj[iu].append((iv, w, len(edges)))
        edges.append((iu, iv, pts))
    return RoadMap(x, y, adj, edges, lat0, lon0, kx)


def search_places(query, bounds, lang="ko", limit=8):
    """
    OSM Nominatim 으로 장소 이름을 검색해 거제 안 결과만 돌려준다 (인터넷 필요).
    Nominatim 은 이름이 거의 정확해야 찾아서, 못 찾으면 띄어쓰기를 뺀 이름으로 한 번 더 찾는다.
    돌려주는 값: [{"name": 짧은 이름, "addr": 전체 주소, "lat": 위도, "lon": 경도}, ...]
    """
    import time

    import osmnx as ox
    import requests

    west, south, east, north = bounds
    tries = [query.strip()]
    if " " in tries[0]:
        tries.append(tries[0].replace(" ", ""))   # "바람의 언덕" -> "바람의언덕"
    results, seen = [], set()
    for i, q in enumerate(tries):
        if results:
            break                                   # 이미 찾았으면 더 안 찾음
        if i:
            time.sleep(1.1)                         # Nominatim 이용 규칙: 1초에 1번까지
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
                continue                            # 거제 상자 밖이면 버림
            key = (round(lat, 4), round(lon, 4))
            if key in seen:
                continue                            # 같은 곳이 여러 번 나오면 하나만
            seen.add(key)
            results.append({"name": x.get("name") or x["display_name"].split(",")[0],
                            "addr": x["display_name"], "lat": lat, "lon": lon})
    return results


def dijkstra_steps(adj, s, goal, dist, prev, checked_order):
    """
    제너레이터: 교차로 하나를 확정(CHECK)할 때마다 그 교차로 번호를 내보낸다.
    dist, prev, checked_order 는 밖에서 만들어 넘기면 여기서 채워 준다.
    prev[to] = (앞 교차로, 지나온 엣지번호)
    골을 꺼내는 순간 종료한다 (C 코드의 if (v == goal) return; 과 동일).
    """
    dist[s] = 0.0
    pq = [(0.0, s)]                 # (거리, 노드) 힙 = 우선순위 큐
    done = set()                    # 이미 확정된 노드

    while pq:
        d, v = heapq.heappop(pq)    # pop_min: 가장 가까운 교차로
        if v in done:               # 같은 노드가 큐에 여러 번 들어간 경우 건너뜀
            continue
        done.add(v)
        checked_order.append(v)
        yield v
        if v == goal:               # 목적지 도착 -> 종료
            return

        for to, w, ei in adj[v]:
            nd = dist[v] + w
            if nd < dist.get(to, float("inf")):   # 더 짧은 길이면 갱신
                dist[to] = nd
                prev[to] = (v, ei)
                heapq.heappush(pq, (nd, to))


def build_route(prev, s, goal):
    """prev 를 거꾸로 따라가 (교차로 목록, 엣지번호 목록)을 만든다. 경로 없으면 빈 리스트."""
    if goal != s and goal not in prev:
        return [], []               # 도달 불가
    nodes, edge_ids = [goal], []
    while nodes[-1] != s:
        v, ei = prev[nodes[-1]]
        nodes.append(v)
        edge_ids.append(ei)
    nodes.reverse()
    edge_ids.reverse()
    return nodes, edge_ids


MAX_STOPS = 8                 # 경유지 최대 개수 (8곳이면 순서 40,320가지를 전부 비교)


def all_distances(adj, s):
    """s 에서 모든 교차로까지의 최단거리 (도착지 없이 끝까지 돌리는 다익스트라)."""
    dist, prev, order = {}, {}, []
    for _ in dijkstra_steps(adj, s, None, dist, prev, order):
        pass
    return dist


def plan_tour(rm, s, stops, goal):
    """
    출발 s -> 경유지들(stops) -> 도착 goal 을 가장 짧게 도는 순서를 찾는다.
      1) 각 지점에서 다익스트라를 돌려 지점 사이 도로 거리표를 만든다
      2) 경유지 순서를 '모든 경우'로 다 비교해서 총거리가 제일 짧은 순서를 고른다 (확실한 최단)
      3) 그 순서대로 구간(leg)마다 다익스트라 탐색 과정을 기록한다 (애니메이션용)
    돌려주는 값:
      visit: 경유지를 들르는 순서 (stops 안의 번호)
      legs: 구간마다 {"order": 확정 순서, "route_edges": 경로 엣지, "on_route": 경로 교차로 수, "km": 거리}
      km: 최적 순서 총거리, km_given: 입력한 순서대로 갔을 때 총거리
    """
    from itertools import permutations

    pts = [s] + list(stops) + [goal]                       # 0=출발, 1..k=경유지, 마지막=도착
    D = []                                                 # D[i][j] = 지점 i -> j 도로 거리(m)
    for a in pts:
        da = all_distances(rm.adj, a)
        D.append([da.get(b, float("inf")) for b in pts])

    k = len(stops)
    last = k + 1

    def total(seq):                                        # seq: 경유지 번호(1..k)를 도는 순서
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
    """다익스트라를 끝까지 한 번에 돌려 (확정 순서, 경로 교차로, 경로 엣지, 총거리m)를 돌려준다."""
    dist, prev, order = {}, {}, []
    for _ in dijkstra_steps(rm.adj, s, goal, dist, prev, order):
        pass
    nodes, edge_ids = build_route(prev, s, goal)
    return order, nodes, edge_ids, dist.get(goal)
