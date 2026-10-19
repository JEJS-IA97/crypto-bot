# Spec 014 — Cerebro que aprende, señales de Telegram y sala de control

Pedido directo de José (2026-10-19), que tiene prioridad sobre el flujo por fases.
Todo opera en paper: nada de esto toca dinero real (constitución #4 y #5 intactas).

## Qué se construyó
- **Cerebro que aprende** (`app/brain/evolve.py`): cada 4 h propone estrategias
  (mutaciones de las ganadoras, familias al azar ponderadas por su tasa de
  aprobación e ideas de Gemini), las examina con 75 % del histórico para entrenar
  y el 25 % más reciente como examen fuera de muestra (comisiones, slippage,
  Monte Carlo p95 ≤ 35 %, dos vecinos de parámetros, sin clones). Las que
  aprueban entran al torneo con 100 USD. En vivo: tras 15 trades, la que pierde
  se retira; las fijas con 30+ trades y esperanza < −0,1 R van a la banca.
  Todo queda en `brain_genomes` y en `docs/brain/memoria.md`, que se le pasa a
  Gemini en el siguiente ciclo. Gemini ya no pasa por OmniRoute.
- **Telegram** (`app/signals/telegram.py`): lee los chats de `TELEGRAM_CHATS`
  con tu cuenta (Telethon); cada mensaje con lado + stop se opera en una cuenta
  virtual del chat. Mensajes sin stop no se copian.
- **Sala de control** (frontend): velas japonesas con SMA50/200 y entradas/salidas
  del torneo, ranking del torneo, cerebro, Telegram, últimas operaciones.
  El backend sirve el build en `http://127.0.0.1:8000/`.
- **Sin Render**: se eliminan `render.yaml` y el despliegue a GitHub Pages; el
  informe diario por correo ahora incluye el torneo y el cerebro.

## Límites conocidos
- Familias de estrategia nuevas: solo largos (spot). Las fijas del torneo siguen
  probando shorts en paper.
- El parser de Telegram cubre formatos comunes (par, LONG/SHORT, entry, SL, TP);
  formatos raros quedan registrados como "no es señal".
