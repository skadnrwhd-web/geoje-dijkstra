"""
algorithms.py
다익스트라와 A* 를 같은 그래프·같은 비용으로 실행하고 결과를 비교한다.

공정성을 위한 규칙
- 두 알고리즘은 같은 인접 리스트(adj), 같은 간선 비용(도로 길이 m), 같은 우선순위 큐(heapq),
  같은 동점 처리 규칙(비용이 같으면 노드 번호가 작은 쪽 먼저)을 쓴다.
- 차이는 A* 가 휴리스틱(목적지까지 남은 직선 거리)을 더한다는 것 하나뿐이다.
- 실행 시간은 '기록 없는' 순수 계산 함수로 여러 번 재고 중앙값을 쓴다.
  애니메이션용 기록(trace)은 별도 실행에서 만들며 시간 측정에 섞이지 않는다.
- 측정 순서 때문에 한쪽이 유리하지 않도록 매 회 순서를 번갈아 바꾸고, 먼저 한 번씩 예열한다.
"""

import gc
import heapq
import json
import math
import platform
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

import networkx as nx

from map_loader import EARTH_RADIUS_M

# 휴리스틱을 아주 조금 줄여 부동소수점 반올림 때문에 실제 거리보다 커지는 일을 막는다.
# (줄인 휴리스틱도 여전히 '일관적'이라 A* 의 최적 경로 보장이 유지된다)
H_SAFETY = 1 - 1e-9


@dataclass
class SearchResult:
    algorithm: str
    found: bool
    path: list
    cost_m: float
    expanded: int          # 확장한(꺼내서 확정한) 고유 노드 수
    edges_scanned: int     # 확장한 노드에서 살펴본 간선 수
    pushes: int            # 우선순위 큐에 넣은 횟수
    trace: list = field(default_factory=list, repr=False)   # 애니메이션용 [(노드, 부모, [새로 발견한 노드...]), ...]


# ---------------------------------------------------------------- 휴리스틱

def prepare_coords(graph):
    """휴리스틱이 쓸 좌표 표를 그래프에 한 번만 만들어 둔다 (그래프 준비 단계, 시간 측정 밖)."""
    if "_c1" not in graph.info:
        if graph.heuristic == "haversine":
            graph.info["_c1"] = [math.radians(v) for v in graph.lat]
            graph.info["_c2"] = [math.radians(v) for v in graph.lon]
        else:
            graph.info["_c1"] = [float(v) for v in graph.x]
            graph.info["_c2"] = [float(v) for v in graph.y]
    return graph.info["_c1"], graph.info["_c2"]


def make_heuristic(graph, target):
    """목적지까지의 남은 거리 추정 함수 h(v) (단위: m, 도로 비용과 같은 단위)."""
    c1, c2 = prepare_coords(graph)
    if graph.heuristic == "haversine":
        # 위경도 대원 거리. OSM 도로 길이는 같은 공식으로 잰 조각 길이의 합이므로
        # 대원 거리 <= 실제 도로 거리 → 과대 추정하지 않는다 (허용적, 일관적)
        lat, lon = c1, c2
        lat_t, lon_t = lat[target], lon[target]
        cos_t = math.cos(lat_t)
        k = 2 * EARTH_RADIUS_M * H_SAFETY
        sin, cos, asin, sqrt = math.sin, math.cos, math.asin, math.sqrt

        def h(v):
            a = sin((lat[v] - lat_t) * 0.5) ** 2 + cos(lat[v]) * cos_t * sin((lon[v] - lon_t) * 0.5) ** 2
            return k * asin(sqrt(min(1.0, a)))
        return h

    # 격자 모드: 간선 비용 = 두 점 사이 직선 거리 → 직선 거리 휴리스틱이 허용적
    xs, ys = c1, c2
    xt, yt = xs[target], ys[target]
    hypot = math.hypot

    def h(v):
        return hypot(xs[v] - xt, ys[v] - yt) * H_SAFETY
    return h


# ---------------------------------------------------------------- 순수 계산 (시간 측정용)

def dijkstra(adj, s, t):
    dist = {s: 0.0}
    parent = {s: None}
    closed = set()
    heap = [(0.0, s)]
    pop, push = heapq.heappop, heapq.heappush
    edges = pushes = 0
    while heap:
        d, u = pop(heap)
        if u in closed:
            continue
        closed.add(u)
        if u == t:
            break
        for v, w in adj[u]:
            edges += 1
            if v in closed:
                continue
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                parent[v] = u
                push(heap, (nd, v))
                pushes += 1
    return _finish("Dijkstra", s, t, dist, parent, closed, edges, pushes)


def astar(adj, s, t, h):
    g = {s: 0.0}
    parent = {s: None}
    closed = set()
    hcache = {}
    heap = [(h(s), s)]
    pop, push = heapq.heappop, heapq.heappush
    edges = pushes = 0
    while heap:
        _, u = pop(heap)
        if u in closed:
            continue
        closed.add(u)
        if u == t:
            break
        gu = g[u]
        for v, w in adj[u]:
            edges += 1
            if v in closed:
                continue
            ng = gu + w
            if ng < g.get(v, math.inf):
                g[v] = ng
                parent[v] = u
                hv = hcache.get(v)
                if hv is None:
                    hv = hcache[v] = h(v)
                push(heap, (ng + hv, v))
                pushes += 1
    return _finish("A*", s, t, g, parent, closed, edges, pushes)


def _finish(name, s, t, dist, parent, closed, edges, pushes):
    if t not in closed:
        return SearchResult(name, False, [], math.inf, len(closed), edges, pushes)
    path = [t]
    while path[-1] != s:
        path.append(parent[path[-1]])
    path.reverse()
    return SearchResult(name, True, path, dist[t], len(closed), edges, pushes)


# ---------------------------------------------------------------- 기록 실행 (애니메이션용)

def search_recorded(name, adj, s, t, h=None):
    """위 두 함수와 똑같은 순서로 탐색하면서 확장 순서를 기록한다. h=None 이면 다익스트라."""
    g = {s: 0.0}
    parent = {s: None}
    closed = set()
    hcache = {}
    heap = [((h(s) if h else 0.0), s)]
    trace = []
    edges = pushes = 0
    while heap:
        _, u = heapq.heappop(heap)
        if u in closed:
            continue
        closed.add(u)
        found = []
        trace.append((u, parent[u], found))
        if u == t:
            break
        for v, w in adj[u]:
            edges += 1
            if v in closed:
                continue
            ng = g[u] + w
            if ng < g.get(v, math.inf):
                if v not in g:
                    found.append(v)
                g[v] = ng
                parent[v] = u
                if h:
                    hv = hcache.get(v)
                    if hv is None:
                        hv = hcache[v] = h(v)
                else:
                    hv = 0.0
                heapq.heappush(heap, (ng + hv, v))
                pushes += 1
    res = _finish(name, s, t, g, parent, closed, edges, pushes)
    res.trace = trace
    return res


# ---------------------------------------------------------------- 시간 측정

def benchmark(graph, s, t, repeats=7):
    """두 알고리즘의 계산 시간(ms)을 잰다. 렌더링·기록은 포함하지 않는다."""
    adj = graph.adj
    prepare_coords(graph)
    runs = {
        "Dijkstra": lambda: dijkstra(adj, s, t),
        "A*": lambda: astar(adj, s, t, make_heuristic(graph, t)),   # 휴리스틱 준비도 A* 시간에 포함
    }
    times = {k: [] for k in runs}
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        for fn in runs.values():           # 예열 (첫 실행의 캐시·메모리 할당 영향 제거)
            fn()
        names = list(runs)
        for i in range(max(1, repeats)):
            order = names if i % 2 == 0 else names[::-1]
            for name in order:
                t0 = time.perf_counter_ns()
                runs[name]()
                times[name].append((time.perf_counter_ns() - t0) / 1e6)
                gc.collect()
    finally:
        if was_enabled:
            gc.enable()
    return {k: {"median_ms": statistics.median(v), "min_ms": min(v), "max_ms": max(v),
                "runs_ms": [round(x, 4) for x in v]} for k, v in times.items()}


# ---------------------------------------------------------------- 판정

def judge(d, a, td, ta, tie_percent=10.0):
    """세 지표를 각각 비교해 승자를 정한다.

    - 경로 길이: 짧을수록 좋음 (0.1m 이내 차이는 같음)
    - 탐색 노드 수: 적을수록 좋음
    - 실행 시간: 짧을수록 좋음 (차이가 tie_percent % 이내면 측정 오차로 보고 무승부)
    지표마다 이긴 쪽이 1점. 점수가 높은 쪽이 종합 승자, 같으면 무승부.
    """
    rows = []

    def add(key, label, dv, av, tie):
        win = "tie" if tie else ("Dijkstra" if dv < av else "A*")
        rows.append({"key": key, "label": label, "dijkstra": dv, "astar": av, "winner": win})

    add("cost", "경로 길이 (km)", d.cost_m / 1000, a.cost_m / 1000, abs(d.cost_m - a.cost_m) < 0.1)
    add("expanded", "탐색 노드 수", d.expanded, a.expanded, d.expanded == a.expanded)
    gap = abs(td - ta) / max(td, ta, 1e-9) * 100
    add("time", "실행 시간 (ms)", td, ta, gap <= tie_percent)

    score = {"Dijkstra": sum(r["winner"] == "Dijkstra" for r in rows),
             "A*": sum(r["winner"] == "A*" for r in rows)}
    if score["Dijkstra"] == score["A*"]:
        winner = "DRAW"
    else:
        winner = max(score, key=score.get)
    return {"rows": rows, "score": score, "winner": winner, "time_gap_percent": gap,
            "rule": f"지표별 1점 (경로 길이·탐색 노드 수·실행 시간, 시간은 {tie_percent:g}% 이내 무승부)"}


# ---------------------------------------------------------------- 한 번에 실행

class NoPathError(RuntimeError):
    pass


def run_battle(graph, s, t, cfg):
    """대결 실행: 기록 실행 → 시간 측정 → 최적성 검증 → 판정."""
    h = make_heuristic(graph, t)
    d = search_recorded("Dijkstra", graph.adj, s, t, None)
    a = search_recorded("A*", graph.adj, s, t, h)
    if not d.found or not a.found:
        raise NoPathError("출발지에서 목적지로 가는 도로 경로가 없습니다 (일방통행·끊긴 도로 확인). "
                          "출발지/목적지를 바꾸거나 지도 영역을 넓혀 주세요.")

    # 기록 실행과 시간 측정용 실행이 정확히 같은 탐색을 했는지 확인
    for rec, pure in ((d, dijkstra(graph.adj, s, t)), (a, astar(graph.adj, s, t, h))):
        assert (rec.expanded, rec.path) == (pure.expanded, pure.path), "기록 실행과 측정 실행이 다릅니다"

    timing = benchmark(graph, s, t, cfg["benchmark"]["repeats"])

    # 독립 검증: networkx 의 다익스트라로 진짜 최단 거리 계산
    ref = nx.dijkstra_path_length(graph.to_networkx(), s, t, weight="length")
    optimal = {r.algorithm: abs(r.cost_m - ref) <= 1e-6 * max(1.0, ref) for r in (d, a)}

    verdict = judge(d, a, timing["Dijkstra"]["median_ms"], timing["A*"]["median_ms"],
                    cfg["benchmark"]["time_tie_percent"])
    return {"dijkstra": d, "astar": a, "timing": timing, "reference_cost_m": ref,
            "optimal": optimal, "verdict": verdict, "start_node": s, "goal_node": t,
            "path_km": {"Dijkstra": path_length_m(graph, d.path) / 1000,
                        "A*": path_length_m(graph, a.path) / 1000}}


def path_length_m(graph, path):
    """선택된 경로의 실제 도로 간선 길이 합 (직선 거리가 아님)."""
    total = 0.0
    for u, v in zip(path, path[1:]):
        total += min(w for x, w in graph.adj[u] if x == v)
    return total


def battle_summary(battle, graph, cfg):
    """재현용 기록 (JSON 으로 저장 가능한 사전)."""
    def res(r):
        x = asdict(r)
        x.pop("trace")
        x["path_nodes"] = len(x.pop("path"))
        x["cost_km"] = r.cost_m / 1000
        return x
    return {
        "created": datetime.now().isoformat(timespec="seconds"),
        "config": {k: cfg[k] for k in ("map_mode", "start", "goal", "seoul_map", "grid_map", "benchmark")},
        "graph": {"mode": graph.mode, "nodes": graph.n_nodes, "edges": graph.n_edges,
                  "source": graph.source, "bbox": graph.info.get("bbox"),
                  "cache_file": graph.info.get("cache_file")},
        "start_node": battle["start_node"], "goal_node": battle["goal_node"],
        "results": {"Dijkstra": res(battle["dijkstra"]), "A*": res(battle["astar"])},
        "timing": battle["timing"],
        "reference_cost_m": battle["reference_cost_m"],
        "optimal": battle["optimal"],
        "verdict": battle["verdict"],
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "processor": platform.processor(),
                        "note": "실행 시간은 PC 성능·실행 환경에 따라 달라질 수 있습니다"},
    }


def save_summary(summary, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
