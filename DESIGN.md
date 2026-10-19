# Design

Mundo visual: **terminal de trader**. Sustituye al diseño anterior (design.json, neón turquesa), que queda como anti-referencia.

- Modo: Operate. Densidad alta, el gráfico de velas es protagonista, sin adornos.
- Color: grafito neutro frío (#0e1013 fondo, #14171b paneles, #262b31 líneas). Un solo acento ámbar #f0b429 para selección, foco y pestaña activa. Verde #26a96c / rojo #e5534b solo para precio y PnL. Nada de degradados ni brillos.
- Tipografía: IBM Plex Sans (UI) e IBM Plex Mono solo para cifras, precios y horas (tabular). Escala fija 12/13/14/16/20 px.
- Forma: radios 4 px, separadores de 1 px, sin sombras salvo menús flotantes. Paneles con título en línea, sin etiquetas "eyebrow".
- Iconos: lucide-react, trazo 1.75.
- Movimiento: 150 ms en hover/estado. Sin animaciones de entrada.
- Gráfico: lightweight-charts; velas verde/rojo, SMA50 ámbar, SMA200 gris azulado, volumen tenue, marcas de entradas/salidas del torneo.
