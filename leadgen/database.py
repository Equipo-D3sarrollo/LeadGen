"""
database.py
-----------
MÓDULO 9 - Duplicados / Persistencia

Guarda cada empresa procesada en SQLite. Si la empresa ya existe
(misma URL de perfil), ACTUALIZA sus datos en vez de crear un
registro nuevo -> así nunca hay duplicados, incluso si vuelves a
correr el pipeline sobre el mismo directorio mañana.

Cambios Fases 2-4 (oct. 2026):
  - Migración automática: las columnas nuevas se agregan con ALTER
    TABLE a bases de datos existentes (no se pierde nada).
  - Tabla `contactos`: registro de cada oferta hecha a una empresa
    (producto, fecha, canal, resultado). Es la materia prima de la
    calibración (Fase 7) y se llena desde el primer lead.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_perfil TEXT UNIQUE NOT NULL,
    nombre TEXT,
    direccion TEXT,
    ciudad TEXT,
    departamento TEXT,
    telefono TEXT,
    whatsapp TEXT,
    correo TEXT,
    facebook TEXT,
    instagram TEXT,
    sitio_web TEXT,
    horario TEXT,
    descripcion TEXT,
    categoria TEXT,
    tiene_web INTEGER,
    tiene_facebook INTEGER,
    tiene_instagram INTEGER,
    tiene_whatsapp INTEGER,
    tiene_telefono INTEGER,
    tiene_correo INTEGER,
    web_puntaje INTEGER,
    web_https INTEGER,
    web_responsive INTEGER,
    web_cms TEXT,
    observacion_ia TEXT,
    lead_score INTEGER,
    lead_clasificacion TEXT,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT
);
"""

# Columnas agregadas después del esquema original: (nombre, tipo SQL)
COLUMNAS_NUEVAS = [
    # Fase 2 - calidad de dato y ubicación
    ("pais", "TEXT"), ("es_empresa", "INTEGER"), ("fuera_de_mercado", "INTEGER"),
    ("datos_invalidos", "TEXT"), ("fuente", "TEXT"),
    # Fase 2 - señales digitales nuevas
    ("rating", "REAL"), ("numero_resenas", "INTEGER"), ("dominio_antiguedad_anios", "REAL"),
    ("web_accesible", "INTEGER"), ("web_formulario", "INTEGER"), ("web_analytics", "INTEGER"),
    ("web_tiempo_carga", "REAL"), ("web_titulo", "TEXT"), ("web_meta_descripcion", "INTEGER"),
    ("web_pixel_facebook", "INTEGER"), ("web_herramientas_pago", "TEXT"), ("contacto_web_escaneado", "INTEGER"),
    # Fase 2 - contexto de negocio (Capa 5)
    ("sedes_detectadas", "INTEGER"), ("tamano_estimado", "TEXT"), ("fase_crecimiento", "TEXT"),
    ("senal_presupuesto", "TEXT"), ("cargos_decision", "TEXT"), ("cobertura_contexto", "REAL"),
    # Fase 3 - perfil conductual (Capa 2)
    ("dim_madurez_digital", "REAL"), ("dim_dolor_urgencia", "REAL"), ("dim_confianza_reputacion", "REAL"),
    ("dim_dinamismo", "REAL"), ("dim_apertura_comercial", "REAL"), ("dim_sofisticacion_marca", "REAL"),
    ("cobertura_perfil", "REAL"), ("confianza_perfil", "TEXT"), ("perfil_detalle", "TEXT"),
    # Fase 4 - núcleo psicológico (Capa 3) y score final
    ("emocion_principal", "TEXT"), ("emocion_secundaria", "TEXT"), ("claridad", "REAL"),
    ("perfil_emocional", "TEXT"), ("mejor_producto", "TEXT"), ("compatibilidad_pct", "REAL"),
    ("compatibilidades", "TEXT"), ("fit_pct", "REAL"), ("intent_pct", "REAL"),
    ("pasa_filtro", "INTEGER"), ("score_final", "REAL"),
    # Fase 5 - diagnóstico legible (Capa 4)
    ("diagnostico", "TEXT"),
    ("diagnostico_origen", "TEXT"),   # "ia" | "reglas"; NULL = anterior a esta columna (origen desconocido)
]

ESQUEMA_CONTACTOS = """
CREATE TABLE IF NOT EXISTS contactos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_perfil TEXT NOT NULL,
    nombre_empresa TEXT,
    producto_id TEXT NOT NULL,
    fecha TEXT NOT NULL,
    canal TEXT,
    resultado TEXT NOT NULL,
    notas TEXT,
    compatibilidad_al_ofrecer REAL,
    score_final_al_ofrecer REAL,
    perfil_al_ofrecer TEXT,
    registrado_por TEXT
);
"""

RESULTADOS_VALIDOS = ["pendiente", "sin_respuesta", "interesado", "reunion", "propuesta", "ganado", "perdido",
                      "descartado"]


def _migrar(conn: sqlite3.Connection) -> None:
    existentes = {r[1] for r in conn.execute("PRAGMA table_info(empresas)")}
    for nombre, tipo in COLUMNAS_NUEVAS:
        if nombre not in existentes:
            conn.execute(f"ALTER TABLE empresas ADD COLUMN {nombre} {tipo}")
    conn.execute(ESQUEMA_CONTACTOS)
    conn.commit()


@contextmanager
def conectar(db_path: str = config.DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(ESQUEMA)
        _migrar(conn)
        yield conn
    finally:
        conn.close()


def guardar_o_actualizar(conn: sqlite3.Connection, registro: dict) -> str:
    """
    Inserta la empresa si no existe (por url_perfil), o la actualiza
    si ya existía. Devuelve "creado" o "actualizado".
    """
    ahora = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    existente = conn.execute(
        "SELECT id FROM empresas WHERE url_perfil = ?", (registro["url_perfil"],)
    ).fetchone()

    campos = {k: v for k, v in registro.items() if k != "url_perfil"}

    if existente:
        set_clause = ", ".join(f"{c} = ?" for c in campos)
        valores = list(campos.values()) + [ahora, registro["url_perfil"]]
        conn.execute(
            f"UPDATE empresas SET {set_clause}, fecha_actualizacion = ? WHERE url_perfil = ?",
            valores,
        )
        conn.commit()
        return "actualizado"

    campos["url_perfil"] = registro["url_perfil"]
    campos["fecha_creacion"] = ahora
    campos["fecha_actualizacion"] = ahora
    columnas = ", ".join(campos.keys())
    signos = ", ".join("?" for _ in campos)
    conn.execute(f"INSERT INTO empresas ({columnas}) VALUES ({signos})", list(campos.values()))
    conn.commit()
    return "creado"


def obtener_todas(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM empresas ORDER BY COALESCE(score_final, -1) DESC, lead_score DESC"
    ).fetchall()


def es_excluida(fila) -> bool:
    """Página del directorio (es_empresa=0) o fuera del mercado objetivo: no es un prospecto.
    Filas anteriores a la Fase 2 (columnas en NULL) se consideran válidas."""
    return fila["es_empresa"] == 0 or bool(fila["fuera_de_mercado"])


def separar_prospectos(filas) -> tuple[list, list]:
    """(válidas, excluidas), conservando el orden recibido (score_final desc de obtener_todas)."""
    validas, excluidas = [], []
    for f in filas:
        (excluidas if es_excluida(f) else validas).append(f)
    return validas, excluidas


# ---------------------------------------------------------------------------
# Contactos / resultados (Fase 2c -> insumo de la Fase 7)
# ---------------------------------------------------------------------------
def registrar_contacto(
    conn: sqlite3.Connection,
    url_perfil: str,
    producto_id: str,
    resultado: str = "pendiente",
    canal: str = "",
    notas: str = "",
    fecha: str | None = None,
    registrado_por: str = "",
) -> int:
    """Registra qué se le ofreció a una empresa y qué pasó. Guarda una foto del score en ese momento."""
    if resultado not in RESULTADOS_VALIDOS:
        raise ValueError(f"resultado debe ser uno de {RESULTADOS_VALIDOS}")
    emp = conn.execute(
        "SELECT nombre, compatibilidades, score_final, perfil_detalle FROM empresas WHERE url_perfil = ?",
        (url_perfil,),
    ).fetchone()
    compat = None
    if emp and emp["compatibilidades"]:
        import json
        try:
            compat = json.loads(emp["compatibilidades"]).get(producto_id, {}).get("compatibilidad_pct")
        except Exception:
            compat = None
    cur = conn.execute(
        """INSERT INTO contactos (url_perfil, nombre_empresa, producto_id, fecha, canal, resultado, notas,
           compatibilidad_al_ofrecer, score_final_al_ofrecer, perfil_al_ofrecer, registrado_por)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (url_perfil, emp["nombre"] if emp else "", producto_id, fecha or datetime.now().isoformat(timespec="seconds"),
         canal, resultado, notas, compat, emp["score_final"] if emp else None,
         emp["perfil_detalle"] if emp else None, registrado_por),
    )
    conn.commit()
    return cur.lastrowid


def obtener_contactos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM contactos ORDER BY fecha DESC").fetchall()
