"""Render approved frame typography and timed subtitles; preserve source audio."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/Users/huan.yu/Downloads/578f3c66-f1c6-4735-92ae-06acba6dfecc.mp4')
MANIFEST = ROOT / 'episodes/tiangong-daily-jiegehuo-10s/subtitles.json'
EXPORT = ROOT / 'exports'

def run(args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)

def main():
    work = Path(tempfile.mkdtemp(prefix='zhixia-jiegehuo-render-'))
    print(f'Working assets: {work}', flush=True)
    video = EXPORT / 'tiangong-daily-jiegehuo-subtitled-v01.mp4'
    cover = EXPORT / 'tiangong-daily-jiegehuo-cover-v01.png'
    if video.exists() or cover.exists():
        raise FileExistsError('Deliverables already exist; use a new version rather than overwrite.')
    cues = json.loads(MANIFEST.read_text())
    previous = 0.0
    for cue in cues:
        if not (previous <= cue['start'] < cue['end'] <= 10.08):
            raise ValueError('Invalid or overlapping subtitle timing')
        previous = cue['end']
    ff = ['ffmpeg', '-v', 'error', '-n']
    run(ff + ['-ss', '3.60', '-i', SOURCE, '-frames:v', '1', '-vf',
              'scale=1080:1920:flags=lanczos,format=rgb24', work / 'base.png'])
    env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(work / 'clang'), SWIFT_MODULECACHE_PATH=str(work / 'swift'))
    run(['swift', ROOT / 'scripts/render_jiegehuo_artwork.swift', MANIFEST, work / 'base.png', work / 'artwork'], env=env)
    args = ff + ['-i', SOURCE]
    for cue in cues:
        args += ['-loop', '1', '-framerate', '24', '-i', work / 'artwork' / (cue['id'] + '.png')]
    filters = []
    for idx, cue in enumerate(cues, 1):
        prior = '0:v' if idx == 1 else f'v{idx-1}'
        filters.append(f"[{prior}][{idx}:v]overlay=enable='gte(t,{cue['start']})*lt(t,{cue['end']})':eof_action=pass[v{idx}]")
    run(args + ['-filter_complex', ';'.join(filters), '-map', f'[v{len(cues)}]', '-map', '0:a:0',
                '-t', '10.08', '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                '-c:a', 'copy', '-movflags', '+faststart', work / 'video.mp4'])
    run(ff + ['-i', work / 'artwork/cover-rgba.png', '-frames:v', '1', '-vf', 'format=rgb24', work / 'cover.png'])
    EXPORT.mkdir(exist_ok=True)
    import shutil
    shutil.copy2(work / 'video.mp4', video)
    shutil.copy2(work / 'cover.png', cover)
    print(video)
    print(cover)

if __name__ == '__main__':
    main()
