# Checklist de Producción para Apps Generadas con IA

> Aplicar cada sección solo cuando sea pertinente al tipo de producto. Un checkbox no reemplaza evidencia.

## Diseño y UI/UX
- [ ] Paleta y tipografía coherentes con la marca/producto
- [ ] Jerarquía visual clara y acción principal evidente
- [ ] Componentes usados por significado (tabla, lista, formulario, diálogo, etc.)
- [ ] Indicadores de estado representan estados reales
- [ ] Iconografía consistente y accesible
- [ ] No hay decoración añadida solo para rellenar espacio o imitar tendencias
- [ ] Responsive validado en los tamaños relevantes

## SEO técnico — solo páginas públicas indexables
- [ ] Títulos únicos y descriptivos; no se fuerza un límite fijo de caracteres
- [ ] Meta descripciones útiles y específicas; no se fuerza un límite fijo de caracteres
- [ ] Jerarquía de encabezados semántica y clara; no se exige exactamente un H1 como regla mecánica
- [ ] Canonicalización definida donde realmente aplica
- [ ] Open Graph / social cards cuando aportan valor
- [ ] Favicon y metadatos básicos correctos
- [ ] Sitemap cuando corresponda
- [ ] robots.txt refleja una política explícita de rastreo
- [ ] Datos estructurados solo cuando son veraces y aplicables
- [ ] `lang` correcto
- [ ] 404 útil y con status correcto cuando existe routing web

## Rendimiento
- [ ] Build de producción verificado
- [ ] Bundle inicial razonable para el producto y medido, no comparado contra un límite arbitrario
- [ ] Code splitting / lazy loading cuando aporta beneficio real
- [ ] Imágenes optimizadas y dimensiones definidas cuando corresponda
- [ ] No hay errores de consola en flujos normales de producción
- [ ] Core Web Vitals medidos cuando sea un objetivo del producto web

## Seguridad
- [ ] Sourcemaps y artefactos de depuración revisados
- [ ] Las variables expuestas al cliente contienen solo datos que pueden ser públicos
- [ ] HTTPS y headers de seguridad aplicables
- [ ] Autorización aplicada en servidor
- [ ] Validación de entrada en servidor
- [ ] No hay secretos en código, bundles ni logs
- [ ] Rate limiting / controles de abuso en operaciones sensibles cuando corresponda

## Preparación para IA y answer engines
- [ ] La política de crawlers de búsqueda/IA está decidida según el producto
- [ ] No se bloquean o permiten crawlers por copiar una plantilla sin evaluar el caso
- [ ] El contenido público importante es descubrible y representable en el rendering elegido
- [ ] No se exige SSR/SSG a una app privada o a una página donde no aporta valor
- [ ] `llms.txt`, si existe, es opcional y tiene contenido útil y verificable

## Despliegue
- [ ] Dominio y URLs públicas intencionales cuando corresponda
- [ ] Variables de entorno configuradas de forma segura
- [ ] Pipeline de CI/CD validado cuando exista
- [ ] Monitoreo/observabilidad definido para producción según necesidad
