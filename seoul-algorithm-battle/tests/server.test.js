// 로컬 서버 + FFmpeg MP4 생성 테스트 — 실행: npm test
// 실제로 FFmpeg를 실행해 MP4를 만들고 ffprobe로 재생 정보를 확인한다.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'seoul-escape-test-'));
process.env.OUTPUT_DIR = TMP;
const { createServer, detectFfmpeg } = await import('../server/server.js');

let server, base;
before(async () => {
  server = createServer();
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => {
  server.close();
  fs.rmSync(TMP, { recursive: true, force: true });
});

// 외부 패키지 없이 단색 PNG 만들기
const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}
function solidPng(w, h, [r, g, b]) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 2; // 8bit RGB
  const row = Buffer.alloc(1 + w * 3);
  for (let x = 0; x < w; x++) { row[1 + x * 3] = r; row[2 + x * 3] = g; row[3 + x * 3] = b; }
  const raw = Buffer.concat(Array.from({ length: h }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0)),
  ]);
}

const post = async (p, body, headers = { 'Content-Type': 'application/json' }) => {
  const res = await fetch(base + p, { method: 'POST', headers, body });
  return { status: res.status, json: await res.json() };
};

test('게임 파일은 제공하고, 서버 코드·상위 폴더는 노출하지 않는다', async () => {
  assert.equal((await fetch(`${base}/`)).status, 200);
  assert.equal((await fetch(`${base}/js/algorithms.js`)).status, 200);
  assert.equal((await fetch(`${base}/data/sample-map.json`)).status, 200);
  assert.equal((await fetch(`${base}/server/server.js`)).status, 404);
  assert.equal((await fetch(`${base}/package.json`)).status, 404);
  assert.equal((await fetch(`${base}/js/..%2F..%2Fpackage.json`)).status, 404);
});

test('health API가 FFmpeg 상태를 알려준다', async () => {
  const j = await (await fetch(`${base}/api/health`)).json();
  assert.equal(j.ok, true);
  assert.equal(typeof j.ffmpeg, 'boolean');
});

test('프레임을 보내면 실제로 재생 가능한 MP4가 만들어진다 (base64 JPEG 경로 포함)', { skip: !detectFfmpeg().available && 'FFmpeg 없음' }, async () => {
  const W = 64, H = 112, FPS = 30, N = 45;
  const start = await post('/api/video/start', JSON.stringify({ width: W, height: H, fps: FPS, format: 'png' }));
  assert.equal(start.status, 200, JSON.stringify(start.json));
  assert.match(start.json.fileName, /^seoul_escape_\d{8}_\d{6}(_\d+)?\.mp4$/);
  for (let i = 0; i < N; i++) {
    const png = solidPng(W, H, [i * 5, 80, 255 - i * 5]);
    // 절반은 바이너리, 절반은 브라우저와 같은 base64 글자로 보낸다
    const r = i % 2
      ? await post(`/api/video/${start.json.id}/frame`, png, { 'Content-Type': 'application/octet-stream' })
      : await post(`/api/video/${start.json.id}/frame`, png.toString('base64'), { 'Content-Type': 'text/plain; charset=base64' });
    assert.equal(r.status, 200, JSON.stringify(r.json));
  }
  const fin = await post(`/api/video/${start.json.id}/finish`, '{}');
  assert.equal(fin.status, 200, JSON.stringify(fin.json));
  assert.ok(fs.existsSync(fin.json.filePath), 'MP4 파일이 실제로 있어야 함');
  assert.ok(fin.json.sizeBytes > 0);
  assert.equal(fin.json.probe.codec, 'h264');
  assert.equal(fin.json.probe.pixFmt, 'yuv420p', 'SNS 호환 색 형식');
  assert.equal(fin.json.probe.width, W);
  assert.equal(fin.json.probe.height, H);
  assert.equal(fin.json.probe.frames, N);
  assert.ok(Math.abs(fin.json.probe.durationSec - N / FPS) < 0.1, `길이 ${fin.json.probe.durationSec}`);
  // 만든 파일을 브라우저에서 내려받을 수 있다
  const res = await fetch(base + fin.json.url);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'video/mp4');
});

test('잘못된 요청에는 이해하기 쉬운 오류를 돌려준다', async () => {
  const odd = await post('/api/video/start', JSON.stringify({ width: 101, height: 200, fps: 30 }));
  if (detectFfmpeg().available) {
    assert.equal(odd.status, 400);
    assert.match(odd.json.error, /짝수/);
  }
  const missing = await post('/api/video/9999/frame', 'abc', { 'Content-Type': 'application/octet-stream' });
  assert.equal(missing.status, 404);
  assert.match(missing.json.error, /영상 작업/);
});

test('취소하면 미완성 파일이 남지 않는다', { skip: !detectFfmpeg().available && 'FFmpeg 없음' }, async () => {
  const s = await post('/api/video/start', JSON.stringify({ width: 32, height: 32, fps: 30, format: 'png' }));
  await post(`/api/video/${s.json.id}/frame`, solidPng(32, 32, [0, 0, 0]), { 'Content-Type': 'application/octet-stream' });
  const c = await post(`/api/video/${s.json.id}/cancel`, '{}');
  assert.equal(c.json.cancelled, true);
  await new Promise((r) => setTimeout(r, 800));
  assert.ok(!fs.existsSync(path.join(TMP, s.json.fileName)), '취소된 파일은 지워져야 함');
});
