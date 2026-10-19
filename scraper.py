"""
scraper.py
----------
MÓDULO 3 - Recolección

Visita la ficha individual de cada empresa y extrae los datos crudos:
nombre, dirección, ciudad, teléfono, WhatsApp, correo, redes sociales,
sitio web, horario, descripción y categoría.

La extracción combina:
  1) Selectores CSS configurables (si conoces la estructura del sitio).
  2) Patrones genéricos (regex) que funcionan en casi cualquier página:
     teléfonos, emails y enlaces a redes sociales sueltos en el HTML.

Cambios Fase 2 (oct. 2026):
  - BUG teléfono concatenado: el regex anterior aceptaba espacios
    dentro del número y "se comía" varios números seguidos (ej. listas
    de resultados de lotería), que luego normalize.py pegaba en un solo
    número de 80 dígitos. Ahora: primero enlaces tel:, y si no hay, un
    regex acotado a 7-13 dígitos reales. La validación final del número
    se hace en normalize.normalizar_telefono_detalle().
  - Nuevos campos de señales: rating, numero_resenas, pais,
    datos_invalidos (lista de campos que llegaron corruptos).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict, field

import requests
from bs4 import BeautifulSoup

from . import config

REGEX_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# Un teléfono: dígitos con separadores simples de a un carácter, entre 7 y ~13 dígitos.
REGEX_TELEFONO = re.compile(r"(?<!\d)(\+?\(?\d{1,4}\)?(?:[ \-.]?\d){6,12})(?!\d)")
REGEX_WHATSAPP = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d+)")


@dataclass
class EmpresaCruda:
    nombre: str = ""
    url_perfil: str = ""
    direccion: str = ""
    ciudad: str = ""
    departamento: str = ""
    telefono: str = ""
    whatsapp: str = ""
    correo: str = ""
    facebook: str = ""
    instagram: str = ""
    sitio_web: str = ""
    horario: str = ""
    descripcion: str = ""
    categoria: str = ""
    # --- Fase 2: señales nuevas (None = no medido, nunca 0 por defecto) ---
    rating: float | None = None
    numero_resenas: int | None = None
    pais: str = ""
    datos_invalidos: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _texto_por_selector(soup: BeautifulSoup, selector: str | None) -> str:
    if not selector:
        return ""
    el = soup.select_one(selector)
    return el.get_text(" ", strip=True) if el else ""


def _extraer_redes_y_contacto(soup: BeautifulSoup, texto_completo: str) -> dict:
    datos = {"facebook": "", "instagram": "", "whatsapp": "", "correo": "", "telefono": "", "sitio_web": ""}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "facebook.com" in href and not datos["facebook"]:
            datos["facebook"] = href
        elif "instagram.com" in href and not datos["instagram"]:
            datos["instagram"] = href
        elif "wa.me" in href or "whatsapp.com" in href:
            match = REGEX_WHATSAPP.search(href)
            if match and not datos["whatsapp"]:
                datos["whatsapp"] = match.group(1)
        elif href.startswith("mailto:") and not datos["correo"]:
            datos["correo"] = href.replace("mailto:", "").split("?")[0]
        elif href.startswith("tel:") and not datos["telefono"]:
            datos["telefono"] = href[4:].strip()

    if not datos["correo"]:
        m = REGEX_EMAIL.search(texto_completo)
        if m:
            datos["correo"] = m.group(0)

    if not datos["telefono"]:
        m = REGEX_TELEFONO.search(texto_completo)
        if m:
            datos["telefono"] = m.group(1)

    return datos


def extraer_empresa(
    url_perfil: str,
    nombre_previo: str = "",
    categoria_previa: str = "",
    selectores: dict | None = None,
    usar_navegador: bool = False,
) -> EmpresaCruda:
    """
    Descarga la ficha de una empresa y extrae sus datos.

    `selectores` es un diccionario opcional con claves como:
    {
      "nombre": "h1.business-name",
      "direccion": ".address",
      "ciudad": ".city",
      "telefono": ".phone",
      "descripcion": ".about",
      "horario": ".hours",
      "sitio_web": "a.website-link",
    }
    Cualquier clave que falte se intenta rellenar con patrones genéricos.

    usar_navegador: si True, renderiza la ficha con Playwright antes de
        leerla (necesario si la ficha también carga datos con JavaScript).
    """
    selectores = selectores or {}
    empresa = EmpresaCruda(nombre=nombre_previo, url_perfil=url_perfil, categoria=categoria_previa)

    try:
        if usar_navegador:
            from .browser import obtener_html_renderizado
            html = obtener_html_renderizado(url_perfil)
        else:
            resp = requests.get(url_perfil, headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        print(f"[scraper] Error al visitar {url_perfil}: {e}")
        return empresa

    empresa = extraer_empresa_desde_html(html, empresa, selectores)
    time.sleep(config.DELAY_BETWEEN_REQUESTS)
    return empresa


def extraer_empresa_desde_html(html: str, empresa: EmpresaCruda, selectores: dict | None = None) -> EmpresaCruda:
    """Parte pura de la extracción (sin red), separada para poder probarla."""
    selectores = selectores or {}
    soup = BeautifulSoup(html, "html.parser")
    texto_completo = soup.get_text(" ", strip=True)

    empresa.nombre = _texto_por_selector(soup, selectores.get("nombre")) or empresa.nombre or (
        soup.title.get_text(strip=True) if soup.title else ""
    )
    empresa.direccion = _texto_por_selector(soup, selectores.get("direccion"))
    empresa.ciudad = _texto_por_selector(soup, selectores.get("ciudad"))
    empresa.departamento = _texto_por_selector(soup, selectores.get("departamento"))
    empresa.horario = _texto_por_selector(soup, selectores.get("horario"))
    empresa.descripcion = _texto_por_selector(soup, selectores.get("descripcion"))

    sitio_web_el = soup.select_one(selectores.get("sitio_web")) if selectores.get("sitio_web") else None
    if sitio_web_el and sitio_web_el.get("href"):
        empresa.sitio_web = sitio_web_el["href"]

    extra = _extraer_redes_y_contacto(soup, texto_completo)
    empresa.facebook = empresa.facebook or extra["facebook"]
    empresa.instagram = empresa.instagram or extra["instagram"]
    empresa.whatsapp = empresa.whatsapp or extra["whatsapp"]
    empresa.correo = empresa.correo or extra["correo"]
    empresa.telefono = _texto_por_selector(soup, selectores.get("telefono")) or extra["telefono"]
    if not empresa.sitio_web:
        empresa.sitio_web = extra["sitio_web"]

    return empresa
