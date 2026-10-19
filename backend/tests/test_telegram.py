"""Señales de Telegram: lectura del mensaje y apertura en la cuenta virtual del chat."""

import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.lab import models as lab_models  # noqa: F401
from app.signals import telegram


class FakeRunner:
    def __init__(self, factory):
        self.session_factory = factory
        self.prices = {"BTCUSDT": Decimal("80000")}
        self.regimes = {}
        self.strategies = []
        self.accounts = {}


class TelegramTests(unittest.TestCase):
    def test_parses_common_formats(self):
        msg = "🚀 #BTC/USDT LONG\nEntry: 79,800\nTP1: 82,000\nSL: 78,500"
        self.assertEqual(
            telegram.parse_signal(msg),
            {"symbol": "BTCUSDT", "side": "LONG", "entry": 79800.0, "stop": 78500.0, "take_profit": 82000.0},
        )
        es = telegram.parse_signal("Venta ETHUSDT zona 2450 stop loss 2520 objetivo 2300")
        self.assertEqual((es["symbol"], es["side"], es["stop"]), ("ETHUSDT", "SHORT", 2520.0))

    def test_ignores_chatter_and_signals_without_stop(self):
        self.assertIsNone(telegram.parse_signal("Buenos días, el mercado está lateral"))
        self.assertIsNone(telegram.parse_signal("BTC LONG ya!! 🚀🚀"))

    def test_apply_signal_opens_paper_trade_in_chat_account(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        runner = FakeRunner(sessionmaker(bind=engine))
        parsed = telegram.parse_signal("BTC/USDT LONG entry 80000 SL 79000 TP 83000")
        self.assertEqual(telegram.apply_signal(-100123, "Señales VIP", parsed, runner), "abierta")
        account = runner.accounts[("tg_100123", Decimal("100"))]
        self.assertIn("BTCUSDT", account.positions)
        self.assertEqual(runner.strategies[0].label, "Telegram · Señales VIP")
        self.assertTrue(telegram.apply_signal(-100123, "x", {"symbol": "PEPEUSDT", "side": "LONG", "stop": 1}, runner).startswith("par no seguido"))


if __name__ == "__main__":
    unittest.main()
