"""
web_analysis.py
---------------
MÓDULO 6 - Análisis Web

Si la empresa tiene sitio web, este módulo lo visita y evalúa:
HTTPS, tiempo de carga, responsive (viewport), CMS (WordPress/Wix/
Shopify), formulario de contacto, mapa embebido, SEO básico (título,
meta descripción, imágenes con/ sin alt), Google Analytics / Tag
Manager, robots.txt y sitemap.xml.

Con todo eso calcula un "puntaje web" de 0 a 100 que luego se usa en
el Módulo 8 para saber si la web ya es "excelente" (penaliza el lead)
o es débil/inexistente (favorece el lead).

Cambios Fase 2 (oct. 2026):
  - Rescate de señales de contacto desde el sitio propio (WhatsApp,
    Instagram, Facebook, correo, teléfono), porque Google Maps casi
    nunca las muestra (0 % de WhatsApp/Instagram en la exportación de
    oct. 2026). contacto_escaneado=True indica que SÍ se buscaron, para
    que la ausencia cuente como "No" medido y no como dato faltante.
  - Señales de presupuesto (píxel de Facebook, herramientas de pago) y
    texto visible de la página (para la Capa 5 / contexto de negocio).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import config


@dataclass
class AnalisisWeb:
    url: str = ""
    accesible: bool = False
    https: bool = False
    tiempo_carga_seg: float = 0.0
    responsive: bool = False
    cms: str = ""              # "WordPress" | "Wix" | "Shopify" | ""
    tiene_formulario: bool = False
    tiene_mapa: bool = False
    titulo: str = ""
    meta_descripcion: str = ""
    total_imagenes: int = 0
    imagenes_sin_alt: int = 0
    google_analytics: bool = False
    google_tag_manager: bool = False
    tiene_robots_txt: bool = False
    tiene_sitemap: bool = False
    puntaje: int = 0  # 0 a 100
    # --- Fase 2 ---
    contacto_escaneado: bool = False
    whatsapp: str = ""
    instagram: str = ""
    facebook: str = ""
    correo: str = ""
    telefono: str = ""
    pixel_facebook: bool = False
    herramientas_pago: list = field(default_factory=list)   # HubSpot, Hotjar, chat en vivo...
    texto: str = ""                                          # texto visible (máx. 6000 caracteres)

    def to_dict(self) -> dict:
        return asdict(self)


HERRAMIENTAS = {
    "HubSpot": "hs-scripts.com", "Hotjar": "hotjar.com", "Intercom": "intercom", "Tawk.to": "tawk.to",
    "Zendesk": "zendesk", "Mailchimp": "mailchimp", "Salesforce": "salesforce", "Google Ads": "googleadservices",
    "Clarity": "clarity.ms", "Shopify": "cdn.shopify.com",
}


def _detectar_cms(html: str) -> str:
    html_lower = html.lower()
    if "wp-content" in html_lower or "wordpress" in html_lower:
        return "WordPress"
    if "wix.com" in html_lower or "wixstatic" in html_lower:
        return "Wix"
    if "cdn.shopify.com" in html_lower or "shopify" in html_lower:
        return "Shopify"
    return ""


def _calcular_puntaje(a: AnalisisWeb) -> int:
    puntaje = 0
    if a.https:
        puntaje += 15
    if a.tiempo_carga_seg and a.tiempo_carga_seg < 2:
        puntaje += 15
    elif a.tiempo_carga_seg and a.tiempo_carga_seg < 4:
        puntaje += 8
    if a.responsive:
        puntaje += 15
    if a.titulo:
        puntaje += 10
    if a.meta_descripcion:
        puntaje += 10
    if a.total_imagenes and a.imagenes_sin_alt / max(a.total_imagenes, 1) < 0.3:
        puntaje += 5
    if a.tiene_formulario:
        puntaje += 10
    if a.tiene_mapa:
        puntaje += 5
    if a.google_analytics or a.google_tag_manager:
        puntaje += 10
    if a.tiene_robots_txt:
        puntaje += 2
    if a.tiene_sitemap:
        puntaje += 3
    return min(puntaje, 100)


def analizar_html(resultado: AnalisisWeb, html: str) -> AnalisisWeb:
    """Parte pura del análisis (sin red), separada para poder probarla."""
    from .scraper import _extraer_redes_y_contacto

    soup = BeautifulSoup(html, "html.parser")

    viewport = soup.find("meta", attrs={"name": "viewport"})
    resultado.responsive = viewport is not None
    resultado.cms = _detectar_cms(html)
    resultado.tiene_formulario = soup.find("form") is not None
    resultado.tiene_mapa = bool(
        soup.find("iframe", src=lambda s: s and ("maps.google" in s or "google.com/maps" in s or "openstreetmap" in s))
    )
    resultado.titulo = soup.title.get_text(strip=True) if soup.title else ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    resultado.meta_descripcion = meta_desc.get("content", "").strip() if meta_desc else ""

    imagenes = soup.find_all("img")
    resultado.total_imagenes = len(imagenes)
    resultado.imagenes_sin_alt = sum(1 for img in imagenes if not img.get("alt"))

    resultado.google_analytics = "gtag(" in html or "google-analytics.com" in html or "analytics.js" in html
    resultado.google_tag_manager = "googletagmanager.com" in html
    resultado.pixel_facebook = "connect.facebook.net" in html and "fbq(" in html
    resultado.herramientas_pago = [n for n, firma in HERRAMIENTAS.items() if firma in html.lower()]

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    texto = soup.get_text(" ", strip=True)
    contacto = _extraer_redes_y_contacto(soup, texto)
    resultado.contacto_escaneado = True
    resultado.whatsapp = contacto["whatsapp"]
    resultado.instagram = contacto["instagram"]
    resultado.facebook = contacto["facebook"]
    resultado.correo = contacto["correo"]
    resultado.telefono = contacto["telefono"]
    resultado.texto = texto[:6000]
    return resultado


def analizar_sitio(url: str) -> AnalisisWeb:
    resultado = AnalisisWeb(url=url)
    if not url:
        return resultado

    parsed = urlparse(url)
    resultado.https = parsed.scheme == "https"

    inicio = time.time()
    try:
        resp = requests.get(url, headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
        resultado.tiempo_carga_seg = round(time.time() - inicio, 2)
        resultado.accesible = resp.ok
        # Si hubo redirección a https, cuenta como https
        resultado.https = resultado.https or resp.url.startswith("https://")
        html = resp.text
    except requests.RequestException as e:
        print(f"[web_analysis] No se pudo analizar {url}: {e}")
        return resultado

    analizar_html(resultado, html)

    base = f"{parsed.scheme}://{parsed.netloc}"
    for ruta, campo in (("/robots.txt", "tiene_robots_txt"), ("/sitemap.xml", "tiene_sitemap")):
        try:
            r = requests.get(urljoin(base, ruta), headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
            setattr(resultado, campo, r.status_code == 200)
        except requests.RequestException:
            setattr(resultado, campo, False)

    resultado.puntaje = _calcular_puntaje(resultado)
    return resultado
