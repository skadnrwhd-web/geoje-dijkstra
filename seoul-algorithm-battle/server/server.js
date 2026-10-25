// server.js — 게임 파일 제공 + FFmpeg MP4 인코딩을 담당하는 로컬 서버.
// 외부 패키지 없이 Node.js 기본 기능만 사용한다. 인터넷 연결이 필요 없다.
//
// 영상 API
//   GET  /api/health                  FFmpeg 설치 여부, 저장 폴더
//   POST /api/video/start             {width,height,fps,format:'jpeg'|'png'} → {id, fileName}
//   POST /api/video/:id/frame         프레임 이미지 1장(바이너리). 순서대로 보낸다.
//   POST /api/video/:id/finish        인코딩 마무리 → {fileName, filePath, sizeBytes, durationSec, frames}
//   POST /api/video/:id/cancel        중단하고 미완성 파일 삭제

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(__dirname, '..');
export const OUTPUT_DIR = path.resolve(process.env.OUTPUT_DIR || path.join(ROOT, 'output'));
const FFMPEG = process.env.FFMPEG_PATH || 'ffmpeg';
const FFPROBE = process.env.FFPROBE_PATH || 'ffprobe';
const PORT = Number(process.env.PORT || 8765);
const HOST = process.env.HOST || '127.0.0.1';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.md': 'text/markdown; charset=utf-8',
};
// 브라우저에 공개하는 폴더 (server, tests 등은 공개하지 않음)
const PUBLIC_PREFIXES = ['index.html', 'css/', 'js/', 'data/', 'assets/', 'output/'];

// ---------- FFmpeg 확인 ----------
let ffmpegInfo = null;
export function detectFfmpeg() {
  if (ffmpegInfo) return ffmpegInfo;
  try {
    const r = spawnSync(FFMPEG, ['-hide_banner', '-version'], { encoding: 'utf8', timeout: 10000, windowsHide: true });
    if (r.status === 0) {
      ffmpegInfo = { available: true, version: (r.stdout.split('\n')[0] || '').trim() };
    } else {
      ffmpegInfo = { available: false, error: r.error ? r.error.message : r.stderr };
    }
  } catch (err) {
    ffmpegInfo = { available: false, error: err.message };
  }
  return ffmpegInfo;
}

function probeDuration(file) {
  try {
    const r = spawnSync(FFPROBE, ['-v', 'error', '-show_entries', 'format=duration:stream=nb_frames,codec_name,width,height,pix_fmt',
      '-of', 'json', file], { encoding: 'utf8', timeout: 20000, windowsHide: true });
    if (r.status !== 0) return null;
    const j = JSON.parse(r.stdout);
    const v = (j.streams || [])[0] || {};
    return { durationSec: Number(j.format?.duration), codec: v.codec_name, pixFmt: v.pix_fmt, width: v.width, height: v.height, frames: Number(v.nb_frames) };
  } catch {
    return null;
  }
}

// ---------- 영상 세션 ----------
const sessions = new Map();
let nextId = 1;

function timestampName(prefix = 'seoul_escape') {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${prefix}_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function uniquePath(base) {
  let file = path.join(OUTPUT_DIR, `${base}.mp4`);
  for (let i = 2; fs.existsSync(file); i++) file = path.join(OUTPUT_DIR, `${base}_${i}.mp4`);
  return file;
}

function startSession(opts) {
  const info = detectFfmpeg();
  if (!info.available) {
    const e = new Error('FFmpeg가 설치되어 있지 않아 MP4를 만들 수 없습니다. README의 FFmpeg 설치 방법을 확인하세요.');
    e.status = 503;
    throw e;
  }
  const width = Number(opts.width) || 1080;
  const height = Number(opts.height) || 1920;
  const fps = Number(opts.fps) || 30;
  if (width % 2 || height % 2) throw Object.assign(new Error('가로·세로 크기는 짝수여야 합니다.'), { status: 400 });
  if (fps < 1 || fps > 120) throw Object.assign(new Error('fps는 1~120 사이여야 합니다.'), { status: 400 });
  const codec = opts.format === 'png' ? 'png' : 'mjpeg';

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const filePath = uniquePath(timestampName());
  const args = [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'image2pipe', '-framerate', String(fps), '-c:v', codec, '-i', '-',
    // JPEG는 full-range 색이라 SNS·휴대폰 호환성을 위해 일반 yuv420p(tv range, BT.709)로 변환
    '-vf', `scale=${width}:${height}:flags=lanczos:out_range=tv:out_color_matrix=bt709,format=yuv420p`,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-profile:v', 'high',
    '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
    '-r', String(fps), '-movflags', '+faststart',
    filePath,
  ];
  const proc = spawn(FFMPEG, args, { stdio: ['pipe', 'ignore', 'pipe'], windowsHide: true });
  const id = String(nextId++);
  const session = { id, proc, filePath, frames: 0, stderr: '', closed: false, exitCode: null, fps };
  session.done = new Promise((resolve) => {
    proc.on('close', (code) => { session.closed = true; session.exitCode = code; resolve(code); });
    proc.on('error', (err) => { session.stderr += err.message; session.closed = true; session.exitCode = -1; resolve(-1); });
  });
  proc.stderr.on('data', (d) => { session.stderr = (session.stderr + d.toString()).slice(-4000); });
  proc.stdin.on('error', (err) => { session.stderr += `\n${err.message}`; });
  sessions.set(id, session);
  return session;
}

function writeFrame(session, buf) {
  return new Promise((resolve, reject) => {
    if (session.closed) return reject(new Error(`FFmpeg가 중간에 종료되었습니다: ${session.stderr}`));
    session.frames++;
    if (session.proc.stdin.write(buf)) resolve();
    else session.proc.stdin.once('drain', resolve);
  });
}

async function finishSession(session) {
  session.proc.stdin.end();
  const code = await session.done;
  sessions.delete(session.id);
  if (code !== 0) {
    try { fs.unlinkSync(session.filePath); } catch {}
    throw new Error(`MP4 인코딩에 실패했습니다 (코드 ${code}). ${session.stderr.trim()}`);
  }
  const stat = fs.statSync(session.filePath);
  const probe = probeDuration(session.filePath);
  return {
    fileName: path.basename(session.filePath),
    filePath: session.filePath,
    url: `/output/${encodeURIComponent(path.basename(session.filePath))}`,
    sizeBytes: stat.size,
    framesSent: session.frames,
    probe,
  };
}

function cancelSession(session) {
  try { session.proc.stdin.destroy(); } catch {}
  try { session.proc.kill(); } catch {}
  sessions.delete(session.id);
  session.done.then(() => { try { fs.unlinkSync(session.filePath); } catch {} });
}

// ---------- HTTP ----------
function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(body);
}

function readBody(req, limit = 50 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > limit) { reject(Object.assign(new Error('요청이 너무 큽니다.'), { status: 413 })); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

async function handleApi(req, res, url) {
  if (url.pathname === '/api/health' && req.method === 'GET') {
    const f = detectFfmpeg();
    return sendJson(res, 200, { ok: true, ffmpeg: f.available, ffmpegVersion: f.version || null, outputDir: OUTPUT_DIR });
  }
  if (req.method !== 'POST') return sendJson(res, 405, { error: '허용되지 않는 요청입니다.' });

  if (url.pathname === '/api/video/start') {
    const body = await readBody(req, 1024 * 64);
    const opts = body.length ? JSON.parse(body.toString('utf8')) : {};
    const s = startSession(opts);
    return sendJson(res, 200, { id: s.id, fileName: path.basename(s.filePath) });
  }
  const m = url.pathname.match(/^\/api\/video\/(\d+)\/(frame|finish|cancel)$/);
  if (m) {
    const session = sessions.get(m[1]);
    if (!session) return sendJson(res, 404, { error: '영상 작업을 찾을 수 없습니다. 다시 시도해 주세요.' });
    if (m[2] === 'frame') {
      // 브라우저는 JPEG를 base64 글자로 보낸다 (text/plain; charset=base64). 그 외에는 바이너리 그대로.
      const raw = await readBody(req);
      const isBase64 = (req.headers['content-type'] || '').includes('base64');
      const buf = isBase64 ? Buffer.from(raw.toString('latin1'), 'base64') : raw;
      if (!buf.length) return sendJson(res, 400, { error: '빈 프레임입니다.' });
      await writeFrame(session, buf);
      return sendJson(res, 200, { frames: session.frames });
    }
    if (m[2] === 'finish') return sendJson(res, 200, await finishSession(session));
    cancelSession(session);
    return sendJson(res, 200, { cancelled: true });
  }
  return sendJson(res, 404, { error: '없는 API입니다.' });
}

function serveStatic(req, res, url) {
  let rel = decodeURIComponent(url.pathname).replace(/^\/+/, '');
  if (rel === '') rel = 'index.html';
  const allowed = PUBLIC_PREFIXES.some((p) => rel === p || rel.startsWith(p));
  const base = rel.startsWith('output/') ? OUTPUT_DIR : ROOT;
  const sub = rel.startsWith('output/') ? rel.slice('output/'.length) : rel;
  const file = path.resolve(base, sub);
  if (!allowed || !file.startsWith(base + path.sep)) {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('Not found');
  }
  fs.stat(file, (err, stat) => {
    if (err || !stat.isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('Not found');
    }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream',
      'Content-Length': stat.size,
      'Cache-Control': 'no-cache',
    });
    fs.createReadStream(file).pipe(res);
  });
}

export function createServer() {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    try {
      if (url.pathname.startsWith('/api/')) await handleApi(req, res, url);
      else if (req.method === 'GET' || req.method === 'HEAD') serveStatic(req, res, url);
      else sendJson(res, 405, { error: '허용되지 않는 요청입니다.' });
    } catch (err) {
      console.error('[server]', err.message);
      if (!res.headersSent) sendJson(res, err.status || 500, { error: err.message });
      else res.end();
    }
  });
}

// 직접 실행했을 때만 서버 시작 (테스트에서 import할 때는 시작하지 않음)
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const f = detectFfmpeg();
  createServer().listen(PORT, HOST, () => {
    console.log('');
    console.log('  SEOUL ESCAPE: Dijkstra vs A*');
    console.log(`  ▶ Chrome에서 열기:  http://localhost:${PORT}`);
    console.log(`  ▶ 영상 저장 폴더:   ${OUTPUT_DIR}`);
    console.log(f.available ? `  ▶ FFmpeg: ${f.version}` : '  ⚠ FFmpeg를 찾지 못했습니다. MP4 대신 WebM으로 저장됩니다 (README 참고).');
    console.log('  종료하려면 이 창에서 Ctrl + C');
    console.log('');
  });
}
