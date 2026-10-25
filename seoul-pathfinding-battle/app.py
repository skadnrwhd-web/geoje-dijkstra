"""
app.py
Seoul Pathfinding Battle 화면 (Streamlit)

실행:  streamlit run app.py
"""

import copy
import json

import streamlit as st

from algorithms import NoPathError, battle_summary, run_battle
from animation import BattleRenderer, map_preview
from config import CONFIG_PATH, DEFAULTS, load_config, resolve_path, save_config, validate
from map_loader import MapLoadError, load_graph, pick_endpoints, seoul_bbox, seoul_cache_file
from video_export import make_video

st.set_page_config(page_title="Seoul Pathfinding Battle", page_icon=":material/route:", layout="wide")

# 자주 쓰는 서울 장소 (대략적인 좌표. 가장 가까운 도로 교차로로 자동으로 맞춰진다)
PLACES = {
    "광화문": ("Gwanghwamun", 37.5716, 126.9769),
    "서울역": ("Seoul Stn", 37.5547, 126.9707),
    "사당역": ("Sadang Stn", 37.4765, 126.9816),
    "강남역": ("Gangnam Stn", 37.4979, 127.0276),
    "이태원역": ("Itaewon Stn", 37.5345, 126.9946),
    "여의도공원": ("Yeouido Park", 37.5259, 126.9223),
    "홍대입구역": ("Hongik Univ Stn", 37.5572, 126.9245),
    "성수역": ("Seongsu Stn", 37.5446, 127.0559),
    "잠실 롯데월드타워": ("Lotte World Tower", 37.5126, 127.1025),
    "수서역": ("Suseo Stn", 37.4873, 127.1015),
    "노원역": ("Nowon Stn", 37.6551, 127.0613),
}

if "cfg" not in st.session_state:
    st.session_state.cfg = load_config()
    st.session_state.battle = None
    st.session_state.video = None
    st.session_state.preview = None
    st.session_state.cfg_ver = 0
cfg = st.session_state.cfg


# ------------------------------------------------------------ 캐시된 계산

def map_key(c):
    keep = {"map_mode": c["map_mode"]}
    keep.update({"seoul_map": c["seoul_map"], "bbox": seoul_bbox(c)} if c["map_mode"] == "seoul"
                else {"grid_map": c["grid_map"]})
    return json.dumps(keep, sort_keys=True, default=str)


@st.cache_resource(max_entries=4, show_spinner=False)
def get_graph(key, _cfg):
    return load_graph(_cfg, progress=lambda m: None)


def current_graph():
    return get_graph(map_key(cfg), copy.deepcopy(cfg))


def battle_key(c):
    return json.dumps([map_key(c), c["start"], c["goal"], c["grid_map"]["start_frac"],
                       c["grid_map"]["goal_frac"], c["benchmark"]], sort_keys=True)


# ------------------------------------------------------------ 사이드바: 설정

with st.sidebar:
    st.header(":material/tune: 설정")
    with st.form("settings"):
        mode = st.segmented_control("지도", ["seoul", "grid"], default=cfg["map_mode"],
                                    format_func={"seoul": "서울 도로망", "grid": "가상 격자"}.get)
        st.caption("가상 격자는 인터넷 없이 동작합니다.")

        st.subheader("출발지 · 목적지", divider="gray")
        names = ["직접 입력"] + list(PLACES)
        ver = st.session_state.cfg_ver   # 설정이 바뀌면 입력칸을 새 값으로 다시 만든다
        picked = {}
        for key, label in (("start", "출발지"), ("goal", "목적지")):
            p = cfg[key]
            idx = names.index(p["name"]) if p["name"] in PLACES else 0
            choice = st.selectbox(label, names, index=idx, key=f"{key}_pick{ver}")
            c1, c2 = st.columns(2)
            lat = c1.number_input("위도", value=float(p["lat"]), format="%.5f", key=f"{key}_lat{ver}")
            lon = c2.number_input("경도", value=float(p["lon"]), format="%.5f", key=f"{key}_lon{ver}")
            name = st.text_input("이름", value=p["name"], key=f"{key}_name{ver}")
            name_en = st.text_input("영문 이름", value=p.get("name_en", ""), key=f"{key}_en{ver}")
            picked[key] = (choice, lat, lon, name, name_en)
        margin = st.slider("지도 여유 영역 (km)", 0.3, 4.0, float(cfg["seoul_map"]["margin_km"]), 0.1)

        st.subheader("영상", divider="gray")
        title = st.text_input("영상 제목", cfg["video"]["title"])
        subtitle = st.text_input("부제목", cfg["video"]["subtitle"])
        duration = st.slider("영상 길이 (초)", 15, 60, int(cfg["video"]["duration_sec"]))
        npf = st.number_input("애니메이션 속도 (프레임당 노드 수, 0 = 영상 길이에 자동 맞춤)", 0, 5000,
                              int(cfg["video"]["nodes_per_frame"]))
        out_dir = st.text_input("출력 폴더", cfg["video"]["output_dir"])

        st.subheader("색상 · 글꼴", divider="gray")
        cc = st.columns(3)
        colors = {}
        for i, (k, label) in enumerate((("dijkstra", "다익스트라"), ("astar", "A*"), ("path", "최종 경로"),
                                        ("background", "배경"), ("road", "도로"), ("road_major", "큰길"))):
            colors[k] = cc[i % 3].color_picker(label, cfg["style"][k])
        font = st.text_input("글꼴 파일 (비우면 자동)", cfg["style"]["font_bold"])

        if st.form_submit_button("적용", icon=":material/check:", type="primary", width="stretch"):
            new = copy.deepcopy(cfg)
            new["map_mode"] = mode or cfg["map_mode"]
            for key, (choice, lat, lon, name, name_en) in picked.items():
                if choice != "직접 입력" and choice != cfg[key]["name"]:
                    en, lat, lon = PLACES[choice]
                    name, name_en = choice, en
                new[key] = {"name": name, "name_en": name_en, "lat": lat, "lon": lon}
            new["seoul_map"]["margin_km"] = margin
            new["video"].update(title=title, subtitle=subtitle, duration_sec=duration,
                                nodes_per_frame=int(npf), output_dir=out_dir)
            new["style"].update(colors)
            new["style"]["font_bold"] = font
            try:
                validate(new)
            except ValueError as e:
                st.error(str(e))
            else:
                st.session_state.cfg = new
                st.session_state.cfg_ver += 1
                st.rerun()

    c1, c2 = st.columns(2)
    if c1.button("config.json 저장", icon=":material/save:", width="stretch"):
        save_config(cfg)
        st.toast(f"저장했습니다: {CONFIG_PATH.name}")
    if c2.button("기본값", icon=":material/restart_alt:", width="stretch"):
        st.session_state.cfg = copy.deepcopy(DEFAULTS)
        st.session_state.cfg_ver += 1
        st.rerun()


# ------------------------------------------------------------ 본문

st.title("Dijkstra vs A* · Seoul Pathfinding Battle")
st.caption("같은 도로 그래프, 같은 출발지·목적지, 같은 이동 비용으로 두 알고리즘을 겨루고 세로 영상으로 만듭니다.")

tabs = st.tabs([":material/map: 지도·경로", ":material/swords: 배틀 실행", ":material/leaderboard: 비교 지표",
                ":material/preview: 영상 미리보기", ":material/movie: MP4 생성", ":material/help: 사용 안내"])

battle = st.session_state.battle
if battle and battle["key"] != battle_key(cfg):
    battle = st.session_state.battle = None      # 설정이 바뀌면 이전 결과는 버린다

# 1. 지도 · 경로
with tabs[0]:
    left, right = st.columns([1, 2])
    with left:
        mode_name = "서울 도로망 (OpenStreetMap)" if cfg["map_mode"] == "seoul" else "가상 격자 도시"
        st.markdown(f"**지도:** {mode_name}")
        if cfg["map_mode"] == "seoul":
            st.markdown(f"**출발지:** {cfg['start']['name']} ({cfg['start']['lat']:.4f}, {cfg['start']['lon']:.4f})")
            st.markdown(f"**목적지:** {cfg['goal']['name']} ({cfg['goal']['lat']:.4f}, {cfg['goal']['lon']:.4f})")
            st.markdown(f"**영역 [서, 남, 동, 북]:** `{seoul_bbox(cfg)}`")
            cached = seoul_cache_file(cfg).exists()
            st.caption(("저장된 지도 사용: " if cached else "처음이면 OpenStreetMap 에서 받습니다 (1~3분): ")
                       + seoul_cache_file(cfg).name)
        load = st.button("지도 불러오기", icon=":material/download:", type="primary")
    with right:
        if load or st.session_state.get("map_loaded") == map_key(cfg):
            try:
                with st.spinner("지도 준비 중..."):
                    g = current_graph()
                    s, t = pick_endpoints(g, cfg)
                    img = map_preview(g, s, t, cfg)
                st.session_state.map_loaded = map_key(cfg)
                c1, c2 = st.columns([1, 1])
                c1.image(img, caption=g.source)
                with c2:
                    st.metric("교차로(노드)", f"{g.n_nodes:,}")
                    st.metric("도로 간선 (방향 있음)", f"{g.n_edges:,}")
                    st.caption("일방통행은 한쪽 방향 간선만 있습니다. 들어가면 나올 수 없는 구역은 "
                               "제거(강한 연결 최대 덩어리)했습니다.")
            except (MapLoadError, ValueError) as e:
                st.error(str(e), icon=":material/error:")
        else:
            st.info("‘지도 불러오기’를 누르면 지도와 출발지·목적지를 보여 줍니다.", icon=":material/info:")

# 2. 배틀 실행
with tabs[1]:
    st.markdown("두 알고리즘을 실행하고, 실행 시간은 렌더링과 분리해 "
                f"**{cfg['benchmark']['repeats']}회 반복 측정의 중앙값**으로 기록합니다.")
    if st.button("배틀 시작", icon=":material/play_arrow:", type="primary"):
        try:
            with st.status("배틀 진행 중...", expanded=True) as status:
                st.write("지도 준비")
                g = current_graph()
                s, t = pick_endpoints(g, cfg)
                st.write(f"탐색·시간 측정 (노드 {g.n_nodes:,}개)")
                b = run_battle(g, s, t, cfg)
                b["key"] = battle_key(cfg)
                st.session_state.battle = battle = b
                st.session_state.preview = None
                status.update(label="배틀 완료", state="complete", expanded=False)
        except (MapLoadError, NoPathError, ValueError) as e:
            st.error(str(e), icon=":material/error:")
    if battle:
        v = battle["verdict"]
        st.success(f"승자: **{v['winner']}**  (다익스트라 {v['score']['Dijkstra']} : {v['score']['A*']} A*)  · "
                   "자세한 내용은 ‘비교 지표’ 탭", icon=":material/emoji_events:")

# 3. 비교 지표
with tabs[2]:
    if not battle:
        st.info("먼저 ‘배틀 실행’ 탭에서 배틀을 시작하세요.", icon=":material/info:")
    else:
        d, a, tm = battle["dijkstra"], battle["astar"], battle["timing"]
        cols = st.columns(2)
        for col, r, name in ((cols[0], d, "Dijkstra"), (cols[1], a, "A*")):
            with col.container(border=True):
                st.subheader(name)
                m = st.columns(3)
                m[0].metric("탐색 노드 수", f"{r.expanded:,}")
                m[1].metric("경로 길이 (km)", f"{battle['path_km'][name]:.2f}")
                m[2].metric("실행 시간 (ms)", f"{tm[name]['median_ms']:.2f}")
                st.caption(f"살펴본 간선 {r.edges_scanned:,} · 큐 삽입 {r.pushes:,} · "
                           f"목적지 도달 {'예' if r.found else '아니오'} · "
                           f"최적 경로 {'예' if battle['optimal'][name] else '아니오'}")
        v = battle["verdict"]
        st.subheader("지표별 판정")
        fmt = {"cost": "{:.3f}", "expanded": "{:,}", "time": "{:.3f}"}
        st.table([{"지표": r["label"], "Dijkstra": fmt[r["key"]].format(r["dijkstra"]),
                   "A*": fmt[r["key"]].format(r["astar"]),
                   "승": {"tie": "무승부"}.get(r["winner"], r["winner"])} for r in v["rows"]])
        diff = d.expanded - a.expanded
        st.markdown(f"- 노드 탐색 수 차이: **{abs(diff):,}개** "
                    f"({'A*' if diff > 0 else 'Dijkstra'} 가 더 적음)" if diff else "- 노드 탐색 수 같음")
        st.markdown(f"- networkx 기준 최단 거리: **{battle['reference_cost_m'] / 1000:.3f} km** → "
                    f"두 결과 모두 최적: **{'예' if all(battle['optimal'].values()) else '아니오'}**")
        st.markdown(f"- 판정 규칙: {v['rule']}. 종합 승자: **{v['winner']}**")
        with st.expander("지표 정의"):
            st.markdown(
                "- **탐색 노드 수**: 우선순위 큐에서 꺼내 확정(확장)한 고유 노드 수\n"
                "- **경로 길이**: 선택된 경로의 실제 도로 간선 길이(OSM `length`, m) 합. 직선 거리가 아님\n"
                f"- **실행 시간**: 기록·렌더링 없는 순수 계산을 {cfg['benchmark']['repeats']}회 번갈아 측정한 중앙값. "
                "PC 성능·실행 환경에 따라 달라질 수 있음\n"
                "- **A\\* 휴리스틱**: 목적지까지의 대원(직선) 거리(m). 도로 비용과 같은 단위이고 실제 도로 거리보다 "
                "길 수 없어 최적 경로가 보장됨")
        with st.expander("측정 원자료"):
            st.json(tm)
        summary = battle_summary(battle, current_graph(), cfg)
        st.download_button("결과 기록(JSON) 받기", json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                           "battle_result.json", "application/json", icon=":material/download:")

# 4. 영상 미리보기
with tabs[3]:
    if not battle:
        st.info("먼저 배틀을 실행하세요.", icon=":material/info:")
    else:
        if st.button("대표 장면 보기", icon=":material/image:"):
            with st.spinner("장면 그리는 중..."):
                st.session_state.preview = BattleRenderer(current_graph(), battle, cfg).key_frames()
        if st.session_state.preview:
            cols = st.columns(4)
            for col, (name, img) in zip(cols, st.session_state.preview.items()):
                col.image(img, caption=name)
        st.divider()
        if st.button("저해상도 미리보기 영상 (540x960)", icon=":material/slow_motion_video:"):
            bar = st.progress(0.0, "미리보기 영상 만드는 중...")
            res = make_video(cfg, preview=True, graph=current_graph(), battle=battle, log=lambda m: None,
                             progress=lambda i, n: bar.progress(i / n, f"{i}/{n} 프레임"))
            st.session_state.preview_video = str(res["mp4"])
        if st.session_state.get("preview_video"):
            st.video(st.session_state.preview_video, width=360)

# 5. MP4 생성
with tabs[4]:
    v = cfg["video"]
    st.markdown(f"**{v['width']}×{v['height']}**, {v['fps']}fps, 목표 길이 {v['duration_sec']}초 · "
                f"저장 폴더 `{resolve_path(v['output_dir'])}`")
    if not battle:
        st.info("먼저 배틀을 실행하세요.", icon=":material/info:")
    elif st.button("MP4 만들기", icon=":material/movie:", type="primary"):
        bar = st.progress(0.0, "영상 만드는 중...")
        try:
            res = make_video(cfg, graph=current_graph(), battle=battle, log=lambda m: None,
                             progress=lambda i, n: bar.progress(i / n, f"{i}/{n} 프레임"))
            st.session_state.video = {"mp4": str(res["mp4"]), "json": str(res["json"]),
                                      "sec": res["renderer"].duration_sec}
        except RuntimeError as e:
            st.error(str(e), icon=":material/error:")
    if st.session_state.video:
        info = st.session_state.video
        st.success(f"저장됨: `{info['mp4']}` ({info['sec']:.1f}초)\n\n설정·결과 기록: `{info['json']}`",
                   icon=":material/check_circle:")
        c1, _ = st.columns([1, 2])
        c1.video(info["mp4"])
        with open(info["mp4"], "rb") as f:
            st.download_button("MP4 받기", f.read(), file_name=resolve_path(info["mp4"]).name,
                               mime="video/mp4", icon=":material/download:")

# 6. 사용 안내
with tabs[5]:
    st.markdown("""
**순서**
1. 왼쪽 사이드바에서 지도(서울/가상 격자), 출발지·목적지, 영상 제목 등을 고르고 **적용**을 누릅니다.
2. **지도·경로** 탭에서 *지도 불러오기* 로 영역과 출발지·목적지를 확인합니다. 서울 지도는 처음 한 번 인터넷에서 받고 `maps/` 에 저장합니다.
3. **배틀 실행** 탭에서 *배틀 시작* → **비교 지표** 탭에서 결과 확인.
4. **영상 미리보기** 에서 장면을 확인하고, **MP4 생성** 탭에서 1080×1920 영상을 만듭니다.
5. 마음에 드는 설정은 사이드바의 *config.json 저장* 으로 남겨 두면 다음에도 그대로 쓰입니다.

**알아 두기**
- 애니메이션은 두 알고리즘이 **프레임당 같은 수의 노드**를 확장합니다. 먼저 끝나는 쪽이 실제로 적게 탐색한 쪽입니다.
- 실행 시간(ms)은 애니메이션과 별개로 측정한 값이며 PC 마다 다릅니다.
- 인터넷이 없으면 지도를 **가상 격자** 로 바꾸세요.
- 지도 데이터: © OpenStreetMap contributors, ODbL 1.0 라이선스. 영상에 출처 문구가 자동으로 들어갑니다.

명령줄로도 만들 수 있습니다: `python video_export.py` (자세한 내용은 README.md)
""")
