"""Catch missing exports, duration changes, audio remixing and cover format errors."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/Users/huan.yu/Downloads/578f3c66-f1c6-4735-92ae-06acba6dfecc.mp4')
VIDEO = ROOT / 'exports/tiangong-daily-jiegehuo-subtitled-v01.mp4'
COVER = ROOT / 'exports/tiangong-daily-jiegehuo-cover-v01.png'

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))

class DeliveryTests(unittest.TestCase):
    def test_video_duration_and_decode(self):
        self.assertTrue(VIDEO.is_file(), 'subtitle video not built')
        info = probe(VIDEO)
        v = next(s for s in info['streams'] if s['codec_type'] == 'video')
        self.assertEqual((v['width'], v['height']), (720, 1280))
        self.assertLess(abs(float(info['format']['duration']) - float(probe(SOURCE)['format']['duration'])), .045)
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(VIDEO), '-f', 'null', '-'], check=True)

    def test_original_audio_packets_preserved(self):
        self.assertTrue(VIDEO.is_file(), 'subtitle video not built')
        def hashes(path):
            return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0', '-c', 'copy', '-f', 'hash', '-'])
        self.assertEqual(hashes(SOURCE), hashes(VIDEO))

    def test_cover_dimensions_and_rgb(self):
        self.assertTrue(COVER.is_file(), 'cover not built')
        v = probe(COVER)['streams'][0]
        self.assertEqual((v['width'], v['height'], v['pix_fmt']), (1080, 1920, 'rgb24'))

if __name__ == '__main__':
    unittest.main()
