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
import sqlite3

import pandas as pd

COLUMNAS_COMERCIALES = [
    "nombre", "categoria", "ciudad", "departamento", "telefono", "whatsapp", "correo", "sitio_web",
    "score_final", "mejor_producto", "compatibilidad_pct", "fit_pct", "intent_pct", "pasa_filtro",
    "confianza_perfil", "cobertura_perfil", "diagnostico", "lead_score", "lead_clasificacion",
    "dim_madurez_digital", "dim_dolor_urgencia", "dim_confianza_reputacion", "dim_dinamismo",
    "dim_apertura_comercial", "dim_sofisticacion_marca", "emocion_principal", "emocion_secundaria", "claridad",
    "es_empresa", "fuera_de_mercado", "datos_invalidos",
]


def _a_dataframe(filas) -> pd.DataFrame:
    df = pd.DataFrame([dict(f) for f in filas])
    primeras = [c for c in COLUMNAS_COMERCIALES if c in df.columns]
    return df[primeras + [c for c in df.columns if c not in primeras]]


def exportar_excel(filas, ruta_salida: str = "leads.xlsx", contactos=None) -> str:
    df = _a_dataframe(filas)
    with pd.ExcelWriter(ruta_salida) as w:
        df.to_excel(w, index=False, sheet_name="Leads")
        if contactos:
            pd.DataFrame([dict(c) for c in contactos]).to_excel(w, index=False, sheet_name="Contactos")
    return ruta_salida


def exportar_csv(filas, ruta_salida: str = "leads.csv") -> str:
    df = _a_dataframe(filas)
    df.to_csv(ruta_salida, index=False, encoding="utf-8-sig")
    return ruta_salida


def exportar_json(filas, ruta_salida: str = "leads.json") -> str:
    datos = [dict(f) for f in filas]
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
    return ruta_salida
