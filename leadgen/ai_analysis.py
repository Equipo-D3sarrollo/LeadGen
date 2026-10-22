"""
ai_analysis.py
--------------
MÓDULO 7 - IA (opcional)

Genera una observación cualitativa sobre la calidad del sitio web,
como "Este negocio podría aumentar conversiones con un rediseño
moderno". Es 100% opcional: si no configuras una API key de
OpenAI, el sistema sigue funcionando mediante las reglas locales.

Para activarlo:
    1) pip install openai
    2) export OPENAI_API_KEY="tu-clave"
"""

from __future__ import annotations

import time
import uuid

from . import ai_provider, ai_usage, config
from .web_analysis import AnalisisWeb

PROMPT_BASE = """Eres un consultor de marketing digital. Con base en estos datos
técnicos de un sitio web, escribe UNA sola frase corta (máx. 25 palabras) en
español, dirigida a explicar a un equipo comercial por qué esta empresa podría
necesitar un rediseño o mejora digital. Sé concreto y evita generalidades.

Datos del sitio:
- HTTPS: {https}
- Tiempo de carga: {tiempo}s
- Responsive (adaptado a móvil): {responsive}
- Tiene formulario de contacto: {formulario}
- Tiene Google Analytics/Tag Manager: {analytics}
- Puntaje técnico (0-100): {puntaje}
- CMS detectado: {cms}
"""


def generar_observacion(analisis: AnalisisWeb) -> str:
    """
    Devuelve una observación generada por IA, o una observación por
    reglas simples si no hay API key configurada (para que el pipeline
    nunca se rompa por falta de este módulo opcional).
    """
    try:
        client = ai_provider.crear_cliente()
    except RuntimeError as error:
        if "No hay una clave de OpenAI" in str(error):
            return _observacion_por_reglas(analisis)
        raise

    ejecucion_id = str(uuid.uuid4())
    inicio = time.perf_counter()
    try:
        prompt = PROMPT_BASE.format(
            https="Sí" if analisis.https else "No",
            tiempo=analisis.tiempo_carga_seg,
            responsive="Sí" if analisis.responsive else "No",
            formulario="Sí" if analisis.tiene_formulario else "No",
            analytics="Sí" if (analisis.google_analytics or analisis.google_tag_manager) else "No",
            puntaje=analisis.puntaje,
            cms=analisis.cms or "Ninguno detectado",
        )
        respuesta = client.responses.create(
            model=config.OPENAI_MODELO,
            max_output_tokens=config.OBSERVACION_MAX_OUTPUT_TOKENS,
            input=prompt,
        )
        ai_usage.registrar_uso(
            "observacion_web", config.OPENAI_MODELO, respuesta,
            proveedor=config.PROVEEDOR_IA, estado="success",
            duracion_ms=round((time.perf_counter() - inicio) * 1000),
            ejecucion_id=ejecucion_id,
        )
    except Exception as e:
        ai_usage.registrar_uso(
            "observacion_web", config.OPENAI_MODELO, None,
            proveedor=config.PROVEEDOR_IA, estado="error",
            duracion_ms=round((time.perf_counter() - inicio) * 1000),
            ejecucion_id=ejecucion_id, tipo_error=type(e).__name__,
        )
        print(f"[ai_analysis] Falló la llamada a la API, uso reglas simples: {e}")
        return _observacion_por_reglas(analisis)
    try:
        return ai_provider.extraer_texto(respuesta).strip()
    except Exception as e:
        print(f"[ai_analysis] Respuesta no utilizable, uso reglas simples: {type(e).__name__}")
        return _observacion_por_reglas(analisis)


def _observacion_por_reglas(analisis: AnalisisWeb) -> str:
    """Fallback sin IA: genera una observación simple basada en reglas."""
    if not analisis.accesible:
        return "El sitio no cargó correctamente; podría estar caído o mal configurado."

    problemas = []
    if not analisis.https:
        problemas.append("no usa HTTPS")
    if not analisis.responsive:
        problemas.append("no está adaptado a móviles")
    if analisis.tiempo_carga_seg and analisis.tiempo_carga_seg > 4:
        problemas.append("carga lenta")
    if not analisis.tiene_formulario:
        problemas.append("no tiene formulario de contacto")
    if not (analisis.google_analytics or analisis.google_tag_manager):
        problemas.append("no mide tráfico con analítica")

    if not problemas:
        return "El sitio cumple los aspectos técnicos básicos; revisar oportunidades de contenido/SEO."

    return "Este negocio podría mejorar su web: " + ", ".join(problemas) + "."
