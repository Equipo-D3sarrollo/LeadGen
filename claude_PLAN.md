# PLAN.md — LeadGen psicológico-matemático (Telcobras)

Checklist por fase. El estado detallado, el % de avance y la bitácora viven en
**PROGRESO_LEADGEN.xlsx** (fuente de verdad del seguimiento). Objetivo: claude/OBJETIVO.md.

## Fase 0 — Gobernanza
- [x] PROGRESO_LEADGEN.xlsx, PLAN.md, DECISIONES.md
- [ ] Repositorio git con un commit por fase (falta definir dónde)

## Fase 1 — Catálogo de productos desde links (`leadgen/catalogo.py`)
- [x] Recorrido de links + páginas internas de producto (HTML, PDF, JSON-LD, tarjetas, títulos)
- [x] Motor IA (Claude, JSON validado) con respaldo por reglas (11 familias)
- [x] Vector ideal 6D + afinidad A_k por producto; investigación amplia (sectores, búsquedas, complementarios, oportunidades)
- [x] Fusión que protege productos aprobados/manuales; `python main.py catalogo <links> [--ia]`
- [ ] Correr con los links reales de Telcobras (BLOQUEADO: faltan links)
- [ ] Aprobación de vectores por Telcobras

## Fase 2 — Señales y correcciones
- [x] Bug teléfono concatenado (scraper.py + validación en normalize.py)
- [x] Ciudad / departamento / país desde la dirección
- [x] Páginas que no son empresa; empresas fuera de Colombia
- [x] Rating y reseñas de Maps (llegan al Lead Score); rescate de contacto desde la web; RDAP
- [x] Contexto de negocio (Capa 5) en `senales.py`
- [x] Tabla `contactos` + `python main.py contacto ...`
- [ ] RUES (verificar dataset) · [ ] evaluar Places API · [ ] corrida en vivo para medir cobertura

## Fase 3 — Perfil conductual (`leadgen/perfil.py`)
- [x] 6 dimensiones, sub-señales medida/no aplica/faltante, cobertura y confianza
- [ ] Correlaciones entre dimensiones con datos nuevos

## Fase 4 — Núcleo psicológico (`leadgen/perfil_psicologico.py`)
- [x] Softmax, punto (x,y,z,w), principal/secundaria, claridad, entropía, filtro
- [x] S y % de compatibilidad por producto; FIT/INTENT; score final α/β con penalización
- [x] Integrado al pipeline + `python main.py reprocesar`

## Fase 5 — Diagnóstico legible (`leadgen/diagnostico.py`)
- [x] Reglas (sin nombres de emociones) + IA con respaldo
- [ ] Léxico NRC en español como señal de baja confianza

## Fase 6 — Presentación
- [x] Export con columnas comerciales primero + hoja Contactos
- [ ] dashboard.py · [ ] emocion_empresas.html con empresas reales · [ ] decidir score único vs FIT/INTENT

## Fase 7 — Calibración
- [ ] Calibrar W, A_k y pesos con contactos · [ ] comparar con vs. sin componente emocional

## Cómo correr
```
pip install -r requirements.txt
python -m pytest tests            # 17 pruebas
python main.py catalogo https://... --ia
python main.py procesar "https://www.google.com/maps/search/clinicas+dentales+en+pereira" --ia
python main.py reprocesar --excel leads_export.xlsx --salida leads_analizados.xlsx
python main.py contacto "<url_perfil>" diseno_web --resultado interesado --canal whatsapp
python main.py exportar --formato excel
```
