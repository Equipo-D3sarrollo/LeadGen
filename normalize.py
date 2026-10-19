"""
normalize.py
------------
MÓDULO 4 - Normalización

Limpia y estandariza los datos crudos extraídos en el Módulo 3:
teléfonos, correos, URLs, ciudades y nombres, para que datos como
"+57 300-123-45-67", "3001234567" y "300 1234567" terminen todos
como "3001234567".

Cambios Fase 2 (oct. 2026), hallazgos de claude/revision_leads_export.md:
  - Teléfono: ahora se VALIDA el formato colombiano (celular 3xx de 10
    dígitos, fijo 60X de 10, fijo antiguo de 8 que se convierte a 60X,
    fijo local de 7, línea 01-8000). Un número que no cumple (ej. 80
    dígitos concatenados, o una fecha "20092026") se descarta y queda
    registrado en empresa.datos_invalidos -> scoring negativo explícito
    (investigación complementaria 9.2), en vez de contar como "tiene
    teléfono".
  - Ciudad / departamento / país: se derivan de la dirección cuando la
    fuente no los trae (antes quedaban vacíos en el 100 % de las filas).
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

from .scraper import EmpresaCruda

# ---------------------------------------------------------------------------
# Teléfonos
# ---------------------------------------------------------------------------


def normalizar_telefono_detalle(valor: str) -> tuple[str, str]:
    """
    Devuelve (numero_normalizado, tipo). tipo ∈ {"celular", "fijo",
    "fijo_local", "linea_gratuita", "extranjero", "invalido", ""}.
    numero_normalizado es "" cuando tipo es "invalido" o vacío.
    """
    if not valor:
        return "", ""
    d = re.sub(r"\D", "", str(valor))
    if d.endswith("0") and re.fullmatch(r"\d+\.0", str(valor).strip()):  # vino como float de Excel
        d = d[:-1]
    if d.startswith("0057"):
        d = d[4:]
    elif d.startswith("57") and len(d) == 12:
        d = d[2:]
    if len(d) == 10 and d.startswith("3"):
        return d, "celular"
    if len(d) == 10 and d.startswith("60"):
        return d, "fijo"
    if len(d) == 8 and d[0] in "1245678":          # formato antiguo (indicativo + 7) -> 60X
        return "60" + d, "fijo"
    if len(d) == 7 and d[0] in "2345678":
        return d, "fijo_local"
    if d.startswith("018000") and len(d) in (11, 12):
        return d, "linea_gratuita"
    if d.startswith("1") and len(d) == 11:          # EE. UU./Canadá (+1)
        return "+" + d, "extranjero"
    return "", "invalido"


def normalizar_telefono(valor: str) -> str:
    """Compatibilidad: devuelve solo el número ("" si es inválido)."""
    return normalizar_telefono_detalle(valor)[0]


def normalizar_correo(valor: str) -> str:
    return valor.strip().lower() if valor else ""


def normalizar_url(valor: str) -> str:
    if not valor:
        return ""
    valor = valor.strip()
    if not valor.startswith(("http://", "https://")):
        valor = "https://" + valor
    parsed = urlparse(valor)
    dominio = parsed.netloc.lower().replace("www.", "")
    return f"{parsed.scheme}://{dominio}{parsed.path.rstrip('/')}"


def normalizar_texto(valor: str) -> str:
    if not valor:
        return ""
    return re.sub(r"\s+", " ", str(valor)).strip()


def normalizar_ciudad(valor: str) -> str:
    return normalizar_texto(valor).title()


# ---------------------------------------------------------------------------
# Ciudad / departamento / país desde la dirección
# ---------------------------------------------------------------------------
DEPARTAMENTOS = [
    "Amazonas", "Antioquia", "Arauca", "Atlántico", "Bogotá", "Bolívar", "Boyacá", "Caldas", "Caquetá",
    "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca", "Guainía", "Guaviare", "Huila",
    "La Guajira", "Magdalena", "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío", "Risaralda",
    "San Andrés y Providencia", "Santander", "Sucre", "Tolima", "Valle del Cauca", "Vaupés", "Vichada",
]
CIUDAD_A_DEPARTAMENTO = {
    "bogota": "Bogotá", "medellin": "Antioquia", "envigado": "Antioquia", "itagui": "Antioquia",
    "bello": "Antioquia", "rionegro": "Antioquia", "cali": "Valle del Cauca", "palmira": "Valle del Cauca",
    "tulua": "Valle del Cauca", "buga": "Valle del Cauca", "jamundi": "Valle del Cauca",
    "buenaventura": "Valle del Cauca", "cartago": "Valle del Cauca", "yumbo": "Valle del Cauca",
    "barranquilla": "Atlántico", "soledad": "Atlántico", "cartagena": "Bolívar", "bucaramanga": "Santander",
    "floridablanca": "Santander", "cucuta": "Norte de Santander", "pereira": "Risaralda",
    "dosquebradas": "Risaralda", "santa rosa de cabal": "Risaralda", "manizales": "Caldas",
    "chinchina": "Caldas", "villamaria": "Caldas", "armenia": "Quindío", "ibague": "Tolima",
    "neiva": "Huila", "pasto": "Nariño", "popayan": "Cauca", "santa marta": "Magdalena",
    "villavicencio": "Meta", "monteria": "Córdoba", "valledupar": "Cesar", "tunja": "Boyacá",
    "sincelejo": "Sucre", "riohacha": "La Guajira", "quibdo": "Chocó", "florencia": "Caquetá",
    "yopal": "Casanare", "soacha": "Cundinamarca", "chia": "Cundinamarca", "zipaquira": "Cundinamarca",
}
PAISES_EXTRANJEROS = ["estados unidos", "united states", "usa", "mexico", "espana", "spain", "ecuador",
                      "peru", "venezuela", "panama", "canada", "chile", "argentina"]
_REGEX_ESTADO_US = re.compile(r"\b[A-Z]{2}\s\d{5}\b")


def _llave(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    return "".join(c for c in txt if not unicodedata.combining(c)).lower().strip(" .")


_DEPTO_POR_LLAVE = {_llave(d): d for d in DEPARTAMENTOS}
_DEPTO_POR_LLAVE.update({"bogota d.c": "Bogotá", "bogota, d.c": "Bogotá", "bogota dc": "Bogotá",
                         "valle": "Valle del Cauca", "atlantico": "Atlántico"})


def derivar_ubicacion(direccion: str) -> dict:
    """
    Devuelve {"ciudad", "departamento", "pais"} a partir de una dirección
    tipo Google Maps: "Cra 20 #25-38, Manizales, Caldas" o
    "4368 W Shaw Ave, Fresno, CA 93722, Estados Unidos".
    Campos no deducibles quedan en "" (nunca se inventan).
    """
    res = {"ciudad": "", "departamento": "", "pais": ""}
    if not direccion:
        return res
    partes = [p.strip() for p in direccion.split(",") if p.strip()]
    llaves = [_llave(p) for p in partes]

    if any(k in PAISES_EXTRANJEROS for k in llaves) or _REGEX_ESTADO_US.search(direccion):
        pais = next((partes[i] for i, k in enumerate(llaves) if k in PAISES_EXTRANJEROS), "Estados Unidos")
        res["pais"] = pais
        # ciudad = la parte antes del "CA 93722"
        for i, p in enumerate(partes):
            if _REGEX_ESTADO_US.search(p) and i > 0:
                res["ciudad"] = partes[i - 1]
        return res

    if llaves and llaves[-1] == "colombia":
        partes, llaves = partes[:-1], llaves[:-1]
    # departamento = última parte si es un departamento conocido
    if llaves and llaves[-1] in _DEPTO_POR_LLAVE:
        res["departamento"] = _DEPTO_POR_LLAVE[llaves[-1]]
        res["pais"] = "Colombia"
        if len(partes) >= 2:
            candidata = partes[-2]
            if _llave(candidata) in CIUDAD_A_DEPARTAMENTO or not re.search(r"\d|#", candidata):
                res["ciudad"] = candidata
        if res["departamento"] == "Bogotá" and not res["ciudad"]:
            res["ciudad"] = "Bogotá"
    # si no hubo departamento, buscar una ciudad conocida en cualquier parte
    if not res["departamento"]:
        for p, k in zip(reversed(partes), reversed(llaves)):
            if k in CIUDAD_A_DEPARTAMENTO:
                res.update(ciudad=p, departamento=CIUDAD_A_DEPARTAMENTO[k], pais="Colombia")
                break
    if res["ciudad"] and not res["departamento"]:
        res["departamento"] = CIUDAD_A_DEPARTAMENTO.get(_llave(res["ciudad"]), "")
    return res


# ---------------------------------------------------------------------------
# Empresa completa
# ---------------------------------------------------------------------------
def normalizar_empresa(empresa: EmpresaCruda) -> EmpresaCruda:
    """Devuelve la empresa normalizada (modifica y devuelve el mismo objeto)."""
    empresa.nombre = normalizar_texto(empresa.nombre)
    empresa.direccion = normalizar_texto(empresa.direccion)
    empresa.ciudad = normalizar_ciudad(empresa.ciudad)
    empresa.departamento = normalizar_ciudad(empresa.departamento)

    if empresa.direccion and not (empresa.ciudad and empresa.departamento and empresa.pais):
        ubic = derivar_ubicacion(empresa.direccion)
        empresa.ciudad = empresa.ciudad or ubic["ciudad"]
        empresa.departamento = empresa.departamento or ubic["departamento"]
        empresa.pais = empresa.pais or ubic["pais"]
    elif empresa.ciudad and not empresa.departamento:
        empresa.departamento = CIUDAD_A_DEPARTAMENTO.get(_llave(empresa.ciudad), "")

    tel, tipo = normalizar_telefono_detalle(empresa.telefono)
    if tipo == "invalido":
        empresa.datos_invalidos = list(empresa.datos_invalidos) + ["telefono"]
    empresa.telefono = tel
    wa, tipo_wa = normalizar_telefono_detalle(empresa.whatsapp)
    if tipo_wa == "invalido":
        empresa.datos_invalidos = list(empresa.datos_invalidos) + ["whatsapp"]
    empresa.whatsapp = wa.lstrip("+")

    empresa.correo = normalizar_correo(empresa.correo)
    if empresa.correo and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", empresa.correo):
        empresa.datos_invalidos = list(empresa.datos_invalidos) + ["correo"]
        empresa.correo = ""
    empresa.facebook = normalizar_url(empresa.facebook) if empresa.facebook else ""
    empresa.instagram = normalizar_url(empresa.instagram) if empresa.instagram else ""
    empresa.sitio_web = normalizar_url(empresa.sitio_web) if empresa.sitio_web else ""
    empresa.horario = normalizar_texto(empresa.horario)
    empresa.descripcion = normalizar_texto(empresa.descripcion)
    empresa.categoria = normalizar_texto(empresa.categoria)
    return empresa
