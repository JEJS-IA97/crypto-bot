"""Tests del recolector de klines históricos (spec 001, RF-15 soporte)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

import collect_klines

INTERVAL_MS = 900_000  # 15m
BASE_MS = 1_700_000_000_000
TOTAL_CANDLES = 2500  # 1000 + 1000 + 500 (3 bloques, el último corto)


def _rows(start_ms: int, count: int) -> list[list]:
    """Payload crudo de /api/v3/klines (formato Binance)."""
    rows = []
    for index in range(count):
        open_time = start_ms + index * INTERVAL_MS
        rows.append(
            [
                open_time,
                "100.0",
                "101.0",
                "99.0",
                "100.5",
                "123.4",
                open_time + INTERVAL_MS - 1,
                "12345.6",
                42,
                "60.0",
                "6010.0",
                "0",
            ]
        )
    return rows


class ChunkDownloadAndResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="klines-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.data_dir = Path(self.tmpdir) / "klines"

    def _read_lines(self) -> list[dict]:
        path = collect_klines.klines_file(self.data_dir, "BTCUSDT")
        with path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def test_chunk_download_and_resume(self) -> None:
        # 1ª ejecución: corta la red tras escribir el primer bloque de 1000.
        first_run_calls: list[dict] = []

        def flaky_request(**kwargs):
            first_run_calls.append(kwargs)
            if len(first_run_calls) == 1:
                start = kwargs["params"]["startTime"]
                return httpx.Response(200, json=_rows(start, 1000))
            raise httpx.ConnectError("red caída")

        with patch(
            "collect_klines.httpx.request", side_effect=flaky_request
        ):
            with self.assertRaises(collect_klines.CollectionError):
                collect_klines.download_symbol(
                    "BTCUSDT",
                    data_dir=self.data_dir,
                    start_time=BASE_MS,
                )

        # Se conserva lo descargado antes del corte (reanudable).
        self.assertEqual(len(self._read_lines()), 1000)
        # Bloques de 1000 velas y sin credenciales.
        self.assertEqual(first_run_calls[0]["params"]["limit"], 1000)
        self.assertEqual(first_run_calls[0]["params"]["interval"], "15m")
        self.assertTrue(
            first_run_calls[0]["url"].endswith("/api/v3/klines")
        )
        self.assertNotIn("headers", first_run_calls[0])

        # 2ª ejecución: continúa exactamente donde iba, sin duplicar.
        resume_calls: list[int] = []

        def resumed_request(**kwargs):
            start = kwargs["params"]["startTime"]
            resume_calls.append(start)
            index = (start - BASE_MS) // INTERVAL_MS
            remaining = TOTAL_CANDLES - index
            if remaining <= 0:
                return httpx.Response(200, json=[])
            return httpx.Response(
                200, json=_rows(start, min(1000, remaining))
            )

        with patch(
            "collect_klines.httpx.request", side_effect=resumed_request
        ):
            stats = collect_klines.download_symbol(
                "BTCUSDT",
                data_dir=self.data_dir,
                start_time=BASE_MS,
            )

        # Reanuda desde la vela siguiente a la última escrita.
        self.assertEqual(
            resume_calls[0],
            BASE_MS + 1000 * INTERVAL_MS,
        )
        self.assertEqual(stats["written"], 1500)

        lines = self._read_lines()
        self.assertEqual(len(lines), TOTAL_CANDLES)
        open_times = [line["open_time"] for line in lines]
        self.assertEqual(open_times, sorted(set(open_times)))
        self.assertEqual(open_times[0], BASE_MS)
        self.assertEqual(
            open_times[-1],
            BASE_MS + (TOTAL_CANDLES - 1) * INTERVAL_MS,
        )
        # Los importes se guardan como texto (sin float, constitución #11).
        self.assertEqual(lines[0]["close"], "100.5")

        # 3ª ejecución: ya está al día → una petición vacía, nada escrito.
        with patch(
            "collect_klines.httpx.request",
            return_value=httpx.Response(200, json=[]),
        ) as up_to_date:
            stats = collect_klines.download_symbol(
                "BTCUSDT",
                data_dir=self.data_dir,
                start_time=BASE_MS,
            )
        self.assertEqual(stats["written"], 0)
        self.assertEqual(up_to_date.call_count, 1)
        self.assertEqual(len(self._read_lines()), TOTAL_CANDLES)


if __name__ == "__main__":
    unittest.main()
