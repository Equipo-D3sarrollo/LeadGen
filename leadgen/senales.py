"""
senales.py
----------
FASE 2 - Señales nuevas (Capa 5: contexto de negocio) y utilidades.

  - antiguedad_dominio(): años desde el registro del dominio vía RDAP
    (estándar público que reemplaza a WHOIS). Si falla: None.
  - contexto_negocio(): tamaño estimado, fase de crecimiento, señales
    de presupuesto y cargos que deciden, a partir del texto del sitio
    web, las herramientas de pago detectadas y el número de sedes.
  - contar_sedes(): "rollup" por cadena (misma empresa en varias sedes,
    investigación complementaria 9.1).

Regla de oro (OBJETIVO.md, sección 8): lo que no se puede medir queda
en None/"" y se reporta en la cobertura; nunca se rellena con cero.
RUES / Confecámaras queda PENDIENTE: el dataset abierto no se pudo
verificar desde este entorno (sección 9.6 del objetivo).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from urllib.parse import urlparse


def _sin_tildes(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    return "".join(c for c in txt if not unicodedata.combining(c)).lower()


# ---------------------------------------------------------------------------
# Antigüedad de dominio (RDAP)
# ---------------------------------------------------------------------------
_MAX_CACHE_RDAP = 256
_CACHE_RDAP: OrderedDict[str, float | None] = OrderedDict()


def _limpiar_cache_rdap() -> None:
    _CACHE_RDAP.clear()


def fecha_registro_desde_rdap(datos: dict) -> datetime | None:
    for ev in datos.get("events", []) or []:
        if ev.get("eventAction") == "registration" and ev.get("eventDate"):
            try:
                return datetime.fromisoformat(ev["eventDate"].replace("Z", "+00:00"))
            except ValueError:
                return None
    return None


def antiguedad_dominio(url_sitio: str, timeout: int = 8) -> float | None:
    """Años de antigüedad del dominio, o None si no se pudo consultar."""
    if not url_sitio:
        return None
    dominio = urlparse(
        url_sitio if "://" in url_sitio else "https://" + url_sitio
    ).netloc.lower()
    if dominio.startswith("www."):
        dominio = dominio[4:]
    if not dominio:
        return None
    if dominio in _CACHE_RDAP:
        _CACHE_RDAP.move_to_end(dominio)
        return _CACHE_RDAP[dominio]

    resultado: float | None = None
    try:
        import requests
        from . import config
        r = requests.get(f"https://rdap.org/domain/{dominio}", headers=config.HEADERS, timeout=timeout)
        if not r.ok:
            fecha = None
        else:
            fecha = fecha_registro_desde_rdap(r.json())
    except Exception:
        fecha = None
    if fecha:
        resultado = round((datetime.now(timezone.utc) - fecha).days / 365.25, 1)

    _CACHE_RDAP[dominio] = resultado
    _CACHE_RDAP.move_to_end(dominio)
    if len(_CACHE_RDAP) > _MAX_CACHE_RDAP:
        _CACHE_RDAP.popitem(last=False)
    return resultado


# ---------------------------------------------------------------------------
# Rollup de sedes
# ---------------------------------------------------------------------------
def llave_cadena(nombre: str) -> str:
    """Nombre sin sufijos de sede: 'Dentix - Sede Norte' -> 'dentix'."""
    n = _sin_tildes(nombre)
    n = re.split(r"\s[-|–(]\s?|\ssede\s|\ssucursal\s", n)[0]
    return re.sub(r"[^a-z0-9 ]", "", n).strip()


def contar_sedes(nombres: list[str]) -> dict[str, int]:
    return Counter(llave_cadena(n) for n in nombres if n)


# ---------------------------------------------------------------------------
# Contexto de negocio (Capa 5)
# ---------------------------------------------------------------------------
_CRECIMIENTO = {
    "expansion": ["nueva sede", "nuevas sedes", "proximamente", "pronto abriremos", "inauguramos", "apertura",
                  "trabaja con nosotros", "vacantes", "estamos contratando", "unete a nuestro equipo", "franquicia"],
    "consolidada": ["anos de experiencia", "desde 19", "desde 20", "trayectoria", "fundada en", "fundado en"],
}
_CARGOS = ["gerente general", "gerente", "director", "directora", "ceo", "fundador", "fundadora", "propietario",
           "propietaria", "socio", "administrador", "administradora", "jefe de compras", "coordinador"]
_TAMANO = [
    (re.compile(r"mas de (\d{2,5}) (empleados|colaboradores|trabajadores|profesionales)"), "por_empleados"),
    (re.compile(r"(\d{2,5}) (empleados|colaboradores|trabajadores)"), "por_empleados"),
]


def contexto_negocio(
    texto_web: str = "",
    herramientas_pago: list | None = None,
    pixel_facebook: bool | None = None,
    sedes: int | None = None,
    numero_resenas: int | None = None,
) -> dict:
    """
    Devuelve {tamano_estimado, fase_crecimiento, senal_presupuesto,
    cargos_decision, cobertura_contexto}. Cada campo vacío = no medido.
    """
    t = _sin_tildes(texto_web)
    res = {"tamano_estimado": "", "fase_crecimiento": "", "senal_presupuesto": "", "cargos_decision": "",
           "cobertura_contexto": 0.0}

    # Tamaño
    empleados = None
    for rx, _ in _TAMANO:
        m = rx.search(t)
        if m:
            empleados = int(m.group(1))
            break
    if empleados is not None:
        res["tamano_estimado"] = "grande" if empleados >= 200 else "mediana" if empleados >= 50 else "pequena"
    elif sedes and sedes >= 3:
        res["tamano_estimado"] = "mediana"
    elif numero_resenas is not None and numero_resenas >= 300:
        res["tamano_estimado"] = "mediana"
    elif sedes == 1 and numero_resenas is not None:
        res["tamano_estimado"] = "pequena"

    # Fase de crecimiento
    if t:
        if any(k in t for k in _CRECIMIENTO["expansion"]) or (sedes and sedes >= 3):
            res["fase_crecimiento"] = "expansion"
        elif any(k in t for k in _CRECIMIENTO["consolidada"]):
            res["fase_crecimiento"] = "consolidada"

    # Señal de presupuesto (invierte en herramientas pagas / pauta)
    herramientas = list(herramientas_pago or [])
    if pixel_facebook:
        herramientas.append("Píxel Facebook")
    if herramientas:
        res["senal_presupuesto"] = "alta" if len(herramientas) >= 2 else "media"
    elif texto_web:
        res["senal_presupuesto"] = "baja"

    # Quién decide
    cargos = sorted({c for c in _CARGOS if re.search(rf"\b{c}\b", t)})
    res["cargos_decision"] = ", ".join(cargos)

    medidos = sum(bool(res[k]) for k in ("tamano_estimado", "fase_crecimiento", "senal_presupuesto", "cargos_decision"))
    res["cobertura_contexto"] = round(medidos / 4, 2)
    return res
