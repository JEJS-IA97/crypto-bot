"""Mensajes de canales de opciones binarias (Quotex, Pocket Option): señal, resultado o informe.

Formatos vistos: "USD/MXN (OTC) • ARRIBA • 10:30 · M5 · 2 reentradas",
"Activo: USD/COP (OTC) · Señal: 10:06 - ABAJO · 1º GALE", "AUDCAD · M1 · 10:30:00 · call",
resultados sueltos ("WIN ✅", "✖️ Loss", "GANADA EN EL MARTINGALA 2") e informes del día
("USD/PKR • 07:45 ✔️ … Marcador 28 x 8").
"""

from __future__ import annotations

import re

CURRENCIES = (
    "USD EUR GBP JPY CHF CAD AUD NZD MXN ARS COP BRL CLP PEN PKR NGN INR TRY ZAR SGD HKD CNY CNH "
    "RUB PHP IDR THB KES EGP BDT DZD MAD VND MYR UAH SAR AED QAR KWD BHD OMR JOD LBP TND YER "
    "SEK NOK DKK PLN HUF CZK ILS KRW XAU XAG"
).split()
_CUR = "|".join(CURRENCIES)
ASSET = re.compile(rf"\b({_CUR})\s*/?\s*({_CUR})\b(\s*[\(\-]?\s*OTC\)?)?", re.I)
UP = re.compile(r"\b(ARRIBA|CALL|UP|COMPRA)\b|🔼|⬆️|⬆", re.I)
DOWN = re.compile(r"\b(ABAJO|PUT|DOWN|VENTA)\b|🔽|⬇️|⬇", re.I)
TIME = re.compile(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm)?", re.I)
TZ = re.compile(r"UTC\s*([+-])\s*0?(\d{1,2})", re.I)
EXPIRY = re.compile(r"\bM(\d{1,2})\b|(\d{1,2})\s*minutos?", re.I)
GALES = re.compile(r"(\d)\s*(?:reentradas?|gales?|martingalas?)|(\d)º?\s*GALE", re.I)
WIN = re.compile(r"\b(WIN|GANADA|GANAMOS|PROFIT RECUPERADO)\b|✅|✔️|🟩", re.I)
LOSS = re.compile(r"\b(LOSS|PERDIDA|PÉRDIDA)\b|✖️|❌|no lleg[óo]|otro rumbo", re.I)
SCORE = re.compile(r"(\d+)\s*[x×]\s*(\d+)", re.I)
GALE_WIN = re.compile(r"(?:MARTINGALA|GALE)\s*(\d)", re.I)


def _asset(match: re.Match) -> tuple[str, bool]:
    return f"{match.group(1).upper()}/{match.group(2).upper()}", bool(match.group(3))


def _hhmm(match: re.Match) -> str:
    hour, minute, ampm = int(match.group(1)), match.group(2), (match.group(3) or "").lower()
    hour += 12 if ampm == "pm" and hour < 12 else 0
    return f"{hour % 24:02d}:{minute}"


def parse_report(text: str) -> dict | None:
    """Informe con varias líneas 'activo · hora · ✅/❌'."""
    items = []
    for line in text.splitlines():
        asset, when = ASSET.search(line), TIME.search(line)
        if not (asset and when):
            continue
        result = "loss" if LOSS.search(line) else "win" if WIN.search(line) else None
        if result:
            name, otc = _asset(asset)
            items.append({"asset": name, "otc": otc, "time": _hhmm(when), "result": result})
    if len(items) < 2:
        return None
    return {
        "kind": "informe",
        "items": items,
        "wins": sum(i["result"] == "win" for i in items),
        "losses": sum(i["result"] == "loss" for i in items),
    }


def parse_binary(text: str) -> dict | None:
    """Mensaje → {"kind": "binaria" | "resultado" | "informe", ...} o None si es promoción."""
    if not text or not text.strip():
        return None
    report = parse_report(text)
    if report:
        return report
    asset = ASSET.search(text)
    when = TIME.search(text)
    direction = "DOWN" if DOWN.search(text) else "UP" if UP.search(text) else None
    if asset and when and direction:
        name, otc = _asset(asset)
        tz, expiry, gales = TZ.search(text), EXPIRY.search(text), GALES.findall(text)
        offset = int(tz.group(2)) * (1 if tz.group(1) == "+" else -1) if tz else -3
        return {
            "kind": "binaria",
            "asset": name,
            "otc": otc,
            "direction": direction,
            "time": _hhmm(when),
            "utc_offset": offset,
            "expiry_min": int(expiry.group(1) or expiry.group(2)) if expiry else None,
            "gales": max((int(a or b) for a, b in gales), default=0),
            "broker": "Pocket Option" if "POCKET" in text.upper() else "Quotex" if "QUOTEX" in text.upper() else None,
        }
    short = len(text) < 160
    score = SCORE.search(text)
    if score and re.search(r"resultado|marcador|finalizamos|sesi[óo]n", text, re.I):
        return {"kind": "informe", "items": [], "wins": int(score.group(1)), "losses": int(score.group(2))}
    if short and LOSS.search(text):
        return {"kind": "resultado", "result": "loss"}
    if short and WIN.search(text) and not re.search(r"@|clic|cupos|acceso", text, re.I):
        gale = GALE_WIN.search(text)
        return {"kind": "resultado", "result": f"win gale {gale.group(1)}" if gale else "win"}
    return None


def describe(parsed: dict | None) -> str:
    """Texto corto para el panel."""
    if not parsed:
        return "no es señal"
    kind = parsed.get("kind")
    if kind == "binaria":
        arrow = "↑ CALL" if parsed["direction"] == "UP" else "↓ PUT"
        extra = f" · M{parsed['expiry_min']}" if parsed.get("expiry_min") else ""
        gales = f" · {parsed['gales']} gale" if parsed.get("gales") else ""
        otc = " · OTC" if parsed["otc"] else ""  # OTC = precio del broker, no verificable
        return f"binaria {parsed['asset']} {arrow} {parsed['time']}{extra}{gales}{otc}"[:60]  # outcome es String(60)
    if kind == "resultado":
        return f"resultado autoreportado: {parsed['result']}"
    if kind == "informe":
        return f"informe autoreportado: {parsed['wins']} ganadas / {parsed['losses']} perdidas"
    return "señal cripto"
