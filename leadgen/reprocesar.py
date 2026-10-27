"""
reprocesar.py
-------------
Aplica las Fases 2-5 SIN volver a hacer scraping, sobre empresas que ya
están en la base de datos o en un Excel exportado (ej. leads_export.xlsx).

Sirve para dos cosas:
  1. Actualizar leads viejos con las correcciones y el análisis nuevo.
  2. La REVISIÓN DEL EXCEL que exige la gobernanza (OBJETIVO.md §10):
     cada fase se corre sobre el Excel y se miden cobertura y anomalías.

Uso:
    python main.py reprocesar --excel leads_export.xlsx --salida leads_analizados.xlsx
    python main.py reprocesar            # sobre la base de datos (actualiza en sitio)
"""

from __future__ import annotations

import math

from . import catalogo as mod_catalogo
from . import config, normalize, perfil_psicologico, scoring, senales, validate
from .web_analysis import AnalisisWeb
from .perfil import calcular_perfil
from .scraper import EmpresaCruda

CAMPOS_CRUDOS = ["nombre", "url_perfil", "direccion", "ciudad", "departamento", "telefono", "whatsapp", "correo",
                 "facebook", "instagram", "sitio_web", "horario", "descripcion", "categoria"]


def _limpio(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def motivo_conservar_diagnostico(f: dict, rediagnosticar_antiguos: bool = False) -> str:
    """
    "ia" si el diagnóstico guardado lo generó la IA (nunca se reemplaza por reglas),
    "antiguo" si tiene texto pero su origen es desconocido (anterior a diagnostico_origen)
    y no se pidió regenerarlos; "" si se puede regenerar.
    """
    origen = _limpio(f.get("diagnostico_origen"))
    if origen == "ia":
        return "ia"
    if not origen and _limpio(f.get("diagnostico")) and not rediagnosticar_antiguos:
        return "antiguo"
    return ""


def reprocesar_filas(filas: list[dict], catalogo: dict | None = None, diagnosticar: bool = True,
                     rediagnosticar_antiguos: bool = False) -> list[dict]:
    """Devuelve las filas con las columnas nuevas (Fases 2-5) agregadas/actualizadas."""
    catalogo = catalogo or mod_catalogo.cargar_catalogo()
    sedes = senales.contar_sedes([_limpio(f.get("nombre")) for f in filas])
    salida = []
    for f in filas:
        f = dict(f)
        cruda = EmpresaCruda(**{k: _limpio(f.get(k)) for k in CAMPOS_CRUDOS})
        for k in ("rating", "numero_resenas"):
            v = f.get(k)
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                setattr(cruda, k, v)
        limpia = normalize.normalizar_empresa(cruda)
        # Marcas históricas: el valor corrupto se descartó en la normalización anterior y ya no
        # puede revalidarse. Se conserva la marca si el campo sigue vacío; se quita si ahora tiene
        # un valor válido (evidencia de corrección).
        historicas = [m.strip() for m in _limpio(f.get("datos_invalidos")).replace(";", ",").split(",") if m.strip()]
        conservadas = [m for m in historicas if not getattr(limpia, m, "")]
        limpia.datos_invalidos = list(dict.fromkeys(conservadas + list(limpia.datos_invalidos)))
        val = validate.validar_empresa(limpia)

        f.update({k: getattr(limpia, k) for k in CAMPOS_CRUDOS})
        f.update(
            pais=limpia.pais,
            es_empresa=int(val.es_empresa),
            fuera_de_mercado=int(val.fuera_de_mercado),
            datos_invalidos=",".join(limpia.datos_invalidos),
            fuente="google_maps" if "google.com/maps" in limpia.url_perfil else "directorio",
            tiene_telefono=int(val.tiene_telefono),
            tiene_whatsapp=int(val.tiene_whatsapp),
            tiene_correo=int(val.tiene_correo),
            tiene_web=int(val.tiene_web),
            sedes_detectadas=sedes.get(senales.llave_cadena(limpia.nombre), 1),
        )
        # Capa 1: misma lógica, ahora con entradas corregidas (teléfono válido, reseñas)
        pw = _num(f.get("web_puntaje"))
        aw = AnalisisWeb(accesible=bool(pw), puntaje=int(pw or 0)) if limpia.sitio_web and pw is not None else None
        f["lead_score_original"] = f.get("lead_score")
        f["lead_score"] = scoring.calcular_lead_score(val, aw, int(limpia.numero_resenas or 0))
        f["lead_clasificacion"] = scoring.clasificar_lead(f["lead_score"])
        ctx = senales.contexto_negocio(
            texto_web="",  # el Excel no guarda el texto del sitio: se mide en el pipeline en vivo
            herramientas_pago=[h for h in _limpio(f.get("web_herramientas_pago")).split(",") if h],
            pixel_facebook=bool(f.get("web_pixel_facebook")) if f.get("web_pixel_facebook") not in (None, "") else None,
            sedes=f["sedes_detectadas"],
            numero_resenas=limpia.numero_resenas,
        )
        for k, v in ctx.items():
            if not _limpio(f.get(k)) or k == "cobertura_contexto":
                f[k] = v

        per = calcular_perfil(f)
        res = perfil_psicologico.analizar(per, catalogo, lead_score=_num(f.get("lead_score")),
                                          es_empresa=val.es_empresa, fuera_de_mercado=val.fuera_de_mercado)
        f.update(perfil_psicologico.a_columnas(per, res))
        if diagnosticar and not motivo_conservar_diagnostico(f, rediagnosticar_antiguos):
            try:
                from . import diagnostico
                f["diagnostico"], f["diagnostico_origen"] = diagnostico.diagnosticar_con_origen(per, res, f, usar_ia=False)
            except ImportError:
                pass
        salida.append(f)
    return salida


def _num(v):
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None
