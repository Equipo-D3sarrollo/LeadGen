"""
catalogo.py
-----------
FASE 1 - Catálogo de productos/servicios a partir de LINKS.

En vez de escribir el catálogo a mano, se le pasan a LeadGen uno o
varios links (la página de servicios de Telcobras, un PDF publicado,
la tienda de un aliado, etc.). Este módulo:

  1. Recorre cada link y sus páginas internas más "de producto"
     (servicios, soluciones, planes, productos...), hasta
     config.CATALOGO_MAX_PAGINAS por link.
  2. Extrae bloques candidatos a producto: datos estructurados
     (JSON-LD Product/Service/Offer), títulos h1-h4 con su texto, y
     tarjetas típicas de catálogo.
  3. Convierte cada producto en lo que necesita el motor psicológico:
       - vector_ideal: las 6 dimensiones de la Capa 2 (0-100) del
         cliente ideal de ese producto.
       - afinidad (A_k): 8 valores en [-1, 1], uno por emoción de
         Plutchik, para el puntaje de venta S = Σ p_k·A_k.
  4. INVESTIGA OPCIONES más amplias por producto: sectores objetivo,
     búsquedas sugeridas para Google Maps/directorios y productos
     complementarios (venta cruzada).

  Dos motores:
  - Con OPENAI_API_KEY: OpenAI lee el texto del catálogo y devuelve
    los productos en JSON (con justificación por vector).
  - Sin API key (o si la API falla): reglas por familias de producto
    (léxico de palabras clave + arquetipos). Nunca rompe el pipeline.

TODO vector generado es un SUPUESTO INICIAL (estado "borrador") hasta
que alguien de Telcobras lo apruebe (estado "aprobado"); los productos
aprobados nunca se sobreescriben al volver a leer los links.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

from . import ai_provider, ai_usage, config

# ---------------------------------------------------------------------------
# Familias de producto (arquetipos). Supuestos iniciales: ver DECISIONES.md
# vector_ideal en el orden de config.DIMENSIONES; afinidad en el de config.EMOCIONES
# ---------------------------------------------------------------------------
FAMILIAS: dict[str, dict] = {
    "diseno_web": {
        "nombre": "Diseño / rediseño web",
        "palabras": ["pagina web", "paginas web", "sitio web", "sitios web", "diseno web", "desarrollo web",
                     "landing", "tienda virtual", "tienda online", "e-commerce", "ecommerce", "wordpress",
                     "rediseno", "portal web"],
        "dolor": "Presencia digital débil o inexistente: el cliente no lo encuentra o la web no convierte.",
        "vector_ideal": [25, 85, 50, 60, 70, 35],
        "afinidad": [0.2, 0.3, 0.6, 0.2, 0.7, -0.5, 0.1, 0.6],
        "sectores": ["clínicas y consultorios", "restaurantes", "abogados", "ferreterías", "agencias de viajes",
                     "inmobiliarias", "talleres"],
        "complementarios": ["marketing_seo", "chatbot_automatizacion", "cloud_hosting"],
    },
    "marketing_seo": {
        "nombre": "Marketing digital / SEO",
        "palabras": ["seo", "posicionamiento", "google ads", "pauta", "publicidad digital", "marketing digital",
                     "redes sociales", "community manager", "sem", "trafico", "campanas"],
        "dolor": "Tiene presencia pero no genera clientes: poca visibilidad o pocas conversiones.",
        "vector_ideal": [55, 60, 60, 70, 70, 50],
        "afinidad": [0.6, 0.5, -0.1, 0.2, 0.1, -0.5, -0.3, 0.9],
        "sectores": ["clínicas estéticas y dentales", "restaurantes", "hoteles", "comercio minorista", "educación"],
        "complementarios": ["diseno_web", "chatbot_automatizacion"],
    },
    "chatbot_automatizacion": {
        "nombre": "Chatbot / automatización con IA",
        "palabras": ["chatbot", "bot", "whatsapp business", "automatizacion", "inteligencia artificial",
                     "asistente virtual", "agente ia", "atencion automatica", "omnicanal", " ia "],
        "dolor": "Muchos mensajes y poca capacidad de respuesta: se pierden clientes por demora.",
        "vector_ideal": [60, 55, 65, 70, 85, 55],
        "afinidad": [0.5, 0.4, 0.1, 0.4, 0.0, -0.5, 0.2, 0.8],
        "sectores": ["clínicas", "agencias de viajes", "concesionarios", "inmobiliarias", "restaurantes con domicilios"],
        "complementarios": ["diseno_web", "software_erp", "telefonia"],
    },
    "conectividad": {
        "nombre": "Internet / conectividad empresarial",
        "palabras": ["internet", "fibra optica", "banda ancha", "canal dedicado", "conectividad", "wifi",
                     "radioenlace", "enlace", "mpls", "sd-wan", "ftth", "megas"],
        "dolor": "Conexión inestable o lenta que frena la operación diaria.",
        "vector_ideal": [50, 60, 60, 60, 60, 50],
        "afinidad": [0.3, 0.6, 0.5, 0.1, 0.0, -0.3, 0.4, 0.5],
        "sectores": ["oficinas", "hoteles", "colegios", "centros médicos", "conjuntos comerciales", "bodegas"],
        "complementarios": ["telefonia", "redes_cableado", "ciberseguridad"],
    },
    "telefonia": {
        "nombre": "Telefonía IP / comunicaciones",
        "palabras": ["telefonia", "pbx", "voip", "conmutador", "call center", "troncal sip", "planta telefonica",
                     "comunicaciones unificadas", "contact center", "extensiones"],
        "dolor": "Llamadas perdidas, costos altos de telefonía o atención telefónica desordenada.",
        "vector_ideal": [50, 55, 60, 60, 75, 50],
        "afinidad": [0.3, 0.6, 0.3, 0.1, 0.0, -0.4, 0.4, 0.5],
        "sectores": ["clínicas", "agencias", "firmas de abogados", "call centers", "distribuidoras"],
        "complementarios": ["conectividad", "chatbot_automatizacion"],
    },
    "redes_cableado": {
        "nombre": "Redes y cableado estructurado",
        "palabras": ["cableado estructurado", "cableado", "redes", "rack", "switch", "certificacion de puntos",
                     "puntos de red", "infraestructura de red", "centro de datos", "datacenter"],
        "dolor": "Infraestructura de red improvisada que falla o no deja crecer.",
        "vector_ideal": [45, 60, 60, 65, 55, 45],
        "afinidad": [0.3, 0.6, 0.4, 0.0, 0.1, -0.3, 0.3, 0.6],
        "sectores": ["oficinas nuevas o en remodelación", "colegios", "clínicas", "bodegas", "constructoras"],
        "complementarios": ["conectividad", "seguridad_electronica", "soporte_ti"],
    },
    "seguridad_electronica": {
        "nombre": "Seguridad electrónica (CCTV, acceso)",
        "palabras": ["camaras", "cctv", "videovigilancia", "control de acceso", "alarmas", "seguridad electronica",
                     "biometrico", "monitoreo"],
        "dolor": "Riesgo de robo o falta de control de quién entra y sale.",
        "vector_ideal": [40, 65, 55, 55, 55, 45],
        "afinidad": [0.0, 0.4, 0.6, 0.3, 0.0, -0.3, 0.2, 0.2],
        "sectores": ["ferreterías", "comercio", "bodegas", "conjuntos residenciales", "estaciones de servicio"],
        "complementarios": ["redes_cableado", "conectividad"],
    },
    "software_erp": {
        "nombre": "Software de gestión / ERP",
        "palabras": ["erp", "odoo", "software", "facturacion electronica", "crm", "inventario", "nomina",
                     "contabilidad", "punto de venta", "pos", "gestion empresarial"],
        "dolor": "Procesos manuales en Excel/papel que generan errores y no escalan.",
        "vector_ideal": [60, 55, 65, 70, 60, 60],
        "afinidad": [0.5, 0.6, 0.2, 0.0, 0.2, -0.5, 0.3, 0.8],
        "sectores": ["distribuidoras", "ferreterías", "pymes de servicios", "manufactura", "comercio"],
        "complementarios": ["cloud_hosting", "chatbot_automatizacion", "soporte_ti"],
    },
    "cloud_hosting": {
        "nombre": "Hosting, dominios y nube",
        "palabras": ["hosting", "dominio", "servidor", "servidores", "nube", "cloud", "correo corporativo",
                     "backup", "copias de seguridad", "microsoft 365", "google workspace"],
        "dolor": "Correo o archivos poco confiables, sin respaldo ni imagen profesional.",
        "vector_ideal": [55, 55, 55, 60, 55, 50],
        "afinidad": [0.3, 0.5, 0.4, 0.0, 0.0, -0.4, 0.1, 0.5],
        "sectores": ["pymes", "profesionales independientes", "consultorios", "agencias"],
        "complementarios": ["diseno_web", "ciberseguridad"],
    },
    "ciberseguridad": {
        "nombre": "Ciberseguridad",
        "palabras": ["ciberseguridad", "firewall", "antivirus", "seguridad informatica", "ethical hacking",
                     "pentesting", "ransomware", "proteccion de datos", "vpn"],
        "dolor": "Exposición a ataques, robo de datos o incumplimiento de protección de datos.",
        "vector_ideal": [70, 60, 65, 55, 50, 65],
        "afinidad": [0.1, 0.4, 0.8, 0.2, -0.2, -0.4, -0.3, 0.3],
        "sectores": ["clínicas (historias clínicas)", "firmas de abogados", "contadores", "comercio electrónico"],
        "complementarios": ["cloud_hosting", "conectividad", "soporte_ti"],
    },
    "soporte_ti": {
        "nombre": "Soporte técnico / outsourcing TI",
        "palabras": ["soporte tecnico", "mesa de ayuda", "mantenimiento", "outsourcing", "computadores",
                     "equipos de computo", "help desk", "reparacion"],
        "dolor": "Fallas de equipos que paran el trabajo y nadie dedicado a resolverlas.",
        "vector_ideal": [45, 65, 55, 55, 55, 40],
        "afinidad": [0.1, 0.5, 0.3, 0.1, 0.2, -0.3, 0.6, 0.2],
        "sectores": ["oficinas pequeñas", "colegios", "consultorios", "contadores"],
        "complementarios": ["redes_cableado", "ciberseguridad", "cloud_hosting"],
    },
}

PALABRAS_RUTA_PRODUCTO = ["servicio", "servicios", "producto", "productos", "solucion", "soluciones", "plan",
                          "planes", "catalogo", "portafolio", "tienda", "shop", "oferta", "precios", "pricing"]

UMBRAL_FAMILIA = 1.0   # puntaje mínimo de coincidencia para asignar familia por reglas


# ---------------------------------------------------------------------------
# Modelo de datos
# ---------------------------------------------------------------------------
@dataclass
class Producto:
    id: str
    nombre: str
    descripcion: str = ""
    familia: str = "otra"
    dolor_que_resuelve: str = ""
    sectores_objetivo: list = field(default_factory=list)
    tamano_empresa_objetivo: str = ""
    vector_ideal: dict = field(default_factory=dict)      # dimension -> 0..100
    afinidad: dict = field(default_factory=dict)          # emocion -> -1..1
    consultas_busqueda: list = field(default_factory=list)
    productos_complementarios: list = field(default_factory=list)
    justificacion: str = ""
    fuente_urls: list = field(default_factory=list)
    metodo: str = "reglas"                                # "ia" | "reglas" | "manual"
    confianza: str = "baja"                               # baja | media | alta
    estado: str = "borrador"                              # borrador | aprobado
    umbral_s_pct: float | None = None                      # filtro propio (None = config.UMBRAL_S_PCT)
    fecha: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Bloque:
    titulo: str
    texto: str
    url: str
    origen: str  # "jsonld" | "titulo" | "tarjeta"


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------
def _sin_tildes(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    return "".join(c for c in txt if not unicodedata.combining(c)).lower()


def _slug(txt: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _sin_tildes(txt)).strip("_")[:60] or "producto"


def _limpio(txt: str) -> str:
    return re.sub(r"\s+", " ", txt or "").strip()


# ---------------------------------------------------------------------------
# 1) Descarga y recorrido de links
# ---------------------------------------------------------------------------
def _descargar(url: str, usar_navegador: bool = False) -> str:
    try:
        if usar_navegador:
            from .browser import obtener_html_renderizado
            return obtener_html_renderizado(url)
        import requests
        resp = requests.get(url, headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        if "pdf" in resp.headers.get("content-type", ""):
            return _texto_pdf(resp.content)
        resp.encoding = resp.encoding or resp.apparent_encoding
        return resp.text
    except Exception as e:  # nunca rompe: se reporta y se sigue con el resto de links
        print(f"[catalogo] No se pudo leer {url}: {e}")
        return ""


def _texto_pdf(contenido: bytes) -> str:
    """Catálogos en PDF: se convierte el texto en un HTML mínimo (un <h3> por línea en mayúsculas)."""
    try:
        import io
        from pypdf import PdfReader
        texto = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(contenido)).pages)
    except Exception as e:
        print(f"[catalogo] PDF no legible ({e}); instala pypdf para catálogos en PDF.")
        return ""
    html = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        es_titulo = len(linea) < 70 and (linea.isupper() or linea.istitle())
        html.append(f"<h3>{linea}</h3>" if es_titulo else f"<p>{linea}</p>")
    return "<html><body>" + "\n".join(html) + "</body></html>"


def _prioridad_link(url: str, texto: str) -> int:
    base = _sin_tildes(urlparse(url).path + " " + texto)
    return sum(1 for p in PALABRAS_RUTA_PRODUCTO if p in base) + sum(
        1 for f in FAMILIAS.values() for p in f["palabras"] if p in base
    )


def recorrer_links(
    urls: list[str],
    max_paginas: int = config.CATALOGO_MAX_PAGINAS,
    usar_navegador: bool = False,
    descargar=_descargar,
) -> dict[str, str]:
    """
    Devuelve {url: html} de cada link inicial y de las páginas internas
    (mismo dominio) con más "olor a producto". `descargar` es inyectable
    para pruebas sin red.
    """
    from bs4 import BeautifulSoup

    paginas: dict[str, str] = {}
    for inicial in urls:
        dominio = urlparse(inicial).netloc
        cola: deque[tuple[int, str]] = deque([(99, inicial)])
        vistas: set[str] = set()
        leidas = 0
        while cola and leidas < max_paginas:
            _, url = cola.popleft()
            url = urldefrag(url)[0]
            if url in vistas or url in paginas:
                continue
            vistas.add(url)
            html = descargar(url, usar_navegador) if descargar is _descargar else descargar(url)
            leidas += 1
            if not html:
                continue
            paginas[url] = html
            soup = BeautifulSoup(html, "html.parser")
            candidatos = []
            for a in soup.find_all("a", href=True):
                destino = urldefrag(urljoin(url, a["href"]))[0]
                if urlparse(destino).netloc != dominio or destino in vistas:
                    continue
                if re.search(r"\.(jpg|jpeg|png|gif|svg|zip|mp4|css|js)$", destino, re.I):
                    continue
                prio = _prioridad_link(destino, a.get_text(" ", strip=True))
                if prio > 0:
                    candidatos.append((prio, destino))
            for prio, destino in sorted(candidatos, reverse=True):
                cola.append((prio, destino))
            cola = deque(sorted(cola, key=lambda x: -x[0]))
    return paginas


# ---------------------------------------------------------------------------
# 2) Extracción de bloques candidatos a producto
# ---------------------------------------------------------------------------
def _bloques_jsonld(soup, url: str) -> list[Bloque]:
    bloques = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            datos = json.loads(script.string or "")
        except Exception:
            continue
        pila = datos if isinstance(datos, list) else [datos]
        while pila:
            nodo = pila.pop()
            if isinstance(nodo, list):
                pila.extend(nodo)
                continue
            if not isinstance(nodo, dict):
                continue
            tipo = nodo.get("@type", "")
            tipo = " ".join(tipo) if isinstance(tipo, list) else str(tipo)
            if any(t in tipo for t in ("Product", "Service", "Offer")) and nodo.get("name"):
                bloques.append(Bloque(_limpio(nodo["name"]), _limpio(str(nodo.get("description", ""))), url, "jsonld"))
            for clave in ("@graph", "itemListElement", "hasOfferCatalog", "makesOffer", "itemOffered", "item"):
                if clave in nodo:
                    pila.append(nodo[clave])
    return bloques


def _bloques_titulos(soup, url: str) -> list[Bloque]:
    bloques = []
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        titulo = _limpio(h.get_text(" ", strip=True))
        if not (3 <= len(titulo) <= 90):
            continue
        partes = []
        for sib in h.find_all_next():
            if sib.name in ("h1", "h2", "h3", "h4"):
                break
            if sib.name in ("p", "li"):
                partes.append(sib.get_text(" ", strip=True))
            if sum(len(p) for p in partes) > 700:
                break
        bloques.append(Bloque(titulo, _limpio(" ".join(partes))[:900], url, "titulo"))
    return bloques


def _bloques_tarjetas(soup, url: str) -> list[Bloque]:
    bloques = []
    patron = re.compile(r"(product|servic|card|plan|item|solucion|feature)", re.I)
    for el in soup.find_all(["div", "article", "li"], class_=patron):
        tit = el.find(["h2", "h3", "h4", "h5", "strong"])
        if not tit:
            continue
        titulo = _limpio(tit.get_text(" ", strip=True))
        texto = _limpio(el.get_text(" ", strip=True).replace(titulo, "", 1))
        if 3 <= len(titulo) <= 90 and len(texto) >= 15:
            bloques.append(Bloque(titulo, texto[:900], url, "tarjeta"))
    return bloques


def extraer_bloques(paginas: dict[str, str]) -> list[Bloque]:
    from bs4 import BeautifulSoup

    todos: list[Bloque] = []
    for url, html in paginas.items():
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            if tag.name == "script" and tag.get("type") == "application/ld+json":
                continue
            tag.decompose()
        todos += _bloques_jsonld(soup, url)
        for tag in soup.find_all(["nav", "footer", "header"]):
            tag.decompose()
        todos += _bloques_tarjetas(soup, url) + _bloques_titulos(soup, url)
    # quitar duplicados por título (se queda el de más texto)
    unicos: dict[str, Bloque] = {}
    for b in todos:
        k = _slug(b.titulo)
        if k not in unicos or len(b.texto) > len(unicos[k].texto):
            unicos[k] = b
    return list(unicos.values())


# ---------------------------------------------------------------------------
# 3a) Motor por reglas
# ---------------------------------------------------------------------------
def clasificar_texto(titulo: str, texto: str = "") -> tuple[str, float]:
    """Devuelve (familia, puntaje). El título pesa el triple que el cuerpo."""
    t_tit = f" {_sin_tildes(titulo)} "
    t_txt = f" {_sin_tildes(texto)} "
    mejor, puntaje_mejor = "otra", 0.0
    for fid, fam in FAMILIAS.items():
        p = 0.0
        for palabra in fam["palabras"]:
            if palabra in t_tit:
                p += 3.0
            p += min(t_txt.count(palabra), 3) * 0.5
        if p > puntaje_mejor:
            mejor, puntaje_mejor = fid, p
    return mejor, puntaje_mejor


TITULOS_GENERICOS = {"inicio", "contacto", "contactenos", "nosotros", "quienes somos", "blog", "home",
                     "nuestros servicios", "servicios", "productos", "nuestros productos", "soluciones",
                     "clientes", "testimonios", "preguntas frecuentes", "faq", "mision", "vision"}


def _consultas_sugeridas(sectores: list[str], ciudades: list[str] | None = None) -> list[str]:
    ciudades = ciudades or ["Cali", "Pereira", "Manizales"]
    return [f"{s} en {c}" for s in sectores[:4] for c in ciudades[:2]]


def _producto_desde_familia(fid: str, nombre: str, descripcion: str, urls: list[str], puntaje: float) -> Producto:
    fam = FAMILIAS[fid]
    return Producto(
        id=_slug(nombre),
        nombre=nombre,
        descripcion=descripcion[:400],
        familia=fid,
        dolor_que_resuelve=fam["dolor"],
        sectores_objetivo=list(fam["sectores"]),
        vector_ideal=dict(zip(config.DIMENSIONES, fam["vector_ideal"])),
        afinidad=dict(zip(config.EMOCIONES, fam["afinidad"])),
        consultas_busqueda=_consultas_sugeridas(fam["sectores"]),
        productos_complementarios=[FAMILIAS[c]["nombre"] for c in fam["complementarios"]],
        justificacion=f"Arquetipo '{fam['nombre']}' asignado por reglas (coincidencia {puntaje:.1f}).",
        fuente_urls=urls,
        metodo="reglas",
        confianza="media" if puntaje >= 4 else "baja",
    )


def construir_por_reglas(bloques: list[Bloque]) -> list[Producto]:
    productos: dict[str, Producto] = {}
    for b in bloques:
        if _sin_tildes(b.titulo).strip(" :") in TITULOS_GENERICOS:
            continue
        fid, puntaje = clasificar_texto(b.titulo, b.texto)
        bono = 1.0 if b.origen == "jsonld" else 0.0
        if fid == "otra" or puntaje + bono < UMBRAL_FAMILIA:
            continue
        p = _producto_desde_familia(fid, b.titulo, b.texto, [b.url], puntaje + bono)
        if p.id not in productos:
            productos[p.id] = p
        elif b.url not in productos[p.id].fuente_urls:
            productos[p.id].fuente_urls.append(b.url)
    return list(productos.values())


# ---------------------------------------------------------------------------
# 3b) Motor con IA (OpenAI)
# ---------------------------------------------------------------------------
PROMPT_CATALOGO = """Eres analista comercial B2B en Colombia. Usa únicamente el texto
suministrado del catálogo.

Tarea:
1) Identifica cada producto o servicio REAL que se vende; no incluyas secciones institucionales.
2) Para cada uno define el CLIENTE IDEAL con 6 dimensiones (0-100):
   madurez_digital (qué tan digitalizada está la empresa que lo compra),
   dolor_urgencia (cuánto le duele hoy la carencia que el producto resuelve),
   confianza_reputacion (reputación/estabilidad del comprador típico),
   dinamismo (actividad, crecimiento, cambios recientes),
   apertura_comercial (qué tan fácil es contactarlo y que responda),
   sofisticacion_marca (cuidado de su imagen/marca).
3) Define la AFINIDAD del producto (-1 a 1) con la postura comercial dominante del comprador,
   usando las 8 emociones de Plutchik como proxies de negocio: alegria (bonanza, optimismo),
   confianza (estabilidad), miedo (riesgo percibido), sorpresa (cambio inesperado),
   tristeza (estancamiento), aversion (rechazo, cerrado a proveedores), ira (frustración con
   un problema actual), anticipacion (planea crecer).
4) Identifica sectores objetivo concretos, búsquedas sugeridas para Google Maps
   ("<tipo de negocio> en <ciudad colombiana>"), productos complementarios y oportunidades
   adicionales inferibles del texto suministrado.

No inventes productos, características ni datos que no estén sustentados por el catálogo.
Familias válidas: {familias}. Si ninguna aplica usa "otra".

TEXTO DEL CATÁLOGO:
{texto}
"""


def _esquema_catalogo_ia() -> dict:
    """Esquema de la parte del catálogo que la IA proporciona."""
    producto = {
        "type": "object",
        "properties": {
            "nombre": {"type": "string"},
            "descripcion": {"type": "string"},
            "familia": {"type": "string", "enum": [*FAMILIAS, "otra"]},
            "dolor_que_resuelve": {"type": "string"},
            "sectores_objetivo": {"type": "array", "items": {"type": "string"}},
            "tamano_empresa_objetivo": {"type": "string"},
            "vector_ideal": {
                "type": "object",
                "properties": {
                    dimension: {"type": "number", "minimum": 0, "maximum": 100}
                    for dimension in config.DIMENSIONES
                },
                "required": list(config.DIMENSIONES),
                "additionalProperties": False,
            },
            "afinidad": {
                "type": "object",
                "properties": {
                    emocion: {"type": "number", "minimum": -1, "maximum": 1}
                    for emocion in config.EMOCIONES
                },
                "required": list(config.EMOCIONES),
                "additionalProperties": False,
            },
            "consultas_busqueda": {"type": "array", "items": {"type": "string"}},
            "productos_complementarios": {"type": "array", "items": {"type": "string"}},
            "justificacion": {"type": "string"},
        },
        "required": [
            "nombre", "descripcion", "familia", "dolor_que_resuelve",
            "sectores_objetivo", "tamano_empresa_objetivo", "vector_ideal",
            "afinidad", "consultas_busqueda", "productos_complementarios",
            "justificacion",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "productos": {"type": "array", "items": producto},
            "opciones_adicionales": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "oportunidad": {"type": "string"},
                        "por_que": {"type": "string"},
                    },
                    "required": ["oportunidad", "por_que"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["productos", "opciones_adicionales"],
        "additionalProperties": False,
    }


def _texto_para_ia(paginas: dict[str, str], limite: int = 28000) -> str:
    from bs4 import BeautifulSoup

    partes = []
    for url, html in paginas.items():
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()
        partes.append(f"\n### {url}\n" + _limpio(soup.get_text(" ", strip=True)))
    return "".join(partes)[:limite]


def _extraer_json(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError("La respuesta no contiene JSON")
    return json.loads(m.group(0))


def _validar_producto_ia(d: dict, urls: list[str]) -> Producto:
    fid = d.get("familia") if d.get("familia") in FAMILIAS else "otra"
    base = FAMILIAS.get(fid)
    vi = d.get("vector_ideal") or {}
    af = d.get("afinidad") or {}
    vector = {}
    for i, dim in enumerate(config.DIMENSIONES):
        v = vi.get(dim)
        if not isinstance(v, (int, float)):
            v = base["vector_ideal"][i] if base else 50
        vector[dim] = float(min(max(v, 0), 100))
    afin = {}
    for i, emo in enumerate(config.EMOCIONES):
        v = af.get(emo)
        if not isinstance(v, (int, float)):
            v = base["afinidad"][i] if base else 0.0
        afin[emo] = float(min(max(v, -1), 1))
    nombre = _limpio(str(d.get("nombre", ""))) or "Producto sin nombre"
    return Producto(
        id=_slug(nombre),
        nombre=nombre,
        descripcion=_limpio(str(d.get("descripcion", "")))[:400],
        familia=fid,
        dolor_que_resuelve=_limpio(str(d.get("dolor_que_resuelve", ""))),
        sectores_objetivo=[str(x) for x in d.get("sectores_objetivo", [])][:10],
        tamano_empresa_objetivo=str(d.get("tamano_empresa_objetivo", "")),
        vector_ideal=vector,
        afinidad=afin,
        consultas_busqueda=[str(x) for x in d.get("consultas_busqueda", [])][:12],
        productos_complementarios=[str(x) for x in d.get("productos_complementarios", [])][:8],
        justificacion=_limpio(str(d.get("justificacion", "")))[:600],
        fuente_urls=urls,
        metodo="ia",
        confianza="media",
    )


def construir_con_ia(paginas: dict[str, str], cliente=None) -> tuple[list[Producto], list[dict]]:
    """Devuelve (productos, opciones_adicionales). Lanza excepción si falla (el llamador hace fallback)."""
    ejecucion_id = str(uuid.uuid4())
    inicio = time.perf_counter()
    urls = list(paginas)
    prompt = PROMPT_CATALOGO.format(
        familias=", ".join(FAMILIAS), texto=_texto_para_ia(paginas)
    )
    try:
        if cliente is None:
            cliente = ai_provider.crear_cliente()
        resp = cliente.responses.create(
            model=config.CATALOGO_MODELO_IA,
            max_output_tokens=config.CATALOGO_MAX_OUTPUT_TOKENS,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "catalogo_productos",
                    "schema": _esquema_catalogo_ia(),
                    "strict": True,
                }
            }
        )
    except Exception as error:
        ai_usage.registrar_uso(
            "catalogo", config.CATALOGO_MODELO_IA, None,
            proveedor=config.PROVEEDOR_IA, estado="error",
            duracion_ms=round((time.perf_counter() - inicio) * 1000),
            ejecucion_id=ejecucion_id, tipo_error=type(error).__name__,
        )
        raise
    ai_usage.registrar_uso(
        "catalogo", config.CATALOGO_MODELO_IA, resp,
        proveedor=config.PROVEEDOR_IA, estado="success",
        duracion_ms=round((time.perf_counter() - inicio) * 1000),
        ejecucion_id=ejecucion_id,
    )
    datos = _extraer_json(ai_provider.extraer_texto(resp))
    productos = [_validar_producto_ia(p, urls) for p in datos.get("productos", []) if isinstance(p, dict)]
    return productos, list(datos.get("opciones_adicionales", []))


# ---------------------------------------------------------------------------
# 4) Orquestación, persistencia y catálogo por defecto
# ---------------------------------------------------------------------------
def leer_catalogo_desde_links(
    urls: list[str],
    usar_ia: bool = True,
    usar_navegador: bool = False,
    max_paginas: int = config.CATALOGO_MAX_PAGINAS,
    descargar=_descargar,
    cliente_ia=None,
) -> dict:
    """Punto de entrada de la Fase 1. Devuelve el dict del catálogo (aún sin guardar)."""
    paginas = recorrer_links(urls, max_paginas=max_paginas, usar_navegador=usar_navegador, descargar=descargar)
    bloques = extraer_bloques(paginas)
    productos: list[Producto] = []
    opciones: list[dict] = []
    metodo = "reglas"
    if usar_ia and (cliente_ia is not None or os.environ.get(config.OPENAI_API_KEY_ENV)) and paginas:
        try:
            productos, opciones = construir_con_ia(paginas, cliente=cliente_ia)
            metodo = "ia"
        except Exception as e:
            print(f"[catalogo] Falló la IA, uso reglas: {e}")
    if not productos:
        productos = construir_por_reglas(bloques)
        metodo = "reglas"
    return {
        "version": 1,
        "generado": datetime.now().isoformat(timespec="seconds"),
        "metodo": metodo,
        "fuentes": urls,
        "paginas_leidas": list(paginas),
        "bloques_detectados": len(bloques),
        "aviso": "Vectores = SUPUESTOS INICIALES (estado borrador) hasta aprobación de Telcobras y calibración (Fase 7).",
        "productos": [p.to_dict() for p in productos],
        "opciones_adicionales": opciones or _opciones_por_reglas(productos),
    }


def _opciones_por_reglas(productos: list[Producto]) -> list[dict]:
    """Investigación amplia sin IA: familias complementarias que el catálogo NO cubre."""
    presentes = {p.familia for p in productos}
    sugeridas: dict[str, str] = {}
    for p in productos:
        for c in FAMILIAS.get(p.familia, {}).get("complementarios", []):
            if c not in presentes and c not in sugeridas:
                sugeridas[c] = f"Complementa '{p.nombre}' (venta cruzada) y no aparece en el catálogo leído."
    return [{"oportunidad": FAMILIAS[c]["nombre"], "familia": c, "por_que": por_que} for c, por_que in sugeridas.items()]


def catalogo_por_defecto() -> dict:
    """Catálogo provisional con un producto por familia (para que el pipeline nunca quede sin catálogo)."""
    productos = [
        _producto_desde_familia(fid, fam["nombre"], fam["dolor"], [], 0.0) for fid, fam in FAMILIAS.items()
    ]
    for p in productos:
        p.id = p.familia
        p.metodo = "arquetipo"
        p.justificacion = "Arquetipo por defecto: usar mientras no se lean los links del catálogo real."
    return {
        "version": 1,
        "generado": datetime.now().isoformat(timespec="seconds"),
        "metodo": "arquetipo",
        "fuentes": [],
        "aviso": "Catálogo PROVISIONAL de arquetipos. Reemplazar leyendo los links del catálogo real.",
        "productos": [p.to_dict() for p in productos],
        "opciones_adicionales": [],
    }


def guardar_catalogo(nuevo: dict, ruta: str = config.CATALOGO_PATH, fusionar: bool = True) -> str:
    """Guarda el catálogo. Si fusionar=True, conserva los productos 'aprobado' y los 'manual' existentes."""
    destino = Path(ruta)
    if fusionar and destino.exists():
        previo = json.loads(destino.read_text(encoding="utf-8"))
        protegidos = {p["id"]: p for p in previo.get("productos", [])
                      if p.get("estado") == "aprobado" or p.get("metodo") == "manual"}
        resto = [p for p in nuevo["productos"] if p["id"] not in protegidos]
        nuevo = dict(nuevo, productos=list(protegidos.values()) + resto,
                     fuentes=sorted(set(previo.get("fuentes", [])) | set(nuevo.get("fuentes", []))))
    destino.write_text(json.dumps(nuevo, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(destino)


def cargar_catalogo(ruta: str = config.CATALOGO_PATH) -> dict:
    """Carga y valida el catálogo; si no existe o está dañado, devuelve el de arquetipos (nunca rompe)."""
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        validos = []
        for p in datos.get("productos", []):
            vi, af = p.get("vector_ideal", {}), p.get("afinidad", {})
            if all(d in vi for d in config.DIMENSIONES) and all(e in af for e in config.EMOCIONES):
                validos.append(p)
            else:
                print(f"[catalogo] Producto '{p.get('nombre')}' ignorado: vectores incompletos.")
        if validos:
            return dict(datos, productos=validos)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[catalogo] No se pudo leer {ruta} ({e}); uso arquetipos por defecto.")
    return catalogo_por_defecto()


def resumen_texto(catalogo: dict) -> str:
    lineas = [f"Catálogo ({catalogo.get('metodo')}): {len(catalogo['productos'])} productos"]
    for p in catalogo["productos"]:
        lineas.append(f"  - [{p['estado']}/{p['confianza']}] {p['nombre']}  ({p['familia']})")
    for o in catalogo.get("opciones_adicionales", []):
        lineas.append(f"  + Oportunidad: {o.get('oportunidad')} -- {o.get('por_que')}")
    return "\n".join(lineas)
