// OpenStreetMap 변환기·실제 도로망 모드 테스트 — 실행: npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { osmToRoadNetwork, onewayDirection, roadClassOf, makeProjection, buildOverpassQuery } from '../js/osm.js';
import { buildGraph, prepareRealNetwork, placeToNode, edgeCost } from '../js/map.js';
import { dijkstra, astar } from '../js/algorithms.js';
import { runRace } from '../js/metrics.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const BBOX = { south: 37.5, west: 127.0, north: 37.51, east: 127.01 };
const CONFIG = {
  name: '테스트',
  bbox: BBOX,
  roadClasses: ['primary', 'secondary'],
  places: [{ id: 'a', name: 'A', lat: 37.509, lon: 127.001 }, { id: 'b', name: 'B', lat: 37.501, lon: 127.009 }],
  scenarios: [{ name: 'A → B', start: 'a', goal: 'b' }],
  difficulties: {
    easy: { label: '쉬움', roads: ['primary'], closureChance: 0 },
    hard: { label: '어려움', roads: ['primary', 'secondary'], closureChance: 0.5 },
  },
};

// 작은 가상의 OSM 응답
//   1 ─(2)─ 3 ─(5)→ 6        A: primary 양방향 1-2-3-4 (2는 굽은 점)
//   │       ↖───(7)───┘       B: secondary 일방통행 3→5→6,  C: secondary oneway=-1 로 그려진 3-7-6 → 실제 통행 6→7→3
//   4                         D: residential 4-8 (등급 제외)   E: primary 4-9-10 (9는 범위 밖)
//                             G: 동떨어진 primary 11-12        H: motorway(기본 일방통행) 1→13
const n = (id, lat, lon) => ({ type: 'node', id, lat, lon });
const OSM = {
  elements: [
    n(1, 37.509, 127.001), n(2, 37.509, 127.003), n(3, 37.509, 127.005), n(4, 37.505, 127.005),
    n(5, 37.507, 127.007), n(6, 37.505, 127.009), n(7, 37.503, 127.007), n(8, 37.502, 127.002),
    n(9, 37.52, 127.005), n(10, 37.5095, 127.0001),
    n(11, 37.5012, 127.0002), n(12, 37.5013, 127.0004), n(13, 37.5099, 127.0099),
    { type: 'way', id: 100, nodes: [1, 2, 3, 4], tags: { highway: 'primary', name: '테스트로' } },
    { type: 'way', id: 101, nodes: [3, 5, 6], tags: { highway: 'secondary', oneway: 'yes' } },
    { type: 'way', id: 102, nodes: [3, 7, 6], tags: { highway: 'secondary_link', oneway: '-1' } },
    { type: 'way', id: 103, nodes: [4, 8], tags: { highway: 'residential' } },
    { type: 'way', id: 104, nodes: [4, 9, 10], tags: { highway: 'primary' } },
    { type: 'way', id: 105, nodes: [11, 12], tags: { highway: 'primary' } },
    { type: 'way', id: 106, nodes: [1, 13], tags: { highway: 'primary', oneway: 'yes' } },
    { type: 'way', id: 107, nodes: [4, 6], tags: { highway: 'primary', bridge: 'yes', name: '테스트대교' } },
    { type: 'way', id: 200, tags: { waterway: 'river', name: '한강' }, geometry: [{ lat: 37.504, lon: 127.0 }, { lat: 37.506, lon: 127.01 }] },
    { type: 'relation', id: 300, tags: { boundary: 'administrative', admin_level: '6', name: '테스트구' }, center: { lat: 37.505, lon: 127.005 } },
  ],
};

const proj = makeProjection(BBOX);
const P = (id) => {
  const el = OSM.elements.find((e) => e.type === 'node' && e.id === id);
  return proj.project(el.lat, el.lon);
};
const dist = (a, b) => Math.hypot(P(a).x - P(b).x, P(a).y - P(b).y);
const findNode = (net, osmId) => net.nodes.findIndex((nd) => Math.abs(nd.x - P(osmId).x) < 1e-3 && Math.abs(nd.y - P(osmId).y) < 1e-3);

test('일방통행 규칙: yes / -1 / no / roundabout / motorway 기본값', () => {
  assert.equal(onewayDirection({ oneway: 'yes' }), 1);
  assert.equal(onewayDirection({ oneway: '-1' }), -1);
  assert.equal(onewayDirection({ oneway: 'no', highway: 'motorway' }), 0);
  assert.equal(onewayDirection({ junction: 'roundabout' }), 1);
  assert.equal(onewayDirection({ highway: 'motorway_link' }), 1);
  assert.equal(onewayDirection({ highway: 'primary' }), 0);
  assert.equal(roadClassOf('primary_link'), 'primary');
});

test('OSM → 도로망: 교차로만 남기고, 굽은 길이를 비용에 합산하고, 방향을 지킨다', () => {
  const net = osmToRoadNetwork(OSM, CONFIG);
  const id1 = findNode(net, 1), id3 = findNode(net, 3), id4 = findNode(net, 4), id6 = findNode(net, 6);
  assert.ok(id1 >= 0 && id3 >= 0 && id4 >= 0 && id6 >= 0, '교차로 1, 3, 4, 6이 남아야 함');
  assert.equal(findNode(net, 2), -1, '굽은 점 2는 노드가 아님');
  assert.equal(findNode(net, 8), -1, '제외 등급(residential) 도로의 점은 없음');
  assert.equal(findNode(net, 10), -1, '범위 밖에서 끊긴 조각은 없음');
  assert.equal(findNode(net, 11), -1, '동떨어진 도로는 제거');
  assert.equal(findNode(net, 13), -1, '돌아올 수 없는 일방통행 끝은 제거');
  assert.equal(net.nodes.length, 4);

  const g = buildGraph(net);
  assert.ok(Math.abs(edgeCost(g, id1, id3) - (dist(1, 2) + dist(2, 3))) < 1e-3, '비용 = 도로를 따라간 길이');
  assert.ok(Number.isFinite(edgeCost(g, id3, id6)) && Math.abs(edgeCost(g, id3, id6) - (dist(3, 5) + dist(5, 6))) < 1e-3);
  assert.ok(Math.abs(edgeCost(g, id6, id3) - (dist(6, 7) + dist(7, 3))) < 1e-3, 'oneway=-1은 그려진 반대 방향으로 통행');
  for (const e of net.edges) {
    const a = net.nodes[e.from], b = net.nodes[e.to];
    assert.ok(e.cost >= Math.hypot(a.x - b.x, a.y - b.y), '비용은 직선거리 이상 (A* 휴리스틱 안전)');
  }
  assert.equal(g.heuristicScale, 1);
  assert.ok(net.edges.some((e) => e.bridge), '대교 표시');
  assert.equal(net.waterLines.length, 1);
  assert.deepEqual(net.districts.map((d) => d.name), ['테스트구']);
  assert.equal(net.meta.isReal, true);
  assert.equal(net.meta.attribution, '© OpenStreetMap contributors');
  assert.equal(net.meta.license, 'ODbL 1.0');
});

test('변환한 도로망에서 다익스트라·A*가 같은 최단 경로를 찾는다', () => {
  const g = buildGraph(osmToRoadNetwork(OSM, CONFIG));
  for (const s of g.nodes) {
    for (const t of g.nodes) {
      const d = dijkstra(g, s.id, t.id), a = astar(g, s.id, t.id);
      assert.equal(d.reached, true, '강연결 요소만 남겼으므로 모든 쌍이 도달 가능');
      assert.ok(Math.abs(d.cost - a.cost) < 1e-9);
    }
  }
});

test('난이도는 도로 등급을, 장애물 재배치는 통제 도로를 바꾼다 (결정론)', () => {
  const net = osmToRoadNetwork(OSM, CONFIG);
  const easy = prepareRealNetwork(net, { difficulty: 'easy' });
  assert.ok(easy.edges.every((e) => e.road === 'primary'));
  const h1 = prepareRealNetwork(net, { difficulty: 'hard', obstacleSeed: 1 });
  const h1b = prepareRealNetwork(net, { difficulty: 'hard', obstacleSeed: 1 });
  assert.deepEqual(h1.edges, h1b.edges);
  assert.ok(h1.edges.filter((e) => e.bridge).every((e) => !e.blocked), '다리는 막지 않음');
  assert.throws(() => prepareRealNetwork(net, { difficulty: 'nope' }), /난이도/);
});

test('Overpass 질의문에 범위와 도로 등급이 들어간다', () => {
  const q = buildOverpassQuery(CONFIG);
  assert.match(q, /\[bbox:37\.5,127,37\.51,127\.01\]/);
  assert.match(q, /\^\(primary\|secondary\)\(_link\)\?\$/);
});

test('잘못된 OSM 데이터에는 이해하기 쉬운 오류', () => {
  assert.throws(() => osmToRoadNetwork({}, CONFIG), /OSM 데이터 형식/);
});

const REAL = path.join(ROOT, 'data/real-map.json');
test('실제 서울 도로망(real-map.json): 모든 난이도·시나리오에서 두 알고리즘 비용 일치, 일방통행 준수', { skip: !fs.existsSync(REAL) && 'real-map.json 없음 (npm run fetch-map)' }, () => {
  const net = JSON.parse(fs.readFileSync(REAL, 'utf8'));
  assert.equal(net.meta.isReal, true);
  assert.match(net.meta.attribution, /OpenStreetMap/);
  for (const difficulty of Object.keys(net.difficulties)) {
    const g = buildGraph(prepareRealNetwork(net, { difficulty, obstacleSeed: 1 }));
    assert.equal(g.heuristicScale, 1);
    for (const sc of net.scenarios) {
      const s = placeToNode(g, sc.start), t = placeToNode(g, sc.goal);
      const race = runRace(g, s, t, { budgetMs: 5 });
      const d = race.dijkstra, a = race.astar;
      assert.ok(d.reached && a.reached, `${difficulty} ${sc.name}`);
      assert.ok(Math.abs(d.pathLength - a.pathLength) < 1e-9, `${difficulty} ${sc.name}: ${d.pathLength} vs ${a.pathLength}`);
      assert.ok(a.expandedCount <= d.expandedCount, 'A*가 더 적게 탐색');
      // 경로의 모든 구간이 통행 방향에 맞는 도로인지
      for (const p of [d.result.path, a.result.path]) {
        for (let i = 1; i < p.length; i++) assert.ok(Number.isFinite(edgeCost(g, p[i - 1], p[i])));
      }
    }
  }
});
