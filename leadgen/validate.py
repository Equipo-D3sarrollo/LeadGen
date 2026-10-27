"""
validate.py
-----------
MÓDULO 5 - Validación

Convierte los datos normalizados en respuestas Sí/No:
¿Tiene teléfono? ¿Tiene correo? ¿Tiene página web? ¿Tiene Facebook?
¿Tiene Instagram? etc. Estas banderas alimentan directamente el
Módulo 8 (Lead Score).

Cambios Fase 2 (oct. 2026):
  - es_empresa: detecta páginas del directorio que NO son fichas de
    empresa (categorías, paginación, resultados de lotería...). En la
    exportación de oct. 2026, la mayoría de las 44 filas de yelu.com.co
    eran de este tipo.
  - fuera_de_mercado: dirección fuera de config.PAIS_OBJETIVO.
  - datos_invalidos: número de campos que llegaron corruptos (scoring
    negativo explícito, sección 9.2 de la investigación).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from . import config
from .scraper import EmpresaCruda

_RUTAS_NO_EMPRESA = re.compile(
    r"/(category|categoria|categorias|lottery|loteria|resultados|search|buscar|tag|page|pagina|"
    r"contact-us|contacto|about|nosotros|privacy|privacidad|terms|terminos|faq|blog|buzz|articles|"
    r"public-holidays|festivos|login|register|registro|create-[a-z-]+|add-[a-z-]+|"
    r"[a-z-]*directories[a-z-]*|saas|baloto|superastro)(/|$|:)", re.I
)


@dataclass
class Validacion:
    tiene_telefono: bool
    tiene_whatsapp: bool
    tiene_correo: bool
    tiene_web: bool
    tiene_facebook: bool
    tiene_instagram: bool
    tiene_direccion: bool
    tiene_horario: bool
    tiene_descripcion: bool
    # Fase 2
    es_empresa: bool = True
    fuera_de_mercado: bool = False
    datos_invalidos: int = 0


def parece_no_empresa(nombre: str, url_perfil: str) -> bool:
    """Heurística: la 'empresa' es en realidad una página de navegación del directorio."""
    nombre = (nombre or "").strip()
    ruta = urlparse(url_perfil or "").path
    if "google.com/maps" in (url_perfil or ""):
        return False
    if _RUTAS_NO_EMPRESA.search(ruta) or ruta in ("", "/"):
        return True
    if not nombre or nombre.isdigit():
        return True
    if re.search(r"(último sorteo|ultimo sorteo|estad[ií]stica|resultados)", nombre, re.I):
        return True
    return False


def validar_empresa(empresa: EmpresaCruda) -> Validacion:
    pais = getattr(empresa, "pais", "") or ""
    invalidos = getattr(empresa, "datos_invalidos", []) or []
    return Validacion(
        tiene_telefono=bool(empresa.telefono),
        tiene_whatsapp=bool(empresa.whatsapp),
        tiene_correo=bool(empresa.correo),
        tiene_web=bool(empresa.sitio_web),
        tiene_facebook=bool(empresa.facebook),
        tiene_instagram=bool(empresa.instagram),
        tiene_direccion=bool(empresa.direccion),
        tiene_horario=bool(empresa.horario),
        tiene_descripcion=bool(empresa.descripcion),
        es_empresa=not parece_no_empresa(empresa.nombre, empresa.url_perfil),
        fuera_de_mercado=bool(pais) and pais != config.PAIS_OBJETIVO,
        datos_invalidos=len(invalidos),
    )
