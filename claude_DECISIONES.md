# DECISIONES.md — por qué cada fórmula y peso, y cuándo cambió

Todo valor numérico es **SUPUESTO INICIAL** hasta la calibración (Fase 7). La tabla
también está en la hoja "Decisiones" de PROGRESO_LEADGEN.xlsx.

| ID | Fecha | Decisión | Por qué |
|---|---|---|---|
| D-01 | 2026-10-06 | El catálogo se arma leyendo **links** (IA o reglas) e investigando cada producto (sectores, búsquedas, complementarios, oportunidades). | Pedido de Desarrollo. |
| D-02 | 2026-10-06 | Productos `aprobado` o `manual` nunca se sobreescriben al releer links. | No perder validación humana. |
| D-03 | 2026-10-06 | Cada sub-señal es *medida*, *no aplica* o *faltante*; cobertura = peso medido / (medido + faltante). | Regla de oro: nunca rellenar con cero. WhatsApp/correo/Instagram en Maps = faltante salvo que se escanee la web. |
| D-04 | 2026-10-06 | `b_k = −0.5·Σ_m W_km` (z = W·(s − 0.5)). | Con b = 0 todas las empresas salían "confianza" por construcción; así una empresa neutra tiene perfil uniforme. |
| D-05 | 2026-10-06 | `s_m = 0.5 + cobertura_m·(dim_m/100 − 0.5)`; igual en INTENT. | Una dimensión medida con 1 señal (ej. solo teléfono) salía 100 % y dominaba el perfil. |
| D-06 | 2026-10-06 | `S% = 50 + 50·(S − S0)/(maxA − S0)` si S ≥ S0, si no `50·(S − minA)/(S0 − minA)`, con S0 = media de A. | Min-max simple dejaba todo en ~92 % y favorecía productos con afinidades casi todas positivas; ahora 50 % = empresa neutra y es comparable entre productos. |
| D-07 | 2026-10-06 | Afinidades ajustadas: diseño web [.2 .3 .6 .2 .7 −.5 .1 .6], soporte TI [.1 .5 .3 .1 .2 −.3 .6 .2], seguridad (miedo .9→.6), hosting [.3 .5 .4 0 0 −.4 .1 .5]. | Revisión del Excel: empresas sin web salían recomendadas a soporte TI. |
| D-08 | 2026-10-06 | `web_puntaje = 0` sin `web_accesible` (exportaciones viejas) = no medido. | 156/247 webs con 0: indistinguible de un análisis fallido. |
| D-09 | 2026-10-06 | No-empresas y empresas fuera de Colombia se guardan pero sin score final. | No contaminar el ranking. |
| D-10 | 2026-10-06 | −5 pts del score final por dato inválido; la Capa 1 no se toca (sí recibe ahora el número de reseñas y teléfonos validados). | Investigación 9.2. |
| D-11 | 2026-10-06 | α = 0.4, β = 0.6; T = 0.5; θ1 = 0.25, θ2 = 0.05, θS = 55 %. | El núcleo psicológico es el centro del proyecto; umbrales del documento técnico, θS reexpresado en %. |
| D-12 | 2026-10-06 | Matriz W 8×6 (config.W_PSICO) definida a partir de la relación del doc. técnico §7: dolor→miedo/tristeza, dinamismo→anticipación/alegría, reputación→confianza, apertura→confianza vs. aversión. | Paso de 4 señales simuladas a las 6 dimensiones reales. |
