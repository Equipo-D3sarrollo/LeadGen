"""
perfil_psicologico.py
---------------------
FASE 4 - NÚCLEO: sistema matemático de análisis psicológico de empresas
(Capa 3). Implementa exactamente la sección 3 del documento técnico
(resumen_perfil_emocional_empresas.txt), con las 6 dimensiones de la
Capa 2 como señales de entrada:

    s_m = 0.5 + cobertura_m · (dimensión_m/100 − 0.5)   (m = 1..6; D-05)
    z_k = b_k + Σ_m W_km · s_m, b_k = −0.5·Σ_m W_km  (k = 8 emociones; D-04)
    p_k = softmax(z_k / T)                         (perfil emocional, suma 1)
    S   = Σ_k p_k · A_k                            (puntaje de venta por producto)
    S%  = 50 ± 50 · (S − S0)/(max|min A − S0)       (S0 = media de A; 50 % = empresa neutra; D-06)

    (x, y, z, w) = (p_ale − p_tri, p_con − p_ave, p_ira − p_mie, p_ant − p_sor)
    k1 = argmax p ; k2 = segunda ; claridad Δ = p_k1 − p_k2
    filtro: p_k1 ≥ θ1  Y  Δ ≥ θ2  Y  S% ≥ θS(producto)

    Score final = α · min(lead_score, 100) + β · S% del mejor producto
                  − penalización · (# datos inválidos)

Decisión documentada (DECISIONES.md D-04): una dimensión NO medida entra
al softmax con el valor neutro config.VALOR_NEUTRO_DIMENSION (0.5), no
con cero; su efecto es "no empuja hacia ninguna emoción" y la falta se
refleja en la cobertura/confianza, nunca en el puntaje.

Además se calcula, por producto, una lectura FIT (cercanía del perfil
al vector ideal del producto en las dimensiones de encaje) y una INTENT
(dolor/urgencia y dinamismo), sección 9.1 del OBJETIVO.

Todos los parámetros (W, b, T, A_k, θ, α, β) son SUPUESTOS INICIALES.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

from . import config
from .perfil import Perfil


@dataclass
class ResultadoPsico:
    s: list = field(default_factory=list)                 # entrada usada (0..1, neutro en faltantes)
    z: list = field(default_factory=list)
    p: dict = field(default_factory=dict)                 # emoción -> probabilidad
    punto: dict = field(default_factory=dict)             # x, y, z, w
    emocion_principal: str = ""
    emocion_secundaria: str = ""
    claridad: float = 0.0
    entropia: float = 0.0
    productos: dict = field(default_factory=dict)         # id -> {...}
    mejor_producto: str = ""
    mejor_producto_nombre: str = ""
    compatibilidad_pct: float | None = None
    fit_pct: float | None = None
    intent_pct: float | None = None
    pasa_filtro: bool = False
    score_final: float | None = None
    excluida: str = ""                                     # motivo si no se puntúa

    def to_dict(self) -> dict:
        return asdict(self)


def softmax(z: list[float], T: float) -> list[float]:
    m = max(v / T for v in z)
    ex = [math.exp(v / T - m) for v in z]
    tot = sum(ex)
    return [v / tot for v in ex]


def entrada_s(perfil: Perfil) -> list[float]:
    """s_m en [0,1]. Faltante -> neutro. Con CONTRAER_POR_COBERTURA: s = n + c·(v − n)."""
    n = config.VALOR_NEUTRO_DIMENSION
    s = []
    for d in config.DIMENSIONES:
        v = perfil.dimensiones.get(d)
        if v is None:
            s.append(n)
            continue
        c = perfil.cobertura.get(d, 1.0) if config.CONTRAER_POR_COBERTURA else 1.0
        s.append(n + c * (v / 100.0 - n))
    return s


def perfil_emocional(s: list[float], W=None, b=None, T=None) -> tuple[list[float], list[float]]:
    W = W or config.W_PSICO
    b = b or config.B_PSICO
    T = T or config.T_PSICO
    z = [b[k] + sum(W[k][m] * s[m] for m in range(len(s))) for k in range(len(W))]
    return z, softmax(z, T)


def puntaje_venta(p: list[float], afinidad: dict) -> tuple[float, float]:
    """
    Devuelve (S en [-1,1], S% en [0,100]).

    S% se ancla en la empresa NEUTRA (perfil uniforme, S0 = media de A),
    DECISIONES D-06: 50 % = igual que una empresa sin postura definida,
    100 % = toda la probabilidad en la emoción más afín, 0 % = toda en la
    menos afín. Así el % es comparable ENTRE productos (con min-max simple,
    un producto con afinidades casi todas positivas salía alto para todos).
    """
    A = [float(afinidad[e]) for e in config.EMOCIONES]
    S = sum(pk * ak for pk, ak in zip(p, A))
    lo, hi, s0 = min(A), max(A), sum(A) / len(A)
    if S >= s0:
        pct = 50.0 if hi == s0 else 50 + 50 * (S - s0) / (hi - s0)
    else:
        pct = 50.0 if s0 == lo else 50 * (S - lo) / (s0 - lo)
    return S, round(pct, 1)


def lectura_fit(perfil: Perfil, vector_ideal: dict) -> float | None:
    """100 − error absoluto medio en las dimensiones de FIT medidas (ponderado por cobertura)."""
    num = den = 0.0
    for d in config.DIMENSIONES:
        if d in config.DIMENSIONES_INTENT:
            continue
        v = perfil.dimensiones.get(d)
        if v is None:
            continue
        w = perfil.cobertura.get(d, 1.0) or 0.0
        num += w * abs(v - float(vector_ideal[d]))
        den += w
    return None if den == 0 else round(100 - num / den, 1)


def lectura_intent(perfil: Perfil) -> float | None:
    """Promedio de dolor/urgencia y dinamismo, contraídos hacia 50 según su cobertura (D-05)."""
    vals = []
    for d in config.DIMENSIONES_INTENT:
        v = perfil.dimensiones.get(d)
        if v is not None:
            c = perfil.cobertura.get(d, 1.0) if config.CONTRAER_POR_COBERTURA else 1.0
            vals.append(50 + c * (v - 50))
    return round(sum(vals) / len(vals), 1) if vals else None


def analizar(
    perfil: Perfil,
    catalogo: dict,
    lead_score: float | None = None,
    es_empresa: bool = True,
    fuera_de_mercado: bool = False,
) -> ResultadoPsico:
    r = ResultadoPsico()
    r.s = [round(v, 3) for v in entrada_s(perfil)]
    z, p = perfil_emocional(r.s)
    r.z = [round(v, 3) for v in z]
    r.p = {e: round(v, 4) for e, v in zip(config.EMOCIONES, p)}
    pe = r.p
    r.punto = {
        "x": round(pe["alegria"] - pe["tristeza"], 3),
        "y": round(pe["confianza"] - pe["aversion"], 3),
        "z": round(pe["ira"] - pe["miedo"], 3),
        "w": round(pe["anticipacion"] - pe["sorpresa"], 3),
    }
    orden = sorted(range(8), key=lambda k: -p[k])
    r.emocion_principal = config.EMOCIONES[orden[0]]
    r.emocion_secundaria = config.EMOCIONES[orden[1]]
    r.claridad = round(p[orden[0]] - p[orden[1]], 4)
    r.entropia = round(-sum(v * math.log(v) for v in p if v > 0), 4)
    r.intent_pct = lectura_intent(perfil)

    # Excluidas (página del directorio / fuera de mercado): se conserva el perfil descriptivo,
    # pero no se les asigna producto, compatibilidad ni score final: no son prospectos.
    if not es_empresa:
        r.excluida = "no es una ficha de empresa (página del directorio)"
    elif fuera_de_mercado:
        r.excluida = f"fuera del mercado objetivo ({config.PAIS_OBJETIVO})"
    if r.excluida:
        return r

    for prod in catalogo.get("productos", []):
        S, pct = puntaje_venta(p, prod["afinidad"])
        umbral = prod.get("umbral_s_pct") or config.UMBRAL_S_PCT
        r.productos[prod["id"]] = {
            "nombre": prod["nombre"],
            "S": round(S, 4),
            "compatibilidad_pct": pct,
            "fit_pct": lectura_fit(perfil, prod["vector_ideal"]),
            "pasa_filtro": bool(p[orden[0]] >= config.UMBRAL_P1 and r.claridad >= config.UMBRAL_DELTA and pct >= umbral),
        }

    if r.productos:
        mejor = max(r.productos, key=lambda k: (r.productos[k]["compatibilidad_pct"], r.productos[k]["fit_pct"] or 0))
        r.mejor_producto = mejor
        r.mejor_producto_nombre = r.productos[mejor]["nombre"]
        r.compatibilidad_pct = r.productos[mejor]["compatibilidad_pct"]
        r.fit_pct = r.productos[mejor]["fit_pct"]
        r.pasa_filtro = r.productos[mejor]["pasa_filtro"]

    if r.compatibilidad_pct is not None:
        lead_norm = 100 * min(float(lead_score or 0), config.LEAD_SCORE_MAX) / config.LEAD_SCORE_MAX
        total = config.ALFA_LEAD * lead_norm + config.BETA_PSICO * r.compatibilidad_pct
        total -= config.PENALIZACION_DATO_INVALIDO * len(perfil.datos_invalidos)
        r.score_final = round(max(total, 0.0), 1)
    return r


def a_columnas(perfil: Perfil, r: ResultadoPsico) -> dict:
    """Aplana perfil + resultado a las columnas de la tabla empresas."""
    col = {f"dim_{d}": perfil.dimensiones.get(d) for d in config.DIMENSIONES}
    col.update(
        cobertura_perfil=perfil.cobertura_global,
        confianza_perfil=perfil.confianza,
        perfil_detalle=json.dumps({"cobertura": perfil.cobertura, "detalle": perfil.detalle}, ensure_ascii=False),
        emocion_principal=r.emocion_principal,
        emocion_secundaria=r.emocion_secundaria,
        claridad=r.claridad,
        perfil_emocional=json.dumps({"p": r.p, "punto": r.punto, "s": r.s}, ensure_ascii=False),
        mejor_producto=r.mejor_producto_nombre,
        compatibilidad_pct=r.compatibilidad_pct,
        compatibilidades=json.dumps(r.productos, ensure_ascii=False),
        fit_pct=r.fit_pct,
        intent_pct=r.intent_pct,
        pasa_filtro=int(r.pasa_filtro),
        score_final=r.score_final,
    )
    return col
