import math
import pickle
from pathlib import Path

# Geoje center
GEOJE_CENTER = (34.8808, 128.6210)
PLACE = "Geoje-si, Gyeongsangnam-do, South Korea"

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
GRAPHML_PATH = CACHE_DIR / "geoje_drive.graphml"
PICKLE_PATH = CACHE_DIR / "roadmap.pkl"

def _try_load_cached_graph():
    """Try to load cached graph from local files, no internet needed"""
    import osmnx as ox
    try:
        if GRAPHML_PATH.exists():
            print(f"[cache] loading graphml {GRAPHML_PATH}")
            G = ox.load_graphml(GRAPHML_PATH)
            return G
        if PICKLE_PATH.exists():
            print(f"[cache] loading pickle {PICKLE_PATH}")
            with open(PICKLE_PATH, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        print(f"[cache] failed: {e}")
    return None

def _save_cache(G):
    try:
        import osmnx as ox
        # save graphml for future offline use
        ox.save_graphml(G, GRAPHML_PATH)
        print(f"[cache] saved {GRAPHML_PATH}")
    except Exception as e:
        print(f"[cache] save failed: {e}")

def _create_synthetic_grid():
    """Fallback: if no internet at all, create a synthetic grid around Geoje"""
    import networkx as nx
    import osmnx as ox
    import random
    print("[fallback] creating synthetic Geoje grid (offline mode)")
    # Create a grid-like graph mimicking Geoje
    G = nx.MultiDiGraph()
    G.graph["crs"] = "EPSG:4326"
    # Geoje roughly 34.7-35.0 N, 128.5-128.8 E
    lat_min, lat_max = 34.75, 35.02
    lon_min, lon_max = 128.5, 128.85
    rows, cols = 25, 25
    nodes = {}
    node_id = 0
    for r in range(rows):
        for c in range(cols):
            lat = lat_min + (lat_max - lat_min) * r / (rows-1) + random.uniform(-0.002, 0.002)
            lon = lon_min + (lon_max - lon_min) * c / (cols-1) + random.uniform(-0.002, 0.002)
            G.add_node(node_id, x=lon, y=lat)
            nodes[(r,c)] = node_id
            node_id += 1
    # connect grid
    for r in range(rows):
        for c in range(cols):
            nid = nodes[(r,c)]
            if c < cols-1:
                nid2 = nodes[(r,c+1)]
                d = ox.distance.great_circle(G.nodes[nid]['y'], G.nodes[nid]['x'], G.nodes[nid2]['y'], G.nodes[nid2]['x'])
                G.add_edge(nid, nid2, length=d, weight=d)
                G.add_edge(nid2, nid, length=d, weight=d)
            if r < rows-1:
                nid2 = nodes[(r+1,c)]
                d = ox.distance.great_circle(G.nodes[nid]['y'], G.nodes[nid]['x'], G.nodes[nid2]['y'], G.nodes[nid2]['x'])
                G.add_edge(nid, nid2, length=d, weight=d)
                G.add_edge(nid2, nid, length=d, weight=d)
    return G

def load_osm_graph():
    import osmnx as ox
    # 1. Try cache first (no internet)
    G = _try_load_cached_graph()
    if G is not None:
        return G
    # 2. Try download (needs internet)
    try:
        print(f"[osmnx] downloading {PLACE}")
        G = ox.graph_from_place(PLACE, network_type="drive", simplify=True)
        _save_cache(G)
        return G
    except Exception as e:
        print(f"[osmnx] download failed: {e}")
        # 3. Fallback synthetic
        return _create_synthetic_grid()

# Compatibility wrapper for existing app.py
class RoadMap:
    def __init__(self, G):
        self.G = G
        self.nodes = list(G.nodes)
        # build adjacency for Dijkstra
        import networkx as nx
        self.graph = {}
        for u in G.nodes:
            self.graph[u] = []
            for v, data in G[u].items():
                # MultiDiGraph: data is dict of edge keys
                for k, ed in data.items():
                    w = ed.get('length', 1.0)
                    self.graph[u].append((v, w))

    def to_dict(self):
        return {"graph": self.graph, "G": self.G}

def load_roadmap(verbose=False):
    G = load_osm_graph()
    # Ensure we have lat/lon for visualization
    return RoadMap(G)
