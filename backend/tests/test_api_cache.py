import time
import unittest
from unittest.mock import patch

from app.api import cache


class CacheTests(unittest.TestCase):
    def test_serves_fresh_then_stale_while_refreshing(self):
        calls = []

        @cache.swr(0.05)
        def endpoint(x=1):
            calls.append(x)
            return len(calls)

        with patch.object(cache, "ENABLED", True):
            cache.clear()
            self.assertEqual(endpoint(x=1), 1)
            self.assertEqual(endpoint(x=1), 1)  # fresca: no recalcula
            time.sleep(0.06)
            self.assertEqual(endpoint(x=1), 1)  # vieja: devuelve al instante...
            time.sleep(0.05)
            self.assertEqual(endpoint(x=1), 2)  # ...y ya se recalculó en segundo plano
