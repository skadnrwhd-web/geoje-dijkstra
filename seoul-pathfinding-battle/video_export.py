"""
video_export.py
대결 애니메이션을 세로형 MP4(기본 1080x1920, 30fps)로 저장한다.

명령줄에서 바로 쓰기:
    python video_export.py                 # config.json 설정대로 영상 만들기
    python video_export.py --grid          # 인터넷 없이 가상 격자 지도로 만들기
    python video_export.py --preview       # 540x960 저해상도 빠른 미리보기
"""

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from algorithms import battle_summary, run_battle, save_summary
from animation import BattleRenderer
from config import load_config, resolve_path
from map_loader import load_graph, pick_endpoints


def find_ffmpeg():
    """시스템 FFmpeg 를 먼저 찾고, 없으면 imageio-ffmpeg 에 들어 있는 FFmpeg 를 쓴다."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("FFmpeg 를 찾을 수 없습니다. `pip install imageio-ffmpeg` 를 실행하거나 "
                           "FFmpeg 를 설치해 PATH 에 추가하세요.") from e


def output_path(cfg, suffix=""):
    v = cfg["video"]
    out_dir = resolve_path(v["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    name = v.get("filename") or f"battle_{cfg['map_mode']}_{datetime.now():%Y%m%d_%H%M%S}"
    name = Path(name).stem + suffix
    return out_dir / f"{name}.mp4"


def export_mp4(renderer, out_path, crf=20, progress=None):
    """렌더러의 프레임을 FFmpeg 로 보내 H.264 MP4 로 저장한다."""
    out_path = Path(out_path)
    cmd = [find_ffmpeg(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{renderer.W}x{renderer.H}",
           "-r", f"{renderer.fps:g}", "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(int(crf)),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    total = renderer.n_frames
    try:
        for i, img in renderer.iter_frames():
            proc.stdin.write(img.tobytes())
            if progress and (i % 15 == 0 or i == total - 1):
                progress(i + 1, total)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0:
        raise RuntimeError(f"FFmpeg 인코딩 실패:\n{err}")
    return out_path


def make_video(cfg, preview=False, out_path=None, log=print, progress=None, graph=None, battle=None):
    """지도 읽기 → 대결 실행 → 영상 저장 → 기록(JSON) 저장. 결과 경로들을 돌려준다."""
    if graph is None:
        log("지도 준비 중...")
        graph = load_graph(cfg, progress=log)
    if battle is None:
        s, t = pick_endpoints(graph, cfg)
        log(f"대결 실행 중... (노드 {graph.n_nodes:,}, 간선 {graph.n_edges:,})")
        battle = run_battle(graph, s, t, cfg)
    size = dict(width=540, height=960, fps=24) if preview else {}
    renderer = BattleRenderer(graph, battle, cfg, **size)
    out_path = Path(out_path) if out_path else output_path(cfg, "_preview" if preview else "")
    log(f"영상 만드는 중: {renderer.n_frames} 프레임, {renderer.duration_sec:.1f}초 → {out_path.name}")
    export_mp4(renderer, out_path, cfg["video"]["crf"], progress=progress)

    summary = battle_summary(battle, graph, cfg)
    summary["video"] = {**cfg["video"], "file": str(out_path), "frames": renderer.n_frames,
                        "width": renderer.W, "height": renderer.H, "fps": renderer.fps,
                        "nodes_per_frame": renderer.npf, "actual_duration_sec": renderer.duration_sec}
    summary["style"] = cfg["style"]
    json_path = out_path.with_suffix(".json")
    save_summary(summary, json_path)
    log(f"완료: {out_path}")
    return {"mp4": out_path, "json": json_path, "battle": battle, "graph": graph, "renderer": renderer}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dijkstra vs A* 세로 영상 만들기")
    ap.add_argument("--config", default=None, help="설정 파일 경로 (기본: config.json)")
    ap.add_argument("--grid", action="store_true", help="가상 격자 지도 사용 (인터넷 불필요)")
    ap.add_argument("--seoul", action="store_true", help="서울 도로망 사용")
    ap.add_argument("--preview", action="store_true", help="540x960 저해상도 미리보기")
    ap.add_argument("--out", default=None, help="저장할 mp4 경로")
    args = ap.parse_args(argv)

    cfg = load_config(args.config) if args.config else load_config()
    if args.grid:
        cfg["map_mode"] = "grid"
    if args.seoul:
        cfg["map_mode"] = "seoul"

    def bar(done, total):
        n = int(30 * done / total)
        sys.stdout.write(f"\r  [{'#' * n}{'.' * (30 - n)}] {done}/{total}")
        sys.stdout.flush()
        if done == total:
            sys.stdout.write("\n")

    res = make_video(cfg, preview=args.preview, out_path=args.out, progress=bar)
    b = res["battle"]
    v = b["verdict"]
    print()
    for r in v["rows"]:
        print(f"  {r['label']:<14} Dijkstra={r['dijkstra']:<12.4g} A*={r['astar']:<12.4g} → {r['winner']}")
    print(f"  승자: {v['winner']}  ({v['score']})")
    print(f"  기록: {res['json']}")


if __name__ == "__main__":
    main()
