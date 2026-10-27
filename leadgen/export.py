"""
export.py
---------
MÓDULO 10 - Exportación

Convierte lo que hay en la base de datos a Excel, CSV o JSON, listo
para subir a un CRM o compartir con el equipo comercial.

Fase 6 (adelanto, oct. 2026): el Excel pone primero las columnas que usa
el vendedor (score final, producto, compatibilidad, diagnóstico,
confianza) y agrega la hoja "Contactos" con el historial de ofertas.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3

import openpyxl
import pandas as pd

COLUMNAS_COMERCIALES = [
    "nombre", "categoria", "ciudad", "departamento", "telefono", "whatsapp", "correo", "sitio_web",
    "score_final", "mejor_producto", "compatibilidad_pct", "fit_pct", "intent_pct", "pasa_filtro",
    "confianza_perfil", "cobertura_perfil", "diagnostico", "lead_score", "lead_clasificacion",
    "dim_madurez_digital", "dim_dolor_urgencia", "dim_confianza_reputacion", "dim_dinamismo",
    "dim_apertura_comercial", "dim_sofisticacion_marca", "emocion_principal", "emocion_secundaria", "claridad",
    "es_empresa", "fuera_de_mercado", "datos_invalidos",
]


# Recomendaciones y puntuaciones comerciales: se vacían en el archivo exportado para las
# excluidas (página del directorio / fuera de mercado). La base de datos no se toca.
COLUMNAS_COMERCIALES_OCULTAS_EXCLUIDAS = [
    "mejor_producto", "compatibilidad_pct", "fit_pct", "intent_pct", "compatibilidades", "pasa_filtro",
    "score_final", "lead_score", "lead_clasificacion",
]

_NUMERO_TEXTO = re.compile(
    r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?$"
)


def _es_excluida(d: dict) -> bool:
    fuera = d.get("fuera_de_mercado")
    if isinstance(fuera, float) and math.isnan(fuera):
        fuera = 0
    return d.get("es_empresa") == 0 or bool(fuera)


def _para_exportar(filas) -> list[dict]:
    datos = []
    for f in filas:
        d = dict(f)
        if _es_excluida(d):
            for c in COLUMNAS_COMERCIALES_OCULTAS_EXCLUIDAS:
                if c in d:
                    d[c] = None
        datos.append(d)
    return datos


def _a_dataframe(filas) -> pd.DataFrame:
    df = pd.DataFrame(_para_exportar(filas))
    primeras = [c for c in COLUMNAS_COMERCIALES if c in df.columns]
    return df[primeras + [c for c in df.columns if c not in primeras]]


def _texto_puede_ser_formula(valor) -> bool:
    if not isinstance(valor, str) or _NUMERO_TEXTO.fullmatch(valor):
        return False
    significativo = valor.lstrip()
    while significativo and ord(significativo[0]) < 32:
        significativo = significativo[1:].lstrip()
    return bool(significativo) and significativo[0] in "=+-@"


def _neutralizar_csv(df: pd.DataFrame) -> pd.DataFrame:
    resultado = df.copy()
    for columna in resultado.columns:
        resultado[columna] = resultado[columna].map(
            lambda valor: "'" + valor if _texto_puede_ser_formula(valor) else valor
        )
    return resultado


def _forzar_texto_excel(ruta_salida: str) -> None:
    libro = openpyxl.load_workbook(ruta_salida)
    for hoja in libro.worksheets:
        for fila in hoja.iter_rows():
            for celda in fila:
                if _texto_puede_ser_formula(celda.value):
                    celda.data_type = "s"
                    celda.number_format = "@"
    libro.save(ruta_salida)


def exportar_excel(filas, ruta_salida: str = "leads.xlsx", contactos=None) -> str:
    df = _a_dataframe(filas)
    with pd.ExcelWriter(ruta_salida) as w:
        df.to_excel(w, index=False, sheet_name="Leads")
        if contactos:
            pd.DataFrame([dict(c) for c in contactos]).to_excel(w, index=False, sheet_name="Contactos")
    _forzar_texto_excel(ruta_salida)
    return ruta_salida


def exportar_csv(filas, ruta_salida: str = "leads.csv") -> str:
    df = _a_dataframe(filas)
    _neutralizar_csv(df).to_csv(ruta_salida, index=False, encoding="utf-8-sig")
    return ruta_salida


def exportar_json(filas, ruta_salida: str = "leads.json") -> str:
    datos = _para_exportar(filas)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
    return ruta_salida
