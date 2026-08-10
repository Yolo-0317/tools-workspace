"""Unit tests for HTTP proxy playback progress helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from server.http_stream import estimate_position_ms
from server.playback_memory import PlaybackRecord, PlaybackStore
from server.quark_client import QuarkStreamSource


class EstimatePositionTests(unittest.TestCase):
    def test_cbr_96k(self) -> None:
        # 96 kbps → 12000 bytes/s; 12000 bytes ≈ 1s
        with mock.patch("server.http_stream.settings") as s:
            s.device_mp3_bitrate_k = 96
            self.assertEqual(estimate_position_ms(bytes_sent=12000, base_offset_ms=0), 1000)
            self.assertEqual(
                estimate_position_ms(bytes_sent=60000, base_offset_ms=5000),
                10000,
            )


class IncompleteCatalogTests(unittest.TestCase):
    def test_incomplete_for_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("server.playback_memory._STATE_DIR", Path(tmp)):
                with mock.patch("server.playback_memory.settings") as s:
                    s.playback_resume_min_ms = 5000
                    s.playback_history_limit = 20
                    store = PlaybackStore("test-dev")
                    store.current = PlaybackRecord(
                        fid="f1",
                        filename="002.mp3",
                        query="西游记",
                        catalog_key="journey_west",
                        position_ms=12000,
                        completed=False,
                    )
                    hit = store.incomplete_for_catalog("journey_west")
                    self.assertIsNotNone(hit)
                    assert hit is not None
                    self.assertEqual(hit.fid, "f1")
                    self.assertIsNone(store.incomplete_for_catalog("frozen"))


if __name__ == "__main__":
    unittest.main()
