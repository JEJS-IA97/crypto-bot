# Constitución — crypto-bot

Principios innegociables. Toda spec, plan y tarea debe cumplirlos.
Si un requisito entra en conflicto con esta constitución, se detiene el trabajo y se pregunta.

1. **Fase 1 solo Binance Spot**: sin futuros, sin margen, sin apalancamiento. Las demás exchanges, el arbitraje entre ellas y las transferencias **no se borran: quedan en reposo** — se construyen y se simulan (paper-trading), pero no tocan dinero real hasta que el capital crezca y una spec nueva lo active.
2. **Lo dormido sigue vivo en la spec**: cada área en reposo se documenta en la spec activa como fase posterior, con sus tests en modo simulación. Reactivarla exige spec nueva aprobada, no código improvisado.
3. **Capital aportado protegido**: el límite de capital se aplica sobre **lo aportado** por el propietario (inicio: 20 USD, configurable al aportar más) — **las ganancias no bloquean nada**. Riesgo máximo por operación ≤1 USD (pérdida real si salta el stop) y pérdida diaria ≤5% del valor de la cuenta al inicio del día UTC; al alcanzarla, no se abren posiciones nuevas hasta el día siguiente.
4. **Primero simulado, después real**: ninguna orden con dinero real hasta que la estrategia rente en paper-trading con criterios de la spec; después testnet de Binance; el dinero real es la última fase.
5. **Doble confirmación para dinero real**: operar en producción exige la flag explícita `ALLOW_LIVE_TRADING=true` y un límite de capital configurado. Por defecto, todo está en simulación/testnet.
6. **Kill switch obligatorio**: debe existir una forma de detener el bot en caliente sin reiniciar el proceso. Si no funciona, no se opera.
7. **La spec manda**: ningún comportamiento se implementa si no está en la spec activa (`specs/NNN-*/spec.md`). Si falta una decisión, se detiene el trabajo y se pregunta.
8. **Tests como puerta**: cada tarea termina con sus tests en verde. Prohibido avanzar con tests en rojo. Un RF sin test cuenta como no implementado.
9. **Sin humo en la "IA"**: toda estrategia/modelo debe ser entrenable, evaluable con backtest en split temporal (train/valid/test, sin *look-ahead*) y medible con métricas. Si no tiene métrica, no entra.
10. **Decisiones auditables**: cada operación persiste su señal, el snapshot de mercado que la justificó, los límites de riesgo aplicados y su resultado.
11. **Dinero en `Decimal`, nunca `float`**; validación estricta de toda entrada de la API; el núcleo de decisión es testeable sin red ni BD.
12. **Dependencias mínimas y versionadas** en `requirements.txt`. Nada de servicios externos no declarados.
13. **Idioma**: código e identificadores en inglés; documentación, mensajes al usuario y specs en español.
