"""
discovery.py
------------
MÓDULO 2 - Descubrimiento

Dado un directorio (una URL con listado de empresas), encuentra los
enlaces a cada ficha de empresa individual.

Como cada directorio tiene una estructura HTML distinta, este módulo
funciona con "selectores" configurables (CSS selectors). Si no le pasas
ninguno, intenta una heurística genérica (Módulo 12: "aceptar cualquier
URL") que busca patrones típicos de tarjetas/listados.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import config


@dataclass
class EmpresaDescubierta:
    nombre: str
    url_perfil: str
    categoria: str = ""


def _get(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"[discovery] Error al obtener {url}: {e}")
        return None


def _heuristica_generica(soup: BeautifulSoup, base_url: str) -> list[EmpresaDescubierta]:
    """
    Módulo 12 (semilla): intenta detectar tarjetas de empresa sin
    configuración previa. Busca <a> dentro de elementos que parezcan
    tarjetas (article, li, div con clases típicas) y cuyo texto no esté vacío.
    """
    candidatos: list[EmpresaDescubierta] = []
    vistos = set()

    contenedores = soup.select(
        "article, li, div[class*=card], div[class*=listing], "
        "div[class*=item], div[class*=result]"
    )

    for cont in contenedores:
        enlace = cont.find("a", href=True)
        if not enlace:
            continue
        href = urljoin(base_url, enlace["href"])
        if href in vistos or urlparse(href).netloc != urlparse(base_url).netloc:
            continue
        nombre = enlace.get_text(strip=True) or cont.get_text(strip=True)[:80]
        if not nombre:
            continue
        vistos.add(href)
        candidatos.append(EmpresaDescubierta(nombre=nombre, url_perfil=href))

    return candidatos


def descubrir_empresas(
    url_directorio: str,
    selector_tarjeta: str | None = None,
    selector_enlace: str | None = None,
    selector_categoria: str | None = None,
    selector_siguiente_pagina: str | None = None,
    max_paginas: int = config.MAX_PAGINAS_DIRECTORIO,
    usar_navegador: bool = False,
    max_clics_cargar_mas: int = 5,
) -> list[EmpresaDescubierta]:
    """
    Recorre un directorio (con paginación opcional) y devuelve la lista
    de empresas encontradas con nombre + URL de su ficha.

    Parámetros:
        url_directorio: la URL inicial que escribe el usuario (Módulo 1).
        selector_tarjeta: selector CSS de cada "tarjeta" de empresa
            (ej: "div.business-card"). Si es None, usa la heurística genérica.
        selector_enlace: selector CSS (relativo a la tarjeta) del <a>
            que lleva a la ficha de la empresa.
        selector_categoria: selector CSS (relativo a la tarjeta) del texto
            de categoría, si existe.
        selector_siguiente_pagina: en modo normal, selector CSS del enlace
            "Siguiente" para paginar por URL. En modo navegador, selector
            CSS de un botón "Cargar más / Ver más" para hacerle clic
            repetidamente (típico en sitios con scroll infinito).
        max_paginas: límite de seguridad de páginas a recorrer (modo normal).
        usar_navegador: si True, usa Playwright para renderizar JavaScript
            antes de buscar las tarjetas. Actívalo cuando el sitio no
            muestre los datos en el HTML crudo (apps React/Next.js/Vue).
        max_clics_cargar_mas: en modo navegador, cuántas veces hacer clic
            en selector_siguiente_pagina como máximo.
    """
    if usar_navegador:
        from .browser import obtener_html_renderizado

        html = obtener_html_renderizado(
            url_directorio,
            esperar_selector=selector_tarjeta,
            click_selector=selector_siguiente_pagina,
            max_clicks=max_clics_cargar_mas,
        )
        soup = BeautifulSoup(html, "html.parser")

        if selector_tarjeta:
            resultados = []
            for t in soup.select(selector_tarjeta):
                enlace = t.select_one(selector_enlace) if selector_enlace else t.find("a", href=True)
                if not enlace or not enlace.get("href"):
                    continue
                href = urljoin(url_directorio, enlace["href"])
                nombre = enlace.get_text(strip=True)
                categoria = ""
                if selector_categoria:
                    cat_el = t.select_one(selector_categoria)
                    categoria = cat_el.get_text(strip=True) if cat_el else ""
                resultados.append(EmpresaDescubierta(nombre=nombre, url_perfil=href, categoria=categoria))
        else:
            resultados = _heuristica_generica(soup, url_directorio)

        vistos = set()
        unicos = []
        for e in resultados:
            if e.url_perfil not in vistos:
                vistos.add(e.url_perfil)
                unicos.append(e)
        return unicos

    # --- Modo normal (requests), con paginación por URL ---------------
    resultados: list[EmpresaDescubierta] = []
    url_actual = url_directorio
    paginas_recorridas = 0

    while url_actual and paginas_recorridas < max_paginas:
        soup = _get(url_actual)
        if soup is None:
            break

        if selector_tarjeta:
            tarjetas = soup.select(selector_tarjeta)
            for t in tarjetas:
                enlace = t.select_one(selector_enlace) if selector_enlace else t.find("a", href=True)
                if not enlace or not enlace.get("href"):
                    continue
                href = urljoin(url_actual, enlace["href"])
                nombre = enlace.get_text(strip=True)
                categoria = ""
                if selector_categoria:
                    cat_el = t.select_one(selector_categoria)
                    categoria = cat_el.get_text(strip=True) if cat_el else ""
                resultados.append(EmpresaDescubierta(nombre=nombre, url_perfil=href, categoria=categoria))
        else:
            resultados.extend(_heuristica_generica(soup, url_actual))

        # Paginación
        url_actual = None
        if selector_siguiente_pagina:
            sig = soup.select_one(selector_siguiente_pagina)
            if sig and sig.get("href"):
                url_actual = urljoin(url_directorio, sig["href"])

        paginas_recorridas += 1
        time.sleep(config.DELAY_BETWEEN_REQUESTS)

    # Deduplicar por URL de perfil
    vistos = set()
    unicos = []
    for e in resultados:
        if e.url_perfil not in vistos:
            vistos.add(e.url_perfil)
            unicos.append(e)

    return unicos
