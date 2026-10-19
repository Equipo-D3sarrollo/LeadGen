=====================================================================
REVISIÓN POR MÓDULOS: leads_export.xlsx (484 empresas, dato real)
Hecha el 1 de octubre de 2026, antes de arrancar la Fase 2 del plan de
adaptación (ver claude/OBJETIVO.md)
=====================================================================
Fuente del archivo: Project file "leads_export.xlsx". 440 filas vienen
de Google Maps, 44 de un directorio (yelu.com.co). Categorías muy
variadas (restaurantes, abogados, dentistas, agencias, ferreterías...):
todavía no hay un catálogo de producto que dirija la búsqueda (Fase 1
pendiente).

---------------------------------------------------------------------
HALLAZGOS POR MÓDULO
---------------------------------------------------------------------
Módulo 1-2 (Entrada/Descubrimiento): OK. 484 empresas, 0 URLs
  duplicadas. Búsqueda genérica, no alineada todavía a los segmentos de
  Telcobras -- normal mientras no exista el catálogo (Fase 1).

Módulo 3 (Recolección) -- BUG CONFIRMADO: 12/484 filas (2.5 %) tienen
  el campo telefono corrompido: varios números concatenados sin
  separador (ej. "5076507550745073..."). Parece originarse en el
  parseo de teléfono de google_maps.py. Arreglar antes de usar
  teléfono como señal de "apertura comercial" o para contacto real.

Módulo 4 (Normalización) -- GAP CONFIRMADO: ciudad y departamento están
  vacíos en el 100 % de las 484 filas, aunque direccion sí existe en el
  90 % (438/484). No es un dato ausente en la fuente: normalize.py no
  lo está derivando de la dirección. Relevante para la Capa 5 (contexto
  de negocio) del objetivo nuevo.

Módulo 5 (Validación) -- LIMITACIÓN ESTRUCTURAL CUANTIFICADA:
  tiene_whatsapp = 0 % (0/484), tiene_instagram = 0 % (0/484),
  tiene_correo = 0.2 % (1/484). Coincide con lo que el README ya
  advertía de Google Maps, pero aquí queda medido: estas 3 señales
  valen 30 de los puntos del Lead Score actual y alimentan la
  dimensión "Apertura comercial" del plan nuevo. Mientras no se
  resuelva, toda empresa de origen Maps va a salir con apertura
  comercial baja por la fuente, no por la empresa. Acción recomendada:
  rescatar estas señales desde el sitio web propio de la empresa
  (cuando exista) en vez de depender solo de Maps, y mientras tanto
  declarar baja cobertura en vez de tratarlo como "No" con certeza.

Módulo 6 (Análisis Web): OK, corre en el 100 % de los casos con sitio
  web (247/247 con web_puntaje calculado, aunque a veces sea 0 si el
  sitio no carga). 80/247 (32 %) no usan HTTPS en 2026 -- dato real
  usable para "madurez digital".

Módulo 7 (IA): no se usó en esta corrida (observacion_ia vacío al
  100 %) -- esperado si no se pasó --ia o no había ANTHROPIC_API_KEY.

Módulo 8 (Lead Score) -- TECHO ARTIFICIAL DETECTADO: rango real 0-75;
  0 empresas en "Muy fuerte" (80+). Distribución: 247 Baja prioridad
  (51 %), 194 Moderada (40 %), 43 Buena (9 %). Consecuencia directa del
  hallazgo del Módulo 5: al faltar casi siempre los 30 puntos de
  whatsapp/instagram/correo, el techo real para leads de Maps queda
  muy por debajo de 100. No interpretar "nadie es un lead muy fuerte"
  como una conclusión sobre las empresas: es un techo de la fuente.

Módulo 9 (Base de datos): OK. 0 url_perfil duplicados; 3 nombres
  repetidos son casos legítimos (misma cadena, distinta sede).

Módulo 10 (Exportación): OK. 30 columnas del Excel = esquema exacto de
  database.py, sin corrupción estructural.

---------------------------------------------------------------------
ACCIONES ANTES DE AVANZAR A LA FASE 2 DEL PLAN NUEVO
---------------------------------------------------------------------
  1. Arreglar el bug de teléfono concatenado (Módulo 3 / google_maps.py).
  2. Hacer que normalize.py derive ciudad/departamento de la dirección
     cuando esta existe (Módulo 4).
  3. Decidir cómo compensar la ausencia estructural de WhatsApp/
     Instagram/correo en datos de Maps antes de que distorsione la
     dimensión "Apertura comercial" del perfil nuevo (Módulo 5).

=====================================================================
FIN DE LA REVISIÓN
=====================================================================
