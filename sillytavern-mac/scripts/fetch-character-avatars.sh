#!/usr/bin/env bash
# 下载《美女江山一锅煮》豆瓣封面 + Wikimedia 公版图，供 prepare-character-avatars.py 裁切
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS="$ROOT/assets/characters"
mkdir -p "$ASSETS"

echo "==> 豆瓣封面（河南文艺版）"
ASSETS="$ASSETS" python3 << 'PY'
import os, re, urllib.request
from pathlib import Path
from PIL import Image

ASSETS = Path(os.environ['ASSETS'])
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://book.douban.com/',
}
subjects = {'vol3l': '2196210', 'vol4l': '2314473'}

def cover_url(subject_id: str) -> str:
    page = f'https://book.douban.com/subject/{subject_id}/'
    html = urllib.request.urlopen(urllib.request.Request(page, headers=headers), timeout=30).read().decode('utf-8', 'replace')
    imgs = re.findall(r'https://img[^"\s>]+doubanio\.com/view/subject/l/public/s[^"\s>]+\.jpg', html)
    if not imgs:
        imgs = re.findall(r'https://img[^"\s>]+doubanio\.com/view/subject/s/public/s[^"\s>]+\.jpg', html)
    if not imgs:
        raise SystemExit(f'no cover for {subject_id}')
    return imgs[0].replace('/s/public/', '/l/public/')

for name, sid in subjects.items():
    url = cover_url(sid)
    dest = ASSETS / f'{name}.jpg'
    data = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30).read()
    dest.write_bytes(data)
    print(f'  {name}: {Image.open(dest).size} <- {url}')
PY

echo "==> Wikimedia（苏晨气质参考：叶小鸾）"
curl -fsSL -A 'Mozilla/5.0' -o "$ASSETS/wiki-suchen-gentle.jpg" \
  'https://upload.wikimedia.org/wikipedia/commons/f/f8/Ye_Xiaoluan_-_Baimei_xinyong.jpg'
python3 -c "from PIL import Image; im=Image.open('$ASSETS/wiki-suchen-gentle.jpg'); print('  ok wiki-suchen-gentle.jpg', im.size)"

echo "==> 裁切头像"
python3 "$ROOT/scripts/prepare-character-avatars.py"

bash "$ROOT/scripts/refresh-character-avatars.sh"
