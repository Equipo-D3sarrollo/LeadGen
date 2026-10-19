"""
perfil.py
---------
FASE 3 - Motor de perfil conductual (Capa 2).

Convierte las señales de una empresa en 6 dimensiones (0-100 %), que
son el vector de entrada "s" del núcleo psicológico (Capa 3):

    madurez_digital · dolor_urgencia · confianza_reputacion ·
    dinamismo · apertura_comercial · sofisticacion_marca

Cada dimensión es un promedio ponderado de sub-señales en [0, 1]. Cada
sub-señal tiene tres estados posibles:
  - medida   -> valor en [0, 1], cuenta en el promedio y en la cobertura.
  - no_aplica-> no tiene sentido para esta empresa (ej. "carga lenta" si
                no tiene web): no cuenta en ningún lado.
  - faltante -> debería poder medirse pero la fuente no lo trae (ej.
                WhatsApp en una ficha de Google Maps sin escanear la
                web): NO se rellena con cero; baja la cobertura.

cobertura(dimensión) = peso medido / (peso medido + peso faltante).
Una dimensión sin nada medido queda en None.

Funciones puras: reciben un dict (fila de la BD o del Excel exportado)
y no hacen red. Pesos = SUPUESTOS INICIALES (ver DECISIONES.md).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from . import config

NA = "no_aplica"
FALTA = None   # faltante


def _num(v):
    """Convierte valores de BD/Excel a float o None (NaN, '', None -> None)."""
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _bool(v):
    f = _num(v)
    return None if f is None else bool(f)


def _texto(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()


def fuente_de(e: dict) -> str:
    if _texto(e.get("fuente")):
        return _texto(e.get("fuente"))
    return "google_maps" if "google.com/maps" in _texto(e.get("url_perfil")) else "directorio"


@dataclass
class Perfil:
    dimensiones: dict = field(default_factory=dict)     # dim -> 0..100 | None
    cobertura: dict = field(default_factory=dict)       # dim -> 0..1
    cobertura_global: float = 0.0
    confianza: str = "baja"
    detalle: dict = field(default_factory=dict)         # dim -> [(señal, valor|estado, peso)]
    datos_invalidos: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def vector(self) -> list:
        return [self.dimensiones.get(d) for d in config.DIMENSIONES]


def _combinar(subs: list[tuple[str, object, float]]) -> tuple[float | None, float, list]:
    num = den = falta = 0.0
    detalle = []
    for nombre, valor, peso in subs:
        if valor == NA:
            detalle.append((nombre, NA, peso))
            continue
        if valor is FALTA:
            falta += peso
            detalle.append((nombre, "faltante", peso))
            continue
        v = min(max(float(valor), 0.0), 1.0)
        num += v * peso
        den += peso
        detalle.append((nombre, round(v, 3), peso))
    if den == 0:
        return None, 0.0, detalle
    return round(100 * num / den, 1), round(den / (den + falta), 3), detalle


def calcular_perfil(e: dict) -> Perfil:
    """e: dict con las columnas de la tabla empresas (o del Excel exportado)."""
    fuente = fuente_de(e)
    tiene_web = bool(_texto(e.get("sitio_web"))) or bool(_bool(e.get("tiene_web")))
    puntaje = _num(e.get("web_puntaje"))
    accesible = _bool(e.get("web_accesible"))
    if accesible is None and puntaje == 0:
        # Exportaciones anteriores a la Fase 2 no guardaban web_accesible: puntaje 0 puede ser
        # "sitio caído" o "el análisis falló/bloqueado". No se puede distinguir -> no medido.
        puntaje = None
    elif accesible is None and puntaje is not None:
        accesible = True
    https = _bool(e.get("web_https"))
    responsive = _bool(e.get("web_responsive"))
    formulario = _bool(e.get("web_formulario"))
    analytics = _bool(e.get("web_analytics"))
    t_carga = _num(e.get("web_tiempo_carga"))
    escaneado = bool(_bool(e.get("contacto_web_escaneado")))
    rating = _num(e.get("rating"))
    resenas = _num(e.get("numero_resenas"))
    anios_dom = _num(e.get("dominio_antiguedad_anios"))
    sedes = _num(e.get("sedes_detectadas"))
    invalidos = [x for x in _texto(e.get("datos_invalidos")).replace(";", ",").split(",") if x.strip()]

    def web(v):
        """Sub-señal que solo existe si hay web; si hay web pero no se midió -> faltante."""
        if not tiene_web:
            return NA
        return FALTA if v is None else v

    def web_ok(v):
        """Como web(), pero si la web no carga la señal no es medible."""
        if not tiene_web:
            return NA
        if accesible is False:
            return NA
        return FALTA if v is None else v

    # ¿Las señales de contacto se pudieron observar? Maps no muestra WhatsApp/Instagram/correo.
    contacto_observable = escaneado or fuente != "google_maps"

    def contacto(flag_col: str):
        v = _bool(e.get(flag_col))
        if v:
            return 1.0
        return 0.0 if contacto_observable else FALTA

    # --- Madurez digital ---
    madurez = [
        ("tiene_web", 1.0 if tiene_web else 0.0, 2.0),
        ("puntaje_web", web_ok(None if puntaje is None else puntaje / 100), 3.0),
        ("https", web(None if https is None else float(https)), 1.0),
        ("responsive", web_ok(None if responsive is None else float(responsive)), 1.0),
        ("analitica", web_ok(None if analytics is None else float(analytics)), 1.0),
        ("redes_sociales", contacto("tiene_facebook") if not _bool(e.get("tiene_instagram")) else 1.0, 1.0),
    ]
    # --- Dolor / urgencia ---
    dolor = [
        ("sin_web", NA if tiene_web else 1.0, 3.0),   # con web, el dolor se mide por la calidad de la web
        ("web_caida", web(None if accesible is None else float(not accesible)), 2.0),
        ("web_debil", web_ok(None if puntaje is None else 1 - puntaje / 100), 2.0),
        ("sin_https", web(None if https is None else float(not https)), 1.0),
        ("sin_movil", web_ok(None if responsive is None else float(not responsive)), 1.0),
        ("sin_formulario", web_ok(None if formulario is None else float(not formulario)), 1.0),
        ("carga_lenta", web_ok(None if not t_carga else min(t_carga / 8, 1.0)), 1.0),
    ]
    # --- Confianza / reputación ---
    if rating is not None and resenas is not None:
        m, c = config.RATING_PRIOR_PESO, config.RATING_PRIOR_MEDIA
        r_bayes = (resenas * rating + m * c) / (resenas + m)
        v_rating = (r_bayes - 1) / 4
    else:
        v_rating = FALTA
    v_resenas = FALTA if resenas is None else math.log1p(resenas) / math.log1p(config.RESENAS_SATURACION)
    confianza = [
        ("rating_bayesiano", v_rating, 2.0),
        ("volumen_resenas", v_resenas, 2.0),
        ("antiguedad_dominio", web(None if anios_dom is None else min(anios_dom / 10, 1.0)), 1.0),
    ]
    # --- Dinamismo ---
    fase = _texto(e.get("fase_crecimiento"))
    horario = _texto(e.get("horario"))
    dinamismo = [
        ("fase_crecimiento", {"expansion": 1.0, "consolidada": 0.5, "": FALTA}.get(fase, 0.3), 2.0),
        ("horario_publicado", 1.0 if horario else (0.0 if fuente != "google_maps" else FALTA), 1.0),
        ("varias_sedes", FALTA if sedes is None else min((sedes - 1) / 3, 1.0), 0.5),
        ("actividad_resenas", FALTA if resenas is None else min(resenas / 100, 1.0), 1.0),
    ]
    # --- Apertura comercial ---
    tel_valido = 0.0 if "telefono" in invalidos else (1.0 if _bool(e.get("tiene_telefono")) else 0.0)
    apertura = [
        ("telefono_valido", tel_valido, 2.0),
        ("whatsapp", contacto("tiene_whatsapp"), 2.0),
        ("correo", contacto("tiene_correo"), 1.0),
        ("formulario_web", web_ok(None if formulario is None else float(formulario)), 1.0),
        ("facebook", contacto("tiene_facebook"), 0.5),
        ("instagram", contacto("tiene_instagram"), 0.5),
    ]
    # --- Sofisticación de marca ---
    desc = _texto(e.get("descripcion"))
    titulo = _texto(e.get("web_titulo"))
    meta = _bool(e.get("web_meta_descripcion"))
    herr = _texto(e.get("web_herramientas_pago"))
    sofisticacion = [
        ("titulo_web", web_ok(None if not escaneado else float(bool(titulo))), 1.0),
        ("meta_descripcion", web_ok(None if meta is None else float(meta)), 1.0),
        ("calidad_web", web_ok(None if puntaje is None else puntaje / 100), 1.0),
        ("herramientas_pago", web_ok(None if not escaneado else min(len([h for h in herr.split(",") if h.strip()]) / 2, 1.0)), 1.0),
        ("descripcion", 1.0 if len(desc) > 80 else (0.5 if desc else (0.0 if fuente != "google_maps" else FALTA)), 0.5),
    ]

    p = Perfil(datos_invalidos=invalidos)
    for dim, subs in zip(config.DIMENSIONES, [madurez, dolor, confianza, dinamismo, apertura, sofisticacion]):
        valor, cob, det = _combinar(subs)
        p.dimensiones[dim] = valor
        p.cobertura[dim] = cob
        p.detalle[dim] = det
    p.cobertura_global = round(sum(p.cobertura.values()) / len(config.DIMENSIONES), 3)
    p.confianza = "alta" if p.cobertura_global >= 0.7 else "media" if p.cobertura_global >= config.COBERTURA_MINIMA else "baja"
    return p


def dimension_dominante(p: Perfil) -> tuple[str, float] | tuple[None, None]:
    """La dimensión más alejada del punto medio (50), útil para el diagnóstico."""
    medidas = {d: v for d, v in p.dimensiones.items() if v is not None}
    if not medidas:
        return None, None
    d = max(medidas, key=lambda k: abs(medidas[k] - 50))
    return d, medidas[d]
