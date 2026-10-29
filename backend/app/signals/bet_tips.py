"""Pronósticos deportivos que llegan por Telegram → seguimiento en paper (1 unidad por pick).

Se guarda el pick ANTES del partido (equipos, mercado, cuota). El resultado sale de la respuesta
del propio canal (✅/❌ respondiendo al pick); por eso se cuenta aparte cuántos picks nunca
reportaron: un canal que solo publica sus aciertos queda en evidencia.
"""

from __future__ import annotations

import re

ODDS = re.compile(r"(?:@|cuota|odds|momio)\s*:?\s*(\d{1,2}[.,]\d{1,3})", re.I)
VERSUS = re.compile(r"([A-Za-zÀ-ÿ0-9.'&\- ]{3,40}?)\s+(?:vs\.?|v\.?|contra|-|–)\s+([A-Za-zÀ-ÿ0-9.'&\- ]{3,40})", re.I)
PICK = re.compile(r"(?:pick|pron[oó]stico|apuesta|selecci[oó]n|mercado|tip)\s*:?\s*(.{2,80})", re.I)
WIN = re.compile(r"(✅|🟢|\bganad[ao]\b|\bgreen\b|\bwin\b|\bacertad[ao]\b)", re.I)
LOSS = re.compile(r"(❌|🔴|\bperdid[ao]\b|\bred\b|\bloss\b|\bfallad[ao]\b)", re.I)
VOID = re.compile(r"(\bnul[ao]\b|\bvoid\b|\bpush\b|\breembols)", re.I)


def parse_tip(text: str) -> dict | None:
    """Mensaje → {"kind": "apuesta", partido, pick, cuota} o None."""
    if not text:
        return None
    odds = ODDS.search(text)
    match = VERSUS.search(text)
    if not odds or not match:
        return None
    value = float(odds.group(1).replace(",", "."))
    if not 1.01 <= value <= 50:
        return None
    pick = PICK.search(text)
    return {
        "kind": "apuesta",
        "partido": f"{match.group(1).strip()} vs {match.group(2).strip()}"[:100],
        "pick": (pick.group(1).strip() if pick else text.strip().splitlines()[0])[:100],
        "cuota": value,
    }


def result_of(text: str) -> str | None:
    """Respuesta del canal a un pick: ganada / perdida / nula (None si no dice)."""
    if not text:
        return None
    if VOID.search(text):
        return "nula"
    win, loss = WIN.search(text), LOSS.search(text)
    if win and not loss:
        return "ganada"
    if loss and not win:
        return "perdida"
    return None


def channel_bets(rows: list[dict]) -> dict:
    """Resumen de los picks de un canal (cada fila es `parsed` de un mensaje tipo apuesta)."""
    picks = [r for r in rows if r.get("kind") == "apuesta"]
    won = [r for r in picks if r.get("resultado") == "ganada"]
    lost = [r for r in picks if r.get("resultado") == "perdida"]
    settled = len(won) + len(lost)
    units = sum(r["cuota"] - 1 for r in won) - len(lost)
    return {
        "picks": len(picks),
        "con_resultado": settled,
        "sin_reportar": len(picks) - settled - sum(1 for r in picks if r.get("resultado") == "nula"),
        "acierto": round(len(won) / settled * 100, 1) if settled else None,
        "cuota_media": round(sum(r["cuota"] for r in picks) / len(picks), 2) if picks else None,
        "unidades": round(units, 2),
        "roi": round(units / settled * 100, 1) if settled else None,
    }
