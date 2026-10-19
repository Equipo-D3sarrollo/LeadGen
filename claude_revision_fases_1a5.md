=====================================================================
REVISIÓN DEL EXCEL DE LEADS TRAS LAS FASES 1 A 5
leads_export.xlsx (484 filas) reprocesado con: python main.py reprocesar
Fecha: 6 de octubre de 2026 · Resultado completo: leads_analizados.xlsx
Métricas también en PROGRESO_LEADGEN.xlsx, hoja "Revisiones".
=====================================================================

FASE 1 - Catálogo
  - No hay links reales todavía: se usaron los 11 arquetipos provisionales.
  - Solo 5 de 11 productos salen recomendados alguna vez (diseño web 255,
    hosting 146, ERP 2, soporte TI 2, marketing 1). La base actual
    (clínicas dentales, restaurantes, agencias) y las señales actuales son
    100 % digitales: nada mide infraestructura (conectividad, telefonía,
    cableado, seguridad). Si Telcobras vende sobre todo infraestructura,
    hacen falta señales de ese tipo (sedes, tamaño, sector) -> Capa 5.

FASE 2 - Señales y correcciones
  - NUEVO: las 44 filas de yelu.com.co NO son empresas (categorías,
    paginación, loterías, "Añade negocio"). Se excluyen del score.
  - NUEVO: 34 empresas están en EE. UU. (Fresno, Sacramento...): búsqueda
    de Maps mal geolocalizada. Se excluyen. Quedan 406 válidas (84 %).
  - Ciudad/departamento: 90.5 % / 83.5 % (antes 0 %).
  - Teléfono: 25 inválidos detectados (los 12 concatenados + fechas y
    fragmentos). El bug venía de scraper.py (directorio), no de Maps.
  - Lead Score recalculado con la misma lógica: 25 cambian, máximo 75->65.
  - rating/reseñas/horario: 0 % en el Excel viejo (no se extraían).
  - web_puntaje = 0 en 156 de 247 webs: no se distingue "caído" de
    "análisis falló" -> tratado como no medido.

FASE 3 - Perfil conductual
  - Cobertura media 28.8 % (máx. 35.8 %): confianza media 250, baja 156.
  - Reputación sin medir (0 %); dinamismo casi sin medir.

FASE 4 - Núcleo psicológico
  - Primera corrida: compatibilidad ~92 % para todos y "confianza" como
    emoción dominante por construcción. Corregido con D-04, D-05, D-06.
  - Ahora: compatibilidad media 65 % (46-73 %); pasan el filtro 193/406;
    el 52 % queda con perfil "poco definido" (claridad < 0.05), lo que es
    honesto con tan pocas señales.
  - Score final medio 46 (sin web 58.5 vs. con web 35.4).
  - Hay muchos empates (pocos perfiles distintos): esperado hasta tener
    rating, reseñas y escaneo de la web.

FASE 5 - Diagnóstico
  - 406/406 válidas con texto; 78 exclusiones explicadas. No usa nombres
    de emociones y declara qué no se pudo verificar.

IMPACTO EN LO QUE SIGUE
  1. Lo más valioso ahora es una corrida EN VIVO con el pipeline nuevo
     (Maps + web) para llenar reputación, dinamismo y contacto: este
     entorno no tiene salida a esos sitios, hay que correrlo en un equipo
     de Telcobras.
  2. Con los links del catálogo real, el % se calcula contra productos
     reales en vez de arquetipos.
  3. Registrar contactos desde ya (python main.py contacto ...) para la
     calibración.
=====================================================================
