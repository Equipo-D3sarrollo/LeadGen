=====================================================================
OBJETIVO DEL PROYECTO: ANÁLISIS PSICOLÓGICO-MATEMÁTICO DE EMPRESAS
Adaptación de LeadGen para medir compatibilidad y necesidades a fondo
=====================================================================
Fecha: 1 de octubre de 2026 (revisado el mismo día dos veces: alcance y
gobernanza de continuidad).
Estado: objetivo acordado en conversación con Desarrollo (Telcobras).
Sirve de ancla para retomar el desarrollo en cualquier sesión futura.

---------------------------------------------------------------------
1. CONTEXTO
---------------------------------------------------------------------
LeadGen hoy recorre un directorio de empresas (web o Google Maps), extrae
sus datos y calcula un Lead Score por reglas (scoring.py / config.py:
SCORING_WEIGHTS), pensado originalmente para un solo producto: diseño o
rediseño web. El score es un puntaje acumulado que se traduce en 4
categorías (Baja prioridad / Moderado / Bueno / Muy fuerte).

Por separado, ya existe en este proyecto un modelo matemático completo
(resumen_perfil_emocional_empresas.txt + su simulación emocion_empresas.html)
que representa la "postura emocional-comercial" de una empresa con las 8
emociones de Plutchik: a partir de señales de entrada normalizadas, una
matriz de pesos W y una temperatura T, calcula por softmax 8 probabilidades
(el perfil emocional), y de ahí un puntaje de venta por producto según la
afinidad A_k de ese producto con cada emoción. Ese porcentaje es,
literalmente, el que hoy se ve en la página de simulación.

También existe una exportación real de 484 empresas ya procesadas
(leads_export.xlsx), que se usó para una primera auditoría módulo por
módulo (ver claude/revision_leads_export.md): confirmó un bug de
teléfono, un gap en normalización de ciudad/departamento, y un sesgo
estructural de cobertura en datos de Google Maps. Esa auditoría ya no es
un evento único: la sección 10 de este documento la convierte en una
práctica que se repite después de cada fase.

---------------------------------------------------------------------
2. OBJETIVO GENERAL
---------------------------------------------------------------------
Adaptar LeadGen para que, por cada empresa descubierta, además del Lead
Score actual (que se conserva sin alterar su lógica), el sistema:

  a) Soporte un CATÁLOGO con varios productos/servicios de Telcobras.
  b) Implemente como NÚCLEO el sistema matemático de análisis
     psicológico de empresas (modelo de Plutchik + softmax ya
     formulado) para construir, con datos reales, el perfil emocional
     de cada empresa — el mismo cálculo de emocion_empresas.html, pero
     alimentado con señales reales en vez de simuladas.
  c) Use ese perfil para calcular, por producto del catálogo, el
     puntaje de venta / % de compatibilidad (la fórmula S = Σ p_k·A_k
     de la sección 3 del documento técnico) — ese % es el resultado
     central que ve el equipo comercial.
  d) Traduzca ese resultado en un DIAGNÓSTICO LEGIBLE por empresa (no
     solo números): qué necesita, con qué urgencia, qué tan abierta
     está comercialmente, en lenguaje de negocio.
  e) Amplíe las señales de entrada más allá de la huella digital, con
     CONTEXTO DE NEGOCIO real de la empresa (sector, tamaño, fase de
     crecimiento, señales de presupuesto, quién decide), para que la
     compatibilidad se mida contra la realidad de la empresa y no solo
     contra lo que su sitio web proyecta.
  f) Combine el % de compatibilidad del mejor producto con el Lead
     Score existente en un SCORE FINAL único y explicable (pesos
     alfa/beta configurables).

Resultado esperado para el equipo comercial: no solo "qué tan buen lead
es esta empresa", sino un perfil profundo de su situación y sus
necesidades, qué producto ofrecerle primero, con qué nivel de confianza,
y por qué (en palabras, no solo en porcentaje).

---------------------------------------------------------------------
3. ARQUITECTURA (capas; se conserva lo que ya funciona)
---------------------------------------------------------------------
  Capa 1 (existe, no se toca en su lógica):
    Lead Score por reglas -- scoring.py, SCORING_WEIGHTS en config.py.

  Capa 2 (nueva, capa de señales medibles):
    Perfil conductual de 6 dimensiones, 0-100 % cada una -- perfil.py.
      Madurez digital · Dolor/urgencia · Confianza/reputación ·
      Dinamismo · Apertura comercial · Sofisticación de marca.
    Estas 6 dimensiones son el vector de entrada "s" del modelo
    psicológico de la Capa 3 -- no son un sistema aparte, son su
    insumo medible (una empresa no se le puede preguntar si tiene
    "miedo", pero sí se puede medir si su web está caída hace meses).
    Nota (investigación complementaria, sección 9): de estas 6, "Dolor/
    urgencia" y "Dinamismo" funcionan más como señal de INTENT (momento
    actual) que el resto, que son más de FIT (encaje general) -- ver
    sección 9 para el porqué de esta distinción.

  Capa 3 (NÚCLEO, antes tratada por error como secundaria):
    Sistema matemático de análisis psicológico de empresas --
    perfil_psicologico.py. Implementa exactamente la fórmula de la
    sección 3 del documento técnico:
      z_k = b_k + Σ_m W_km · s_m      (s = las 6 dimensiones de la Capa 2)
      p_k = softmax(z_k / T)           (perfil emocional: 8 probabilidades)
      S   = Σ_k p_k · A_k              (puntaje de venta, por producto)
    A_k = vector de afinidad de cada producto del catálogo (Fase 1).
    El S normalizado a 0-100 % ES el porcentaje de compatibilidad que
    ve el equipo comercial -- el mismo cálculo que ya corre en
    emocion_empresas.html, ahora con datos reales en vez de simulados.
    La matriz W pasa de 8x4 (las 4 señales de la simulación) a 8x6 (las
    6 dimensiones de la Capa 2); se define junto con el catálogo
    (Fase 1) y se recalibra con resultados reales (Fase 7).

  Capa 4 (nueva):
    Diagnóstico legible -- traduce emoción principal/secundaria,
    claridad (Δ), la dimensión dominante de la Capa 2 y el contexto de
    negocio (Capa 5) en una lectura de negocio por empresa (ej. "alta
    urgencia y baja madurez digital, pero poca apertura comercial: hay
    necesidad pero cuesta que respondan"). Por defecto NO se expone al
    vendedor con nombres de emociones (alegría/miedo/etc.), solo en
    lenguaje de negocio -- queda abierto a cambiar esto si se prefiere
    mostrar también la etiqueta emocional cruda.

  Capa 5 (nueva):
    Contexto de negocio ampliado -- señales no solo digitales que
    también alimentan la Capa 2 y/o la Capa 4: sector/categoría (ya se
    captura hoy), tamaño estimado, fase de crecimiento, señales de
    presupuesto, contacto o cargo que decide. Se esperan de baja
    cobertura al inicio (no siempre se consiguen) y NUNCA bloquean el
    pipeline ni se rellenan con cero -- se guardan como nulo con su
    cobertura declarada, igual que el resto de señales.

  Score final mostrado = alfa * lead_score_normalizado (Capa 1)
                        + beta * S_normalizado del mejor producto (Capa 3)
  con alfa y beta en config.py, documentados y ajustables sin tocar código.
  Recomendación de la investigación complementaria (sección 9): mostrar
  también por separado una lectura de FIT (encaje, más estable) y una de
  INTENT (urgencia/momento, más cambiante) en vez de un solo número --
  ver sección 9 antes de fijar el formato final de presentación (Fase 6).

---------------------------------------------------------------------
4. DECISIONES YA TOMADAS (conversación del 1 oct. 2026)
---------------------------------------------------------------------
  1. El catálogo cubre VARIOS productos/servicios de Telcobras, no solo
     diseño web. Pendiente de Telcobras: la lista real (ver sección 6).
  2. No hay historial de ventas todavía; se empieza a registrar cada
     contacto (empresa, producto ofrecido, fecha, resultado) desde el
     primer lead que procese el nuevo sistema, sin esperar a tener
     volumen, para poder calibrar en cuanto sea posible. La
     investigación complementaria (sección 9.4) da una referencia
     realista: modelos similares se estabilizan en 2-3 semanas de uso
     activo con registro constante, no en meses.
  3. El sistema matemático de análisis psicológico (Plutchik + softmax,
     Capa 3) es el NÚCLEO que calcula el perfil y de él sale el % de
     compatibilidad por producto que ve el equipo comercial -- no es
     una vía secundaria/exploratoria. Las 6 dimensiones conductuales
     (Capa 2) son la capa de señales medibles que lo alimentan.
  4. El resultado por empresa debe incluir, además del dato cuantitativo
     (perfil + %), un diagnóstico legible en lenguaje de negocio (Capa
     4), y debe incorporar contexto de negocio real más allá de la
     huella digital (Capa 5), siempre marcando qué tan cubierta/
     confiable está cada señal usada.
  5. Después de cada fase completada del plan (sección 5), se hace una
     revisión del Excel de leads del proyecto (leads_export.xlsx, o la
     versión más reciente que exista) antes de pasar a la siguiente
     fase -- ver sección 10, Gobernanza.

---------------------------------------------------------------------
5. ALCANCE POR FASES (resumen operativo; detalle técnico en el chat)
---------------------------------------------------------------------
  Fase 1 - Catálogo de productos: por cada producto, su vector ideal de
           6 dimensiones Y su vector de afinidad A_k (8 emociones).
           Bloqueante: requiere el insumo de Telcobras (sección 6).
  Fase 2 - Señales: (a) digitales nuevas (rating, reseñas, antigüedad de
           dominio, registro mercantil); (b) contexto de negocio
           ampliado (tamaño, fase de crecimiento, presupuesto, quién
           decide), opcional y de baja cobertura esperada; (c) tabla de
           contactos/resultados desde ya; (d) corregir los 3 hallazgos
           de la auditoría (bug de teléfono, ciudad/departamento sin
           derivar, sesgo de cobertura de Maps) -- ver
           claude/revision_leads_export.md y la sección 9.2 de la
           investigación complementaria (scoring negativo por dato
           inválido).
  Fase 3 - Motor de perfil conductual (perfil.py): las 6 dimensiones de
           la Capa 2, con su cobertura registrada.
  Fase 4 - Motor de análisis psicológico (perfil_psicologico.py): la
           Capa 3 completa -- softmax, perfil emocional, puntaje de
           venta S por producto. Este es el módulo central del proyecto.
  Fase 5 - Diagnóstico legible (Capa 4): texto por empresa, reutilizando
           el patrón de ai_analysis.py (LLM con evidencia + respaldo por
           reglas si no hay API key). Evaluar aquí el uso del léxico de
           emociones en español (sección 9.5) como señal adicional de
           baja confianza.
  Fase 6 - Presentación: %, diagnóstico y cobertura en dashboard.py y
           export.py; evolución de emocion_empresas.html para mostrar
           empresas reales en vez de simuladas. Decidir aquí si se
           presenta un solo score o la lectura separada FIT/INTENT
           (sección 9.1).
  Fase 7 - Calibración continua de W, A_k y los pesos de las 6
           dimensiones, con los resultados de venta registrados desde
           la Fase 2.

Cada fase termina con la revisión del Excel descrita en la sección 10
antes de pasar a la siguiente.

---------------------------------------------------------------------
6. PRÓXIMO PASO INMEDIATO (bloqueante para la Fase 1)
---------------------------------------------------------------------
Telcobras necesita entregar, para cada producto o servicio que vende:
  - Nombre del producto/servicio.
  - A qué tipo de empresa le sirve normalmente (sector, tamaño, si se
    sabe).
  - Qué carencia o "dolor" resuelve.
  - Si existe algún caso de referencia: una empresa que sí lo compró y,
    si se puede, una que no, y por qué.

Con eso se construye catalogo_productos.json (vector ideal de 6
dimensiones + vector de afinidad A_k por producto) y se desbloquea todo
lo demás.

---------------------------------------------------------------------
7. QUÉ NO ES ESTE SISTEMA (límites honestos, para no sobre-prometer)
---------------------------------------------------------------------
  - Aunque se llame "análisis psicológico", es un modelo matemático de
    proxies de negocio sobre la empresa como entidad (su web, sus
    reseñas, su registro público) -- no mide la psicología real de las
    personas que trabajan allí, ni es un diagnóstico clínico de nada.
  - No reemplaza al vendedor ni predice la compra por sí solo: faltan
    presupuesto exacto, autoridad de decisión real y timing, que el
    modelo solo aproxima con proxies.
  - No está calibrado con resultados reales todavía. W, A_k, los
    umbrales y los pesos de las 6 dimensiones son SUPUESTOS INICIALES,
    declarados como tales, hasta que haya historial de ventas para
    contrastarlos (Fase 7). El propio documento técnico (sección 10)
    recomienda, en cuanto haya datos, comparar un modelo CON este
    componente contra uno SIN él antes de confiar en que mejora algo.

---------------------------------------------------------------------
8. CRITERIOS DE ÉXITO
---------------------------------------------------------------------
  - El pipeline completo sigue funcionando aunque falten señales nuevas
    o de contexto de negocio: nunca se rompe, nunca se rellena un dato
    no medido con cero (se guarda como nulo y se reporta la cobertura).
  - Cada empresa procesada muestra: Lead Score actual + perfil emocional
    (Capa 3) + % de compatibilidad por producto + diagnóstico legible +
    nivel de cobertura/confianza del dato.
  - Desde el primer lead procesado con el nuevo sistema queda registrado
    qué se le ofreció y qué pasó.
  - Ningún peso, umbral o vector se presenta como verdad absoluta: todos
    están marcados como supuestos iniciales hasta su calibración.
  - Ninguna fase se da por cerrada sin su revisión del Excel (sección 10).

---------------------------------------------------------------------
9. INVESTIGACIÓN COMPLEMENTARIA (resumen; detalle en
   claude/investigacion_complementaria.md)
---------------------------------------------------------------------
  9.1 Marco FIT (encaje general) vs. INTENT (urgencia/momento): práctica
      estándar de la industria B2B que ya encaja con nuestras 6
      dimensiones; considerar mostrarlos por separado en la Fase 6, no
      solo como un score único. También sugiere un "rollup" cuando una
      misma empresa/cadena aparece en varias sedes (ya vimos 3 casos de
      esto en el leads_export.xlsx).
  9.2 Scoring negativo explícito por dato inválido (no solo "no sumar"):
      aplica directo al bug de teléfono corrupto ya encontrado --
      incorporar validación de formato en la Fase 2-3.
  9.3 El decaimiento por recencia que ya estaba planeado
      (peso = exp(-lambda*dias)) coincide con la práctica estándar; sin
      cambios, solo confirmado.
  9.4 Cold start: partir de reglas simples e inspeccionables (lo que ya
      hacemos) y esperar una estabilización en 2-3 semanas de uso activo
      con registro constante de resultados, no meses.
  9.5 Léxico de emociones en español (NRC/AFINN traducido, en CSV,
      gratuito) disponible para la Fase 5, como señal adicional de baja
      confianza -- la traducción automática "contiene errores" según su
      propia documentación, no usar como única fuente de verdad.
  9.6 RUES/Confecámaras: existe un dataset abierto en datos.gov.co que
      en principio cubre lo que pedía la Fase 2, pero no se pudieron
      verificar sus campos ni su API en vivo por una restricción de red
      de este entorno -- confirmar directamente antes de construir el
      conector.
  9.7 Marco legal (Ley 1581/2012, Habeas Data): sigue vigente, sin
      cambios relevantes encontrados para 2026 -- se mantiene la
      recomendación de consultar a un abogado antes de contacto masivo.

---------------------------------------------------------------------
10. GOBERNANZA DE CONTINUIDAD
---------------------------------------------------------------------
Esta conversación (y este documento) es el punto de partida para
retomar el trabajo en cualquier sesión futura: antes de seguir, leer
este objetivo, el resumen técnico y la investigación complementaria
(sección 9). Cuando el catálogo de productos de la Fase 1 esté
definido, se crean en el repositorio de código PLAN.md (checklist por
fase) y DECISIONES.md (por qué cada fórmula y peso, y cuándo cambió),
con un commit por fase completada.

REGLA FIJA (añadida el 1 de octubre de 2026): al terminar cada fase de
la sección 5, antes de pasar a la siguiente, se hace una revisión del
Excel de leads del proyecto (leads_export.xlsx, o su versión más
reciente) igual a la de claude/revision_leads_export.md: por módulo/
fase, qué columnas o campos nuevos aparecen, qué cobertura real tienen,
qué anomalías de calidad de dato aparecen, y qué impacto tiene eso en
las fases siguientes. Cada revisión se guarda como un nuevo documento
en el proyecto (ej. claude/revision_fase_2.md) o se añade a
claude/revision_leads_export.md si el volumen lo permite, para que el
historial de hallazgos quede trazable fase por fase.

=====================================================================
FIN DEL OBJETIVO
=====================================================================
