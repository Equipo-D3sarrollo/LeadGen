=====================================================================
INVESTIGACIÓN COMPLEMENTARIA: prácticas externas relevantes
Hecha el 1 de octubre de 2026, a pedido de Desarrollo (Telcobras), antes
de seguir con la implementación del objetivo (ver claude/OBJETIVO.md)
=====================================================================
Nota: esto es investigación externa (literatura y práctica de industria
en lead scoring B2B), no un cambio de decisión. Se incorpora lo que
tiene sentido para el proyecto y se descarta/adapta lo que no aplica.

---------------------------------------------------------------------
1. MARCO "FIT vs. INTENT" (práctica estándar de industria B2B, 2026)
---------------------------------------------------------------------
Las guías de lead scoring B2B actuales separan dos preguntas que
nuestro diseño venía mezclando en un solo número:

  FIT  = ¿esta empresa en general encaja con lo que vendemos?
         (datos firmográficos: sector, tamaño, categoría -- más
         estático, cambia poco en el tiempo)
  INTENT = ¿esta empresa está mostrando señales de necesitarlo AHORA?
         (comportamiento reciente: reseñas nuevas, cambios en su web,
         eventos -- se degrada con el tiempo)

Relación directa con lo que ya definimos: el "vector ideal de 6
dimensiones" por producto (Fase 1) es esencialmente un FIT; la
dimensión "Dolor/urgencia" y "Dinamismo" son más bien INTENT.

Recomendación: no colapsar todo en un solo % desde el inicio. Mostrar
al equipo comercial DOS lecturas separadas por empresa-producto (ej.
"Encaje: Bueno (grado B)" + "Urgencia/momento: Alta (82 %)"), y combinar
ambas en el score final solo como resumen, no como el único dato
visible. Esto es más legible que nuestro S único y es como lo hacen las
herramientas de referencia del sector (fuente: guía de priorización B2B
2026, ver sección 6).

Otra práctica de la misma fuente, útil para cuando haya varias sedes de
una misma empresa (ya detectamos 3 casos de nombres repetidos en el
leads_export.xlsx, ej. "In-N-Out Burger" con distintas sedes): un
"rollup" a nivel de cuenta/cadena en vez de tratar cada sede como un
lead aislado cuando aplique. Queda como decisión abierta para la Fase 6
(presentación): ¿se reporta por sede o se agrupa por cadena/razón
social?

---------------------------------------------------------------------
2. SCORING NEGATIVO POR CALIDAD DE DATO (acción directa sobre un bug
   que ya encontramos)
---------------------------------------------------------------------
La práctica estándar es restar puntos explícitamente cuando un dato de
contacto es inválido (no solo "no sumar" por falta de dato), y aplicar
un decaimiento por inactividad/antigüedad del dato.

Esto aplica directamente al bug de teléfono concatenado que encontramos
en la revisión del Excel (12/484 registros, ver
claude/revision_leads_export.md): ese tipo de dato no debería contar
como "tiene_telefono = Sí" sin más -- debería marcarse como dato
inválido, excluirse de la señal de "apertura comercial", y bajar la
cobertura declarada de esa empresa en vez de pasar silenciosamente como
información buena.

Recomendación para la Fase 2-3: agregar una validación de formato antes
de aceptar teléfono/correo como señal positiva (regex de longitud y
estructura razonable), y loggear cuántos registros fueron rechazados
por esta validación -- es una métrica de salud del pipeline, no solo un
detalle técnico.

---------------------------------------------------------------------
3. DECAIMIENTO POR RECENCIA (confirma, no cambia, lo ya documentado)
---------------------------------------------------------------------
La fórmula que ya está en resumen_perfil_emocional_empresas.txt
(peso = exp(-lambda * dias)) es exactamente la misma que usa la
industria para la dimensión "Dinamismo" y para no sobre-valorar una
reseña o evento de hace dos años igual que uno de la semana pasada.
No hay cambio aquí, solo confirmación de que el enfoque ya elegido es
el estándar correcto.

---------------------------------------------------------------------
4. COLD START: QUÉ TAN RÁPIDO SE PUEDE CALIBRAR SIN HISTORIAL
---------------------------------------------------------------------
La práctica documentada para arrancar un modelo de scoring sin datos
históricos (justo nuestro caso, según la decisión ya tomada de empezar
a registrar resultados desde la Fase 2) es:
  - Partir de reglas simples, explícitas e inspeccionables -- es
    exactamente el enfoque de este proyecto (pesos declarados en
    config.py, no una caja negra).
  - Validar a mano un puñado de casos (cientos, no miles) antes de
    confiar en el modelo.
  - Revisar con más atención los casos "intermedios" (donde el modelo
    duda), no solo los extremos.
  - Expectativa realista de tiempo: implementaciones reales reportan
    que el modelo se estabiliza en 2-3 SEMANAS de uso activo con
    registro constante de resultados, no meses. Esto le da una fecha
    aproximada a la Fase 7 una vez arranque la Fase 2.

---------------------------------------------------------------------
5. LÉXICOS DE EMOCIONES EN ESPAÑOL (recurso concreto, gratuito)
---------------------------------------------------------------------
El documento técnico original (mejora recomendada #8) sugiere medir
emociones del texto con un léxico real en vez de heurísticas simples.
Existe una traducción al español de los léxicos NRC y AFINN, en CSV,
lista para usar:
  https://github.com/jboscomendoza/lexicos-nrc-afinn

Advertencia importante encontrada: la traducción es automática con
correcciones manuales parciales, y el propio repositorio avisa que
"contiene errores". Recomendación: usarlo como una señal más de baja
confianza dentro de la Capa 2 (ej. aporta a "Sofisticación de marca" o
al tono del texto de la descripción), nunca como la única fuente de
verdad, y declarar su cobertura/confianza igual que cualquier otra
señal débil.

---------------------------------------------------------------------
6. FUENTES DE DATOS COLOMBIANAS (RUES / Confecámaras)
---------------------------------------------------------------------
Existe un dataset abierto en datos.gov.co ("Personas Naturales,
Personas Jurídicas y Entidades Sin Ánimo de Lucro", categoría Comercio-
Industria-y-Turismo) que en principio cubre lo que el documento técnico
pedía para la Fase 2 (matrícula, actividad económica, etc.).

LIMITACIÓN DE ESTA INVESTIGACIÓN: no pude verificar en vivo los campos
exactos, el formato de API ni la frecuencia de actualización de ese
dataset -- la política de red de este entorno bloqueó la conexión
saliente a datos.gov.co al intentar consultarlo. Hay que confirmarlo
directamente desde el entorno de desarrollo real del proyecto (no
desde aquí) antes de construir el conector en la Fase 2.

Alternativa ya usada por terceros si el acceso oficial resulta
complicado: proveedores de pago que ya scrapean RUES (ej. servicios en
Apify de los proveedores "regdata" y "scrapers_lat") -- tienen costo y
habría que revisar sus términos antes de depender de ellos.

---------------------------------------------------------------------
7. MARCO LEGAL -- SIN CAMBIOS, SOLO CONFIRMADO VIGENTE
---------------------------------------------------------------------
La Ley 1581 de 2012 (Habeas Data) sigue vigente en 2026 y la Superintendencia
de Industria y Comercio (SIC) sigue siendo la autoridad de control. No
cambia la recomendación que ya estaba en el documento técnico original:
consultar a un abogado antes de cualquier contacto masivo, y tener
política de tratamiento de datos documentada. Esta investigación no
encontró ningún cambio normativo relevante para 2026 que modifique esa
recomendación -- solo la confirma.

---------------------------------------------------------------------
8. QUÉ SE DESCARTA DE ESTA INVESTIGACIÓN (y por qué)
---------------------------------------------------------------------
  - Modelos de machine learning entrenados (Gradient Boosting, etc.)
    que usa la industria cuando ya hay miles de registros históricos:
    no aplican todavía, porque no hay historial de ventas. Quedan como
    referencia para la Fase 7, cuando haya datos suficientes para
    comparar contra las reglas actuales (el propio documento técnico ya
    recomienda esa comparación en su sección de mejoras).
  - "Intent data de terceros" (compra de señales de intención de
    proveedores externos tipo Bombora): tiene costo y depende de
    cobertura en el mercado colombiano, que no está confirmada. No se
    descarta para el futuro, pero no es parte del alcance actual.

=====================================================================
FIN DE LA INVESTIGACIÓN COMPLEMENTARIA
=====================================================================
