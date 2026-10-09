# Ejemplo de constitución para un proyecto nuevo

Este archivo contiene una plantilla lista para copiar en `docs/constitution.md` y un ejemplo relleno de referencia.

---

## Archivo: `docs/constitution.md`

```markdown
# Constitución — {{PROJECT_NAME}}

Principios innegociables. Toda spec, plan y tarea debe cumplirlos.
Si un requisito entra en conflicto con esta constitución, se detiene el trabajo y se pregunta.

1. **Simplicidad primero**: {{MAIN_STACK}}. Dependencias mínimas. {{DEPENDENCY_RULE}}.
2. **La spec manda**: ningún comportamiento se implementa si no está en la spec activa. Si falta una decisión, se detiene el trabajo y se pregunta.
3. **Separación de capas**: {{ARCHITECTURE_RULES}}. El núcleo es testeable sin la interfaz.
4. **Verificación como puerta**: cada tarea termina con su verificación en verde. Prohibido avanzar con la verificación en rojo.
5. **Datos locales y transparentes**: {{PERSISTENCE_RULES}}.
6. **Idioma**: código e identificadores en inglés; mensajes al usuario y documentación en {{DOCS_LANGUAGE}}.
```

---

## Ejemplo relleno (referencia del repo `habits-cli`)

> Este bloque NO forma parte del proyecto nuevo; es solo un ejemplo de cómo se ve una constitución real. Bórralo al inicializar.

1. **Simplicidad primero**: Python 3.12+ y solo biblioteca estándar en la aplicación. Única dependencia de desarrollo permitida: pytest.
2. **La spec manda**: ningún comportamiento se implementa si no está en la spec activa.
3. **Lógica separada de interfaz**: el núcleo (core) no imprime ni lee de consola. La CLI es una capa fina. Todo el core es testeable sin la CLI.
4. **Verificación como puerta**: cada tarea termina con su verificación en verde.
5. **Datos locales y transparentes**: persistencia en un único archivo JSON legible. Nada de bases de datos ni de red.
6. **Idioma**: código e identificadores en inglés; mensajes al usuario y documentación en español.