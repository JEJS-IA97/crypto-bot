"""Analista del cerebro: contexto → conclusiones propias → LLM (OmniRoute) → Markdown."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app import database
from app.config import settings
from app.lab import live, store
from app.lab.backtest import REPORT_JSON
from app.lab.models import LabTrade
from app.lab.strategies import STRATEGIES

logger = logging.getLogger(__name__)

LABELS = {s.name: s.label for s in STRATEGIES}
ANSI = re.compile(r"\x1b\[[0-9;]*m")
STARTUP_DELAY_SECONDS = 120

SYSTEM = (
    "Eres un trader e inversor senior de criptomonedas que supervisa un torneo de "
    "estrategias en paper trading (Binance, comisión 0,10 % por lado, longs y shorts, "
    "cuentas de 20, 50 y 100 USD). Analiza los datos con rigor estadístico: no "
    "confundas suerte con ventaja (pocas operaciones = poca evidencia), ten en cuenta "
    "comisiones y régimen de mercado (tendencia/rango, volatilidad). No inventes datos. "
    "Responde SOLO con un objeto JSON válido, en español, con estas claves: "
    '"resumen" (máx. 6 frases), "alertas" (lista de frases cortas), '
    '"hipotesis" (lista de objetos {"titulo", "razon", "como_probar"}; como_probar debe '
    "ser una variante concreta y medible de una estrategia o filtro de régimen que se "
    "pueda añadir al torneo)."
)


# --- contexto ---------------------------------------------------------------


def _backtest() -> dict | None:
    path = Path(REPORT_JSON)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def gather_context(db, hours: int) -> dict[str, Any]:
    since_ms = int((time.time() - hours * 3600) * 1000)
    recent = db.scalars(
        select(LabTrade).where(LabTrade.status == "CLOSED", LabTrade.closed_ts >= since_ms)
    ).all()
    open_count = len(db.scalars(select(LabTrade).where(LabTrade.status == "OPEN")).all())
    return {
        "feed": live.runner.status() if live.runner else None,
        "live": store.leaderboard(db, LABELS),
        "backtest": _backtest(),
        "recent": [
            {
                "estrategia": LABELS.get(t.strategy, t.strategy),
                "capital": float(t.capital),
                "par": t.symbol,
                "lado": t.side,
                "pnl": float(t.pnl),
                "r": float(t.r_multiple) if t.r_multiple is not None else None,
                "motivo": t.reason,
                "regimen": t.regime,
            }
            for t in recent
        ],
        "open_positions": open_count,
        "hours": hours,
    }


# --- conclusiones propias (sin LLM) ----------------------------------------


def best_by_regime(backtest: dict | None, min_trades: int = 10) -> dict[str, tuple[str, float, int]]:
    """Por régimen: la estrategia con mejor esperanza en el backtest (cuentas de 100)."""
    if not backtest:
        return {}
    best: dict[str, tuple[str, float, int]] = {}
    for row in backtest["rows"]:
        if row["capital"] != 100:
            continue
        for regime, stats in (row.get("by_regime") or {}).items():
            if stats["trades"] < min_trades:
                continue
            current = best.get(regime)
            if current is None or stats["expectancy"] > current[1]:
                best[regime] = (row["label"], stats["expectancy"], stats["trades"])
    return best


def findings(ctx: dict[str, Any]) -> list[str]:
    out: list[str] = []
    live_rows = ctx["live"]
    total = sum(r["trades"] for r in live_rows)
    out.append(
        f"Torneo en vivo: {total} operaciones cerradas en total, "
        f"{len(ctx['recent'])} en las últimas {ctx['hours']} h y {ctx['open_positions']} abiertas."
    )
    ranked = [r for r in live_rows if r["trades"] >= 3]
    if ranked:
        top = max(ranked, key=lambda r: r["return_pct"])
        low = min(ranked, key=lambda r: r["return_pct"])
        out.append(
            f"Mejor cuenta en vivo: {top['label']} ({top['capital']:.0f} USD) {top['return_pct']:+.2f} % "
            f"en {top['trades']} trades; peor: {low['label']} ({low['capital']:.0f} USD) "
            f"{low['return_pct']:+.2f} % en {low['trades']} trades."
        )
    else:
        out.append("Aún no hay cuentas con 3 o más operaciones cerradas: muy poca evidencia en vivo.")
    for r in live_rows:
        if r["trades"] >= 20 and (r["expectancy_r"] or 0) < -0.2:
            out.append(
                f"Alerta: {r['label']} ({r['capital']:.0f} USD) pierde {r['expectancy_r']} R por trade "
                f"tras {r['trades']} operaciones en vivo."
            )
    fees = sum(r["fees"] for r in live_rows)
    net = sum(r["net_pnl"] for r in live_rows)
    if total:
        out.append(f"Comisiones pagadas en vivo: {fees:.2f} USD frente a un PnL neto de {net:+.2f} USD.")
    best = best_by_regime(ctx["backtest"])
    regimes = (ctx["feed"] or {}).get("regimes", {})
    for symbol, regime in regimes.items():
        if regime in best:
            label, expectancy, n = best[regime]
            if expectancy > 0:
                verdict = f"la mejor estrategia en ese régimen fue {label}"
            else:
                verdict = f"ninguna estrategia ganó en ese régimen; la menos mala fue {label}"
            out.append(
                f"{symbol} está en régimen «{regime}»: en el backtest {verdict} "
                f"({expectancy:+.4f} USD por trade, n={n})."
            )
    return out


# --- LLM vía OmniRoute ------------------------------------------------------


def _compact(ctx: dict[str, Any]) -> dict[str, Any]:
    keep = ("label", "capital", "trades", "win_rate", "profit_factor", "expectancy_r", "return_pct", "max_dd_pct", "fees")
    backtest = ctx["backtest"] or {}
    return {
        "regimenes_actuales": (ctx["feed"] or {}).get("regimes"),
        "precios": (ctx["feed"] or {}).get("prices"),
        "ranking_vivo": [{k: r.get(k) for k in keep} for r in ctx["live"] if r["trades"]],
        "backtest_365d": [
            {k: r.get(k) for k in keep} for r in backtest.get("rows", []) if r["capital"] == 100
        ],
        "mejor_por_regimen_backtest": best_by_regime(ctx["backtest"]),
        "operaciones_recientes": ctx["recent"][-40:],
    }


def parse_json(text: str) -> dict | None:
    text = ANSI.sub("", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except ValueError:
        return None


def ask_llm(ctx: dict[str, Any], notes: list[str]) -> tuple[dict | None, str]:
    """Devuelve (respuesta, error). Usa la CLI de OmniRoute (token local de la máquina).

    shortcut: CLI en vez de HTTP para no gestionar una API key de OmniRoute;
    pasar a /v1/chat/completions con BRAIN key si el bot corre en otra máquina.
    """
    command = shutil.which(settings.brain_command)
    if command is None:
        return None, f"no se encontró '{settings.brain_command}' en el PATH"
    prompt = (
        f"{SYSTEM}\n\nCONCLUSIONES DEL SISTEMA:\n- " + "\n- ".join(notes)
        + "\n\nDATOS (JSON):\n" + json.dumps(_compact(ctx), ensure_ascii=False, default=str)
    )
    try:
        result = subprocess.run(
            [command, "chat", "--no-history", "-m", settings.brain_model, "--max-tokens", "2000", "--stdin"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.brain_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return None, "el modelo no respondió a tiempo"
    output = ANSI.sub("", result.stdout + result.stderr)
    parsed = parse_json(result.stdout)
    if result.returncode != 0 or parsed is None:
        error = next((line for line in output.splitlines() if "✖" in line or "error" in line.lower()), output[-300:])
        return None, error.strip()[:300]
    return parsed, ""


# --- escritura ------------------------------------------------------------


README = """# Cerebro del bot

Memoria escrita por el analista automático (cada {hours} h). No es código: es lo que el
bot "piensa" y aprende del torneo de estrategias del laboratorio.

- `diario/AAAA-MM-DD.md`: una entrada por análisis (régimen, datos, lectura del LLM).
- `hipotesis.md`: ideas nuevas a probar como variantes del torneo (nunca se aplican solas).

graphify indexa esta carpeta para que cualquier agente (Claude, opencode, Gemini) pueda
consultar lo aprendido aunque cambie la suscripción.
"""


def write_entry(directory: Path, now: datetime, notes: list[str], ctx: dict, answer: dict | None, error: str) -> Path:
    diary = directory / "diario"
    diary.mkdir(parents=True, exist_ok=True)
    readme = directory / "README.md"
    if not readme.exists():
        readme.write_text(README.format(hours=settings.brain_interval_hours), encoding="utf-8")
    regimes = (ctx["feed"] or {}).get("regimes", {})
    lines = [f"\n## {now:%H:%M} UTC\n"]
    if regimes:
        lines.append("**Régimen:** " + " · ".join(f"{s.replace('USDT', '')}: {r}" for s, r in regimes.items()) + "\n")
    lines.append("### Lo que dicen los datos\n")
    lines += [f"- {n}" for n in notes]
    lines.append("\n### Lectura del analista (LLM)\n")
    if answer:
        lines.append(str(answer.get("resumen", "")).strip())
        alerts = answer.get("alertas") or []
        if alerts:
            lines.append("\n**Alertas:**")
            lines += [f"- {a}" for a in alerts]
        hypotheses = answer.get("hipotesis") or []
        if hypotheses:
            lines.append("\n**Hipótesis nuevas:** ver [[hipotesis]].")
    else:
        lines.append(f"_LLM no disponible ({error}). Solo conclusiones estadísticas._")
    path = diary / f"{now:%Y-%m-%d}.md"
    if not path.exists():
        path.write_text(f"# Diario del cerebro — {now:%Y-%m-%d}\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    if answer:
        _append_hypotheses(directory / "hipotesis.md", now, answer.get("hipotesis") or [])
    return path


def _append_hypotheses(path: Path, now: datetime, items: list) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Hipótesis del cerebro\n\nIdeas a probar en el torneo. Estado inicial: pendiente.\n"
    new = []
    for item in items:
        if not isinstance(item, dict) or not item.get("titulo"):
            continue
        title = str(item["titulo"]).strip()
        if f"### {title}" in existing:
            continue
        new.append(
            f"\n### {title}\n- Fecha: {now:%Y-%m-%d %H:%M} UTC · Estado: pendiente\n"
            f"- Por qué: {item.get('razon', '')}\n- Cómo probarla: {item.get('como_probar', '')}\n"
        )
    if new or not path.exists():
        path.write_text(existing + "".join(new), encoding="utf-8")


# --- orquestación ---------------------------------------------------------


def run_once(session_factory=None, now: datetime | None = None) -> Path:
    now = now or datetime.now(timezone.utc)
    factory = session_factory or database.SessionLocal
    with factory() as db:
        ctx = gather_context(db, settings.brain_interval_hours)
    notes = findings(ctx)
    answer, error = ask_llm(ctx, notes)
    path = write_entry(Path(settings.brain_dir), now, notes, ctx, answer, error)
    (Path(settings.brain_dir) / ".ultima-corrida").write_text(now.isoformat(), encoding="utf-8")
    logger.info("brain: entry written to %s (llm=%s)", path, "ok" if answer else error)
    return path


def seconds_until_due(now: float | None = None) -> float:
    marker = Path(settings.brain_dir) / ".ultima-corrida"
    if not marker.exists():
        return 0
    last = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip()).timestamp()
    return max(0.0, last + settings.brain_interval_hours * 3600 - (now or time.time()))


async def brain_loop(stop_event) -> None:
    """Cada `brain_interval_hours` (respeta la última corrida aunque el bot se reinicie)."""
    try:  # da tiempo al feed en vivo a conectar y conocer el régimen
        await asyncio.wait_for(stop_event.wait(), timeout=STARTUP_DELAY_SECONDS)
    except TimeoutError:
        pass
    while not stop_event.is_set():
        wait = seconds_until_due()
        if wait <= 0:
            try:
                await asyncio.to_thread(run_once)
            except Exception:
                logger.exception("brain: analysis failed")
            wait = settings.brain_interval_hours * 3600
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=min(wait, 600))
        except TimeoutError:
            pass

