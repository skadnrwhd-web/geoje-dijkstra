// fetch-seoul-map.js — OpenStreetMap에서 서울 도로망을 내려받아 data/real-map.json으로 변환한다.
//
//   npm run fetch-map                 내려받기 + 변환 (처음 한 번, 인터넷 필요)
//   npm run fetch-map -- --offline    이미 받아 둔 원본(data/osm-cache/seoul-osm.json)으로 다시 변환만
//   npm run fetch-map -- --input 파일.json   직접 받은 Overpass JSON 파일을 변환
//
// API 키가 필요 없는 공개 Overpass API를 한 번만 호출한다. 받은 원본은 캐시해 두므로
// 이후에는 인터넷 없이 실행된다. 지도 데이터: © OpenStreetMap contributors (ODbL 1.0)

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { osmToRoadNetwork, buildOverpassQuery } from '../js/osm.js';
import { buildGraph, prepareRealNetwork, nearestNode } from '../js/map.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CONFIG_PATH = path.join(ROOT, 'data/real-map-config.json');
const CACHE_PATH = path.join(ROOT, 'data/osm-cache/seoul-osm.json');
const OUT_PATH = path.join(ROOT, 'data/real-map.json');

const args = process.argv.slice(2);
const inputIdx = args.indexOf('--input');
const inputFile = inputIdx >= 0 ? path.resolve(args[inputIdx + 1] || '') : null;
const offline = args.includes('--offline');

async function download(config) {
  const query = buildOverpassQuery(config);
  let lastErr;
  for (const endpoint of config.overpassEndpoints) {
    try {
      console.log(`  ▶ ${endpoint} 에서 내려받는 중… (1~3분 걸릴 수 있습니다)`);
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'User-Agent': 'SEOUL-ESCAPE-local-game/1.0 (educational, one-time download)',
        },
        body: `data=${encodeURIComponent(query)}`,
        signal: AbortSignal.timeout(300_000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status} ${(await res.text()).slice(0, 200)}`);
      const text = await res.text();
      const json = JSON.parse(text);
      if (!Array.isArray(json.elements) || json.elements.length === 0) throw new Error('받은 데이터가 비어 있습니다.');
      fs.mkdirSync(path.dirname(CACHE_PATH), { recursive: true });
      fs.writeFileSync(CACHE_PATH, text);
      console.log(`  ✔ 원본 저장: ${CACHE_PATH} (${(text.length / 1e6).toFixed(1)} MB)`);
      return json;
    } catch (err) {
      lastErr = err;
      console.log(`  ⚠ 실패: ${err.message}`);
    }
  }
  throw new Error(`모든 Overpass 서버에서 내려받지 못했습니다: ${lastErr?.message}`);
}

async function main() {
  const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  console.log('\n  서울 실제 도로망 만들기 (OpenStreetMap)');
  let osm;
  if (inputFile) {
    console.log(`  ▶ 입력 파일 사용: ${inputFile}`);
    osm = JSON.parse(fs.readFileSync(inputFile, 'utf8'));
  } else if (offline) {
    if (!fs.existsSync(CACHE_PATH)) throw new Error(`캐시가 없습니다: ${CACHE_PATH}. 먼저 인터넷이 연결된 상태에서 'npm run fetch-map'을 실행하세요.`);
    console.log(`  ▶ 캐시 사용: ${CACHE_PATH}`);
    osm = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
  } else {
    osm = await download(config);
  }

  const timestamp = osm.osm3s?.timestamp_osm_base || new Date().toISOString();
  const net = osmToRoadNetwork(osm, config, { downloadedAt: timestamp });
  if (net.nodes.length < 50) throw new Error(`변환된 교차로가 너무 적습니다 (${net.nodes.length}개). bbox와 roadClasses 설정을 확인하세요.`);
  fs.writeFileSync(OUT_PATH, JSON.stringify(net));
  const size = fs.statSync(OUT_PATH).size;

  console.log(`  ✔ 변환 완료: 교차로 ${net.nodes.length.toLocaleString()}개, 도로 ${net.edges.length.toLocaleString()}개` +
    ` (일방통행 ${net.edges.filter((e) => e.oneway).length.toLocaleString()}), 다리 ${net.edges.filter((e) => e.bridge).length}, 구 ${net.districts.length}, 강 선 ${net.waterLines.length}`);
  console.log(`  ✔ 저장: ${OUT_PATH} (${(size / 1e6).toFixed(2)} MB)`);
  console.log(`  ℹ 데이터 기준 시각: ${timestamp}`);

  // 시나리오 점검: 난이도별로 출발·도착을 찾을 수 있는지
  for (const key of Object.keys(net.difficulties)) {
    const g = buildGraph(prepareRealNetwork(net, { difficulty: key, obstacleSeed: 1 }));
    const main = g.component.filter((c) => c === g.mainComponent).length;
    const far = net.places.map((p) => {
      const id = nearestNode(g, p.x, p.y);
      const n = g.nodes[id];
      return `${p.name} ${Math.hypot(n.x - p.x, n.y - p.y).toFixed(2)}km`;
    });
    console.log(`  · ${key}: 사용 가능한 교차로 ${main.toLocaleString()}개 / 장소→가장 가까운 교차로 거리: ${far.join(', ')}`);
  }
  console.log('\n  게임에서 "지도: 실제 서울 (OSM)"을 선택하세요. 지도 데이터 © OpenStreetMap contributors (ODbL 1.0)\n');
}

main().catch((err) => {
  console.error(`\n  ✖ ${err.message}\n`);
  process.exit(1);
});
