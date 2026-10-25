"""
animation.py
대결 결과(run_battle)를 세로 영상 프레임(PIL 이미지)으로 그린다.

화면 구성 (1080 x 1920 기준)
  위    : 제목 · 경로
  가운데: 왼쪽 다익스트라 / 오른쪽 A* 지도 패널 (같은 지도)
  아래  : 실시간 탐색 노드 수 · 간선 수 · 상태
  끝    : 결과 비교 카드와 승자

공정한 애니메이션: 두 패널 모두 '한 프레임에 같은 수의 노드'를 확장한다.
그래서 화면에서 먼저 끝나는 쪽은 실제로 더 적은 노드를 탐색한 쪽이다.
(실행 시간 ms 는 algorithms.benchmark 에서 따로 잰 값이며 애니메이션 속도와 무관하다)
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import resolve_path

BASE_W, BASE_H = 1080, 1920
LEFT_PANEL = (30, 290, 530, 1520)       # x0, y0, x1, y1 (1080x1920 기준)
RIGHT_PANEL = (550, 290, 1050, 1520)

FONT_CANDIDATES = {
    True: ["C:/Windows/Fonts/malgunbd.ttf",
           "/System/Library/Fonts/AppleSDGothicNeo.ttc",
           "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"],
    False: ["C:/Windows/Fonts/malgun.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
}


def hex_rgb(h, alpha=None):
    h = h.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return rgb if alpha is None else rgb + (int(alpha),)


def ease_out(t):
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


class Fonts:
    """글꼴 찾기. 한글 글꼴이 없으면 matplotlib 에 들어 있는 DejaVu 글꼴로 영어만 쓴다."""

    def __init__(self, style):
        self.paths = {}
        self.korean = True
        for bold, key in ((True, "font_bold"), (False, "font")):
            p = (str(resolve_path(style[key])) if style.get(key) else None) or next((c for c in FONT_CANDIDATES[bold] if Path(c).exists()), None)
            if p is None:
                import matplotlib
                name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
                p = str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name)
                self.korean = False
            self.paths[bold] = p
        self.cache = {}

    def get(self, size, bold=True):
        key = (int(size), bold)
        if key not in self.cache:
            self.cache[key] = ImageFont.truetype(self.paths[bold], max(6, int(size)))
        return self.cache[key]


def map_preview(graph, s, t, cfg):
    """대결을 돌리기 전에 지도와 출발지·목적지만 그려 본다."""
    from algorithms import SearchResult
    dummy = SearchResult("Dijkstra", True, [s, t], 0.0, 1, 0, 0)
    battle = {"dijkstra": dummy, "astar": SearchResult("A*", True, [s, t], 0.0, 1, 0, 0),
              "start_node": s, "goal_node": t}
    return BattleRenderer(graph, battle, cfg, header=False).map_image()


class BattleRenderer:
    def __init__(self, graph, battle, cfg, width=None, height=None, fps=None, header=True):
        self.g, self.b, self.cfg = graph, battle, cfg
        v = cfg["video"]
        self.W = int(width or v["width"])
        self.H = int(height or v["height"])
        self.fps = float(fps or v["fps"])
        self.sx, self.sy = self.W / BASE_W, self.H / BASE_H
        self.s = min(self.sx, self.sy)
        self.st = cfg["style"]
        self.fonts = Fonts(self.st)
        self.col = {k: hex_rgb(self.st[k]) for k in
                    ("background", "road", "road_major", "dijkstra", "astar", "path",
                     "start", "goal", "text", "muted")}

        self._timeline()
        self._project()
        self.base = self._render_base_map()
        self.pins = self._render_pins()
        self.header = self._render_header() if header else None

    # ------------------------------------------------------------ 시간표

    def _timeline(self):
        v, fps = self.cfg["video"], self.fps
        d, a = self.b["dijkstra"], self.b["astar"]
        self.intro_n = max(1, round(v["intro_sec"] * fps))
        self.path_n = max(1, round(v["path_sec"] * fps))
        self.result_n = max(1, round(v["result_sec"] * fps))
        max_exp = max(d.expanded, a.expanded)
        if v.get("nodes_per_frame"):
            self.npf = int(v["nodes_per_frame"])
            self.search_n = math.ceil(max_exp / self.npf)
        else:
            self.search_n = max(1, round(v["duration_sec"] * fps) - self.intro_n - self.path_n - self.result_n)
            self.npf = max(1, math.ceil(max_exp / self.search_n))
            self.search_n = math.ceil(max_exp / self.npf)
        self.max_exp = max_exp
        self.n_frames = self.intro_n + self.search_n + self.path_n + self.result_n
        # 각 알고리즘이 목적지에 닿는 프레임 (탐색 구간 기준)
        self.done_at = {r.algorithm: math.ceil(r.expanded / self.npf) for r in (d, a)}

    @property
    def duration_sec(self):
        return self.n_frames / self.fps

    # ------------------------------------------------------------ 좌표

    def X(self, x):
        return x * self.sx

    def Y(self, y):
        return y * self.sy

    def rect(self, r):
        return (round(self.X(r[0])), round(self.Y(r[1])), round(self.X(r[2])), round(self.Y(r[3])))

    def _project(self):
        x0, y0, x1, y1 = self.rect(LEFT_PANEL)
        self.pw, self.ph = x1 - x0, y1 - y0
        g = self.g
        gx0, gx1 = float(g.x.min()), float(g.x.max())
        gy0, gy1 = float(g.y.min()), float(g.y.max())
        pad = 12 * self.s
        k = min((self.pw - 2 * pad) / max(gx1 - gx0, 1), (self.ph - 2 * pad) / max(gy1 - gy0, 1))
        ox = (self.pw - k * (gx1 - gx0)) / 2
        oy = (self.ph - k * (gy1 - gy0)) / 2
        self._k, self._ox, self._oy, self._gx0, self._gy1 = k, ox, oy, gx0, gy1
        self.px = [ox + k * (x - gx0) for x in g.x]
        self.py = [oy + k * (gy1 - y) for y in g.y]

    def to_px(self, x, y):
        return (self._ox + self._k * (x - self._gx0), self._oy + self._k * (self._gy1 - y))

    def edge_px(self, u, v):
        if (u, v) in self.g.geom:
            return [self.to_px(x, y) for x, y in self.g.geom[(u, v)]]
        return [(self.px[u], self.py[u]), (self.px[v], self.py[v])]

    # ------------------------------------------------------------ 고정 그림

    def _render_base_map(self):
        """도로망 배경. 2배 크기로 그린 뒤 줄여서 선을 부드럽게 만든다."""
        ss = 2
        img = Image.new("RGBA", (self.pw * ss, self.ph * ss), hex_rgb(self.st["background"], 255))
        dr = ImageDraw.Draw(img)
        # 희미한 격자 (테크 분위기)
        step = int(40 * self.s * ss)
        for gx in range(0, img.width, step):
            dr.line([(gx, 0), (gx, img.height)], fill=(18, 26, 40, 255), width=1)
        for gy in range(0, img.height, step):
            dr.line([(0, gy), (img.width, gy)], fill=(18, 26, 40, 255), width=1)
        for wx0, wy0, wx1, wy1 in self.g.water:
            a = self.to_px(wx0, wy1)
            b = self.to_px(wx1, wy0)
            dr.rectangle([a[0] * ss, a[1] * ss, b[0] * ss, b[1] * ss], fill=(10, 30, 58, 255))
        minor_w = max(1, round(1.0 * self.s * ss))
        major_w = max(2, round(2.2 * self.s * ss))
        for major in (False, True):
            color = self.col["road_major"] if major else self.col["road"]
            for u, nbrs in enumerate(self.g.adj):
                for v, _ in nbrs:
                    if ((u, v) in self.g.major) != major:
                        continue
                    if v < u and any(x == u for x, _ in self.g.adj[v]):
                        continue   # 양방향 도로는 한 번만 그린다
                    pts = [(x * ss, y * ss) for x, y in self.edge_px(u, v)]
                    dr.line(pts, fill=color, width=major_w if major else minor_w)
        img = img.resize((self.pw, self.ph), Image.LANCZOS)
        return img

    def _render_pins(self):
        """출발지(초록 원) · 목적지(빨간 핀) 아이콘."""
        img = Image.new("RGBA", (self.pw, self.ph), (0, 0, 0, 0))
        glow = Image.new("RGBA", (self.pw, self.ph), (0, 0, 0, 0))
        s = self.s
        sx, sy = self.px[self.b["start_node"]], self.py[self.b["start_node"]]
        gx, gy = self.px[self.b["goal_node"]], self.py[self.b["goal_node"]]
        gd = ImageDraw.Draw(glow)
        gd.ellipse([sx - 26 * s, sy - 26 * s, sx + 26 * s, sy + 26 * s], fill=self.col["start"] + (150,))
        gd.ellipse([gx - 26 * s, gy - 46 * s, gx + 26 * s, gy + 6 * s], fill=self.col["goal"] + (150,))
        glow = glow.filter(ImageFilter.GaussianBlur(10 * s))
        img.alpha_composite(glow)
        d = ImageDraw.Draw(img)
        r = 13 * s
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=self.col["start"] + (255,), outline=(255, 255, 255, 255),
                  width=max(2, round(3 * s)))
        d.text((sx, sy), "S", font=self.fonts.get(16 * s), fill=(0, 0, 0, 255), anchor="mm")
        # 목적지 핀: 원 + 아래로 뾰족한 삼각형
        r = 15 * s
        cy = gy - 26 * s
        d.polygon([(gx - r * 0.8, cy + r * 0.5), (gx + r * 0.8, cy + r * 0.5), (gx, gy)],
                  fill=self.col["goal"] + (255,))
        d.ellipse([gx - r, cy - r, gx + r, cy + r], fill=self.col["goal"] + (255,), outline=(255, 255, 255, 255),
                  width=max(2, round(3 * s)))
        d.text((gx, cy), "G", font=self.fonts.get(17 * s), fill=(255, 255, 255, 255), anchor="mm")
        return img

    def T(self, ko, en):
        return ko if self.fonts.korean else en

    def text(self, d, xy, txt, size, fill, anchor="la", bold=True):
        d.text((self.X(xy[0]), self.Y(xy[1])), txt, font=self.fonts.get(size * self.s, bold),
               fill=fill, anchor=anchor)

    def glow_text(self, img, xy, txt, size, color, anchor="mm", radius=12, alpha=255):
        """빛나는 글자. 글자 주변만 잘라서 흐리게 처리해 빠르게 그린다."""
        if alpha <= 0:
            return
        font = self.fonts.get(size * self.s)
        x, y = self.X(xy[0]), self.Y(xy[1])
        l, t, r, b = font.getbbox(txt, anchor=anchor)
        pad = int(radius * self.s * 3) + 4
        box = (int(x + l) - pad, int(y + t) - pad, int(x + r) + pad, int(y + b) + pad)
        w, h = box[2] - box[0], box[3] - box[1]
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(glow).text((x - box[0], y - box[1]), txt, font=font, fill=color + (int(alpha),),
                                  anchor=anchor)
        crisp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(crisp).text((x - box[0], y - box[1]), txt, font=font, fill=(255, 255, 255, int(alpha)),
                                   anchor=anchor)
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(radius * self.s)), dest=box[:2])
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(radius * self.s / 3)), dest=box[:2])
        img.alpha_composite(crisp, dest=box[:2])

    def _place_label(self, key):
        p = self.cfg[key]
        if self.g.mode == "grid":
            return "START" if key == "start" else "GOAL"
        return p.get("name") if self.fonts.korean else (p.get("name_en") or p.get("name"))

    def _render_header(self):
        """제목 · 경로 · 바닥 안내 문구 (탐색 구간에 고정)."""
        img = Image.new("RGBA", (self.W, self.H), hex_rgb(self.st["background"], 255))
        d = ImageDraw.Draw(img)
        # 배경 장식: 가는 가로줄
        for y in range(0, self.H, max(2, round(4 * self.sy))):
            d.line([(0, y), (self.W, y)], fill=(9, 12, 20, 255))
        title = self.cfg["video"]["title"]
        size = 58
        while self.fonts.get(size * self.s).getlength(title) > self.W * 0.92 and size > 24:
            size -= 2
        self.glow_text(img, (540, 92), title, size, self.col["astar"], radius=16)
        d = ImageDraw.Draw(img)
        route = f"{self._place_label('start')}  →  {self._place_label('goal')}"
        self.text(d, (540, 170), route, 34, self.col["text"], "mm")
        self.text(d, (540, 222), self.cfg["video"]["subtitle"] if self.fonts.korean else
                  "Same map · same start · same goal", 24, self.col["muted"], "mm", bold=False)
        # 패널 테두리
        for r, c in ((LEFT_PANEL, self.col["dijkstra"]), (RIGHT_PANEL, self.col["astar"])):
            x0, y0, x1, y1 = self.rect(r)
            d.rectangle([x0 - 2, y0 - 2, x1 + 1, y1 + 1], outline=c + (200,), width=max(1, round(2 * self.s)))
        # 바닥 안내
        g = self.g
        info = (self.T(f"같은 속도: 프레임당 {self.npf:,}개 노드 확장  ·  교차로 {g.n_nodes:,}개",
                       f"Same speed: {self.npf:,} nodes/frame  ·  {g.n_nodes:,} intersections"))
        self.text(d, (540, 1846), info, 22, self.col["muted"], "mm", bold=False)
        self.text(d, (540, 1880), g.source, 20, self.col["muted"], "mm", bold=False)
        return img

    # ------------------------------------------------------------ 움직이는 그림

    def _new_state(self):
        mk = lambda: Image.new("RGBA", (self.pw, self.ph), (0, 0, 0, 0))
        return {name: {"trail": mk(), "step": 0, "open": set(), "edges": 0, "recent": []}
                for name in ("Dijkstra", "A*")}

    def _advance(self, state, result, upto):
        """trace 를 upto 단계까지 진행시키며 방문 흔적을 그린다."""
        stt = state[result.algorithm]
        color = self.col["dijkstra" if result.algorithm == "Dijkstra" else "astar"]
        d = ImageDraw.Draw(stt["trail"])
        w = max(1, round(1.8 * self.s))
        r = 1.6 * self.s
        stt["recent"] = []
        goal = self.b["goal_node"]
        while stt["step"] < min(upto, len(result.trace)):
            u, parent, found = result.trace[stt["step"]]
            stt["step"] += 1
            stt["open"].discard(u)
            stt["open"].update(found)
            if u != goal:
                stt["edges"] += len(self.g.adj[u])
            if parent is not None:
                d.line(self.edge_px(parent, u), fill=color + (150,), width=w)
            x, y = self.px[u], self.py[u]
            d.ellipse([x - r, y - r, x + r, y + r], fill=color + (110,))
            stt["recent"].append(u)

    def _path_points(self, result):
        if not hasattr(self, "_pp"):
            self._pp = {}
        if result.algorithm not in self._pp:
            pts = []
            for u, v in zip(result.path, result.path[1:]):
                seg = self.edge_px(u, v)
                pts.extend(seg if not pts else seg[1:])
            cum = [0.0]
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
            self._pp[result.algorithm] = (pts, cum)
        return self._pp[result.algorithm]

    def _partial_path(self, result, frac):
        pts, cum = self._path_points(result)
        if frac >= 1:
            return pts
        target = cum[-1] * frac
        out = [pts[0]]
        for i in range(1, len(pts)):
            if cum[i] <= target:
                out.append(pts[i])
            else:
                seg = cum[i] - cum[i - 1]
                t = (target - cum[i - 1]) / seg if seg else 0
                out.append((pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]),
                            pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1])))
                break
        return out

    def _panel(self, state, result, search_frame, intro_t=None):
        """패널 하나의 현재 모습."""
        img = self.base.copy()
        name = result.algorithm
        stt = state[name]
        color = self.col["dijkstra" if name == "Dijkstra" else "astar"]
        if intro_t is None:
            img.alpha_composite(stt["trail"])
            d = ImageDraw.Draw(img)
            done = stt["step"] >= len(result.trace)
            if not done:
                r = 2.6 * self.s
                for v in stt["open"]:                       # 탐색 중(큐에 있는) 노드
                    x, y = self.px[v], self.py[v]
                    d.ellipse([x - r, y - r, x + r, y + r], fill=color + (255,))
                r = 3.2 * self.s
                for v in stt["recent"][-60:]:                # 방금 확장한 노드
                    x, y = self.px[v], self.py[v]
                    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 230))
            else:
                since = search_frame - self.done_at[name]
                frac = ease_out(since / self.path_n)
                pts = self._partial_path(result, frac)
                if len(pts) >= 2:
                    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
                    ld = ImageDraw.Draw(layer)
                    pc = self.col["path"]
                    ld.line(pts, fill=pc + (90,), width=max(4, round(14 * self.s)), joint="curve")
                    ld.line(pts, fill=pc + (170,), width=max(3, round(8 * self.s)), joint="curve")
                    ld.line(pts, fill=(255, 255, 230, 255), width=max(2, round(3 * self.s)), joint="curve")
                    img.alpha_composite(layer)
        img.alpha_composite(self.pins)
        if intro_t is not None:
            # 인트로: 지도가 서서히 밝아진다
            dark = Image.new("RGBA", img.size, (0, 0, 0, int(200 * (1 - ease_out(intro_t * 1.5)))))
            img.alpha_composite(dark)
        # 패널 이름표
        d = ImageDraw.Draw(img)
        label = "DIJKSTRA" if name == "Dijkstra" else "A* (A-STAR)"
        f = self.fonts.get(30 * self.s)
        tw = f.getlength(label)
        d.rounded_rectangle([10 * self.s, 10 * self.s, 10 * self.s + tw + 28 * self.s, 56 * self.s],
                            radius=10 * self.s, fill=(0, 0, 0, 190), outline=color + (255,),
                            width=max(1, round(2 * self.s)))
        d.text((24 * self.s, 33 * self.s), label, font=f, fill=color + (255,), anchor="lm")
        return img.convert("RGB")

    def _hud(self, img, state, search_frame, blink):
        d = ImageDraw.Draw(img)
        for res, rect in ((self.b["dijkstra"], LEFT_PANEL), (self.b["astar"], RIGHT_PANEL)):
            name = res.algorithm
            stt = state[name]
            color = self.col["dijkstra" if name == "Dijkstra" else "astar"]
            x0 = rect[0] + 6
            self.text(d, (x0, 1548), self.T("탐색 노드  EXPLORED", "EXPLORED NODES"), 22,
                      self.col["muted"], bold=False)
            self.text(d, (x0, 1578), f"{stt['step']:,}", 66, color)
            self.text(d, (x0, 1668), self.T(f"살펴본 간선 {stt['edges']:,}", f"edges scanned {stt['edges']:,}"),
                      24, self.col["text"], bold=False)
            done = stt["step"] >= len(res.trace)
            if done:
                km = self.b["path_km"][name]
                self.text(d, (x0, 1712), self.T(f"● 도착  {km:.2f} km", f"● REACHED  {km:.2f} km"), 30,
                          self.col["path"])
            elif blink:
                self.text(d, (x0, 1712), self.T("탐색 중 ▶", "SEARCHING ▶"), 30, self.col["text"])
            # 같은 눈금(더 많이 탐색한 쪽 기준)의 진행 막대
            bx0, bx1 = self.X(x0), self.X(rect[2] - 6)
            by0, by1 = self.Y(1768), self.Y(1786)
            d.rounded_rectangle([bx0, by0, bx1, by1], radius=4 * self.s, fill=(20, 28, 44))
            frac = stt["step"] / self.max_exp
            if frac > 0:
                d.rounded_rectangle([bx0, by0, bx0 + (bx1 - bx0) * frac, by1], radius=4 * self.s, fill=color)

    # ------------------------------------------------------------ 인트로 / 결과

    def _intro(self, i):
        t = i / self.intro_n
        state = self._new_state()
        img = self.header.copy()
        for res, rect in ((self.b["dijkstra"], LEFT_PANEL), (self.b["astar"], RIGHT_PANEL)):
            img.paste(self._panel(state, res, 0, intro_t=t), self.rect(rect)[:2])
        # 큰 VS
        a = ease_out(t * 2.5)
        pulse = 1 + 0.06 * math.sin(t * math.pi * 6)
        self.glow_text(img, (540, 905), "VS", 150 * pulse * (0.6 + 0.4 * a), self.col["path"],
                       radius=20, alpha=255 * a)
        d = ImageDraw.Draw(img)
        self.text(d, (285, 1600), "DIJKSTRA", 52, self.col["dijkstra"], "mm")
        self.text(d, (800, 1600), "A*", 60, self.col["astar"], "mm")
        self.text(d, (285, 1660), self.T("모든 방향을 고르게", "explores evenly"), 26, self.col["muted"], "mm", False)
        self.text(d, (800, 1660), self.T("목적지 방향을 먼저", "heads to the goal"), 26, self.col["muted"], "mm", False)
        left = self.intro_n - i
        if left <= self.fps * 0.8:
            self.glow_text(img, (540, 1745), "GO!", 80, self.col["start"], radius=14)
        return img

    def _result(self, state, k):
        """결과 카드. k = 결과 구간 안의 프레임 번호."""
        t = k / self.fps
        img = self.header.copy()
        last = self.search_n + self.path_n
        for res, rect in ((self.b["dijkstra"], LEFT_PANEL), (self.b["astar"], RIGHT_PANEL)):
            img.paste(self._panel(state, res, last), self.rect(rect)[:2])
        img = img.convert("RGB")
        self._hud(img, state, last, blink=False)
        img = img.convert("RGBA")
        fade = ease_out(t / 0.5)
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle([0, self.Y(270), self.W, self.Y(1530)], fill=(0, 0, 0, int(150 * fade)))
        cx0, cy0, cx1, cy1 = self.rect((60, 400, 1020, 1480))
        od.rounded_rectangle([cx0, cy0, cx1, cy1], radius=28 * self.s, fill=(8, 14, 26, int(240 * fade)),
                             outline=self.col["path"] + (int(255 * fade),), width=max(2, round(3 * self.s)))
        img.alpha_composite(ov)
        # 글자·상자는 투명 레이어에 그린 뒤 합성해야 서서히 나타나는 효과가 산다
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        al = int(255 * fade)
        self.text(d, (540, 455), self.T("결과  RESULT", "RESULT"), 42, self.col["text"] + (al,), "mm")
        self.text(d, (640, 540), "DIJKSTRA", 34, self.col["dijkstra"] + (al,), "mm")
        self.text(d, (880, 540), "A*", 40, self.col["astar"] + (al,), "mm")

        verdict = self.b["verdict"]
        reps = self.cfg["benchmark"]["repeats"]
        labels = {
            "expanded": (self.T("탐색 노드 수", "Explored nodes"), self.T("확장한 고유 노드", "unique expanded")),
            "cost": (self.T("경로 길이", "Path length"), self.T("도로 간선 길이 합", "sum of road edges")),
            "time": (self.T("실행 시간", "Run time"), self.T(f"{reps}회 중앙값·렌더링 제외",
                                                           f"median of {reps}, no rendering")),
        }
        fmt = {"expanded": lambda v: f"{v:,}", "cost": lambda v: f"{v:.2f} km", "time": lambda v: f"{v:.2f} ms"}
        rows = {r["key"]: r for r in verdict["rows"]}
        for idx, key in enumerate(("expanded", "cost", "time")):
            ra = ease_out((t - 0.4 - idx * 0.35) / 0.4)
            if ra <= 0:
                continue
            r = rows[key]
            y = 640 + idx * 135
            a = int(255 * ra)
            self.text(d, (105, y - 14), labels[key][0], 34, self.col["text"] + (a,), "lm")
            self.text(d, (105, y + 28), labels[key][1], 20, self.col["muted"] + (a,), "lm", False)
            for name, cx, val in (("Dijkstra", 640, r["dijkstra"]), ("A*", 880, r["astar"])):
                c = self.col["dijkstra" if name == "Dijkstra" else "astar"]
                if r["winner"] == name:
                    bx = self.rect((cx - 115, y - 50, cx + 115, y + 50))
                    d.rounded_rectangle(bx, radius=16 * self.s, fill=c + (int(60 * ra),),
                                        outline=c + (a,), width=max(1, round(2 * self.s)))
                    self.text(d, (cx, y + 34), "WIN", 18, c + (a,), "mm")
                elif r["winner"] == "tie":
                    self.text(d, (cx, y + 34), self.T("동점", "TIE"), 18, self.col["muted"] + (a,), "mm")
                self.text(d, (cx, y - 6), fmt[key](val), 38, (255, 255, 255, a), "mm")

        ra = ease_out((t - 1.6) / 0.5)
        if ra > 0:
            a = int(255 * ra)
            dd, aa = self.b["dijkstra"].expanded, self.b["astar"].expanded
            if dd != aa:
                fewer, more = ("A*", "Dijkstra") if aa < dd else ("Dijkstra", "A*")
                pct = (1 - min(dd, aa) / max(dd, aa)) * 100
                line = self.T(f"{fewer} 가 노드를 {pct:.0f}% 덜 탐색 ({abs(dd - aa):,}개 차이)",
                              f"{fewer} explored {pct:.0f}% fewer nodes ({abs(dd - aa):,})")
            else:
                line = self.T("두 알고리즘의 탐색 노드 수가 같음", "Same number of explored nodes")
            self.text(d, (540, 1050), line, 28, self.col["path"] + (a,), "mm")
            opt = self.b["optimal"]
            ok = all(opt.values())
            line = (self.T("● 두 경로 모두 최단 경로 (networkx 로 검증)", "● Both paths optimal (verified)")
                    if ok else self.T("주의: 최단 경로가 아닌 결과가 있음", "Warning: non-optimal result"))
            self.text(d, (540, 1095), line, 24, (self.col["start"] if ok else self.col["goal"]) + (a,), "mm", False)

        ra = ease_out((t - 2.3) / 0.5)
        win_label = None
        if ra > 0:
            win = verdict["winner"]
            sc = verdict["score"]
            ties = 3 - sc["Dijkstra"] - sc["A*"]
            self.text(d, (540, 1170), "WINNER", 32, self.col["muted"] + (int(255 * ra),), "mm")
            wc = (self.col["dijkstra"] if win == "Dijkstra" else self.col["astar"] if win == "A*"
                  else self.col["text"])
            label = {"Dijkstra": "DIJKSTRA", "A*": "A*", "DRAW": self.T("무승부", "DRAW")}[win]
            pulse = 1 + 0.03 * math.sin(t * 5)
            win_label = (label, 104 * (0.7 + 0.3 * ra) * pulse, wc, 255 * ra)
            score = self.T(f"다익스트라 {sc['Dijkstra']} : {sc['A*']} A*" + (f"   (무승부 {ties})" if ties else ""),
                           f"Dijkstra {sc['Dijkstra']} : {sc['A*']} A*" + (f"   ({ties} tie)" if ties else ""))
            self.text(d, (540, 1350), score, 30, self.col["text"] + (int(255 * ra),), "mm")
            self.text(d, (540, 1408), self.cfg["video"]["disclaimer"] if self.fonts.korean else
                      "* Run time depends on your PC and environment", 21, self.col["muted"] + (int(255 * ra),),
                      "mm", False)
        img.alpha_composite(lay)
        if win_label:
            label, size, wc, alpha = win_label
            self.glow_text(img, (540, 1255), label, size, wc, radius=22, alpha=alpha)
        return img.convert("RGB")

    # ------------------------------------------------------------ 전체 프레임

    def iter_frames(self, only=None):
        """(프레임 번호, 이미지) 를 차례로 돌려준다. only 를 주면 그 번호들만 그린다 (상태는 계속 진행)."""
        only = None if only is None else set(only)
        for i in range(self.intro_n):
            if only is None or i in only:
                yield i, self._intro(i).convert("RGB")
        state = self._new_state()
        d, a = self.b["dijkstra"], self.b["astar"]
        for k in range(self.search_n + self.path_n):
            i = self.intro_n + k
            upto = (k + 1) * self.npf
            self._advance(state, d, upto)
            self._advance(state, a, upto)
            if only is not None and i not in only:
                continue
            img = self.header.copy()
            for res, rect in ((d, LEFT_PANEL), (a, RIGHT_PANEL)):
                img.paste(self._panel(state, res, k + 1), self.rect(rect)[:2])
            img = img.convert("RGB")
            self._hud(img, state, k, blink=(k // max(1, int(self.fps / 3))) % 2 == 0)
            yield i, img
        base = self.intro_n + self.search_n + self.path_n
        for k in range(self.result_n):
            i = base + k
            if only is None or i in only:
                yield i, self._result(state, k)
            if only is not None and i >= max(only):
                return

    def map_image(self):
        """출발지·목적지가 표시된 지도 한 장 (설정 확인용)."""
        img = self.base.copy()
        img.alpha_composite(self.pins)
        return img.convert("RGB")

    def key_frames(self):
        """미리보기용 대표 장면 4개: 인트로, 탐색 중, 경로 표시, 결과."""
        picks = {
            "인트로": self.intro_n // 2,
            "탐색 중": self.intro_n + self.done_at["A*"] // 2 + self.search_n // 4,
            "경로 표시": self.intro_n + self.search_n + self.path_n - 1,
            "결과": self.n_frames - 1,
        }
        picks = {k: min(v, self.n_frames - 1) for k, v in picks.items()}
        got = dict(self.iter_frames(only=picks.values()))
        return {k: got[v] for k, v in picks.items()}
