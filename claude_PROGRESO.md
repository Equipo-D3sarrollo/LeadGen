# PROGRESO (espejo en texto de PROGRESO_LEADGEN.xlsx)

El Excel es el registro oficial (el proyecto no guarda binarios: se entrega en el chat y se guarda en la carpeta de Telcobras). Este archivo es su copia en texto para que cualquier sesión retome sin el Excel. Al cerrar cada fase se actualizan los dos.

## Resumen

| Fase | Nombre | Hechas/Tareas | % | Estado | Revisión Excel |
|---|---|---|---|---|---|
| 0 | Gobernanza y seguimiento | 2/3 | 67% | En curso | No |
| 1 | Catálogo de productos desde links | 6/8 | 75% | En curso | Sí |
| 2 | Señales + correcciones de auditoría + contactos | 9/12 | 75% | En curso | Sí |
| 3 | Motor de perfil conductual (Capa 2) | 2/3 | 67% | En curso | Sí |
| 4 | Núcleo psicológico (Capa 3) y score final | 5/5 | 100% | Completa | Sí |
| 5 | Diagnóstico legible (Capa 4) | 2/3 | 67% | En curso | Sí |
| 6 | Presentación (dashboard, export, simulación) | 1/4 | 25% | En curso | No |
| 7 | Calibración continua | 0/2 | 0% | No iniciada | No |
|  | AVANCE GLOBAL (tareas hechas / totales) | 27/40 | 68% |  | 5 de 8 fases revisadas |

## Tareas

| ID | Fase | Tarea | Estado | Notas |
|---|---|---|---|---|
| F0-01 | 0 | Crear Excel de seguimiento (este archivo) | Hecha |  |
| F0-02 | 0 | Crear PLAN.md y DECISIONES.md | Hecha |  |
| F0-03 | 0 | Repositorio git con un commit por fase | Pendiente | No hay repositorio conectado; el código vive en el proyecto de Claude. Definir dónde versionar. |
| F1-01 | 1 | Lector de catálogos por links (recorre páginas internas, PDF, JSON-LD, tarjetas, títulos) | Hecha | Probado con sitio simulado (sin red en el entorno). |
| F1-02 | 1 | Motor por reglas: 11 familias de producto con vector ideal 6D y afinidad A_k | Hecha | Supuestos iniciales. |
| F1-03 | 1 | Motor con IA (Claude lee el catálogo y devuelve JSON validado) + respaldo por reglas | Hecha | Probado con cliente simulado; falta prueba con API real. |
| F1-04 | 1 | Investigación amplia: sectores, búsquedas sugeridas, complementarios, oportunidades no listadas | Hecha |  |
| F1-05 | 1 | Fusión que protege productos 'aprobado' y 'manual' | Hecha |  |
| F1-06 | 1 | Comando: python main.py catalogo <links> [--ia] | Hecha |  |
| F1-07 | 1 | Correr el lector con los links REALES del catálogo de Telcobras | Bloqueada | Falta que Telcobras entregue los links. |
| F1-08 | 1 | Aprobación de vectores por Telcobras (estado 'aprobado') | Pendiente |  |
| F2-01 | 2 | Bug teléfono concatenado: regex acotado + enlaces tel: + validación formato Colombia | Hecha | El bug venía de scraper.py (yelu), no de google_maps.py. |
| F2-02 | 2 | Derivar ciudad / departamento / país de la dirección | Hecha |  |
| F2-03 | 2 | Detectar páginas del directorio que no son empresas | Hecha | Hallazgo nuevo: 44/44 filas de yelu. |
| F2-04 | 2 | Marcar empresas fuera del mercado (país) | Hecha | 34 en EE. UU. |
| F2-05 | 2 | Rating y número de reseñas desde la ficha de Maps; reseñas llegan al Lead Score | Hecha | Parser probado; falta prueba en vivo con Maps. |
| F2-06 | 2 | Rescatar WhatsApp/Instagram/Facebook/correo desde la web propia | Hecha |  |
| F2-07 | 2 | Antigüedad del dominio por RDAP | Hecha | Falta prueba en vivo. |
| F2-08 | 2 | Contexto de negocio (Capa 5): tamaño, fase de crecimiento, presupuesto, cargos, sedes | Hecha |  |
| F2-09 | 2 | Tabla de contactos/resultados + comando 'contacto' + hoja Contactos en el export | Hecha |  |
| F2-10 | 2 | Conector RUES / Confecámaras | Bloqueada | Verificar campos y API del dataset de datos.gov.co (sección 9.6). |
| F2-11 | 2 | Evaluar Google Places API oficial en vez de scraping de Maps | Pendiente | Términos de uso y costo. |
| F2-12 | 2 | Corrida en vivo con Maps + web para medir la cobertura real de las señales nuevas | Pendiente | Prioridad 1 de la próxima sesión (en el equipo de Telcobras: este entorno no tiene salida a esos sitios). |
| F3-01 | 3 | perfil.py: 6 dimensiones con estados medida / no aplica / faltante y cobertura | Hecha |  |
| F3-02 | 3 | Nunca rellenar con cero; WhatsApp/correo de Maps = faltante, no 'No' | Hecha |  |
| F3-03 | 3 | Revisar correlación entre dimensiones con datos nuevos | Pendiente | Necesita la corrida F2-12. |
| F4-01 | 4 | perfil_psicologico.py: z=b+W·s, softmax, punto (x,y,z,w), principal/secundaria, claridad, entropía | Hecha |  |
| F4-02 | 4 | S por producto y % de compatibilidad (anclado en empresa neutra) | Hecha | D-06 |
| F4-03 | 4 | Lectura FIT e INTENT por producto | Hecha |  |
| F4-04 | 4 | Score final alfa/beta + penalización por dato inválido + exclusiones | Hecha |  |
| F4-05 | 4 | Integración al pipeline y comando 'reprocesar' | Hecha |  |
| F5-01 | 5 | Diagnóstico legible por reglas (sin nombres de emociones) | Hecha |  |
| F5-02 | 5 | Diagnóstico con IA (evidencia JSON) + respaldo por reglas | Hecha | Falta prueba con API real. |
| F5-03 | 5 | Evaluar léxico de emociones en español (NRC) como señal de baja confianza | Pendiente |  |
| F6-01 | 6 | Export con columnas comerciales primero | Hecha | Adelanto de la Fase 6. |
| F6-02 | 6 | dashboard.py: mostrar score final, producto, diagnóstico y radar del perfil | Pendiente |  |
| F6-03 | 6 | emocion_empresas.html con empresas reales | Pendiente |  |
| F6-04 | 6 | Decidir: score único vs lectura FIT/INTENT separada | Pendiente | Decisión de Telcobras. |
| F7-01 | 7 | Calibrar W, A_k y pesos con contactos registrados | Pendiente | Necesita historial (2-3 semanas de uso). |
| F7-02 | 7 | Comparar modelo con vs. sin componente emocional (AUC / lift) | Pendiente |  |

## Bitácora

| Fecha | Sesión | Fases | Qué se hizo | Siguiente paso |
|---|---|---|---|---|
| 2026-10-06 | Sesión 1 (Claude, Cowork) | 0-5 | Creado el seguimiento. Fase 1: lector de catálogos por links. Fase 2: corregidos los 3 hallazgos de auditoría + 2 hallazgos nuevos (no-empresas, fuera de mercado), señales nuevas, Capa 5 y tabla de contactos. Fases 3-5: perfil.py, perfil_psicologico.py y diagnostico.py integrados al pipeline. 17 pruebas automáticas en verde. Revisión del Excel hecha tras cada fase (hoja Revisiones). Código subido al proyecto. | 1) Pedir a Telcobras los links del catálogo y correr: python main.py catalogo <links> --ia. 2) Corrida en vivo (Maps + web) en un equipo con internet para medir cobertura real de rating/reseñas/contacto. 3) Empezar a registrar contactos. 4) Fase 6: dashboard y simulación con empresas reales. |

## Pendientes

| Quién | Pendiente | Impacto | Estado |
|---|---|---|---|
| Telcobras | Links del catálogo de productos/servicios (web, PDF, tienda, aliados) | Bloquea F1-07 y que el % sea contra productos reales | Abierto |
| Telcobras | ¿Mostrar al vendedor también la etiqueta emocional cruda o solo el lenguaje de negocio? | Hoy: solo negocio (config.DIAGNOSTICO_MOSTRAR_EMOCION) | Abierto |
| Telcobras | ¿Score único o lectura FIT/INTENT separada en el dashboard? | Fase 6 | Abierto |
| Desarrollo | Correr el pipeline en un equipo con internet (este entorno no llega a Maps ni a los sitios) | Medir cobertura real de señales nuevas | Abierto |
| Desarrollo | Dónde versionar el código (git) para el commit por fase | Gobernanza | Abierto |
| Legal | Consulta Ley 1581/2012 antes de contacto masivo | Sección 9.7 | Abierto |
