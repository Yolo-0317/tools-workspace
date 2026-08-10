from __future__ import annotations

import math
import os
import unittest

from a_share_stock_diagnosis.eastmoney import EastmoneyClient


@unittest.skipUnless(
    os.getenv("A_SHARE_DIAGNOSIS_ONLINE") == "1",
    "set A_SHARE_DIAGNOSIS_ONLINE=1 to access public market endpoints",
)
class OnlineMarketTests(unittest.TestCase):
    def test_shanghai_and_shenzhen_public_data(self) -> None:
        client = EastmoneyClient()
        for code in ("603011", "000001"):
            with self.subTest(code=code):
                security = client.resolve_symbol(code)
                bars = client.fetch_daily_bars(security)
                quote = client.fetch_quote(security)
                self.assertEqual(security.code, code)
                self.assertTrue(security.name)
                self.assertGreaterEqual(len(bars), 20)
                self.assertEqual(
                    [item.trade_date for item in bars],
                    sorted(item.trade_date for item in bars),
                )
                self.assertTrue(math.isfinite(quote.price))
                self.assertGreater(quote.price, 0)


if __name__ == "__main__":
    unittest.main()
