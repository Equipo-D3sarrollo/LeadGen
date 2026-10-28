"""
diagnostico.py
--------------
FASE 5 - Diagnóstico legible (Capa 4).

Traduce el perfil conductual (Capa 2) y el perfil emocional (Capa 3) en
un texto corto en lenguaje de negocio para el equipo comercial: qué
necesita la empresa, con qué urgencia, qué tan abierta está, qué
ofrecerle primero y qué tan confiable es la lectura.

Por defecto NO muestra nombres de emociones (alegría/miedo/...), solo su
traducción de negocio (OBJETIVO.md, Capa 4). Para verlos también:
config.DIAGNOSTICO_MOSTRAR_EMOCION = True.

Mismo patrón que ai_analysis.py: con OPENAI_API_KEY y usar_ia=True,
OpenAI redacta el texto a partir de la evidencia (sin inventar datos);
sin API key, o si falla, se usa la redacción por reglas.
"""

from __future__ import annotations

import json
import os
import time
import uuid

from . import ai_provider, ai_usage, config
from .perfil import Perfil, dimension_dominante
from .perfil_psicologico import ResultadoPsico

POSTURA_NEGOCIO = {
    "alegria": "está en un buen momento y con disposición a invertir",
    "confianza": "se ve estable y abierta a proveedores que le den seguridad",
    "miedo": "está en postura defensiva: percibe riesgo o se está quedando atrás",
    "sorpresa": "parece estar viviendo un cambio reciente o inesperado",
    "tristeza": "muestra señales de estancamiento",
    "aversion": "parece cerrada o reacia a nuevos proveedores",
    "ira": "probablemente está frustrada con un problema que hoy le afecta",
    "anticipacion": "da señales de estar planeando crecer",
}

NOMBRE_DIM = {
    "madurez_digital": "madurez digital", "dolor_urgencia": "urgencia", "confianza_reputacion": "reputación",
    "dinamismo": "dinamismo", "apertura_comercial": "apertura comercial", "sofisticacion_marca": "cuidado de marca",
}


def _nivel(v: float | None, alto: float = 66, bajo: float = 40) -> str:
    if v is None:
        return "sin dato"
    return "alta" if v >= alto else "media" if v >= bajo else "baja"


def _necesidad(e: dict, perfil: Perfil) -> str:
    detalle = perfil.detalle.get("dolor_urgencia", [])
    activos = {n for n, v, _ in detalle if isinstance(v, (int, float)) and v >= 0.5}
    if "sin_web" in activos:
        return "No tiene sitio web propio"
    problemas = []
    if "web_caida" in activos:
        problemas.append("su web no carga")
    if "sin_https" in activos:
        problemas.append("su web no usa HTTPS")
    if "sin_movil" in activos:
        problemas.append("no está adaptada a celular")
    if "sin_formulario" in activos:
        problemas.append("no tiene formulario de contacto")
    if "web_debil" in activos:
        problemas.append("su web tiene un puntaje técnico bajo")
    if "carga_lenta" in activos:
        problemas.append("carga lento")
    if problemas:
        return "Tiene web, pero " + ", ".join(problemas[:3])
    if perfil.dimensiones.get("dolor_urgencia") is None:
        return "No se pudo medir su necesidad digital (web sin analizar)"
    return "Su presencia digital básica está cubierta; la oportunidad está en crecer, no en corregir"


def _apertura(e: dict, perfil: Perfil) -> str:
    v = perfil.dimensiones.get("apertura_comercial")
    det = perfil.detalle.get("apertura_comercial", [])
    faltan = [n for n, val, _ in det if val == "faltante"]
    canales = [n.replace("_valido", "").replace("_web", "").replace("_", " ") for n, val, _ in det if isinstance(val, (int, float)) and val >= 1]
    cob = perfil.cobertura.get("apertura_comercial", 0)
    txt = f"apertura comercial {_nivel(v)}" if cob >= 0.5 else "apertura comercial por confirmar"
    if canales:
        txt += f" (canales verificados: {', '.join(canales)})"
    if faltan:
        txt += f"; no se pudo verificar {', '.join(f.replace('_', ' ') for f in faltan)}"
    if "telefono" in perfil.datos_invalidos:
        txt += "; el teléfono que trae la fuente está corrupto"
    return txt


def diagnostico_por_reglas(perfil: Perfil, res: ResultadoPsico, e: dict) -> str:
    if res.excluida:
        return f"No se analiza: {res.excluida}."
    partes = [_necesidad(e, perfil) + "."]
    urg = _nivel(res.intent_pct)
    postura = POSTURA_NEGOCIO.get(res.emocion_principal, "")
    if res.claridad < config.UMBRAL_DELTA:
        partes.append(f"Urgencia {urg}. Perfil poco definido con los datos actuales: confirmar la necesidad en la primera llamada.")
    else:
        etiqueta = f" [{res.emocion_principal}/{res.emocion_secundaria}]" if getattr(config, "DIAGNOSTICO_MOSTRAR_EMOCION", False) else ""
        partes.append(f"Urgencia {urg}; la empresa {postura}{etiqueta}.")
    partes.append(_apertura(e, perfil).capitalize() + ".")
    if res.mejor_producto_nombre:
        fit = f", encaje con su perfil {res.fit_pct:.0f} %" if res.fit_pct is not None else ""
        partes.append(f"Ofrecer primero: {res.mejor_producto_nombre} (compatibilidad {res.compatibilidad_pct:.0f} %{fit}).")
    dom, val = dimension_dominante(perfil)
    if dom:
        partes.append(f"Rasgo más marcado: {NOMBRE_DIM[dom]} {_nivel(val)}.")
    partes.append(f"Confianza del análisis: {perfil.confianza} (cobertura de datos {perfil.cobertura_global:.0%}).")
    return " ".join(partes)


def _reglas_suficientes(perfil: Perfil, res: ResultadoPsico) -> bool:
    """Indica si el filtro existente permite confiar en el diagnóstico por reglas."""
    return bool(
        perfil.cobertura_global >= config.COBERTURA_MINIMA
        and perfil.confianza == "alta"
        and res.pasa_filtro
        and res.mejor_producto_nombre
        and res.compatibilidad_pct is not None
    )


PROMPT_DIAGNOSTICO = """Eres asesor comercial B2B en Colombia.

Redacta un diagnóstico de 2 a 3 frases en español, en lenguaje comercial para un vendedor,
indicando qué necesita la empresa, con qué urgencia, qué probabilidad hay de que responda
y qué producto conviene ofrecerle primero.
Usa únicamente la evidencia proporcionada. Si la confianza es baja, indícalo.
No inventes datos ni menciones emociones por su nombre; exprésalas como postura comercial.

EVIDENCIA:
{evidencia}
"""


def diagnosticar(perfil: Perfil, res: ResultadoPsico, e: dict, usar_ia: bool = False, cliente=None) -> str:
    return diagnosticar_con_origen(perfil, res, e, usar_ia=usar_ia, cliente=cliente)[0]


def diagnosticar_con_origen(perfil: Perfil, res: ResultadoPsico, e: dict, usar_ia: bool = False,
                            cliente=None) -> tuple[str, str]:
    """(texto, origen). origen = "ia" solo si la IA devolvió texto; cualquier respaldo es "reglas"."""
    base = diagnostico_por_reglas(perfil, res, e)
    if (
        res.excluida
        or not usar_ia
        or _reglas_suficientes(perfil, res)
        or not (cliente or os.environ.get(config.OPENAI_API_KEY_ENV))
    ):
        return base, "reglas"
    ejecucion_id = str(uuid.uuid4())
    inicio = time.perf_counter()
    try:
        if cliente is None:
            cliente = ai_provider.crear_cliente()
        evidencia = {
            "empresa": e.get("nombre"), "categoria": e.get("categoria"), "ciudad": e.get("ciudad"),
            "dimensiones_0_100": perfil.dimensiones, "cobertura": perfil.cobertura,
            "postura": POSTURA_NEGOCIO.get(res.emocion_principal), "claridad": res.claridad,
            "urgencia_pct": res.intent_pct, "mejor_producto": res.mejor_producto_nombre,
            "compatibilidad_pct": res.compatibilidad_pct, "datos_invalidos": perfil.datos_invalidos,
        }
        r = cliente.responses.create(
            model=config.CATALOGO_MODELO_IA,
            max_output_tokens=config.DIAGNOSTICO_MAX_OUTPUT_TOKENS,
            input=PROMPT_DIAGNOSTICO.format(evidencia=json.dumps(evidencia, ensure_ascii=False)),
        )
        ai_usage.registrar_uso(
            "diagnostico", config.CATALOGO_MODELO_IA, r,
            proveedor=config.PROVEEDOR_IA, estado="success",
            duracion_ms=round((time.perf_counter() - inicio) * 1000),
            ejecucion_id=ejecucion_id,
        )
    except Exception as ex:
        ai_usage.registrar_uso(
            "diagnostico", config.CATALOGO_MODELO_IA, None,
            proveedor=config.PROVEEDOR_IA, estado="error",
            duracion_ms=round((time.perf_counter() - inicio) * 1000),
            ejecucion_id=ejecucion_id, tipo_error=type(ex).__name__,
        )
        print(f"[diagnostico] Falló la IA, uso reglas: {ex}")
        return base, "reglas"
    try:
        texto = ai_provider.extraer_texto(r).strip()
    except Exception as ex:
        print(f"[diagnostico] Respuesta no utilizable, uso reglas: {type(ex).__name__}")
        return base, "reglas"
    return (texto, "ia") if texto else (base, "reglas")
