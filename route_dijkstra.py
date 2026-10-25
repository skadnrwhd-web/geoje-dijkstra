"""
route_dijkstra.py
거제 도로망 위 다익스트라 탐색을 pygame으로 그린다 (실시간 창 또는 쇼츠용 mp4).
보통은 Streamlit 앱(app.py)에서 'mp4 만들기' 버튼으로 쓴다.

설치:  pip install pygame-ce osmnx numpy imageio-ffmpeg streamlit
실행:
  python route_dijkstra.py         -> 실시간 창으로 보기 (540x960, 세로)
  python route_dijkstra.py --mp4   -> 쇼츠용 1080x1920 mp4로 저장 (geoje_dijkstra.mp4)

조작키 (실시간 창):
  SPACE : 일시정지 / 재생
  UP/DOWN : 탐색 속도 올리기 / 내리기
  R : 처음부터 다시
  ESC : 종료 (mp4 저장 중이면 저장 중단)
"""

import os
import sys

import route_core as rc

# ------------------------------------------------------------------
# 설정값
# ------------------------------------------------------------------
START_NAME = "거제시청"               # 출발지 (route_core.PLACES 에 있는 이름)
GOAL_NAME = "바람의 언덕"              # 도착지

OUT_W, OUT_H = 1080, 1920             # 기준 화면 크기 (쇼츠 세로)
MAP_H = 1220                          # 위쪽 지도 영역 높이 (기준 화면 기준)
MSG_H = 170                           # 지도 아래 문구 줄 높이 (그 아래는 코드 패널)
PREVIEW_SCALE = 0.5                   # 실시간 창은 기준 크기의 절반 (540x960)
FPS = 60                              # 초당 프레임
START_SPEED = 3                       # 프레임당 확정할 교차로 수 (시작값)
START_HOLD_SEC = 1.0                  # 탐색 시작 전 지도만 보여주는 시간
END_HOLD_SEC = 3.0                    # mp4: 마지막 문구를 보여주는 시간
MP4_PATH = "geoje_dijkstra.mp4"       # mp4 저장 파일 이름

LANG = "en"                           # 영상 문구 언어: "en" 영어, "ko" 한국어

# 영상 문구 (언어별). 코드 패널은 글자 폭이 같은 영어 글꼴을 써야 줄이 맞아서 영어로 둔다
VIDEO_TEXT = {
    "en": {"checked": "CHECKED", "onroute": "ON ROUTE",
           "final_ok": ["SHORTEST FOR SURE,", "AT {n} INTERSECTIONS."],
           "final_none": ["NO ROUTE FOUND.", "ROADS NOT CONNECTED."],
           "final_tour": ["SHORTEST ORDER FOR SURE,", "{k} STOPS, {km} KM."], "stops": "STOPS"},
    "ko": {"checked": "확인한 교차로", "onroute": "경로 위 교차로",
           "final_ok": ["최단경로 확정!", "교차로 {n}개 확인"],
           "final_none": ["경로 없음.", "길이 이어져 있지 않다."],
           "final_tour": ["최단 순서 확정!", "{k}곳 경유, 총 {km} km"], "stops": "경유지"},
}
OSM_CREDIT = "Map data © OpenStreetMap contributors"   # 지도 데이터 출처 표시 (OSM 라이선스 조건)

COL_BG = (10, 10, 10)                 # 배경 #0a0a0a
COL_ROAD = (45, 45, 50)               # 기본 도로 (어두운 회색)
COL_SEARCH = (255, 214, 0)            # 탐색 중 노란 선
COL_ROUTE = (0, 230, 118)             # 최단경로 초록
COL_TEXT = (230, 230, 230)
COL_DIM = (130, 130, 130)
COL_START = (80, 160, 255)
COL_GOAL = (255, 80, 80)
COL_PANEL = (18, 18, 22)              # 코드 패널 배경

# 영상에 나온 C 코드 (아래 패널에 표시용)
C_CODE = [
    "// route_dijkstra.c",
    "dist[s] = 0; push(s, 0);",
    "while (!pq_empty()) {",
    "  v = pop_min();          // closest first",
    "  if (v == goal) return;  // reached goal",
    "  for (r=head[v]; r; r=r->next)",
    "    if (dist[r->to] > dist[v] + r->w) {",
    "      dist[r->to] = dist[v] + r->w;",
    "      push(r->to, dist[r->to]);",
    "    }",
    "}",
]


def point_from_place(name, lang=LANG):
    """route_core.PLACES 의 장소 이름 -> run() 에 넘길 점 {"lat", "lon", "label"}."""
    lat, lon = rc.PLACES[name]
    return {"lat": lat, "lon": lon, "label": rc.place_name(name, lang)}


def run(rm, start, goal_pt, record=False, out_path=MP4_PATH, show_window=True, lang=LANG,
        stops=None):
    """
    rm: route_core.RoadMap
    start, goal_pt: 출발/도착 점 {"lat": 위도, "lon": 경도, "label": 화면에 쓸 이름}
    record=False -> 실시간 창, True -> out_path 에 mp4 저장
    show_window=False 면 창 없이 영상만 만든다 (Streamlit 버튼에서 사용)
    lang: 영상 문구 언어 ("en" 또는 "ko")
    stops: 경유지 점 목록 (있으면 최단 방문 순서로 구간마다 탐색을 보여 줌)
    """
    VT = VIDEO_TEXT[lang]
    s, s_off = rm.nearest_node(start["lat"], start["lon"])
    goal, g_off = rm.nearest_node(goal_pt["lat"], goal_pt["lon"])
    print(f"출발 노드 {s} (지정 좌표에서 {s_off:.0f}m), 도착 노드 {goal} (지정 좌표에서 {g_off:.0f}m)")

    # 출발 -> 경유지(최단 순서) -> 도착 구간들을 미리 계산 (경유지가 없으면 구간 1개)
    stop_nodes = [rm.nearest_node(p["lat"], p["lon"])[0] for p in (stops or [])]
    plan = rc.plan_tour(rm, s, stop_nodes, goal)
    legs = plan["legs"]
    visit_nodes = [stop_nodes[i] for i in plan["visit"]]   # 경유지 교차로 (들르는 순서대로)
    total_checked = sum(len(l["order"]) for l in legs)

    # 그릴 캔버스 크기: mp4는 1080x1920 그대로, 실시간 창은 절반 크기
    S = 1.0 if record else PREVIEW_SCALE       # 모든 크기에 곱하는 배율
    W, H, MH = int(OUT_W * S), int(OUT_H * S), int(MAP_H * S)
    PY0 = int((MAP_H + MSG_H) * S)             # 코드 패널이 시작하는 높이

    def k(v):
        """기준 크기(1080 기준) 값을 지금 배율에 맞춘 정수로 바꾼다 (최소 1)."""
        return max(1, int(round(v * S)))

    # 미터 좌표 -> 화면 좌표 (지도 영역에 꽉 차게, 비율 유지)
    pad = k(50)
    w_m, h_m = float(rm.x.max()), float(rm.y.max())
    scale = min((W - 2 * pad) / w_m, (MH - 2 * pad) / h_m)
    off_x, off_y = (W - w_m * scale) / 2, (MH - h_m * scale) / 2

    def proj(x, y):
        return (x * scale + off_x, y * scale + off_y)

    # 엣지마다 곡선 점들을 화면 좌표로 미리 바꿔 둔다
    edge_pts = [[proj(x, y) for x, y in pts] for _, _, pts in rm.edges]
    node_pt = [(int(px), int(py)) for px, py in (proj(x, y) for x, y in zip(rm.x, rm.y))]

    import pygame
    pygame.init()
    window = None
    if record:
        canvas = pygame.Surface((W, H))        # 영상은 보이지 않는 큰 캔버스에 그린다
        if show_window:                         # 창에는 절반 크기로 줄여서 진행 상황만 보여 준다
            window = pygame.display.set_mode((int(W * PREVIEW_SCALE), int(H * PREVIEW_SCALE)))
    else:
        canvas = window = pygame.display.set_mode((W, H))
    if window is not None:
        pygame.display.set_caption("DIJKSTRA - Shortest route on a real map")
    clock = pygame.time.Clock()
    mono = "consolas,couriernew,monospace"
    # 한국어 문구는 한글이 나오는 맑은 고딕으로, 영어는 영상 느낌대로 고정폭 글꼴로
    txt_font = "malgungothic" if lang == "ko" else mono
    f_big = pygame.font.SysFont(txt_font, k(58), bold=True)
    f_mid = pygame.font.SysFont(txt_font, k(32))
    f_title = pygame.font.SysFont(mono, k(32))     # 코드 패널 제목 (영어)
    f_code = pygame.font.SysFont(mono, k(29))
    f_info = pygame.font.SysFont(mono, k(24))

    w_road, w_search, w_route = k(2), k(2), k(7)   # 선 굵기
    r_dot = k(12)                                   # 출발/도착 점 크기

    def draw_edge(surf, color, ei, width):
        """엣지 하나를 곡선(점 여러 개를 잇는 선)으로 그린다."""
        pygame.draw.lines(surf, color, False, edge_pts[ei], width)

    # 기본 도로 지도를 한 번만 그려 두고 매 프레임 복사해서 쓴다
    base = pygame.Surface((W, MH))
    base.fill(COL_BG)
    for ei in range(len(rm.edges)):
        draw_edge(base, COL_ROAD, ei, w_road)

    def new_layer():
        """노란 탐색선을 그릴 투명한 레이어 (구간이 바뀔 때마다 새로)."""
        return pygame.Surface((W, MH), pygame.SRCALPHA)

    # 진행 상태: li = 지금 구간 번호, idx = 그 구간에서 확인한 교차로 수
    layer = new_layer()
    li, idx, checked_before = 0, 0, 0
    route_shown = 0                # 지금 구간 경로 엣지를 몇 개까지 그렸나
    phase = "wait"                 # wait -> [구간마다 search -> route] -> done
    frame = 0                      # 지금 단계에서 지난 프레임 수
    paused = False
    speed = START_SPEED
    s_txt, g_txt = start["label"], goal_pt["label"]
    # 문구: "출발 → (경유지 N) → 도착" (경유지가 없으면 가운데는 빠짐)
    parts = [s_txt] + ([f"({VT['stops']} {len(visit_nodes)})"] if visit_nodes else []) + [g_txt]
    label = " -> ".join(parts).upper() if lang == "en" else " → ".join(parts)
    # 영어 화면이라도 검색으로 고른 한글 이름이 섞이면 한글이 나오는 글꼴로
    f_label = f_mid if label.isascii() else pygame.font.SysFont("malgungothic", k(32))

    writer = None
    if record:
        import imageio_ffmpeg
        writer = imageio_ffmpeg.write_frames(
            str(out_path), (W, H), fps=FPS, codec="libx264",
            pix_fmt_out="yuv420p", macro_block_size=1, quality=8)
        writer.send(None)       # 인코더 시작
        print(f"mp4 저장 시작 -> {out_path}")

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif record:
                    pass                     # 저장 중엔 다른 키는 무시 (영상이 꼬이지 않게)
                elif e.key == pygame.K_SPACE:
                    paused = not paused
                elif e.key == pygame.K_UP:
                    speed = min(speed * 2, 5000)
                elif e.key == pygame.K_DOWN:
                    speed = max(speed // 2, 1)
                elif e.key == pygame.K_r:
                    layer, li, idx, checked_before = new_layer(), 0, 0, 0
                    route_shown, phase, frame = 0, "wait", 0

        if not paused:
            frame += 1
            if phase == "wait":
                if frame >= START_HOLD_SEC * FPS:     # 잠깐 지도만 보여준 뒤 탐색 시작
                    phase, frame = "search", 0
            elif phase == "search":
                order = legs[li]["order"]
                for _ in range(speed):
                    if idx >= len(order):             # 이 구간 도착지까지 확인 끝
                        phase, frame = ("route" if legs[li]["route_edges"] else "next"), 0
                        break
                    v = order[idx]
                    idx += 1
                    if idx < len(order):              # 구간 도착지에서 뻗는 길은 안 그림 (거기서 끝이라)
                        # 확정된 교차로에서 뻗는 길을 노란색 곡선으로 표시
                        for _to, _w, ei in rm.adj[v]:
                            draw_edge(layer, COL_SEARCH, ei, w_search)
            elif phase == "route":
                # 구간 경로를 그린다 (구간이 1개면 약 2초, 여러 개면 구간마다 약 1초)
                route_e = legs[li]["route_edges"]
                dur = 60 if len(legs) > 1 else 120
                route_shown = min(route_shown + max(1, len(route_e) // dur), len(route_e))
                if route_shown >= len(route_e):
                    phase, frame = "next", 0
            elif phase == "done" and record and frame >= END_HOLD_SEC * FPS:
                running = False                       # mp4: 마지막 문구 보여준 뒤 끝
            if phase == "next":                       # 다음 구간으로 (없으면 끝)
                if li + 1 < len(legs):
                    checked_before += len(legs[li]["order"])
                    li, idx, route_shown, layer = li + 1, 0, 0, new_layer()   # 노란 선은 구간마다 새로
                    phase = "search"
                else:
                    phase = "done"

        # ---------------- 그리기 ----------------
        canvas.fill(COL_BG)
        canvas.blit(base, (0, 0))
        canvas.blit(layer, (0, 0))

        # 초록 최단경로: 끝난 구간 전부 + 지금 구간 진행분 (곡선)
        drawn = []
        for i, leg in enumerate(legs):
            if phase == "done" or i < li:
                drawn += leg["route_edges"]
            elif i == li:
                drawn += leg["route_edges"][:route_shown]
        for ei in drawn:
            draw_edge(canvas, COL_ROUTE, ei, w_route)

        # 출발/도착 표시, 경유지는 흰 동그라미 + 들르는 순서 번호
        pygame.draw.circle(canvas, COL_START, node_pt[s], r_dot)
        pygame.draw.circle(canvas, COL_GOAL, node_pt[goal], r_dot)
        for i, n in enumerate(visit_nodes):
            pygame.draw.circle(canvas, COL_TEXT, node_pt[n], k(20))
            num = f_info.render(str(i + 1), True, COL_BG)
            canvas.blit(num, num.get_rect(center=node_pt[n]))

        # 좌측 위 카운터 (ON ROUTE = 지나간 교차로 수 = 그린 엣지 수 + 1)
        checked = total_checked if phase == "done" else checked_before + idx
        on_route = len(drawn) + 1 if drawn else 0
        canvas.blit(f_mid.render(VT["checked"], True, COL_DIM), (k(40), k(40)))
        canvas.blit(f_big.render(f"{checked:,}", True, COL_SEARCH), (k(40), k(78)))
        canvas.blit(f_mid.render(VT["onroute"], True, COL_DIM), (k(40), k(170)))
        canvas.blit(f_big.render(f"{on_route:,}", True, COL_ROUTE), (k(40), k(208)))

        # 지도 아래 문구 줄: 처음엔 출발->도착 이름, 끝나면 마지막 문구 (두 줄)
        if phase == "done":
            ok = bool(drawn)
            if not ok:
                lines = VT["final_none"]
            elif visit_nodes:
                lines = [ln.replace("{k}", str(len(visit_nodes))).replace("{km}", f"{plan['km']:.2f}")
                         for ln in VT["final_tour"]]
            else:
                lines = [ln.replace("{n}", f"{total_checked:,}") for ln in VT["final_ok"]]
            for i, msg in enumerate(lines):
                txt = f_big.render(msg, True, COL_TEXT if ok else COL_GOAL)
                canvas.blit(txt, ((W - txt.get_width()) // 2, MH + k(10) + i * k(75)))
        else:
            txt = f_label.render(label, True, COL_DIM)
            canvas.blit(txt, ((W - txt.get_width()) // 2, MH + k(65)))

        # 아래 코드 패널
        pygame.draw.rect(canvas, COL_PANEL, (0, PY0, W, H - PY0))
        canvas.blit(f_title.render("DIJKSTRA - Shortest route on a real map", True, COL_DIM),
                    (k(50), PY0 + k(30)))
        for i, line in enumerate(C_CODE):
            canvas.blit(f_code.render(line, True, COL_TEXT),
                        (k(50), PY0 + k(90) + i * k(36)))
        # 맨 아래: 지도 출처, 그리고 실시간 창이면 조작키 안내
        credit = f_info.render(OSM_CREDIT, True, COL_DIM)
        canvas.blit(credit, (W - credit.get_width() - k(30), H - k(40) - (0 if record else k(34))))
        if not record:
            # 조작키 안내는 실시간 창에서만 (영상에는 안 넣음)
            info = f"speed x{speed}  UP/DOWN speed  SPACE pause  R restart  ESC quit"
            canvas.blit(f_info.render(info, True, COL_DIM), (k(50), H - k(40)))

        if record:
            writer.send(pygame.image.tobytes(canvas, "RGB"))   # 한 프레임 저장
            if window is not None:
                window.blit(pygame.transform.smoothscale(canvas, window.get_size()), (0, 0))
                pygame.display.flip()
            clock.tick()            # 저장 모드는 최대한 빨리 (속도 제한 없음)
        else:
            pygame.display.flip()
            clock.tick(FPS)

    if writer is not None:
        writer.close()              # 파일 마무리 (이걸 해야 mp4가 열림)
        print(f"저장 끝 -> {os.path.abspath(out_path)}")
    pygame.quit()


def render_mp4(rm, start, goal_pt, out_path, lang=LANG, stops=None):
    """창 없이 mp4만 만든다 (Streamlit 앱의 'mp4 만들기' 버튼용, 앱에서 고른 점·경유지·언어로)."""
    run(rm, start, goal_pt, record=True, out_path=out_path, show_window=False, lang=lang,
        stops=stops)


def main():
    record = "--mp4" in sys.argv               # --mp4 를 붙이면 영상 저장 모드
    rm = rc.load_roadmap()
    run(rm, point_from_place(START_NAME), point_from_place(GOAL_NAME), record=record)


if __name__ == "__main__":
    sys.exit(main())
