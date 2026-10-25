# Seoul Pathfinding Battle — 다익스트라 vs A* 서울 탈출

서울 도로망 위에서 **다익스트라(Dijkstra)** 와 **A\*** 가 같은 출발지에서 같은 목적지까지 길을 찾는 과정을
좌우 분할 화면으로 동시에 보여 주고, YouTube Shorts · Instagram Reels 용 **세로 MP4(1080×1920, 30fps)** 로 저장하는 도구입니다.

- 지도: OpenStreetMap 서울 도로망 (OSMnx 로 받아 `maps/` 에 저장), 또는 인터넷 없이 쓰는 **가상 격자 도시**
- 지표: 탐색 노드 수 · 경로 길이(km) · 실행 시간(ms) — 모두 실제 계산값
- 화면: Streamlit 웹 화면 또는 명령줄 한 줄

---

## 1. 설치

Python 3.11 이상이 필요합니다.

```bash
cd seoul-pathfinding-battle
python -m pip install -r requirements.txt
```

- FFmpeg 는 따로 설치하지 않아도 됩니다. 시스템에 `ffmpeg` 가 있으면 그것을, 없으면 `imageio-ffmpeg` 에 들어 있는 FFmpeg 를 씁니다.
- 지도 API 키나 유료 서비스는 필요 없습니다.

## 2. 실행 (화면)

```bash
python -m streamlit run app.py
```

(`streamlit run app.py` 로 쳤을 때 "내부 또는 외부 명령이 아닙니다" 오류가 나면 위처럼 `python -m` 을 붙이세요. Streamlit 실행 파일이 PATH 에 없을 때 생기는 문제입니다.)

브라우저가 열리면(안 열리면 http://localhost:8501) 다음 순서로 씁니다.

| 탭 | 하는 일 |
|---|---|
| 사이드바 | 지도 종류(서울/가상 격자), 출발지·목적지(목록 또는 위경도), 영상 제목·길이·속도, 색상·글꼴, 출력 폴더. **적용** 후 *config.json 저장* 으로 남길 수 있음 |
| 지도·경로 | *지도 불러오기* → 지도 영역, 출발지(S)·목적지(G), 노드·간선 수 확인 |
| 배틀 실행 | *배틀 시작* → 두 알고리즘 실행 + 시간 측정 + 최적성 검증 |
| 비교 지표 | 세 지표, 지표별 승자, 종합 승자, 측정 원자료, 결과 JSON 받기 |
| 영상 미리보기 | 대표 장면 4개, 540×960 저해상도 미리보기 영상 |
| MP4 생성 | 1080×1920 MP4 만들기, 재생, 받기 |
| 사용 안내 | 간단한 설명 |

## 3. MP4 만들기 (명령줄)

```bash
python video_export.py            # config.json 설정대로 (기본: 서울 도로망)
python video_export.py --grid     # 가상 격자 지도 (인터넷 불필요)
python video_export.py --preview  # 540x960 빠른 미리보기
python video_export.py --out output/my_video.mp4
```

결과는 `output/` 에 저장됩니다.

- `battle_seoul_YYYYMMDD_HHMMSS.mp4` — 영상
- 같은 이름의 `.json` — 설정값, 그래프 정보, 출발·목적 노드, 세 지표, 시간 측정 원자료, 판정, PC 정보 (같은 조건 재실행·검증용)

영상 구성: **인트로**(제목, VS, 출발지→목적지) → **탐색 애니메이션**(좌: 다익스트라, 우: A\*) → **최종 경로 강조** → **결과 비교와 승자**.

## 4. 설정 파일 `config.json`

바꾸고 싶은 값만 고쳐도 됩니다(빠진 값은 `config.py` 의 기본값 사용).

| 항목 | 뜻 |
|---|---|
| `map_mode` | `"seoul"` 또는 `"grid"` |
| `start`, `goal` | `name`, `name_en`, `lat`, `lon`. 가장 가까운 도로 교차로로 자동으로 맞춤 (1.5km 넘게 떨어지면 오류) |
| `seoul_map.margin_km` | 출발지·목적지 둘레 여유(km) |
| `seoul_map.bbox` | 직접 영역 지정 `[서쪽 경도, 남쪽 위도, 동쪽 경도, 북쪽 위도]` |
| `seoul_map.network_type` | `drive`(기본) / `walk` / `bike` |
| `seoul_map.overpass_url` | OSM 데이터 서버 주소 (비우면 기본 서버). 서버가 붐빌 때 바꿈 |
| `grid_map.*` | 가상 도시 크기, 끊긴 길·일방통행 비율, 강·다리 수, 난수 씨앗, 출발·목적 위치 |
| `benchmark.repeats` | 실행 시간 측정 반복 횟수 (중앙값 사용) |
| `benchmark.time_tie_percent` | 시간 차이가 이 % 이내면 무승부 |
| `video.title`, `video.subtitle` | 영상 제목·부제 |
| `video.duration_sec` | 전체 길이(초). `nodes_per_frame` 이 0 이면 이 길이에 맞춰 속도를 자동 계산 |
| `video.nodes_per_frame` | 애니메이션 속도 (프레임당 확장 노드 수). 0 이 아니면 길이가 이 값에 따라 정해짐 |
| `video.intro_sec`, `path_sec`, `result_sec` | 구간 길이 |
| `video.width`, `height`, `fps`, `crf` | 해상도, 프레임 속도, 화질(낮을수록 고화질) |
| `video.output_dir`, `filename` | 저장 폴더, 파일 이름(비우면 날짜·시간) |
| `style.*` | 색상(배경, 도로, 다익스트라, A\*, 경로, 출발, 도착, 글자), 글꼴 파일 경로 |

## 5. 정확성과 공정성

- **같은 조건**: 두 알고리즘은 같은 인접 리스트, 같은 간선 비용(도로 길이 m), 같은 우선순위 큐(heapq), 같은 동점 처리 규칙을 씁니다. 차이는 A\* 의 휴리스틱 하나뿐입니다.
- **휴리스틱**: 목적지까지의 대원(직선) 거리(m). OSMnx 의 도로 길이는 같은 지구 반지름(6,371,009m)으로 잰 조각 길이의 합이므로 휴리스틱은 실제 도로 거리를 넘지 않습니다(허용적·일관적) → 최적 경로 보장. 부동소수점 오차 대비로 `1 - 1e-9` 배를 곱합니다.
- **방향성**: OSM 일방통행 정보를 반영한 방향 그래프를 씁니다. 들어가면 나올 수 없는 구역은 '강한 연결 최대 덩어리'만 남겨 제거합니다. 평행 간선은 가장 짧은 것을 씁니다.
- **경로 길이**: 직선 거리가 아니라 선택된 경로의 실제 도로 간선 길이 합입니다.
- **검증**: 매 배틀마다 networkx 의 다익스트라로 최단 거리를 따로 구해 두 결과가 최적인지 확인하고 화면에 표시합니다.
- **실행 시간**: 애니메이션 기록이 없는 순수 계산 함수로 측정합니다. 예열 1회 후 `repeats` 회, 매 회 실행 순서를 번갈아 바꾸고 GC 를 끈 채 `perf_counter_ns` 로 재며 **중앙값**을 씁니다. 렌더링·인코딩 시간은 포함하지 않습니다. A\* 의 휴리스틱 준비·계산 시간은 A\* 시간에 포함합니다. **PC 성능·실행 환경에 따라 달라집니다.**
- **애니메이션 속도**: 양쪽이 **프레임당 같은 수의 노드**를 확장하므로, 화면에서 먼저 끝나는 쪽이 실제로 적게 탐색한 쪽입니다. 애니메이션 속도는 ms 측정과 무관합니다.
- **지표 정의**
  - 탐색 노드 수: 큐에서 꺼내 확정(확장)한 고유 노드 수 (목적지 포함)
  - 살펴본 간선 수: 확장한 노드에서 검사한 나가는 간선 수
  - 경로 길이(km), 실행 시간(ms, 중앙값), 목적지 도달 여부, 최적 경로 여부, 탐색 노드 수 차이
- **승자 판정**: 경로 길이(짧을수록, 0.1m 이내는 동점) · 탐색 노드 수(적을수록) · 실행 시간(짧을수록, 기본 10% 이내 무승부)을 각각 비교해 1점씩. 점수가 높은 쪽이 승자, 같으면 무승부. 실행 시간만으로 정하지 않습니다.
- 경로가 없거나 좌표가 지도 밖이면 이유를 알려 주는 오류 메시지를 보여 줍니다. 결과를 조작하거나 가짜 수치를 넣지 않습니다.

## 6. 테스트

```bash
python -m pytest -q tests
```

- 격자·무작위 위경도 그래프에서 두 알고리즘이 networkx 와 같은 최단 거리를 내는지
- 휴리스틱이 허용적인지, 일방통행을 지키는지, 경로가 없을 때 명확한 오류가 나는지
- 기록 실행과 측정 실행이 같은 탐색을 하는지, 판정 규칙
- 설정 파일 병합·검증, 영상 시간표, 대표 장면, 짧은 MP4 인코딩
- Streamlit 앱 실행과 격자 배틀 흐름 (AppTest)
- 서울 지도가 `maps/` 에 저장되어 있으면 서울 배틀의 최적성·방향성 (없으면 건너뜀)

## 7. 폴더 구성

```
seoul-pathfinding-battle/
├── app.py            Streamlit 화면
├── config.py         기본 설정, config.json 읽기·저장·검증
├── config.json       사용자 설정
├── map_loader.py     서울 도로망(OSMnx) 받기·캐시, 가상 격자 도시, 공통 그래프 형식
├── algorithms.py     다익스트라, A*, 시간 측정, 최적성 검증, 승자 판정, 결과 기록
├── animation.py      프레임 그리기 (Pillow): 인트로, 좌우 탐색, 경로, 결과 카드
├── video_export.py   FFmpeg 로 MP4 저장, 명령줄 실행
├── requirements.txt
├── assets/           (선택) 직접 쓸 글꼴 등
├── maps/             받은 서울 도로망 캐시 (.graphml)
├── output/           만든 영상과 결과 JSON
└── tests/            pytest 테스트
```

## 8. 지도 데이터 출처와 이용 조건

- 도로망 데이터: **© OpenStreetMap contributors**, [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
  - 사용·수정·공유가 자유롭지만 **출처 표시**가 필요합니다. 영상 아래쪽에 `Map data © OpenStreetMap contributors (ODbL)` 문구가 자동으로 들어갑니다. 영상 설명란에도 같은 문구를 적어 두는 것을 권장합니다.
  - 자세한 내용: https://www.openstreetmap.org/copyright
- 데이터는 OSMnx 가 공개 Overpass API(기본 `overpass-api.de`)에서 받습니다. 공개 서버이므로 과도한 반복 요청을 피하세요. 한 번 받은 지도는 `maps/` 에 저장되어 다시 받지 않습니다.
- 가상 격자 모드는 외부 데이터를 쓰지 않습니다.
- 글꼴: 시스템 글꼴(Windows 맑은 고딕 등)을 사용하며 프로젝트에 포함하지 않습니다. 다른 글꼴을 쓰려면 라이선스가 허용하는 글꼴 파일 경로를 `style.font_bold` 에 넣으세요. 한글 글꼴이 없으면 영어 문구로 바뀝니다.
- 사용한 라이브러리: OSMnx(MIT), NetworkX(BSD-3), NumPy(BSD-3), Pillow(MIT-CMU), Matplotlib(PSF 기반), Streamlit(Apache-2.0), imageio-ffmpeg(BSD-2, FFmpeg 은 LGPL/GPL).

## 9. 문제 해결

| 증상 | 해결 |
|---|---|
| `도로망을 받지 못했습니다` | 공개 Overpass 서버가 자주 붐빕니다. 잠시 뒤 다시 시도(자동 3회 재시도), `seoul_map.overpass_url` 변경, 또는 `map_mode: "grid"` |
| `가장 가까운 도로가 ...m 떨어져 있습니다` | 좌표가 지도 영역 밖. 좌표 확인 또는 `margin_km` 늘리기 |
| `경로가 없습니다` | 일방통행·끊긴 도로 때문. 출발/목적지 변경 또는 영역 넓히기 |
| 한글이 네모로 나옴 | `style.font_bold` 에 한글 글꼴(.ttf/.ttc) 경로 지정 |
| 영상이 너무 빠르거나 느림 | `video.duration_sec` 조정, 또는 `video.nodes_per_frame` 직접 지정 |
