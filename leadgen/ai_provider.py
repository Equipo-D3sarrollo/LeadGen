"""Pequeños adaptadores para el cliente y las respuestas de OpenAI."""

from __future__ import annotations

import os
from pathlib import Path

from . import config


def crear_cliente(test: bool = False):
    """Crea un cliente real usando producción o una clave de prueba explícita."""
    from dotenv import load_dotenv
    from openai import OpenAI

    raiz_proyecto = Path(__file__).resolve().parent.parent
    nombre_variable = (
        config.OPENAI_API_KEY_TEST_ENV if test else config.OPENAI_API_KEY_ENV
    )
    archivo_entorno = raiz_proyecto / (".env.test" if test else ".env")
    load_dotenv(archivo_entorno, override=False)
    clave = os.environ.get(nombre_variable)
    if not clave:
        modo = "de prueba" if test else "de producción"
        raise RuntimeError(f"No hay una clave de OpenAI {modo} configurada")
    return OpenAI(api_key=clave)


def extraer_texto(respuesta) -> str:
    """Obtiene el texto de una respuesta de Responses API."""
    texto = getattr(respuesta, "output_text", None)
    if isinstance(texto, str):
        return texto
    raise ValueError("La respuesta de OpenAI no contiene texto")
