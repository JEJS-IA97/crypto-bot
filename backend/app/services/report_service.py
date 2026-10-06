"""Informe diario para el correo (spec 002 RF-3/RF-5; spec 004 HTML).

Fuente única de datos: `_collect_report` devuelve `ReportData` y dos
renderers lo consumen — `build_daily_report` (texto plano, contrato de la
spec 002 sin cambios) y `build_daily_report_html` (HTML con el diseño del
panel, spec 004). Todas las secciones están siempre presentes en ambas
salidas; cuando la fuente de datos no existe (sin cuenta de paper, sin fila
de riesgo, sin decisiones) se muestra «sin datos» en lugar de fallar,
porque el informe tiene que salir aunque el bot esté vacío, detenido o
bloqueado (RF-5). Ningún valor pasa por `float` (constitución #11): las
métricas llegan ya cuantizadas con `money()` (8 decimales) desde
`decision_store.get_metrics` (RF-17). El renderer HTML escapa todo valor
dinámico con `html.escape` (spec 004, RF-4).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.risk_math import MAX_OPEN_POSITIONS
from app.models import (
    BotRuntime,
    DecisionStatus,
    SignalDecision,
    SimulationBalance,
    utc_now,
)
from app.services.decision_store import get_metrics
from app.services.phase_service import get_phase
from app.services.risk_guard_service import MAX_OPENS_PER_DAY, get_runtime

_EXECUTED_STATUSES = frozenset(
    {
        DecisionStatus.OPENED,
        DecisionStatus.CLOSED,
    }
)

# Paleta de design.json (misma que el panel, spec 004 RF-3).
_BG = "#1d1e21"
_CARD = "#202124"
_DIVIDER = "#303236"
_LABEL = "#929292"
_TEXT = "#f2f2f2"
_ACCENT = "#27e7cf"
_POSITIVE = "#21d99b"
_NEGATIVE = "#ff4d5a"
_MONO = (
    "font-family:Menlo,Consolas,'Courier New',monospace;"
    "font-variant-numeric:tabular-nums;"
)
_SANS = (
    "font-family:Inter,-apple-system,BlinkMacSystemFont,"
    "'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
)


@dataclass(frozen=True)
class ReportSummary:
    """Recuento de las últimas 24 h, ya agregado (spec 004 D-1)."""

    total: int
    executed: int
    rejected: int
    pending: int
    errors: int
    reasons: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ReportData:
    """Datos del informe, independientes del formato de salida."""

    day: str
    phase: str
    state: str
    metrics: dict[str, Any] | None
    summary: ReportSummary | None
    breaker_active: bool
    breaker_reason: str | None


def build_daily_report(
    db: Session,
    *,
    account_id: int | None = None,
    now: datetime | None = None,
) -> str:
    """Compone el informe del día (texto plano en español, UTF-8).

    `account_id` por defecto es la cuenta de paper-trading y `now` el
    instante UTC actual; ambos son parámetros para poder testear.
    """
    data = _collect_report(db, account_id=account_id, now=now)
    lines = [
        f"Informe diario — crypto-bot — {data.day} (UTC)",
        f"Fase: {data.phase}",
        f"Estado: {data.state}",
        *_balance_and_pnl_lines(data.metrics),
        _daily_line(data.metrics),
        _summary_text(data.summary),
        _breaker_text(data.breaker_active, data.breaker_reason),
    ]
    return "\n".join(lines)


def build_daily_report_html(
    db: Session,
    *,
    account_id: int | None = None,
    now: datetime | None = None,
) -> str:
    """Compone el informe del día en HTML con el diseño del panel.

    Mismos datos que `build_daily_report` (spec 004 RF-2): CSS inline y
    valores escapados, sin JS ni hojas externas (RF-3, RF-4).
    """
    data = _collect_report(db, account_id=account_id, now=now)
    return _render_html(data)


def _collect_report(
    db: Session,
    *,
    account_id: int | None,
    now: datetime | None,
) -> ReportData:
    account = (
        account_id
        if account_id is not None
        else settings.simulation_bot_account_id
    )
    moment = now if now is not None else utc_now()

    phase = get_phase(db)
    runtime = get_runtime(db)
    balance = db.scalar(
        select(SimulationBalance).where(
            SimulationBalance.account_id == account
        )
    )
    metrics = (
        get_metrics(db, account_id=account, day=moment.date())
        if balance is not None
        else None
    )
    return ReportData(
        day=moment.strftime("%Y-%m-%d"),
        phase=phase.phase.value,
        state=_state_text(runtime),
        metrics=metrics,
        summary=_collect_summary(db, moment),
        breaker_active=runtime.breaker_active,
        breaker_reason=runtime.breaker_reason,
    )


def _num(value: Decimal) -> str:
    """Formatea un `Decimal` en notación fija sin pasar por `float`.

    `money()` devuelve `Decimal('0E-8')` para el cero, cuyo `str` sería
    «0E-8»; con `f` sale «0.00000000» (constitución #11).
    """
    return format(value, "f")


def _state_text(runtime: BotRuntime) -> str:
    """activo | detenido | bloqueado (motivo): el breaker manda sobre `running`."""
    if runtime.breaker_active:
        reason = runtime.breaker_reason or "circuito abierto"
        return f"bloqueado ({reason})"
    if not runtime.running:
        return "detenido"
    return "activo"


def _balance_and_pnl_lines(
    metrics: dict[str, Any] | None,
) -> list[str]:
    if metrics is None:
        return [
            "Balance: sin datos",
            "PnL: sin datos",
        ]
    return [
        (
            "Balance: "
            f"disponible {_num(metrics['available_usd'])} USDT | "
            f"posiciones {_num(metrics['market_value_usd'])} USDT | "
            f"total {_num(metrics['balance_usd'])} USDT"
        ),
        (
            "PnL: "
            f"realizado {_num(metrics['realized_pnl_usd'])} USDT | "
            f"no realizado {_num(metrics['unrealized_pnl_usd'])} USDT | "
            f"drawdown {_num(metrics['drawdown_pct'])}%"
        ),
    ]


def _daily_line(metrics: dict[str, Any] | None) -> str:
    if metrics is None:
        return "Día UTC: sin datos"
    if metrics["daily_blocked"]:
        reason = metrics["block_reason"]
        detail = (
            f"(bloqueado: sí — {reason})"
            if reason
            else "(bloqueado: sí)"
        )
    else:
        detail = "(bloqueado: no)"
    return (
        f"Día UTC: pérdida {_num(metrics['daily_loss_usd'])} USDT {detail} | "
        f"aperturas {metrics['opens_today']}/{MAX_OPENS_PER_DAY} | "
        f"posiciones abiertas {metrics['open_positions']}/{MAX_OPEN_POSITIONS}"
    )


def _collect_summary(db: Session, moment: datetime) -> ReportSummary | None:
    """Recuento de las últimas 24 h: estados y motivos de rechazo."""
    since = moment - timedelta(hours=24)
    recent = list(
        db.scalars(
            select(SignalDecision)
            .where(SignalDecision.created_at >= since)
            .order_by(
                SignalDecision.created_at.asc(),
                SignalDecision.id.asc(),
            )
        ).all()
    )
    if not recent:
        return None

    reasons: Counter[str] = Counter(
        decision.rejection_reason
        for decision in recent
        if decision.status == DecisionStatus.REJECTED
        and decision.rejection_reason
    )
    ordered = tuple(
        sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
    )
    return ReportSummary(
        total=len(recent),
        executed=sum(
            1 for decision in recent if decision.status in _EXECUTED_STATUSES
        ),
        rejected=sum(
            1
            for decision in recent
            if decision.status == DecisionStatus.REJECTED
        ),
        pending=sum(
            1
            for decision in recent
            if decision.status == DecisionStatus.PENDING
        ),
        errors=sum(
            1
            for decision in recent
            if decision.status == DecisionStatus.ERROR
        ),
        reasons=ordered,
    )


def _summary_text(summary: ReportSummary | None) -> str:
    if summary is None:
        return "Últimas 24 h: sin datos (0 decisiones)"

    noun = "decisión" if summary.total == 1 else "decisiones"
    line = (
        f"Últimas 24 h: {summary.total} {noun} — "
        f"ejecutadas {summary.executed}, rechazadas {summary.rejected}, "
        f"pendientes {summary.pending}, con error {summary.errors}"
    )
    if summary.reasons:
        joined = ", ".join(
            f"{reason} ({count})" for reason, count in summary.reasons
        )
        line += f" — motivos: {joined}"
    return line


def _breaker_text(active: bool, reason: str | None) -> str:
    if active:
        return f"Breaker: activo ({reason or 'sin motivo'})"
    return "Breaker: inactivo"


# ============================================================
# Renderer HTML (spec 004): CSS inline, 600 px, sin JS.
# ============================================================


def _e(value: Any) -> str:
    """Escapa un valor para insertarlo en el HTML (spec 004, RF-4)."""
    return escape(str(value), quote=True)


def _state_color(state: str) -> str:
    if state.startswith("bloqueado"):
        return _NEGATIVE
    if state == "detenido":
        return _LABEL
    return _POSITIVE


def _html_row(
    label: str,
    value: str,
    color: str,
    *,
    last: bool = False,
) -> str:
    border = "" if last else f"border-bottom:1px solid {_DIVIDER};"
    return (
        "<tr>"
        f'<td style="padding:10px 0;{border}color:{_LABEL};'
        f'font-size:13px;">{_e(label)}</td>'
        f'<td align="right" style="padding:10px 0;{border}color:{color};'
        f'font-size:13px;font-weight:650;{_MONO}">{_e(value)}</td>'
        "</tr>"
    )


def _html_card(title: str, rows: str, extra: str = "") -> str:
    return (
        '<tr><td style="padding:0 0 16px;">'
        f'<div style="background:{_CARD};border-radius:16px;'
        'padding:0 20px 14px;">'
        f'<div style="color:{_TEXT};font-size:14px;font-weight:650;'
        'padding:16px 0 6px;">'
        f"{_e(title)}</div>"
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" style="width:100%;border-collapse:collapse;">'
        f"{rows}</table>"
        f"{extra}"
        "</div></td></tr>"
    )


def _render_html(data: ReportData) -> str:
    metrics = data.metrics
    cards = [
        _html_card(
            "Bot",
            _html_row(
                "Estado", data.state, _state_color(data.state), last=True
            ),
        )
    ]

    if metrics is None:
        empty = _html_row("Datos", "sin datos", _LABEL, last=True)
        cards.append(_html_card("Balance", empty))
        cards.append(_html_card("PnL", empty))
        cards.append(_html_card("Día UTC", empty))
    else:
        balance_rows = (
            _html_row(
                "Disponible",
                f"{_num(metrics['available_usd'])} USDT",
                _TEXT,
            )
            + _html_row(
                "Posiciones",
                f"{_num(metrics['market_value_usd'])} USDT",
                _TEXT,
            )
            + _html_row(
                "Total",
                f"{_num(metrics['balance_usd'])} USDT",
                _TEXT,
                last=True,
            )
        )
        cards.append(_html_card("Balance", balance_rows))

        realized = _num(metrics["realized_pnl_usd"])
        unrealized = _num(metrics["unrealized_pnl_usd"])
        drawdown = _num(metrics["drawdown_pct"])
        drawdown_color = (
            _NEGATIVE if metrics["drawdown_pct"] != 0 else _LABEL
        )
        pnl_rows = (
            _html_row(
                "Realizado",
                f"{realized} USDT",
                _NEGATIVE if metrics["realized_pnl_usd"] < 0 else _POSITIVE,
            )
            + _html_row(
                "No realizado",
                f"{unrealized} USDT",
                (
                    _NEGATIVE
                    if metrics["unrealized_pnl_usd"] < 0
                    else _POSITIVE
                ),
            )
            + _html_row(
                "Drawdown",
                f"{drawdown}%",
                drawdown_color,
                last=True,
            )
        )
        cards.append(_html_card("PnL", pnl_rows))

        if metrics["daily_blocked"]:
            reason = metrics["block_reason"]
            block_text = f"sí — {reason}" if reason else "sí"
            block_color = _NEGATIVE
        else:
            block_text = "no"
            block_color = _TEXT
        loss = _num(metrics["daily_loss_usd"])
        daily_rows = (
            _html_row(
                "Pérdida",
                f"{loss} USDT",
                _NEGATIVE if metrics["daily_loss_usd"] != 0 else _LABEL,
            )
            + _html_row("Bloqueado", block_text, block_color)
            + _html_row(
                "Aperturas",
                f"{metrics['opens_today']}/{MAX_OPENS_PER_DAY}",
                _TEXT,
            )
            + _html_row(
                "Posiciones abiertas",
                f"{metrics['open_positions']}/{MAX_OPEN_POSITIONS}",
                _TEXT,
                last=True,
            )
        )
        cards.append(_html_card("Día UTC", daily_rows))

    summary = data.summary
    if summary is None:
        summary_rows = _html_row(
            "Decisiones",
            "sin datos (0 decisiones)",
            _LABEL,
            last=True,
        )
        cards.append(_html_card("Últimas 24 h", summary_rows))
    else:
        summary_rows = (
            _html_row("Decisiones", str(summary.total), _TEXT)
            + _html_row("Ejecutadas", str(summary.executed), _POSITIVE)
            + _html_row("Rechazadas", str(summary.rejected), _NEGATIVE)
            + _html_row("Pendientes", str(summary.pending), _LABEL)
            + _html_row(
                "Con error",
                str(summary.errors),
                _NEGATIVE,
                last=True,
            )
        )
        reasons_extra = ""
        if summary.reasons:
            joined = ", ".join(
                f"{_e(reason)} ({count})"
                for reason, count in summary.reasons
            )
            reasons_extra = (
                f'<div style="padding-top:10px;color:{_LABEL};'
                f'font-size:12px;">Motivos de rechazo: {joined}</div>'
            )
        cards.append(
            _html_card("Últimas 24 h", summary_rows, reasons_extra)
        )

    if data.breaker_active:
        breaker_value = f"activo ({data.breaker_reason or 'sin motivo'})"
        breaker_color = _NEGATIVE
    else:
        breaker_value = "inactivo"
        breaker_color = _LABEL
    cards.append(
        _html_card(
            "Breaker",
            _html_row("Circuito", breaker_value, breaker_color, last=True),
        )
    )

    header = (
        '<tr><td style="padding:0 0 16px;border-bottom:1px solid '
        f'{_DIVIDER};">'
        f'<div style="color:{_ACCENT};font-size:11px;font-weight:700;'
        "letter-spacing:0.14em;text-transform:uppercase;"
        '">Informe diario</div>'
        f'<div style="color:{_TEXT};font-size:26px;font-weight:750;'
        "letter-spacing:-0.02em;padding-top:8px;"
        f'">crypto-bot — {_e(data.day)} '
        f'<span style="color:{_LABEL};font-weight:400;">(UTC)</span></div>'
        '<div style="padding-top:12px;">'
        f'<span style="display:inline-block;padding:4px 12px;'
        f"border:1px solid {_ACCENT};border-radius:999px;"
        f"color:{_ACCENT};font-size:11px;font-weight:700;"
        f'letter-spacing:0.08em;">{_e(data.phase)}</span>'
        "</div></td></tr>"
    )
    spacer = (
        '<tr><td style="height:20px;font-size:0;line-height:0;">'
        "&nbsp;</td></tr>"
    )
    footer = (
        f'<tr><td style="padding:4px 0 0;color:{_LABEL};'
        'font-size:11px;line-height:1.5;">'
        "crypto-bot · informe automático a las 08:00 UTC · valores en "
        "USDT · copia en texto plano incluida por compatibilidad."
        "</td></tr>"
    )

    body_rows = header + spacer + "".join(cards) + footer
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, '
        'initial-scale=1">\n'
        f"<title>Informe diario — crypto-bot — {_e(data.day)} (UTC)"
        "</title>\n"
        "</head>\n"
        f'<body style="margin:0;padding:0;background:{_BG};">\n'
        '<table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" border="0" style="width:100%;background:{_BG};'
        'border-collapse:collapse;">\n'
        '<tr><td align="center" style="padding:32px 16px;">\n'
        '<table role="presentation" width="600" cellpadding="0" '
        'cellspacing="0" border="0" style="width:100%;max-width:600px;'
        f"border-collapse:collapse;{_SANS}\">\n"
        f"{body_rows}\n"
        "</table>\n"
        "</td></tr>\n"
        "</table>\n"
        "</body>\n"
        "</html>"
    )
