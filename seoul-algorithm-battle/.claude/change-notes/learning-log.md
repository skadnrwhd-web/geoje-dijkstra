# 변경 학습 기록


---
## 15:12 · sample-map.json, map.js, algorithms.js, metrics.js, animation.js, game-settings.json, recorder.js, server.js, export.js, index.html, style.css, app.js, launch.json, algorithms.test.js, server.test.js, README.md, seoul-escape-project.md, MEMORY.md

### sample-map.json (새 파일)
**한 줄 요약**: 서울을 본뜬 가상 도시의 크기, 난이도, 강, 다리, 산, 구 이름, 장소, 출발·도착 시나리오를 적어 둔 설정 파일입니다.
**왜 바꿨나**: 설명에 따르면 코드를 몰라도 지도와 장소를 고칠 수 있게 하려는 목적입니다. JSON(데이터를 적는 글 형식) 파일로 분리한 구체적인 이유는 자료에서 확인되지 않음.
**줄별 설명**
- `"disclaimer": "서울을 모티브로 한 가상 도로망 · 실제 지도 아님"` → 실제 지도가 아니라는 안내 문구입니다.
- `"width": 24, "height": 15` → 가상 도시의 가로·세로 크기입니다(단위는 가상 km).
- `"seed": 20261025` → 난수(무작위 숫자)의 시작값입니다. 같은 값이면 같은 도시가 만들어집니다.
- `"difficulties": { easy, normal, hard }` → 난이도별 설정입니다. `cols`·`rows`는 교차로의 가로·세로 개수라서 어려울수록 도로가 촘촘합니다. `missingRoadChance`는 도로가 빠질 확률, `blockedRoadChance`는 막힐 확률, `constructionZones`는 공사 구역 수입니다.
- `"river"` → 한강(가상)의 폭과 흐르는 길(좌표 점들)입니다.
- `"bridges"` → 강을 건널 수 있는 다리 8개의 이름과 가로 위치입니다.
- `"obstacles"` → 북한산, 남산 같은 산입니다. `r`은 반지름으로, 이 안으로는 길이 생기지 않습니다.
- `"districts"` → 지도에 글자로 표시할 구 이름과 위치입니다.
- `"places"` → 출발·도착이 될 수 있는 장소(홍대입구, 잠실 등)입니다. `id`는 시나리오에서 장소를 가리키는 이름표입니다.
- `"scenarios"` → "홍대입구 → 잠실"처럼 미리 정해 둔 경로 5개입니다.

---

### map.js (새 파일)
**한 줄 요약**: 설정 파일을 읽어 가상 도시의 도로망(교차로와 도로)을 만드는 모듈입니다.
**왜 바꿨나**: 설명에 따르면 나중에 실제 도로망으로 바꿀 수 있게 게임 로직과 분리해 만들었습니다.
**줄별 설명**
- `export function mulberry32(seed)` → 시드를 받아 난수를 만들어 주는 함수입니다. 같은 시드면 항상 같은 숫자가 나와서 결과를 재현할 수 있습니다.
- `function hashString(s)` → 글자를 숫자로 바꿉니다. 난이도 이름 등으로 시드를 섞을 때 씁니다.
- `export function distance(ax, ay, bx, by)` → 두 점 사이의 직선거리를 구합니다.
- `function segmentPointDistance(...)` → 도로(선분)와 한 점(산의 중심) 사이의 가장 짧은 거리를 구합니다. 도로가 산을 지나는지 확인할 때 쓰는 것으로 보입니다.
- `export function riverYAt(river, x)` → 가로 위치 x에서 강이 세로 어디쯤 있는지 두 점 사이를 이어서 계산합니다.
- `export function generateCity(config, options = {})` → 설정과 난이도를 받아 도시를 만드는 핵심 함수입니다.
- `if (!diff) throw new Error(...)` → 없는 난이도면 오류를 내며 멈춥니다.
- `const dx = (W - 2 * margin) / (cols - 1);` → 교차로 사이의 가로 간격입니다. 세로 간격 `dy`도 같은 방식입니다.
- `layoutRng`, `obstacleRng` → 난수 생성기 두 개입니다. 하나는 도시 배치용, 하나는 공사 구역용입니다. 그래서 장애물만 따로 바꿀 수 있습니다.
- `while (construction.length < diff.constructionZones && guard++ < 500)` → 공사 구역을 필요한 개수만큼 만듭니다. 최대 500번 시도하여 무한 반복을 막습니다.
- `if (Math.abs(y - riverYAt(river, x)) < riverHalf + r) continue;` → 강 위에는 공사 구역을 놓지 않습니다.
- `nearPlace`, `nearOther` → 주요 장소나 다른 장애물과 너무 가까우면 건너뜁니다.
- `const side = ...` → 어떤 점이 강의 위쪽인지 아래쪽인지 알려 줍니다.
- `insideObstacle`, `crossesObstacle` → 점이 장애물 안에 있는지, 도로가 장애물을 가로지르는지 검사합니다.
- `// 1) 교차로 배치 (격자 + 흔들림)` → 격자 모양으로 교차로를 놓고 약간 흔들어 자연스럽게 만듭니다.

(이후 코드는 자료에서 생략되어 설명하지 않습니다.)

---

### algorithms.js (새 파일)
**한 줄 요약**: 다익스트라와 A* 길찾기 알고리즘을 화면 코드와 분리해 구현한 파일입니다.
**왜 바꿨나**: 설명에 따르면 두 알고리즘이 같은 지도·출발·도착·비용으로 공정하게 비교되도록 하려는 것입니다.
**줄별 설명**
- `export class MinHeap` → 가장 작은 값을 빨리 꺼내는 대기열(우선순위 큐)입니다. 다음에 탐색할 후보를 고를 때 씁니다.
- `function less(x, y)` → 값이 같으면 `tie`, 그다음 들어온 순서로 비교합니다. 그래서 결과가 항상 같습니다.
- `function bestFirstSearch(...)` → 두 알고리즘이 함께 쓰는 탐색 본체입니다.
- `const g = new Float64Array(n).fill(Infinity)` → 출발점에서 각 지점까지의 최소 비용 기록표입니다. 처음에는 모두 무한대입니다.
- `const parent = ...` → 각 지점에 어디서 왔는지 적어 둡니다. 나중에 경로를 거꾸로 찾는 데 씁니다.
- `if (closed[u]) continue;` → 이미 확정한 지점이면 건너뜁니다.
- `expandedOrder.push(u)` → 탐색한 순서를 기록합니다. 애니메이션에 쓰입니다.
- `if (u === goal) { reached = true; break; }` → 목적지에 닿으면 멈춥니다.
- `if (nd < g[to])` → 더 짧은 길을 찾았을 때만 기록을 갱신합니다.
- `for (let v = goal; v !== -1; v = parent[v]) path.push(v); path.reverse();` → 목적지에서 거꾸로 따라가 경로를 만든 뒤 뒤집습니다.
- `dijkstra` → 휴리스틱(목적지까지의 예상 거리)을 0으로 줍니다.
- `astar` → 휴리스틱을 목적지까지의 직선거리 × `heuristicScale`로 줍니다. 주석에 따르면 이렇게 하면 최적 경로가 보장됩니다.

---

### metrics.js (새 파일)
**한 줄 요약**: 탐색 노드 수, 경로 길이, 실행 시간을 계산하고 비교 문장을 만드는 파일입니다.
**왜 바꿨나**: 설명에 따르면 실행 시간에 그리기 시간이 섞이지 않게 하고, 작은 차이를 과장하지 않기 위해서입니다.
**줄별 설명**
- `runRace(...)` → 두 알고리즘을 한 번씩 실행해 기록을 얻고, 따로 반복 실행하여 평균 시간을 잽니다.
- `for (let i = 0; i < 3; i++) {...}` → 본 측정 전에 몇 번 미리 돌리는 워밍업입니다.
- `while (runs < maxRuns && (runs < 10 || now() - begin < budgetMs))` → 최소 10번, 최대 2000번, 약 60ms 동안 반복합니다.
- `buildMetrics` → 방문한 노드 수와 경로 길이 등을 묶습니다.
- `computePathLength` → 경로의 도로 비용을 다시 더합니다. 없는 도로가 있으면 오류를 냅니다.
- `formatDistance`, `formatMs` → 숫자를 "22.79 가상 km", "µs" 같은 읽기 쉬운 글자로 바꿉니다.
- `compareMetrics` → "A*가 N% 적게 탐색" 같은 문장을 만듭니다. 시간 차이가 0.02ms 미만이거나 1.15배 미만이면 "비슷함"으로 표시합니다.
- `lines.headline = ... 'A* WINS' ...` → 탐색 노드가 더 적은 쪽을 승자로 표시합니다.


---
## 16:05 · real-map-config.json, osm.js, map.js, fetch-seoul-map.js, animation.js, recorder.js, index.html, style.css, osm.test.js, app.js, README.md, seoul-escape-project.md, MEMORY.md

### real-map-config.json (새 파일)
**한 줄 요약**: 실제 서울 지도를 내려받을 범위, 도로 종류, 난이도, 장소, 경주 코스를 적어 둔 설정 파일입니다.
**왜 바꿨나**: 작업 설명에 "범위·장소·경로 목록은 이 파일에서 바꾼다"고 되어 있어, 코드를 건드리지 않고 설정만 고치게 하려는 것으로 보입니다.
**줄별 설명**
- `"bbox": { "south": 37.425, ... }` → 지도로 쓸 직사각형 범위(남·서·북·동 끝의 위도·경도)입니다.
- `"roadClasses": ["motorway", ... "tertiary"]` → 내려받을 도로 종류입니다. 고속도로부터 집산도로(작은 동네 길을 큰 길로 모아주는 도로)까지입니다.
- `"overpassEndpoints": [...]` → 데이터를 받아올 서버 주소 두 개입니다. 하나가 실패하면 다음 서버를 씁니다.
- `"difficulties"` → 쉬움·보통·어려움별로 쓸 도로 종류(`roads`)와 막힐 확률(`closureChance`, 1%·2%·3%)을 정합니다.
- `"places": [...]` → 홍대입구역, 김포공항 같은 장소 10곳의 이름과 위도(lat)·경도(lon)입니다.
- `"scenarios": [...]` → "홍대입구역 → 잠실역"처럼 출발지와 도착지를 짝지은 경주 5개입니다.

### js/osm.js (새 파일 + 이후 수정)
**한 줄 요약**: OpenStreetMap 원본 데이터를 게임에서 쓰는 도로망(교차로+도로)으로 바꾸는 변환기입니다.
**왜 바꿨나**: 실제 서울 지도 모드를 만들려면 원본 데이터를 변환해야 하기 때문입니다(작업 설명 기준).
**줄별 설명**
- `makeProjection(bbox)` → 위도·경도를 km 단위 평면 좌표로 바꿔 화면에 그릴 수 있게 합니다.
- `roadClassOf(highway)` → `primary_link`처럼 끝에 `_link`가 붙은 이름을 `primary`로 줄여 같은 등급으로 취급합니다.
- `onewayDirection(tags)` → 도로가 일방통행인지, 어느 방향인지 판단합니다. 로터리와 고속도로는 기본적으로 일방통행으로 봅니다.
- `if (el.type === 'node' && ... proj.inside(...))` → 범위 안에 있는 점만 좌표로 저장합니다.
- `// 2) 교차로 찾기` 부분 → 도로의 끝점이거나 두 번 이상 쓰인 점만 교차로로 남깁니다. 굽은 중간 점은 길이만 더합니다.
- `osmToRoadNetwork(...)` → 위 과정을 모두 실행해 최종 도로망 데이터를 돌려주는 핵심 함수입니다.
- **수정된 부분**: `const chord = Math.hypot(...)` → 두 교차로 사이의 직선거리를 계산합니다.
- `const cost = Math.ceil(Math.max(e.cost, chord) * 1e4) / 1e4;` → 도로 비용이 직선거리보다 작아지지 않게 보정합니다. 주석에 따르면 좌표를 반올림해도 A*(목적지 방향을 추측해 빨리 찾는 길찾기)의 추측값이 틀리지 않게 하려는 것입니다.

### js/map.js (수정)
**한 줄 요약**: "강하게 연결된 요소"를 찾는 함수를 추가하고, 실제 지도를 난이도·장애물에 맞게 준비하는 함수를 만들었습니다.
**왜 바꿨나**: 주석에 따르면 일방통행이 있어도 출발·도착 후보가 서로 오갈 수 있게 하려는 것입니다.
**줄별 설명**
- 이전의 방향 무시 연결 요소 계산 코드 → 삭제되었습니다. 일방통행이면 "갈 수는 있어도 돌아올 수 없는" 곳이 생길 수 있기 때문입니다.
- `const { component, sizes } = stronglyConnectedComponents(n, adj);` → 새 함수로 서로 오갈 수 있는 교차로 묶음을 구합니다.
- `export function stronglyConnectedComponents(n, adj)` → Tarjan 방식(그래프에서 서로 오갈 수 있는 묶음을 찾는 알고리즘)으로 묶음을 계산합니다. 반복문으로 짜여 있습니다.
- `const work = [[s, 0]];` → 재귀(함수가 자기 자신을 부르는 방식) 대신 직접 만든 작업 목록을 씁니다. 이유는 자료에서 확인되지 않습니다.
- `if (low[u] === index[u])` → 한 묶음의 시작점에 도달했다는 뜻이며, 쌓아 둔 점들을 꺼내 같은 묶음 번호를 붙입니다.
- `export function prepareRealNetwork(data, {difficulty, obstacleSeed})` → 난이도에 맞는 도로만 고르고 일부 도로를 막습니다.
- `const blocked = !e.bridge && rand() < (diff.closureChance || 0);` → 다리가 아닌 도로를 난이도별 확률로 막습니다. `obstacleSeed`가 같으면 같은 결과가 나옵니다.

### tools/fetch-seoul-map.js (새 파일)
**한 줄 요약**: 서울 도로 데이터를 인터넷에서 받아 `data/real-map.json`으로 저장하는 실행 스크립트입니다(`npm run fetch-map`).
**왜 바꿨나**: 한 번 받아 저장해 두면 이후 인터넷 없이 쓸 수 있게 하려는 것입니다.
**줄별 설명**
- `const offline = args.includes('--offline');` → 이미 받은 원본으로 변환만 하는 옵션입니다.
- `async function download(config)` → 서버 목록을 차례로 시도해 데이터를 받습니다.
- `signal: AbortSignal.timeout(300_000)` → 5분 안에 응답이 없으면 포기합니다.
- `fs.writeFileSync(CACHE_PATH, text);` → 받은 원본을 캐시(임시 보관) 파일로 저장합니다.
- `if (net.nodes.length < 50) throw ...` → 교차로가 너무 적으면 설정이 잘못된 것으로 보고 중단합니다.
- `fs.writeFileSync(OUT_PATH, JSON.stringify(net));` → 변환 결과를 저장합니다.
- 마지막 반복문 → 난이도별로 출발·도착을 찾을 수 있는지 점검합니다. 뒷부분은 생략되어 자세한 내용은 확인되지 않습니다.

### js/animation.js 등
길이 제한으로 생략되어 설명할 수 없습니다.
