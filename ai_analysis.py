"""
ai_analysis.py
--------------
MÓDULO 7 - IA (opcional)

Genera una observación cualitativa sobre la calidad del sitio web,
como "Este negocio podría aumentar conversiones con un rediseño
moderno". Es 100% opcional: si no configuras una API key de
Anthropic, el sistema sigue funcionando y simplemente se salta
este módulo (deja el campo vacío).

Para activarlo:
    1) pip install anthropic
    2) export ANTHROPIC_API_KEY="tu-clave"
"""

from __future__ import annotations

import os

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
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        return _observacion_por_reglas(analisis)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = PROMPT_BASE.format(
            https="Sí" if analisis.https else "No",
            tiempo=analisis.tiempo_carga_seg,
            responsive="Sí" if analisis.responsive else "No",
            formulario="Sí" if analisis.tiene_formulario else "No",
            analytics="Sí" if (analisis.google_analytics or analisis.google_tag_manager) else "No",
            puntaje=analisis.puntaje,
            cms=analisis.cms or "Ninguno detectado",
        )
        respuesta = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        return respuesta.content[0].text.strip()
    except Exception as e:
        print(f"[ai_analysis] Falló la llamada a la API, uso reglas simples: {e}")
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
