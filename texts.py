"""
texts.py
앱 화면에 나오는 문구를 한국어/영어로 모아 둔 사전
  - 문구를 고치거나 새 언어를 넣을 때는 이 파일만 고치면 된다
  - 사용법: TEXT["ko"]["title"] -> "거제 다익스트라"
"""

# ------------------------------------------------------------------
# 아래 패널에 보여줄 C 코드 (줄마다 주석)
# 코드 부분은 두 언어가 같고, // 뒤 주석만 언어별로 다르다
# ------------------------------------------------------------------
_C_LINES = [
    # (코드, 한국어 주석, 영어 주석)
    ("dist[s] = 0; push(s, 0);", "출발지 거리는 0, 큐에 넣고 시작",
     "start: distance 0, put it in the queue"),
    ("while (!pq_empty()) {", "큐에 교차로가 남아 있는 동안 반복",
     "repeat while the queue is not empty"),
    ("  v = pop_min();", "아직 확정 안 된 것 중 제일 가까운 교차로",
     "take the closest unchecked intersection"),
    ("  if (v == goal) return;", "도착지를 꺼냈으면 최단경로 확정, 끝",
     "goal popped -> shortest route is final"),
    ("  for (r = head[v]; r; r = r->next)", "v에서 나가는 길을 하나씩 본다",
     "look at every road leaving v"),
    ("    if (dist[r->to] > dist[v] + r->w) {", "v를 거쳐 가는 게 더 짧으면",
     "is going through v shorter?"),
    ("      dist[r->to] = dist[v] + r->w;", "더 짧은 거리로 바꾸고",
     "update to the shorter distance"),
    ("      prev[r->to] = v;", "어디서 왔는지 기록 (경로 복원용)",
     "remember where we came from"),
    ("      push(r->to, dist[r->to]);", "큐에 넣어 나중에 확인",
     "add it to the queue"),
    ("    }", "", ""),
    ("}", "", ""),
]


def c_code(lang):
    """언어에 맞는 주석을 붙인 C 코드 문자열을 만든다 (주석 위치를 세로로 맞춤)."""
    head = "// 다익스트라: s에서 goal까지 최단경로" if lang == "ko" else \
           "// Dijkstra: shortest route from s to goal"
    width = max(len(code) for code, _, _ in _C_LINES) + 2   # 주석 시작 칸
    lines = [head]
    for code, ko, en in _C_LINES:
        note = ko if lang == "ko" else en
        lines.append(f"{code.ljust(width)}// {note}" if note else code)
    return "\n".join(lines)


# ------------------------------------------------------------------
# 화면 문구
# ------------------------------------------------------------------
TEXT = {
    "ko": {
        "page_title": "거제 다익스트라",
        "title": "거제 다익스트라",
        "subtitle": "실제 OSM 도로망 위에서 다익스트라가 최단경로를 찾아가는 과정. 휠로 줌, 드래그로 이동.",
        "lang_label": "언어",
        "route_header": "경로 설정",
        "start": "출발지",
        "goal": "도착지",
        "place_note": "고른 곳에서 가장 가까운 교차로를 출발/도착점으로 씀.",
        "support_header": "☕ 후원하기",
        "support_note": "마음에 드셨다면 커피 한 잔으로 응원해 주세요.",
        "support_btn": "Buy Me a Coffee",
        "same_place": "출발지와 도착지가 같은 교차로야. 다른 곳을 골라 줘.",
        "swap": "출발 ↔ 도착 바꾸기",
        "pick_list": "목록에서 고르기",
        "pick_search": "이름으로 검색",
        "pick_click": "지도에서 찍기",
        "list_ph": "목록에서 선택",
        "search_label": "장소 이름",
        "search_ph": "예: 거제대학교, 바람의언덕, 고현동",
        "search_btn": "검색",
        "search_note": "OSM 검색이라 이름이 거의 정확해야 찾음 (띄어쓰기 뺀 이름도 자동으로 시도). "
                       "'병원'처럼 일반 단어는 잘 안 찾아짐. 못 찾으면 지도에서 찍어 줘.",
        "search_none": "거제 안에서 '{q}'(을)를 못 찾았어. 다른 이름이나 지도 클릭으로 해 봐.",
        "search_err": "검색 서버에 연결하지 못했어. 인터넷 연결을 확인해 줘.",
        "search_result": "검색 결과",
        "set_start": "출발지로",
        "set_goal": "도착지로",
        "click_help": "지도 아래 **출발 찍기**, **경유 찍기**, **도착 찍기** 중 하나를 누른 뒤 지도를 클릭해.",
        "map_point": "지도에서 찍은 곳 ({lat:.4f}, {lon:.4f})",
        "stops": "경유지",
        "no_stops": "경유지 없음 (여러 곳을 들르려면 경유지를 추가해)",
        "add_stop": "경유지로",
        "list_stop": "경유지 추가",
        "clear_stops": "경유지 모두 지우기",
        "remove": "빼기",
        "max_stops": "경유지는 최대 {n}곳까지 넣을 수 있어.",
        "tour_header": "최단 방문 순서",
        "tour_note": "경유지 순서를 모든 경우({cases:,}가지) 다 비교해서 고른 확실한 최단 순서야. 출발지와 도착지는 고정.",
        "tour_given": "입력한 순서대로 가면 **{given:.2f} km** → 최단 순서로 가면 **{best:.2f} km** ({save:.2f} km 절약)",
        "tour_same": "입력한 순서가 이미 최단 순서야 ({best:.2f} km).",
        "leg_col": "구간", "km_col": "거리 (km)",
        "loading_map": "거제 도로망 불러오는 중... (처음엔 몇 분 걸릴 수 있음)",
        "solving": "최단경로 계산 중...",
        "m_checked": "확인한 교차로",
        "m_onroute": "경로 위 교차로",
        "m_dist": "최단거리",
        "offset_note": "출발점은 지정 좌표에서 {s}m, 도착점은 {g}m 떨어진 교차로.",
        "mp4_header": "쇼츠 mp4 저장",
        "mp4_note": "지금 고른 경로를 1080x1920 세로 영상으로 만든다. 30초쯤 걸림.",
        "mp4_btn": "mp4 만들기",
        "mp4_busy": "영상 만드는 중...",
        "mp4_dl": "mp4 내려받기",
        "osm": "지도 데이터 © OpenStreetMap contributors (ODbL)",
        "tab_about": "프로그램 소개",
        "tab_how": "다익스트라 원리",
        "tab_ideas": "활용 아이디어",
        # 지도 안(브라우저 컴포넌트) 문구
        "map": {
            "checked": "확인한 교차로", "onroute": "경로 위 교차로",
            "final_ok": "최단경로 확정! 교차로 {n}개를 확인했다.",
            "final_none": "경로 없음. 길이 이어져 있지 않다.",
            "play": "재생/일시정지", "restart": "처음부터", "slower": "느리게",
            "faster": "빠르게", "zin": "줌 +", "zout": "줌 −", "fit": "전체",
            "zin_t": "줌 인", "zout_t": "줌 아웃", "fit_t": "전체 보기",
            "pick_s": "출발 찍기", "pick_w": "경유 찍기", "pick_g": "도착 찍기",
            "pick_s_t": "누른 뒤 지도를 클릭하면 출발지가 됨", "pick_g_t": "누른 뒤 지도를 클릭하면 도착지가 됨",
            "pick_w_t": "누른 뒤 지도를 클릭하면 경유지로 추가됨",
            "hint_s": "지도를 클릭해서 출발지를 정해 (취소: 버튼 다시 누르기)",
            "hint_g": "지도를 클릭해서 도착지를 정해 (취소: 버튼 다시 누르기)",
            "hint_w": "지도를 클릭해서 경유지를 추가해 (취소: 버튼 다시 누르기)",
            "final_tour": "최단 순서 확정! {k}곳 경유, 총 {km} km",
        },
        "about": """
**거제 다익스트라**는 거제시의 실제 도로망(OpenStreetMap) 위에서
다익스트라 알고리즘이 최단경로를 찾는 과정을 눈으로 보여주는 프로그램이다.

#### 기능
- **실제 도로 지도**: 거제시 자동차 도로 3,690개 교차로, 8,684개 도로 구간. 도로는 실제 모양대로 곡선으로 그림
- **출발지·도착지 선택** (고르면 새 경로를 바로 계산)
  - 목록: 거제 관광 명소 14곳(바람의 언덕, 신선대, 매미성, 공곶이, 해수욕장 등)과 시내·교통 4곳
  - 이름 검색: OSM에서 거제 안 장소를 찾음 (인터넷 필요)
  - 지도 클릭: 지도 아래 '출발 찍기' / '도착 찍기'를 누르고 원하는 곳을 클릭
  - 출발 ↔ 도착 바꾸기 버튼
- **경유지 (최대 8곳)**: 여러 곳을 들를 때, 들르는 순서를 모든 경우를 비교해 최단거리로 맞춰 줌.
  입력한 순서와 비교해 몇 km 줄었는지, 구간별 거리도 보여 줌
- **탐색 애니메이션**: 노란 선 = 다익스트라가 확인한 길, 초록 선 = 최종 최단경로
- **줌·이동**: 마우스 휠로 줌, 드래그로 이동, 아래 버튼으로 줌 +/−, 전체 보기
- **속도 조절·일시정지·다시 시작**: 지도 아래 버튼
- **쇼츠 mp4 저장**: 1080x1920 세로 영상으로 저장하고 내려받기
- **한국어/영어 전환**: 왼쪽 위 언어 버튼

#### 사용법
1. 왼쪽 목록·검색 또는 지도 클릭으로 출발지와 도착지를 고른다
2. 지도에서 탐색이 퍼지는 걸 본다 (휠로 줌, 드래그로 이동)
3. 마음에 들면 오른쪽 아래 **mp4 만들기**로 영상 저장

#### 파일 구성
| 파일 | 하는 일 |
|---|---|
| `app.py` | Streamlit 화면 (지금 보는 이 앱) |
| `route_core.py` | 도로망 받기, 다익스트라 계산 |
| `route_dijkstra.py` | mp4 영상 만들기 |
| `texts.py` | 한국어/영어 문구 |
""",
        "how": """
다익스트라는 **"출발지에서 가까운 곳부터 차례로 확정해 나가는"** 방법이다.

1. 출발지 거리를 0으로 두고 시작
2. 아직 확정 안 된 교차로 중 **제일 가까운 곳**을 꺼내 확정 (노란 선이 퍼지는 순간)
3. 그 교차로에서 나가는 길을 보고, 더 짧게 갈 수 있는 이웃이 있으면 거리를 고친다
4. **도착지를 꺼내는 순간** 그 거리가 최단거리로 확정. 기록해 둔 '어디서 왔는지'를 거꾸로 따라가면 초록 경로

가까운 순서로 확정하기 때문에, 나중에 더 짧은 길이 나타날 수 없다. 그래서 **"SHORTEST FOR SURE"** 다.

노란 선이 원처럼 사방으로 퍼지는 이유도 이것. 다익스트라는 도착지 방향을 모르고 가까운 곳부터 다 본다.
도착지가 멀면 섬 거의 전체를 확인하게 된다 (거제시청 → 바람의 언덕: 3,690개 중 3,668개 확인).

이 앱의 계산 결과는 검증용 라이브러리(networkx)와 임의의 출발·도착 100쌍으로 비교해 모두 같은 거리였다.
""",
        "ideas": """
#### 생활·지역
- **관광 동선 짜기**: 이 앱의 경유지 기능이 바로 이것. 곳곳 사이 최단거리를 다익스트라로 구한 뒤 방문 순서를 정함.
  더 나아가 '몇 시까지 도착' 같은 시간 조건을 넣을 수도 있음
- **가장 가까운 시설 찾기**: 출발점을 여러 개(병원, 소방서, 편의점 전부)로 두고 한 번에 돌리면, 거제 모든 교차로에서 "제일 가까운 병원"이 어딘지 지도로 칠할 수 있다
- **10분 안에 갈 수 있는 범위 지도**: 도로 길이 대신 '걸리는 시간'(길이 ÷ 제한속도)을 거리로 쓰면, 시청에서 5·10·15분 안에 닿는 범위를 색으로 보여줄 수 있다. OSM 제한속도는 빠진 곳이 많아 추정값을 써야 함
- **재난 대피 경로**: 통제된 도로를 지도에서 빼고 다시 돌리면 우회 경로와 늘어난 거리를 바로 비교

#### 회사·업무
- **사내 물류 동선**: 공장·야드 통로를 그래프로 만들면 자재 운반 최단 경로, 지게차 이동 거리 비교
- **통근버스 노선 검토**: 정류장 후보 사이 거리를 구해 노선 길이 비교
- **배관·케이블 경로**: 설치 가능한 통로를 그래프로 두고 가장 짧은 경로 찾기
- **네트워크**: 사내망 라우터의 경로 계산(OSPF)도 다익스트라를 쓴다

#### 콘텐츠 (쇼츠)
- **도시 대결**: 같은 거리의 두 도시에서 확인한 교차로 수 비교 (도로가 촘촘한 도시일수록 많이 본다)
- **A\\* vs 다익스트라**: 도착지 방향을 아는 A\\*는 확인하는 교차로가 훨씬 적다. 두 탐색을 나란히 보여주기
- **차 vs 걷기**: 도로망 종류를 '걷기'로 바꾸면 길이 달라진다
""",
    },
    "en": {
        "page_title": "Geoje Dijkstra",
        "title": "Geoje Dijkstra",
        "subtitle": "Watch Dijkstra find the shortest route on the real OSM road network. Scroll to zoom, drag to pan.",
        "lang_label": "Language",
        "route_header": "Route",
        "start": "Start",
        "goal": "Destination",
        "place_note": "The nearest intersection to each chosen point is used.",
        "support_header": "☕ Support",
        "support_note": "If you enjoyed this, a coffee would be much appreciated.",
        "support_btn": "Buy Me a Coffee",
        "same_place": "Start and destination are the same intersection. Pick a different place.",
        "swap": "Swap start ↔ destination",
        "pick_list": "Pick from list",
        "pick_search": "Search by name",
        "pick_click": "Click on the map",
        "list_ph": "Choose from list",
        "search_label": "Place name",
        "search_ph": "e.g. Geoje University, Windy Hill",
        "search_btn": "Search",
        "search_note": "Uses OSM search, so names must be nearly exact (also retried without spaces). "
                       "Generic words like 'hospital' rarely work. If not found, click on the map.",
        "search_none": "Couldn't find '{q}' in Geoje. Try another name or click on the map.",
        "search_err": "Couldn't reach the search server. Check your internet connection.",
        "search_result": "Results",
        "set_start": "Set as start",
        "set_goal": "Set as destination",
        "click_help": "Press **Pick start**, **Add stop** or **Pick dest.** under the map, then click on the map.",
        "map_point": "Map point ({lat:.4f}, {lon:.4f})",
        "stops": "Stops",
        "no_stops": "No stops (add stops to visit several places)",
        "add_stop": "Add as stop",
        "list_stop": "Add stop",
        "clear_stops": "Clear all stops",
        "remove": "Remove",
        "max_stops": "You can add up to {n} stops.",
        "tour_header": "Shortest visiting order",
        "tour_note": "Every possible order of the stops ({cases:,}) was compared, so this order is shortest for sure. Start and destination stay fixed.",
        "tour_given": "In the order you added them: **{given:.2f} km** → shortest order: **{best:.2f} km** ({save:.2f} km saved)",
        "tour_same": "The order you added is already the shortest ({best:.2f} km).",
        "leg_col": "Leg", "km_col": "Distance (km)",
        "loading_map": "Loading the Geoje road network... (first run can take a few minutes)",
        "solving": "Computing the shortest route...",
        "m_checked": "Checked",
        "m_onroute": "On route",
        "m_dist": "Shortest distance",
        "offset_note": "Start intersection is {s} m from the chosen point, destination is {g} m.",
        "mp4_header": "Save shorts mp4",
        "mp4_note": "Renders the current route as a 1080x1920 vertical video. Takes about 30 s.",
        "mp4_btn": "Make mp4",
        "mp4_busy": "Rendering video...",
        "mp4_dl": "Download mp4",
        "osm": "Map data © OpenStreetMap contributors (ODbL)",
        "tab_about": "About",
        "tab_how": "How Dijkstra works",
        "tab_ideas": "Ideas",
        "map": {
            "checked": "CHECKED", "onroute": "ON ROUTE",
            "final_ok": "SHORTEST FOR SURE, AT {n} INTERSECTIONS.",
            "final_none": "NO ROUTE FOUND. ROADS NOT CONNECTED.",
            "play": "Play/Pause", "restart": "Restart", "slower": "Slower",
            "faster": "Faster", "zin": "Zoom +", "zout": "Zoom −", "fit": "Fit",
            "zin_t": "Zoom in", "zout_t": "Zoom out", "fit_t": "Fit to map",
            "pick_s": "Pick start", "pick_w": "Add stop", "pick_g": "Pick dest.",
            "pick_s_t": "Press, then click the map to set the start",
            "pick_g_t": "Press, then click the map to set the destination",
            "pick_w_t": "Press, then click the map to add a stop",
            "hint_s": "Click the map to set the start (press the button again to cancel)",
            "hint_g": "Click the map to set the destination (press the button again to cancel)",
            "hint_w": "Click the map to add a stop (press the button again to cancel)",
            "final_tour": "SHORTEST ORDER FOR SURE: {k} STOPS, {km} KM.",
        },
        "about": """
**Geoje Dijkstra** shows, step by step, how Dijkstra's algorithm finds the shortest route
on the real road network of Geoje, South Korea (OpenStreetMap).

#### Features
- **Real road map**: 3,690 intersections and 8,684 road segments of Geoje's drivable roads, drawn with their real curves
- **Pick start and destination** (the route is recomputed right away)
  - List: 14 Geoje sights (Windy Hill, Sinseondae, Maemiseong, Gongotji, beaches, etc.) and 4 town/transport places
  - Name search: finds places in Geoje via OSM (needs internet)
  - Map click: press 'Pick start' / 'Pick dest.' under the map, then click a spot
  - Swap start ↔ destination button
- **Stops (up to 8)**: when visiting several places, the visiting order is set to the shortest by comparing every possible order.
  Shows how many km were saved versus the order you added, and the distance of each leg
- **Search animation**: yellow = roads Dijkstra has checked, green = the final shortest route
- **Zoom and pan**: mouse wheel to zoom, drag to pan, buttons for zoom +/− and fit
- **Speed, pause, restart**: buttons under the map
- **Shorts mp4**: save a 1080x1920 vertical video and download it
- **Korean / English**: language buttons at the top left

#### How to use
1. Pick a start and a destination from the list, by search, or by clicking the map
2. Watch the search spread on the map (wheel to zoom, drag to pan)
3. Press **Make mp4** at the bottom right to save a video

#### Files
| File | Role |
|---|---|
| `app.py` | Streamlit screen (this app) |
| `route_core.py` | Road network download, Dijkstra |
| `route_dijkstra.py` | mp4 rendering |
| `texts.py` | Korean / English text |
""",
        "how": """
Dijkstra **settles places in order of distance from the start**.

1. Start with distance 0 at the start
2. Take the **closest** intersection not yet settled and settle it (that's when the yellow lines grow)
3. Check the roads leaving it; if a neighbor can be reached by a shorter way, update its distance
4. **The moment the destination is taken**, its distance is final. Following the recorded "came from" links backwards gives the green route

Because places are settled closest-first, no shorter way can show up later. That's why it's **"SHORTEST FOR SURE"**.

This is also why the yellow lines spread like a circle: Dijkstra doesn't know where the destination is,
so it checks everything that is closer first. A far destination means checking almost the whole island
(City Hall → Windy Hill: 3,668 of 3,690 intersections).

The app's results were checked against a reference library (networkx) on 100 random start/destination pairs; all distances matched.
""",
        "ideas": """
#### Daily life and the local area
- **Plan a sightseeing route**: this app's stops feature does exactly this, using Dijkstra distances between spots to pick the visiting order.
  It could go further with time limits like "arrive by 5 pm"
- **Nearest facility map**: start from many points at once (all hospitals, fire stations, convenience stores) and color every intersection by its nearest facility
- **10-minute reach map**: use travel time (length ÷ speed limit) instead of length to show what's reachable in 5, 10, 15 minutes. OSM speed limits are often missing, so estimates are needed
- **Evacuation routes**: remove closed roads and rerun to compare the detour and the extra distance

#### Work
- **In-plant logistics**: model factory or yard aisles as a graph to find the shortest material-handling paths
- **Commuter bus routes**: compare route lengths between candidate stops
- **Pipe and cable routing**: find the shortest path through the corridors where installation is allowed
- **Networking**: router path computation (OSPF) uses Dijkstra too

#### Content (shorts)
- **City battle**: compare how many intersections get checked for the same distance in two cities (denser cities mean more)
- **A\\* vs Dijkstra**: A\\* knows the direction of the goal and checks far fewer intersections; show both side by side
- **Car vs walking**: switch the network type to walking and the route changes
""",
    },
}
