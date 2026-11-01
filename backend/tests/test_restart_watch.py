import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import restart_watch as rw


class RestartWatchTests(unittest.TestCase):
    def test_flag_triggers_restart_once(self):
        with tempfile.TemporaryDirectory() as d:
            flag = Path(d) / "restart.flag"
            with patch.object(rw, "FLAG", flag), patch.object(rw, "launch_restart", return_value=True) as launch:
                self.assertFalse(rw.check_once())
                flag.write_text("prueba", encoding="utf-8")
                self.assertTrue(rw.check_once())
                self.assertFalse(flag.exists())
                self.assertFalse(rw.check_once())
            launch.assert_called_once()

    def test_no_restart_off_windows(self):
        with patch.object(rw.sys, "platform", "linux"):
            self.assertFalse(rw.launch_restart())
