# Geoje Dijkstra - Real Map Shortest Path Visualization

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-red) ![OSM](https://img.shields.io/badge/Map-OpenStreetMap-green)

Real Dijkstra algorithm spreading on the real road network of Geoje, South Korea. Inspired by the viral Facebook Reel [Dijkstra on HCMC map](https://www.facebook.com/share/r/19u1DiymGH/?mibextid=wwXIfr).

> **SHORTEST FOR SURE, AT 2168 INTERSECTIONS.**

[Demo](geoje_dijkstra.mp4)

### Demo
- **Live App (Streamlit):** [geoje-dijkstra.streamlit.app](https://geoje-dijkstra.streamlit.app/)
- **Video:** `geoje_dijkstra.mp4` - 1080x1920 vertical shorts format

### Features
- **Real road network:** 3,690 nodes, 8,684 edges from OpenStreetMap (drive network, largest strongly connected component)
- **Custom Dijkstra implementation:** generator `yield v` for animation, not using networkx shortcut
- **TSP for stops:** Up to 8 stops, brute-force all permutations (40,320 cases) to find shortest visiting order
- **Interaction:** 
  - List / Search (Nominatim) / Map click to pick start/goal
  - Mouse wheel zoom, drag pan, speed control, pause/restart
- **Export:** 1080x1920 mp4 with pygame-ce + imageio-ffmpeg
- **i18n:** Korean / English (texts.py)

### How Dijkstra Works
1. Start distance 0
2. Pop closest unsettled node (yellow spreading)
3. Relax neighbors
4. When goal is popped, distance is final - reconstruct green route via prev links

Why yellow spreads in circle? Dijkstra doesn't know goal direction, so it checks all closer nodes first.

### Installation
```bash
pip install -r requirements.txt
python -m streamlit run app.py
# or render mp4
python route_dijkstra.py --mp4
```

### Files
| File | Role |
|---|---|
| app.py | Streamlit UI + Canvas animation (browser) |
| route_core.py | OSM download, RoadMap class, dijkstra_steps(), plan_tour() |
| route_dijkstra.py | mp4 rendering with pygame-ce |
| texts.py | i18n strings |

### License & Credit
Map data © OpenStreetMap contributors (ODbL)
Code MIT

### Ideas to Extend
- A* vs Dijkstra battle (see Step 3)
- Reachability map, evacuation routes
- City battle: Geoje vs Seoul density
