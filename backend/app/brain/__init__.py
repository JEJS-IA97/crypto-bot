"""Cerebro del bot: un analista que cada 4 h estudia el torneo y escribe.

Lee el ranking del laboratorio (en vivo y backtest), el régimen de mercado y
las últimas operaciones; saca conclusiones estadísticas por su cuenta y,
si hay un modelo disponible en OmniRoute, le pide además un análisis de
trader senior con hipótesis nuevas. Todo queda en `docs/brain/` (diario e
hipótesis en Markdown) para que graphify lo indexe y sobreviva a cualquier
suscripción. Nunca cambia código ni abre operaciones.
"""
