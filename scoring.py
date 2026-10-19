"""
scoring.py
----------
MÓDULO 8 - Lead Score  (Capa 1 -- su lógica NO se modifica)

Aquí ocurre "la magia": convierte todas las validaciones y el análisis
web en un único número que te dice qué tan buen cliente potencial es
una empresa. Entre más alto, más interesante (normalmente = poca
presencia digital pero sí redes/contacto activo).

Nota Fase 2 (oct. 2026): el pipeline ahora SÍ le pasa numero_resenas
(antes siempre llegaba 0 y el bono "muchas_resenas" nunca aplicaba).
La penalización por dato inválido (sección 9.2) se aplica en el score
final (perfil_psicologico.py), no aquí, para no alterar la Capa 1.
"""

from __future__ import annotations

from . import config
from .validate import Validacion
from .web_analysis import AnalisisWeb


def calcular_lead_score(
    validacion: Validacion,
    analisis_web: AnalisisWeb | None,
    numero_resenas: int = 0,
) -> int:
    w = config.SCORING_WEIGHTS
    puntaje = 0

    if not validacion.tiene_web:
        puntaje += w["sin_web"]

    if validacion.tiene_facebook:
        puntaje += w["tiene_facebook"]
    if validacion.tiene_instagram:
        puntaje += w["tiene_instagram"]
    if validacion.tiene_whatsapp:
        puntaje += w["tiene_whatsapp"]
    if validacion.tiene_telefono:
        puntaje += w["tiene_telefono"]
    if validacion.tiene_correo:
        puntaje += w["tiene_correo"]

    if (numero_resenas or 0) >= config.RESENAS_UMBRAL:
        puntaje += w["muchas_resenas"]

    if not (validacion.tiene_facebook or validacion.tiene_instagram):
        puntaje += w["sin_redes"]

    if analisis_web is not None and analisis_web.accesible and analisis_web.puntaje >= config.WEB_SCORE_EXCELENTE:
        puntaje += w["web_excelente"]

    return max(puntaje, 0)


def clasificar_lead(puntaje: int) -> str:
    """Traduce el número a una etiqueta legible para el equipo comercial."""
    if puntaje >= 80:
        return "Cliente potencial muy fuerte"
    if puntaje >= 50:
        return "Cliente potencial bueno"
    if puntaje >= 25:
        return "Cliente potencial moderado"
    return "Baja prioridad"
