# Prompts por fase SDD

Copia y pega el prompt de la fase en tu agente. **No saltes fases.**
Cada fase espera tu aprobación antes de pasar a la siguiente.

| Fase | Prompt esencial |
|------|-----------------|
| **Constitución** | "Proponme la constitución de este proyecto: N principios cortos y verificables sobre stack, calidad, tests y límites. Máx. 15 líneas. Espera mi aprobación." |
| **Spec (entrevista)** | "NO escribas código. Hazme preguntas de una en una (máx. 6) sobre casos límite, errores y alcance, y después genera `spec.md` con RF numerados en EARS, fuera de alcance y criterios de finalización. Solo el QUÉ y el POR QUÉ." |
| **Clarificación** | "Revisa la spec como un QA profesional: ambigüedades, contradicciones, casos límite ausentes, conflictos con la constitución. Solo detecta, no resuelvas." |
| **Plan** | "Lee constitución y spec. Sin código: genera `plan.md` con módulos, modelo de datos, decisiones justificadas (con la alternativa descartada) y estrategia de tests. Indica qué RF cubre cada parte." |
| **Tareas** | "Divide el plan en tareas de <30 min, ordenadas por dependencia, cada una con sus RF y una línea 'Hecho cuando:' verificable. Con checkboxes." |
| **Implementación** | "Implementa SOLO la tarea Tn. Tests primero. Ejecuta la suite y muéstrame el resultado. Marca Tn como hecha y PÁRATE." |
| **Validación** | "Recorre la spec RF por RF: qué test cubre cada uno y su resultado. Veredicto final: ¿spec cumplida?" |
| **Cambio** | "Nuevo requisito: {{descripción}}. NO toques código: actualiza primero la spec y muéstrame el diff." |

---

## Reglas de uso de los prompts

1. **Un prompt = una fase.** No mezcles "genera spec y plan" en la misma instrucción.
2. **Espera aprobación.** El agente no debe pasar de fase sin tu OK.
3. **Itera la entrevista.** Si el agente escribe código durante la fase de spec, rechaza la respuesta.
4. **No reescribas los prompts a la ligera.** Son la interfaz entre tú y el agente; cambios deben probarse.
5. **Registra excepciones.** Si un prompt falla sistemáticamente, anótalo aquí y ajústalo.