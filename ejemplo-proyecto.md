
---

## Archivo: `docs/constitution.md`

```markdown
# Constitución — {{NOMBRE_PROYECTO}}

Principios innegociables. Toda spec, plan y tarea debe cumplirlos.
Si un requisito entra en conflicto con esta constitución, se detiene el trabajo y se pregunta.

1. **Simplicidad primero**: {{STACK_PRINCIPAL}}. Dependencias mínimas. {{REGLA_DEPENDENCIAS}}.
2. **La spec manda**: ningún comportamiento se implementa si no está en la spec activa. Si falta una decisión, se detiene el trabajo y se pregunta.
3. **Separación de capas**: {{REGLAS_DE_ARQUITECTURA}}. El núcleo es testeable sin la interfaz.
4. **Tests como puerta**: cada tarea termina con sus tests en verde. Prohibido avanzar con tests en rojo.
5. **Datos locales y transparentes**: {{REGLAS_DE_PERSISTENCIA}}.
6. **Idioma**: código e identificadores en inglés; mensajes al usuario y documentación en {{IDIOMA_DOCUMENTACION}}.

---

## Ejemplo relleno (referencia del repo `habits-cli`)

> Este bloque NO forma parte del proyecto nuevo; es solo un ejemplo de cómo se ve una constitución real. Bórralo al inicializar.

1. **Simplicidad primero**: Python 3.12+ y solo biblioteca estándar en la aplicación. Única dependencia de desarrollo permitida: pytest.
2. **La spec manda**: ningún comportamiento se implementa si no está en la spec activa.
3. **Lógica separada de interfaz**: el núcleo (core) no imprime ni lee de consola. La CLI es una capa fina. Todo el core es testeable sin la CLI.
4. **Tests como puerta**: cada tarea termina con sus tests en verde.
5. **Datos locales y transparentes**: persistencia en un único archivo JSON legible. Nada de bases de datos ni de red.
6. **Idioma**: código e identificadores en inglés; mensajes al usuario y documentación en español.