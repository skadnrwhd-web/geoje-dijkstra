// 알고리즘·지도·지표 테스트 — 실행: npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { dijkstra, astar, MinHeap } from '../js/algorithms.js';
import { generateCity, buildGraph, placeToNode, mulberry32, riverYAt, edgeCost } from '../js/map.js';
import { runRace, computePathLength, compareMetrics } from '../js/metrics.js';
import { RaceController } from '../js/animation.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CONFIG = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/sample-map.json'), 'utf8'));
const EPS = 1e-9;

// 기준 정답: 우선순위 큐 없이 O(n²)로 구하는 단순 다익스트라 (구현이 완전히 다름)
function referenceShortest(graph, s, t) {
  const n = graph.nodes.length;
  const dist = new Array(n).fill(Infinity);
  const done = new Array(n).fill(false);
  dist[s] = 0;
  for (let k = 0; k < n; k++) {
    let u = -1;
    for (let i = 0; i < n; i++) if (!done[i] && (u === -1 || dist[i] < dist[u])) u = i;
    if (u === -1 || dist[u] === Infinity) break;
    done[u] = true;
    for (const { to, cost } of graph.adj[u]) if (dist[u] + cost < dist[to]) dist[to] = dist[u] + cost;
  }
  return dist[t];
}

function assertValidPath(graph, res) {
  assert.equal(res.path[0], res.start, '경로는 출발점에서 시작해야 함');
  assert.equal(res.path[res.path.length - 1], res.goal, '경로는 목적지에서 끝나야 함');
  for (let i = 1; i < res.path.length; i++) {
    assert.ok(Number.isFinite(edgeCost(graph, res.path[i - 1], res.path[i])), '경로의 모든 구간은 통행 가능한 도로여야 함');
  }
}

function randomGraph(seed, n, extraEdges) {
  const rand = mulberry32(seed);
  const nodes = Array.from({ length: n }, (_, id) => ({ id, x: rand() * 20, y: rand() * 20 }));
  const edges = [];
  const add = (a, b, oneway = false) => {
    const d = Math.hypot(nodes[a].x - nodes[b].x, nodes[a].y - nodes[b].y);
    edges.push({ from: a, to: b, cost: d * (1 + rand() * 0.8), oneway, blocked: rand() < 0.05 });
  };
  for (let i = 1; i < n; i++) add(i, Math.floor(rand() * i)); // 트리로 대부분 연결
  for (let k = 0; k < extraEdges; k++) {
    const a = Math.floor(rand() * n), b = Math.floor(rand() * n);
    if (a !== b) add(a, b, rand() < 0.15);
  }
  return buildGraph({ meta: {}, bounds: { minX: 0, minY: 0, maxX: 20, maxY: 20 }, nodes, edges });
}

// ---------------------------------------------------------------------------
test('MinHeap은 작은 키부터 꺼내고, 같은 키는 넣은 순서대로 꺼낸다', () => {
  const h = new MinHeap();
  [5, 1, 4, 1, 3, 9, 2].forEach((k, i) => h.push(`v${i}`, k));
  const out = [];
  while (h.size) out.push(h.pop());
  assert.deepEqual(out.map((o) => o.key), [1, 1, 2, 3, 4, 5, 9]);
  assert.deepEqual(out.slice(0, 2).map((o) => o.value), ['v1', 'v3']);
});

test('작은 손 계산 그래프에서 최단 경로를 찾는다', () => {
  //  0 --1-- 1 --1-- 2
  //  |               |
  //  +-------5-------+   (0→2 직행은 비용 5, 우회는 2)
  const nodes = [{ id: 0, x: 0, y: 0 }, { id: 1, x: 1, y: 0 }, { id: 2, x: 2, y: 0 }];
  const edges = [
    { from: 0, to: 1, cost: 1 }, { from: 1, to: 2, cost: 1 }, { from: 0, to: 2, cost: 5 },
  ];
  const g = buildGraph({ nodes, edges, bounds: { minX: 0, minY: 0, maxX: 2, maxY: 1 } });
  for (const fn of [dijkstra, astar]) {
    const r = fn(g, 0, 2);
    assert.equal(r.reached, true);
    assert.deepEqual(r.path, [0, 1, 2]);
    assert.equal(r.cost, 2);
  }
});

test('무작위 그래프 200개: 두 알고리즘의 비용이 기준 정답(최적)과 일치', () => {
  for (let seed = 1; seed <= 200; seed++) {
    const g = randomGraph(seed, 40 + (seed % 60), 60 + (seed % 90));
    const rand = mulberry32(seed * 7);
    const s = Math.floor(rand() * g.nodes.length);
    const t = Math.floor(rand() * g.nodes.length);
    const ref = referenceShortest(g, s, t);
    const d = dijkstra(g, s, t);
    const a = astar(g, s, t);
    assert.equal(d.start, a.start);
    assert.equal(d.goal, a.goal);
    if (ref === Infinity) {
      assert.equal(d.reached, false, `seed ${seed}`);
      assert.equal(a.reached, false, `seed ${seed}`);
      continue;
    }
    assert.ok(Math.abs(d.cost - ref) < EPS, `다익스트라 seed ${seed}: ${d.cost} vs ${ref}`);
    assert.ok(Math.abs(a.cost - ref) < EPS, `A* seed ${seed}: ${a.cost} vs ${ref}`);
    assertValidPath(g, d);
    assertValidPath(g, a);
    assert.ok(Math.abs(computePathLength(g, d.path) - ref) < 1e-6);
    assert.ok(Math.abs(computePathLength(g, a.path) - ref) < 1e-6);
  }
});

test('가상 서울 지도(모든 난이도 × 장애물 배치 5종 × 모든 시나리오)에서 최적 경로를 찾는다', () => {
  for (const difficulty of Object.keys(CONFIG.difficulties)) {
    for (let obstacleSeed = 1; obstacleSeed <= 5; obstacleSeed++) {
      const g = buildGraph(generateCity(CONFIG, { difficulty, obstacleSeed }));
      for (const sc of CONFIG.scenarios) {
        const s = placeToNode(g, sc.start), t = placeToNode(g, sc.goal);
        const ref = referenceShortest(g, s, t);
        const d = dijkstra(g, s, t), a = astar(g, s, t);
        assert.ok(Number.isFinite(ref), `${difficulty}/${obstacleSeed}/${sc.name}: 도달 가능해야 함`);
        assert.ok(Math.abs(d.cost - ref) < EPS && Math.abs(a.cost - ref) < EPS, `${difficulty}/${obstacleSeed}/${sc.name}`);
        assertValidPath(g, d);
        assertValidPath(g, a);
      }
    }
  }
});

test('도달할 수 없는 목적지는 reached=false, 빈 경로, 비용 Infinity', () => {
  const nodes = [{ id: 0, x: 0, y: 0 }, { id: 1, x: 1, y: 0 }, { id: 2, x: 5, y: 5 }, { id: 3, x: 6, y: 5 }];
  const edges = [{ from: 0, to: 1, cost: 1 }, { from: 2, to: 3, cost: 1 }];
  const g = buildGraph({ nodes, edges, bounds: { minX: 0, minY: 0, maxX: 6, maxY: 5 } });
  for (const fn of [dijkstra, astar]) {
    const r = fn(g, 0, 3);
    assert.equal(r.reached, false);
    assert.deepEqual(r.path, []);
    assert.equal(r.cost, Infinity);
    assert.equal(r.expandedCount, 2); // 0과 1만 확장
  }
  const m = runRace(g, 0, 3, { budgetMs: 5 });
  assert.equal(compareMetrics(m.dijkstra, m.astar).headline, '도달 불가');
});

test('막힌 도로와 일방통행을 지킨다', () => {
  // 0 - 1 - 3 이 최단이지만 1-3을 막으면 0 - 2 - 3으로 우회해야 함
  const nodes = [{ id: 0, x: 0, y: 0 }, { id: 1, x: 1, y: 0 }, { id: 2, x: 1, y: 1 }, { id: 3, x: 2, y: 0 }];
  const base = [
    { from: 0, to: 1, cost: 1 }, { from: 1, to: 3, cost: 1 },
    { from: 0, to: 2, cost: 1.5 }, { from: 2, to: 3, cost: 1.5 },
  ];
  const open = buildGraph({ nodes, edges: base, bounds: { minX: 0, minY: 0, maxX: 2, maxY: 1 } });
  assert.deepEqual(astar(open, 0, 3).path, [0, 1, 3]);

  const blocked = buildGraph({ nodes, edges: base.map((e, i) => (i === 1 ? { ...e, blocked: true } : e)), bounds: open.bounds });
  for (const fn of [dijkstra, astar]) {
    const r = fn(blocked, 0, 3);
    assert.deepEqual(r.path, [0, 2, 3]);
    assert.equal(r.cost, 3);
  }

  const oneway = buildGraph({ nodes, edges: base.map((e) => ({ ...e, oneway: true })), bounds: open.bounds });
  assert.equal(dijkstra(oneway, 0, 3).reached, true);
  assert.equal(dijkstra(oneway, 3, 0).reached, false, '일방통행은 반대 방향으로 갈 수 없음');
  assert.equal(astar(oneway, 3, 0).reached, false);
});

test('장애물 재배치는 도로 연결을 바꾸고, 두 알고리즘은 바뀐 지도에서도 최적이다', () => {
  const g1 = buildGraph(generateCity(CONFIG, { difficulty: 'normal', obstacleSeed: 1 }));
  const g2 = buildGraph(generateCity(CONFIG, { difficulty: 'normal', obstacleSeed: 2 }));
  const sig = (g) => g.edges.filter((e) => e.blocked).map((e) => `${e.from}-${e.to}`).join(',');
  assert.notEqual(sig(g1), sig(g2), '막힌 도로 배치가 달라야 함');
  // 막힌 도로는 인접 리스트에 들어가지 않는다 (양방향 도로 1개 = 인접 항목 2개)
  for (const g of [g1, g2]) {
    const adjCount = g.adj.reduce((s, list) => s + list.length, 0);
    assert.equal(adjCount, 2 * g.edges.filter((e) => !e.blocked).length);
    assert.ok(g.edges.some((e) => e.blocked));
  }
});

test('같은 설정이면 항상 같은 지도가 만들어진다 (결정론)', () => {
  const a = generateCity(CONFIG, { difficulty: 'hard', obstacleSeed: 3 });
  const b = generateCity(CONFIG, { difficulty: 'hard', obstacleSeed: 3 });
  assert.deepEqual(a.nodes, b.nodes);
  assert.deepEqual(a.edges, b.edges);
});

test('강은 다리로만 건널 수 있다', () => {
  for (const difficulty of Object.keys(CONFIG.difficulties)) {
    const g = generateCity(CONFIG, { difficulty, obstacleSeed: 1 });
    const side = (n) => (n.y < riverYAt(CONFIG.river, n.x) ? -1 : 1);
    for (const e of g.edges) {
      const crosses = side(g.nodes[e.from]) !== side(g.nodes[e.to]);
      if (crosses) assert.ok(e.bridge, `${difficulty}: 다리가 아닌 도로가 강을 건넘`);
    }
    assert.ok(g.bridges.length >= 5, `${difficulty}: 다리가 충분해야 함`);
  }
});

test('지표: 탐색 노드 수 = 확장한 고유 노드 수, 경로 길이 = 실제 간선 비용 합', () => {
  const g = buildGraph(generateCity(CONFIG, { difficulty: 'normal', obstacleSeed: 1 }));
  for (const sc of CONFIG.scenarios) {
    const race = runRace(g, placeToNode(g, sc.start), placeToNode(g, sc.goal), { budgetMs: 5 });
    for (const m of [race.dijkstra, race.astar]) {
      const order = m.result.expandedOrder;
      assert.equal(new Set(order).size, order.length, '같은 노드를 두 번 확장하면 안 됨');
      assert.equal(m.expandedCount, order.length);
      assert.ok(Math.abs(m.pathLength - m.result.cost) < 1e-9, '경로 길이는 탐색 비용과 같아야 함');
      let manual = 0;
      for (let i = 1; i < m.result.path.length; i++) {
        const a = g.nodes[m.result.path[i - 1]], b = g.nodes[m.result.path[i]];
        const e = g.edges.find((x) => !x.blocked && ((x.from === a.id && x.to === b.id) || (x.to === a.id && x.from === b.id)));
        manual += e.cost;
      }
      assert.ok(Math.abs(manual - m.pathLength) < 1e-9);
      assert.ok(m.timeMs > 0 && Number.isFinite(m.timeMs), '실행 시간은 실제로 측정된 양수');
      assert.ok(m.timingRuns >= 10);
    }
  }
});

test('실행 시간 측정에 애니메이션·그리기 시간이 포함되지 않는다', () => {
  // 1) 지표 모듈은 화면/영상 모듈을 불러오지 않는다
  const src = fs.readFileSync(path.join(ROOT, 'js/metrics.js'), 'utf8');
  assert.ok(!/animation\.js|recorder\.js|export\.js/.test(src), 'metrics.js가 화면 모듈을 import하면 안 됨');
  // 2) 애니메이션을 재생해도 이미 계산된 지표는 바뀌지 않는다
  const g = buildGraph(generateCity(CONFIG, { difficulty: 'normal', obstacleSeed: 1 }));
  const race = runRace(g, placeToNode(g, 'hongdae'), placeToNode(g, 'jamsil'), { budgetMs: 5 });
  const before = JSON.stringify([race.dijkstra.timeMs, race.astar.timeMs, race.dijkstra.expandedCount, race.astar.pathLength]);
  const c = new RaceController({ stepsPerSecond: 60 });
  c.load(race);
  c.start();
  for (let i = 0; i < 2000; i++) c.tick(1 / 60);
  assert.equal(c.state, 'finished');
  assert.equal(JSON.stringify([race.dijkstra.timeMs, race.astar.timeMs, race.dijkstra.expandedCount, race.astar.pathLength]), before);
});

test('경주 상태: 시작·일시정지·재개·재시작·중복 시작 방지·새 결과 교체', () => {
  const g = buildGraph(generateCity(CONFIG, { difficulty: 'easy', obstacleSeed: 1 }));
  const race = runRace(g, placeToNode(g, 'gimpo'), placeToNode(g, 'gangnam'), { budgetMs: 5 });
  const c = new RaceController({ stepsPerSecond: 10 });
  assert.equal(c.start(), false, '결과가 없으면 시작 불가');
  const gen1 = c.load(race);
  assert.equal(c.state, 'ready');
  assert.equal(c.pause(), false, '시작 전에는 일시정지 불가');
  assert.equal(c.start(), true);
  assert.equal(c.start(), false, '실행 중 중복 시작은 무시');
  c.tick(1);
  assert.equal(c.step, 10);
  assert.equal(c.pause(), true);
  c.tick(5);
  assert.equal(c.step, 10, '일시정지 중에는 진행하지 않음');
  assert.equal(c.resume(), true);
  assert.equal(c.resume(), false);
  c.tick(0.5);
  assert.equal(c.step, 15);
  assert.equal(c.restart(), true);
  assert.equal(c.step, 0);
  assert.equal(c.state, 'running');
  c.setSpeed(2);
  c.tick(1);
  assert.equal(c.step, 20, '속도 2배');
  const v = c.view('astar');
  assert.ok(v.shown <= race.astar.expandedCount);
  // 실행 중에 새 결과를 불러오면 처음 상태로 돌아간다 (이전 결과와 섞이지 않음)
  const gen2 = c.load(race);
  assert.ok(gen2 > gen1);
  assert.equal(c.state, 'ready');
  assert.equal(c.step, 0);
  c.start();
  assert.equal(c.finish(), true);
  assert.equal(c.state, 'finished');
  assert.equal(c.view('dijkstra').shown, race.dijkstra.expandedCount);
  assert.equal(c.view('dijkstra').pathProgress, 1);
  assert.equal(c.start(), true, '끝난 뒤 시작하면 처음부터 다시');
  assert.equal(c.step, 0);
  c.clear();
  assert.equal(c.state, 'empty');
  assert.equal(c.restart(), false);
});
