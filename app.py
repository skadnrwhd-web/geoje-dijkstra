"""
app.py
거제 도로망 위에서 다익스트라 탐색이 퍼져 나가는 과정을 보여주는 Streamlit 앱

실행:  python -m streamlit run app.py
조작:
  - 왼쪽: 언어(한국어/English), 출발지·경유지·도착지 선택 (목록 / 이름 검색)
  - 지도 아래 '출발 찍기'/'경유 찍기'/'도착 찍기' 누른 뒤 지도 클릭으로도 선택
  - 경유지가 있으면 들르는 순서를 모든 경우 비교해서 최단 순서로 맞춤 (최대 8곳)
  - 마우스 휠: 줌 인/아웃 (마우스 위치 기준)
  - 드래그: 지도 옮기기
  - 지도 아래 버튼: 재생/일시정지, 처음부터, 속도 -/+, 줌 +/-, 전체 보기
"""

import math
from pathlib import Path

import streamlit as st

import route_core as rc
from texts import TEXT, c_code

LANGS = {"ko": "한국어", "en": "English"}   # 언어 코드 -> 버튼에 보일 이름

# 언어는 페이지 제목에도 쓰므로 위젯보다 먼저 읽는다 (처음엔 한국어)
_lang0 = st.session_state.get("lang") or "ko"
st.set_page_config(page_title=TEXT[_lang0]["page_title"],
                   page_icon=":material/route:", layout="wide")

# ------------------------------------------------------------------
# 지도 애니메이션 컴포넌트 (브라우저 안에서 canvas로 그림)
# 파이썬은 데이터만 넘기고, 애니메이션/줌/드래그는 브라우저가 처리한다.
# ------------------------------------------------------------------
MAP_HTML = """
<div class="wrap">
  <canvas></canvas>
  <div class="count">
    <div class="lbl" data-id="checked_lbl"></div><div class="num yel" data-id="checked">0</div>
    <div class="lbl" data-id="onroute_lbl"></div><div class="num grn" data-id="onroute">0</div>
  </div>
  <div class="hint" data-id="hint"></div>
  <div class="label" data-id="label"></div>
  <div class="final" data-id="final"></div>
  <div class="bar">
    <button data-act="pick_s" class="ps"></button>
    <button data-act="pick_w" class="pw"></button>
    <button data-act="pick_g" class="pg"></button>
    <span class="sep"></span>
    <button data-act="play">❚❚</button>
    <button data-act="restart">↺</button>
    <span class="sep"></span>
    <button data-act="slower">−</button>
    <span class="speed" data-id="speed">x3</span>
    <button data-act="faster">+</button>
    <span class="sep"></span>
    <button data-act="zin"></button>
    <button data-act="zout"></button>
    <button data-act="fit"></button>
  </div>
</div>
"""

MAP_CSS = """
/* 지도 상자: 화면 높이의 78% */
.wrap { position: relative; width: 100%; height: 78vh; min-height: 520px;
        background: #0a0a0a; border-radius: 8px; overflow: hidden;
        font-family: Consolas, "Malgun Gothic", monospace; user-select: none; }
canvas { width: 100%; height: 100%; display: block; cursor: grab; touch-action: none; }
canvas.drag { cursor: grabbing; }
canvas.pick { cursor: crosshair; }
/* 지도 찍기 모드일 때 위쪽 안내 문구 */
.hint { position: absolute; left: 50%; top: 14px; transform: translateX(-50%);
        background: rgba(20,20,24,.92); color: #e6e6e6; border: 1px solid #3a3a42;
        border-radius: 8px; padding: 6px 12px; font-size: 14px; display: none;
        pointer-events: none; white-space: nowrap; }
/* 왼쪽 위 카운터 */
.count { position: absolute; left: 18px; top: 14px; pointer-events: none; }
.lbl { color: #828282; font-size: 15px; margin-top: 6px; }
.num { font-size: 30px; font-weight: bold; line-height: 1.1; }
.yel { color: #ffd600; }  .grn { color: #00e676; }
/* 아래쪽 출발->도착 이름, 마지막 문구 */
.label { position: absolute; left: 0; right: 0; bottom: 64px; text-align: center;
         color: #828282; font-size: 16px; pointer-events: none; }
.final { position: absolute; left: 0; right: 0; bottom: 58px; text-align: center;
         color: #e6e6e6; font-size: clamp(16px, 2.2vw, 28px); font-weight: bold;
         pointer-events: none; background: rgba(0,0,0,.6); padding: 6px 8px; display: none; }
/* 버튼 줄 */
.bar { position: absolute; left: 50%; bottom: 12px; transform: translateX(-50%);
       display: flex; gap: 6px; align-items: center; background: rgba(20,20,24,.9);
       border: 1px solid #333; border-radius: 8px; padding: 6px 8px; }
.bar button { background: #26262c; color: #e6e6e6; border: 1px solid #3a3a42;
              border-radius: 6px; min-width: 36px; height: 30px; padding: 0 8px;
              white-space: nowrap; cursor: pointer; font-size: 14px; }
.bar button:hover { background: #33333b; }
.bar button.ps { border-color: #50a0ff; }   /* 출발 찍기 = 파랑 */
.bar button.pg { border-color: #ff5050; }   /* 도착 찍기 = 빨강 */
.bar button.pw { border-color: #e6e6e6; }   /* 경유 찍기 = 흰색 */
.bar button.pw.on { background: #e6e6e6; color: #0a0a0a; }
.bar button.ps.on { background: #50a0ff; color: #0a0a0a; }   /* 찍기 모드 켜짐 */
.bar button.pg.on { background: #ff5050; color: #0a0a0a; }
.speed { color: #e6e6e6; min-width: 42px; text-align: center; font-size: 14px; }
.sep { width: 1px; height: 22px; background: #3a3a42; margin: 0 2px; }
"""

MAP_JS = """
const STATES = new WeakMap();   // 컴포넌트마다 애니메이션 상태를 따로 보관
const COL = { bg: "#0a0a0a", road: "#2d2d32", search: "#ffd600", route: "#00e676",
              start: "#50a0ff", goal: "#ff5050" };
const SPEEDS = [0.25, 0.5, 1, 2, 3, 5, 8, 12, 20, 40, 80];   // 프레임당 확정할 교차로 수

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  if (!data) return;
  const old = STATES.get(parentElement);
  if (old && old.sig === data.sig) {         // 같은 경로면 애니메이션은 그대로 두고
    old.setText(data.t, data.label);         // 언어만 바뀐 경우 문구만 바꾼다
    return;
  }
  if (old) {                                 // 출발/도착이 바뀌면 이전 애니메이션 정리
    old.stop = true;
    old.ac.abort();                          // 이전 마우스/휠 처리 해제 (겹치지 않게)
    old.ro.disconnect();
  }

  const q = (sel) => parentElement.querySelector(sel);
  const canvas = q("canvas");
  const ctx = canvas.getContext("2d");
  const el = (id) => q(`[data-id="${id}"]`);
  const btn = (act) => q(`[data-act="${act}"]`);
  const st = { sig: data.sig, stop: false, ac: new AbortController() };
  const on = { signal: st.ac.signal };       // 이 신호로 등록한 처리는 abort() 한 번에 해제
  STATES.set(parentElement, st);

  // ---- 문구 (언어) ----
  let T = data.t;                            // 지금 언어의 문구 묶음
  st.setText = (t, label) => {
    T = t;
    el("checked_lbl").textContent = T.checked;
    el("onroute_lbl").textContent = T.onroute;
    el("label").textContent = label;
    for (const a of ["play", "restart", "slower", "faster"]) btn(a).title = T[a];
    for (const a of ["zin", "zout", "fit", "pick_s", "pick_w", "pick_g"]) {
      btn(a).textContent = T[a]; btn(a).title = T[a + "_t"];
    }
    showPick();
  };
  // ---- 지도 찍기 모드 (출발 찍기 / 도착 찍기) ----
  let pick = null;                           // null, "start"(출발), "stop"(경유), "goal"(도착)
  function showPick() {                      // 버튼 강조, 커서, 안내 문구를 지금 모드에 맞춘다
    btn("pick_s").classList.toggle("on", pick === "start");
    btn("pick_w").classList.toggle("on", pick === "stop");
    btn("pick_g").classList.toggle("on", pick === "goal");
    canvas.classList.toggle("pick", !!pick);
    el("hint").style.display = pick ? "block" : "none";
    if (pick) el("hint").textContent = { start: T.hint_s, stop: T.hint_w, goal: T.hint_g }[pick];
  }
  st.setText(data.t, data.label);

  // ---- 데이터 풀기 ----
  const E = data.edges;               // E[i] = [x0,y0,x1,y1,...] 엣지 i 의 곡선 점들 (미터)
  const out = data.out;               // out[v] = v에서 나가는 엣지 번호들
  // 구간(leg): 출발 -> 경유지1 -> ... -> 도착. 경유지가 없으면 구간은 1개
  //   legs[i].order = 그 구간에서 다익스트라가 확정한 교차로 순서
  //   legs[i].route_edges = 그 구간 최단경로 엣지 번호들
  const legs = data.legs;
  const stops = data.stops;           // 경유지 교차로 번호 (들르는 순서대로)
  const nx = data.nx, ny = data.ny;   // 교차로 좌표
  const totalChecked = legs.reduce((a, l) => a + l.order.length, 0);

  function addEdge(path, i) {         // 엣지 i 의 곡선을 path 에 이어 붙인다
    const p = E[i];
    path.moveTo(p[0], p[1]);
    for (let k = 2; k < p.length; k += 2) path.lineTo(p[k], p[k + 1]);
  }
  const roads = new Path2D();         // 전체 도로 (한 번만 만든다)
  for (let i = 0; i < E.length; i++) addEdge(roads, i);

  // ---- 화면 크기 / 줌 상태 ----
  let dpr = 1, cw = 1, ch = 1;              // 화면 배율, 캔버스 너비/높이 (CSS 픽셀)
  let view = old ? old.view : { s: 1, tx: 0, ty: 0 };   // 화면 = 미터 * s + t (경로가 바뀌어도 줌은 유지)
  let drawnView = "";                       // 숨은 캔버스를 그릴 때의 줌 상태 (바뀌면 다시 그림)
  let fitted = !!(old && old.fitted);       // 지도 전체 맞춤을 한 번이라도 했나 (경로가 바뀌어도 유지)
  function fit() {                          // 지도 전체가 보이게 맞춘다
    const pad = 40, bottom = 110;           // 아래쪽은 버튼/문구 자리로 비워 둠
    const aw = cw - 2 * pad, ah = ch - pad - bottom;   // 지도를 그릴 수 있는 가로/세로
    // 화면이 아직 너무 작으면(숨김 탭, 로딩 중: 크기 0) 맞추지 않는다. 크기 0으로 계산하면
    // 배율이 음수가 돼서 지도가 영영 안 그려졌다. 나중에 화면이 커지면 그때 맞춘다.
    if (aw < 50 || ah < 50) return;
    const s = Math.min(aw / data.w, ah / data.h);
    setView({ s, tx: (cw - data.w * s) / 2, ty: pad + (ah - data.h * s) / 2 });
    fitted = true; st.fitted = true;
  }
  function resize() {                       // 창 크기가 바뀌면 캔버스 크기도 맞춘다
    dpr = window.devicePixelRatio || 1;
    cw = canvas.clientWidth; ch = canvas.clientHeight;
    canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr);
    if (!fitted) fit();                     // 처음엔 화면이 충분히 커졌을 때 한 번만 전체 맞춤
  }
  resize();
  st.ro = new ResizeObserver(() => { if (!st.stop) resize(); });
  st.ro.observe(canvas);

  function setView(v) { view = v; st.view = v; }   // 줌 상태를 바꾸고, 다음 경로에도 넘겨줄 수 있게 보관
  setView(view);
  function zoomAt(f, mx, my) {              // (mx,my) 화면 위치를 고정하고 f배 줌
    const s = Math.min(Math.max(view.s * f, 0.002), 5);
    const k = s / view.s;
    setView({ s, tx: mx - (mx - view.tx) * k, ty: my - (my - view.ty) * k });
  }
  canvas.addEventListener("wheel", (e) => { // 마우스 휠 = 줌 (페이지 스크롤은 막음)
    e.preventDefault();
    const r = canvas.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false, signal: st.ac.signal });
  let drag = null;                          // 드래그로 지도 옮기기 (찍기 모드에선 클릭으로 처리)
  canvas.addEventListener("pointerdown", (e) => {
    drag = { x: e.clientX, y: e.clientY, tx: view.tx, ty: view.ty };
    canvas.setPointerCapture(e.pointerId); canvas.classList.add("drag");
  }, on);
  canvas.addEventListener("pointermove", (e) => {
    if (!drag) return;
    setView({ s: view.s, tx: drag.tx + e.clientX - drag.x, ty: drag.ty + e.clientY - drag.y });
  }, on);
  canvas.addEventListener("pointerup", (e) => {
    // 찍기 모드에서 거의 안 움직이고 뗐으면 = 클릭 -> 그 위치를 파이썬에 알린다
    if (drag && pick && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 5) {
      const r = canvas.getBoundingClientRect();
      const x = (e.clientX - r.left - view.tx) / view.s;   // 화면 픽셀 -> 지도 미터 좌표
      const y = (e.clientY - r.top - view.ty) / view.s;
      setTriggerValue("picked", { kind: pick, x, y });
      pick = null; showPick();
    }
    drag = null; canvas.classList.remove("drag");
  }, on);
  canvas.addEventListener("pointercancel", () => { drag = null; canvas.classList.remove("drag"); }, on);

  // ---- 애니메이션 상태 ----
  // phase: wait(지도만 1초) -> [구간마다 search(노란 선 퍼짐) -> route(초록 경로)] -> done(마지막 문구)
  let phase, frame, li, idx, acc, search, routeShown, checkedBefore, paused = false;
  let speedI = SPEEDS.indexOf(3);
  function reset() {
    phase = "wait"; frame = 0; li = 0; idx = 0; acc = 0; routeShown = 0;
    checkedBefore = 0;                      // 앞 구간들에서 확인한 교차로 수 (카운터용)
    search = new Path2D();                  // 노란 탐색선 (점점 늘어남, 구간마다 새로)
    drawnView = "";                         // 숨은 캔버스도 새로 그리게
    el("final").style.display = "none";
  }
  reset();

  // ---- 버튼 ----
  q(".bar").onclick = (e) => {
    const act = e.target.closest("button")?.dataset.act;
    if (act === "play") paused = !paused;
    else if (act === "restart") { reset(); paused = false; }
    else if (act === "slower") speedI = Math.max(speedI - 1, 0);
    else if (act === "faster") speedI = Math.min(speedI + 1, SPEEDS.length - 1);
    else if (act === "zin") zoomAt(1.5, cw / 2, ch / 2);
    else if (act === "zout") zoomAt(1 / 1.5, cw / 2, ch / 2);
    else if (act === "fit") fit();
    else if (act === "pick_s") { pick = pick === "start" ? null : "start"; showPick(); }  // 다시 누르면 취소
    else if (act === "pick_g") { pick = pick === "goal" ? null : "goal"; showPick(); }
    else if (act === "pick_w") { pick = pick === "stop" ? null : "stop"; showPick(); }
    btn("play").textContent = paused ? "▶" : "❚❚";
    el("speed").textContent = "x" + SPEEDS[speedI];
  };

  // ---- 한 프레임 진행 (dt: 지난 프레임부터 흐른 시간, 60fps 기준 프레임 수) ----
  // 브라우저가 느려 프레임이 덜 나와도 같은 시간에 같은 만큼 진행되게 시간 기준으로 계산
  let fresh = null;                         // 이번 프레임에 새로 확정된 길 (노란 레이어에 덧그림)
  function step(dt) {
    frame += dt;
    if (phase === "wait") {
      if (frame >= 60) { phase = "search"; frame = 0; }    // 1초 동안 지도만 보여 줌
    } else if (phase === "search") {
      const order = legs[li].order;
      acc += SPEEDS[speedI] * dt;
      if (acc >= 1) fresh = new Path2D();
      while (acc >= 1 && idx < order.length) {
        acc -= 1;
        const v = order[idx++];
        for (const ei of out[v]) { addEdge(search, ei); addEdge(fresh, ei); }  // 확정된 교차로에서 뻗는 길
      }
      if (idx >= order.length) {
        phase = legs[li].route_edges.length ? "route" : "next"; frame = 0;
      }
    } else if (phase === "route") {
      // 구간 경로를 그린다 (구간이 1개면 2초, 여러 개면 구간마다 1초)
      const routeE = legs[li].route_edges;
      const dur = legs.length > 1 ? 60 : 120;
      routeShown = Math.min(Math.ceil(routeE.length * frame / dur), routeE.length);
      if (routeShown >= routeE.length) { phase = "next"; frame = 0; }
    }
    if (phase === "next") {                    // 다음 구간으로 (없으면 끝)
      if (li + 1 < legs.length) {
        checkedBefore += legs[li].order.length;
        li++; idx = 0; acc = 0; routeShown = 0;
        search = new Path2D(); drawnView = "";  // 노란 선은 구간마다 새로 (지난 구간 초록 경로는 남김)
        phase = "search";
      } else {
        phase = "done";
      }
    }
  }
  // 지금까지 그린 초록 경로의 엣지들 (끝난 구간 전부 + 지금 구간 진행분)
  function routeSoFar() {
    const done = phase === "done";
    const res = [];
    for (let i = 0; i < legs.length; i++) {
      if (done || i < li) res.push(...legs[i].route_edges);
      else if (i === li) res.push(...legs[i].route_edges.slice(0, routeShown));
    }
    return res;
  }

  // ---- 그리기 ----
  // 도로/노란선은 각각 숨은 캔버스에 미리 그려 두고, 줌·이동할 때만 다시 그린다 (빠르게)
  const roadsCv = document.createElement("canvas"), searchCv = document.createElement("canvas");
  function useView(c) {                      // 지도 좌표(미터) -> 화면 픽셀 변환을 건다
    c.setTransform(view.s * dpr, 0, 0, view.s * dpr, view.tx * dpr, view.ty * dpr);
    c.lineJoin = "round"; c.lineCap = "round";
  }
  function strokeSearch(path) {              // 노란 탐색선을 숨은 캔버스에 그린다
    const c = searchCv.getContext("2d");
    useView(c); c.lineWidth = 1.2 / view.s; c.strokeStyle = COL.search; c.stroke(path);
  }
  function redrawLayers() {                  // 줌/이동/크기 변경 시 전부 다시 그림
    for (const cv of [roadsCv, searchCv]) {
      cv.width = canvas.width; cv.height = canvas.height;   // 크기 지정 = 지우기
    }
    const c = roadsCv.getContext("2d");
    useView(c); c.lineWidth = 1 / view.s; c.strokeStyle = COL.road; c.stroke(roads);
    strokeSearch(search);
  }
  function draw() {
    if (!(view.s > 0) || canvas.width < 2 || canvas.height < 2) return;   // 화면이 아직 준비 안 됐으면 건너뜀
    const v = `${view.s},${view.tx},${view.ty},${canvas.width},${canvas.height}`;
    if (v !== drawnView) { redrawLayers(); drawnView = v; }
    else if (fresh) strokeSearch(fresh);       // 줌 그대로면 새 길만 덧그림
    fresh = null;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = COL.bg; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(roadsCv, 0, 0); ctx.drawImage(searchCv, 0, 0);
    useView(ctx);                              // 선 굵기는 줌과 상관없이 일정하게 (/view.s)
    const rs = routeSoFar();
    if (rs.length) {                           // 초록 최단경로 (진행된 만큼)
      const rp = new Path2D();
      for (const ei of rs) addEdge(rp, ei);
      ctx.lineWidth = 4 / view.s; ctx.strokeStyle = COL.route; ctx.stroke(rp);
    }
    for (const [n, c] of [[data.s, COL.start], [data.g, COL.goal]]) {   // 출발(파랑)/도착(빨강) 점
      ctx.beginPath(); ctx.arc(nx[n], ny[n], 7 / view.s, 0, Math.PI * 2);
      ctx.fillStyle = c; ctx.fill();
    }
    // 경유지: 흰 동그라미 안에 들르는 순서 번호 (글자는 화면 픽셀 기준으로 그림)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = "bold 12px Consolas, monospace"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    stops.forEach((n, i) => {
      const sx = nx[n] * view.s + view.tx, sy = ny[n] * view.s + view.ty;
      ctx.beginPath(); ctx.arc(sx, sy, 10, 0, Math.PI * 2);
      ctx.fillStyle = "#e6e6e6"; ctx.fill();
      ctx.fillStyle = "#0a0a0a"; ctx.fillText(String(i + 1), sx, sy + 1);
    });
    // 카운터 (ON ROUTE = 지나간 교차로 수 = 그린 엣지 수 + 1)
    const checked = phase === "done" ? totalChecked : checkedBefore + idx;
    el("checked").textContent = checked.toLocaleString("en-US");
    el("onroute").textContent = (rs.length ? rs.length + 1 : 0).toLocaleString("en-US");
    const f = el("final");
    if (phase === "done") {                    // 마지막 문구
      const ok = rs.length > 0;
      f.textContent = !ok ? T.final_none
        : stops.length ? T.final_tour.replace("{k}", stops.length).replace("{km}", data.km.toFixed(2))
        : T.final_ok.replace("{n}", totalChecked.toLocaleString("en-US"));
      f.style.color = ok ? "#e6e6e6" : COL.goal;
      f.style.display = "block";
    }
    el("label").style.display = phase === "done" ? "none" : "block";   // 끝나면 출발->도착 이름은 숨김
  }

  let last = performance.now();
  function loop(now) {
    if (st.stop || !canvas.isConnected) return;   // 다른 데이터로 바뀌었거나 화면에서 사라지면 멈춤
    const dt = Math.min((now - last) / (1000 / 60), 6);  // 60fps 기준 몇 프레임 지났나 (최대 6)
    last = now;
    if (!paused) step(dt);
    draw();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}
"""

_dijkstra_map = st.components.v2.component(
    "dijkstra_map", html=MAP_HTML, css=MAP_CSS, js=MAP_JS)


# ------------------------------------------------------------------
# 데이터 준비 (무거운 작업은 캐시해서 한 번만)
# ------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_roadmap():
    """도로망은 앱 전체에서 하나만 만들어 같이 쓴다."""
    return rc.load_roadmap(verbose=False)


@st.cache_resource(show_spinner=False)
def get_map_data():
    """브라우저에 넘길 지도 모양 데이터 (경로와 무관해서 한 번만 만든다)."""
    rm = get_roadmap()
    return {
        "w": float(rm.x.max()), "h": float(rm.y.max()),
        # 곡선 점들은 1m 단위 정수로 줄여서 보낸다 (데이터 크기 절약)
        "edges": [[round(c) for pt in pts for c in pt] for _, _, pts in rm.edges],
        "out": [[ei for _, _, ei in nb] for nb in rm.adj],
        "nx": [round(v, 1) for v in rm.x], "ny": [round(v, 1) for v in rm.y],
    }


@st.cache_data(max_entries=50, show_spinner=False)
def get_tour(s, stops, g):
    """출발 -> 경유지들 -> 도착 최단 순서와 구간별 탐색 기록 (같은 조합은 다시 계산 안 함)."""
    return rc.plan_tour(get_roadmap(), s, list(stops), g)


@st.cache_data(ttl=3600, max_entries=200, show_spinner=False)
def search(query, lang):
    """장소 이름 검색 (같은 검색어는 1시간 동안 다시 묻지 않음: 검색 서버 부담 줄이기)."""
    return rc.search_places(query, get_roadmap().bounds(), lang)


# ------------------------------------------------------------------
# 출발/도착 '점' 관리
# 점 = {"kind": "preset"(목록) | "search"(검색) | "click"(지도 클릭), "name", "lat", "lon"}
# ------------------------------------------------------------------
def preset_point(name):
    lat, lon = rc.PLACES[name]
    return {"kind": "preset", "name": name, "lat": lat, "lon": lon}


ss = st.session_state
ss.setdefault("start_pt", preset_point("거제시청"))
ss.setdefault("goal_pt", preset_point("바람의 언덕"))
ss.setdefault("stops", [])          # 경유지 점들 (추가한 순서대로)


def point_label(pt, lang):
    """점을 화면에 보일 이름으로 (목록 장소는 언어에 맞게, 클릭한 곳은 좌표로)."""
    if pt["kind"] == "preset":
        return rc.place_name(pt["name"], lang)
    if pt["kind"] == "click":
        return TEXT[lang]["map_point"].format(lat=pt["lat"], lon=pt["lon"])
    return pt["name"]


# 아래 함수들은 버튼/선택이 바뀔 때 화면을 다시 그리기 '전에' 불리는 처리(콜백)
def set_point(which, pt):
    """which("start"/"goal"/"stop")에 점을 넣는다. 경유지는 목록 끝에 추가 (최대 개수까지)."""
    if which == "stop":
        if len(ss.stops) < rc.MAX_STOPS:
            ss.stops = ss.stops + [pt]
        else:
            ss.stop_full = True             # 꽉 찼다는 안내를 한 번 보여 주기 위한 표시
    else:
        ss[f"{which}_pt"] = pt


def on_list(which):
    """목록에서 고르면 그 장소로 정하고, 선택 상자는 다시 비운다."""
    name = ss[f"list_{which}"]
    if name:
        set_point(which, preset_point(name))
        ss[f"list_{which}"] = None


def on_search_set(which):
    """검색 결과 중 고른 곳을 출발지/경유지/도착지로 정한다."""
    r = ss.search_res[ss.search_pick]
    set_point(which, {"kind": "search", "name": r["name"], "lat": r["lat"], "lon": r["lon"]})


def on_swap():
    ss.start_pt, ss.goal_pt = ss.goal_pt, ss.start_pt


def on_remove_stop(i):
    ss.stops = ss.stops[:i] + ss.stops[i + 1:]


def on_clear_stops():
    ss.stops = []


def on_map_pick():
    """지도에서 찍은 위치(미터 좌표)를 위경도로 바꿔 출발지/경유지/도착지로 정한다."""
    p = ss["map"].picked
    if not p:
        return
    lat, lon = get_roadmap().to_latlon(p["x"], p["y"])
    set_point(p["kind"], {"kind": "click", "name": "", "lat": lat, "lon": lon})


# ------------------------------------------------------------------
# 사이드바: 언어, 지금 출발/도착, 고르는 방법 3가지
# ------------------------------------------------------------------
names = list(rc.PLACES)
with st.sidebar:
    lang = st.segmented_control(
        "언어 / Language", list(LANGS), format_func=LANGS.get,
        default="ko", required=True, key="lang")
    T = TEXT[lang]
    st.header(T["route_header"])
    st.markdown(f":blue[●] **{T['start']}**: {point_label(ss.start_pt, lang)}  \n"
                f":red[●] **{T['goal']}**: {point_label(ss.goal_pt, lang)}")
    st.button(T["swap"], icon=":material/swap_vert:", on_click=on_swap)

    # 경유지 목록 (추가한 순서. 실제로 들르는 순서는 본문의 '최단 방문 순서'에 나옴)
    st.markdown(f"**{T['stops']}** ({len(ss.stops)}/{rc.MAX_STOPS})")
    if not ss.stops:
        st.caption(T["no_stops"])
    for i, pt in enumerate(ss.stops):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"{i + 1}. {point_label(pt, lang)}", width="stretch")
            st.button(T["remove"], key=f"rm_{i}", icon=":material/close:", type="tertiary",
                      on_click=on_remove_stop, args=(i,))
    if ss.stops:
        st.button(T["clear_stops"], icon=":material/delete_sweep:", on_click=on_clear_stops)
    if ss.pop("stop_full", False):
        st.warning(T["max_stops"].format(n=rc.MAX_STOPS), icon=":material/block:")
    st.caption(T["place_note"])

    # 1) 목록에서 고르기 (고르면 바로 적용되고 상자는 비워짐)
    st.subheader(T["pick_list"])
    for which, lbl in (("start", T["start"]), ("stop", T["list_stop"]), ("goal", T["goal"])):
        st.selectbox(lbl, names, index=None, placeholder=T["list_ph"],
                     format_func=lambda n: rc.place_name(n, lang),
                     key=f"list_{which}", on_change=on_list, args=(which,))

    # 2) 이름으로 검색
    st.subheader(T["pick_search"])
    with st.form("search_form", border=False):
        query = st.text_input(T["search_label"], placeholder=T["search_ph"])
        submitted = st.form_submit_button(T["search_btn"], icon=":material/search:")
    if submitted and query.strip():
        try:
            ss.search_res = search(query.strip(), lang)
            ss.search_q = query.strip()
        except Exception:
            ss.search_res, ss.search_q = None, None
            st.error(T["search_err"], icon=":material/wifi_off:")
    res = ss.get("search_res")
    if res:
        st.radio(T["search_result"], range(len(res)), key="search_pick",
                 format_func=lambda i: res[i]["name"],
                 captions=[r["addr"].split(", 대한민국")[0].split(", South Korea")[0] for r in res])
        with st.container(horizontal=True):
            st.button(T["set_start"], on_click=on_search_set, args=("start",))
            st.button(T["add_stop"], on_click=on_search_set, args=("stop",))
            st.button(T["set_goal"], on_click=on_search_set, args=("goal",))
    elif res == [] and ss.get("search_q"):
        st.info(T["search_none"].format(q=ss.search_q), icon=":material/search_off:")
    st.caption(T["search_note"])

    # 3) 지도에서 찍기 (실제 버튼은 지도 아래에 있음)
    st.subheader(T["pick_click"])
    st.caption(T["click_help"])

# ------------------------------------------------------------------
# 본문
# ------------------------------------------------------------------
st.title(T["title"])
st.caption(T["subtitle"])

with st.spinner(T["loading_map"]):
    rm = get_roadmap()
    map_data = get_map_data()
# 각 점에서 가장 가까운 교차로 번호
s, s_off = rm.nearest_node(ss.start_pt["lat"], ss.start_pt["lon"])
g, g_off = rm.nearest_node(ss.goal_pt["lat"], ss.goal_pt["lon"])
stop_nodes = tuple(rm.nearest_node(p["lat"], p["lon"])[0] for p in ss.stops)
no_route = s == g and not stop_nodes            # 경유지 없이 출발=도착이면 갈 길이 없음

if no_route:
    st.warning(T["same_place"], icon=":material/warning:")
    tour = {"visit": [], "km": 0.0, "km_given": 0.0,
            "legs": [{"order": [s], "route_edges": [], "on_route": 1, "km": 0.0}]}
else:
    with st.spinner(T["solving"]):
        tour = get_tour(s, stop_nodes, g)
legs = tour["legs"]
visit_nodes = [stop_nodes[i] for i in tour["visit"]]   # 경유지 교차로 (들르는 순서대로)

# 지도: 모양 데이터 + 이번 경로(구간들) + 지금 언어의 문구를 같이 넘긴다
label = f"{point_label(ss.start_pt, lang)}  →  {point_label(ss.goal_pt, lang)}"
if stop_nodes:
    label = f"{point_label(ss.start_pt, lang)}  →  ({T['stops']} {len(stop_nodes)})  →  " \
            f"{point_label(ss.goal_pt, lang)}"
_dijkstra_map(
    data={**map_data,
          "legs": [{"order": l["order"], "route_edges": l["route_edges"]} for l in legs],
          "stops": visit_nodes, "km": tour["km"], "s": s, "g": g,
          "sig": f"{s}>{','.join(map(str, stop_nodes))}>{g}",   # 경로가 바뀌었는지 브라우저가 알아보는 표시
          "t": T["map"], "label": label},
    key="map", on_picked_change=on_map_pick)
st.caption(T["osm"])

# 결과 숫자 (경유지가 있으면 모든 구간 합)
checked = sum(len(l["order"]) for l in legs)
on_route = sum(len(l["route_edges"]) for l in legs) + 1
with st.container(horizontal=True):
    st.metric(T["m_checked"], f"{checked:,}")
    st.metric(T["m_onroute"], f"{on_route:,}")
    st.metric(T["m_dist"], "-" if no_route else f"{tour['km']:.2f} km")

# 경유지가 있으면: 최단 방문 순서, 입력 순서와 비교, 구간별 거리
if stop_nodes and not no_route:
    with st.container(border=True):
        st.subheader(T["tour_header"], anchor=False)
        seq = [f":blue[●] {point_label(ss.start_pt, lang)}"]
        seq += [f"**{n + 1}.** {point_label(ss.stops[i], lang)}" for n, i in enumerate(tour["visit"])]
        seq += [f":red[●] {point_label(ss.goal_pt, lang)}"]
        st.markdown("  →  ".join(seq))
        save = tour["km_given"] - tour["km"]
        if save > 0.005:
            st.success(T["tour_given"].format(given=tour["km_given"], best=tour["km"], save=save),
                       icon=":material/savings:")
        else:
            st.info(T["tour_same"].format(best=tour["km"]), icon=":material/check_circle:")
        names_seq = [point_label(ss.start_pt, lang)] + \
                    [point_label(ss.stops[i], lang) for i in tour["visit"]] + \
                    [point_label(ss.goal_pt, lang)]
        st.dataframe(
            {T["leg_col"]: [f"{names_seq[i]} → {names_seq[i + 1]}" for i in range(len(legs))],
             T["km_col"]: [round(l["km"], 2) for l in legs]},
            hide_index=True)
        st.caption(T["tour_note"].format(cases=math.factorial(len(stop_nodes))))

col_code, col_mp4 = st.columns([3, 2])
with col_code:
    st.code(c_code(lang), language="c")         # 줄마다 주석이 달린 C 코드
    st.caption(T["offset_note"].format(s=f"{s_off:.0f}", g=f"{g_off:.0f}"))

with col_mp4:
    with st.container(border=True):
        st.subheader(T["mp4_header"])
        st.caption(T["mp4_note"])
        if st.button(T["mp4_btn"], icon=":material/movie:", disabled=no_route):
            import route_dijkstra
            out_path = Path(__file__).parent / route_dijkstra.MP4_PATH
            # 영상에 넘길 점: 좌표 + 지금 언어로 된 이름
            s_pt = {**ss.start_pt, "label": point_label(ss.start_pt, lang)}
            g_pt = {**ss.goal_pt, "label": point_label(ss.goal_pt, lang)}
            w_pts = [{**p, "label": point_label(p, lang)} for p in ss.stops]
            with st.spinner(T["mp4_busy"]):
                route_dijkstra.render_mp4(rm, s_pt, g_pt, out_path, lang, stops=w_pts)
            st.session_state.mp4 = str(out_path)
        mp4 = st.session_state.get("mp4")
        if mp4 and Path(mp4).exists():
            st.video(mp4)
            st.download_button(T["mp4_dl"], Path(mp4).read_bytes(),
                               file_name=Path(mp4).name, mime="video/mp4",
                               icon=":material/download:")

# 프로그램 소개 / 원리 / 활용 아이디어
tab_about, tab_how, tab_ideas = st.tabs(
    [f":material/info: {T['tab_about']}", f":material/school: {T['tab_how']}",
     f":material/lightbulb: {T['tab_ideas']}"])
with tab_about:
    st.markdown(T["about"])
with tab_how:
    st.markdown(T["how"])
with tab_ideas:
    st.markdown(T["ideas"])
