"""
app.py
------
Interfaz web local para el pipeline de LeadGen.

Uso:
    pip install -r requirements.txt
    python app.py
    -> abre http://localhost:5000 en tu navegador

Desde ahí puedes:
  - Pegar la URL de un directorio y procesarla (con selectores opcionales).
  - Ver la tabla de resultados y las estadísticas en la misma página.
  - Descargar Excel / CSV / JSON.
  - Regenerar el dashboard.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from functools import wraps

from flask import Flask, Response, flash, redirect, render_template, request, send_file, url_for

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leadgen import config, database, export
from leadgen.pipeline import ejecutar_pipeline

app = Flask(__name__)
# En producción, define SECRET_KEY como variable de entorno (no dejes el valor por defecto).
app.secret_key = os.environ.get("SECRET_KEY", "leadgen-dev-key-cambiame")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "leadgen.db")

# --- Autenticación básica ---------------------------------------------------
# Si defines LEADGEN_USER y LEADGEN_PASSWORD como variables de entorno, la app
# pide usuario/contraseña antes de dejar entrar a nadie. Si no las defines
# (ej. mientras pruebas en tu computador), queda abierta sin pedir nada.
LEADGEN_USER = os.environ.get("LEADGEN_USER")
LEADGEN_PASSWORD = os.environ.get("LEADGEN_PASSWORD")


def _requiere_auth():
    return Response(
        "Acceso restringido. Ingresa el usuario y la contraseña.", 401,
        {"WWW-Authenticate": 'Basic realm="LeadGen"'},
    )


def login_requerido(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        if not LEADGEN_USER or not LEADGEN_PASSWORD:
            return f(*args, **kwargs)  # sin credenciales configuradas -> abierto (uso local)
        auth = request.authorization
        if not auth or auth.username != LEADGEN_USER or auth.password != LEADGEN_PASSWORD:
            return _requiere_auth()
        return f(*args, **kwargs)
    return decorada

# Estado simple en memoria para saber si hay un procesamiento en curso
ESTADO = {"procesando": False, "url": "", "progreso": "", "error": ""}


def _obtener_filas():
    with database.conectar(DB_PATH) as conn:
        return database.obtener_todas(conn)


def _calcular_stats(filas):
    total = len(filas)
    sin_web = sum(1 for f in filas if not f["tiene_web"])
    web_vieja = sum(1 for f in filas if f["tiene_web"] and (f["web_puntaje"] or 0) < 50)
    potenciales = sum(1 for f in filas if (f["lead_score"] or 0) >= 50)
    con_whatsapp = sum(1 for f in filas if f["tiene_whatsapp"])
    con_correo = sum(1 for f in filas if f["tiene_correo"])
    return {
        "total": total,
        "sin_web": sin_web,
        "web_vieja": web_vieja,
        "potenciales": potenciales,
        "con_whatsapp": con_whatsapp,
        "con_correo": con_correo,
    }


def _correr_pipeline_en_hilo(url, selectores_directorio, selectores_ficha, usar_ia, usar_navegador, max_resultados_maps):
    ESTADO["procesando"] = True
    ESTADO["url"] = url
    ESTADO["progreso"] = "Iniciando..."
    ESTADO["error"] = ""
    try:
        ejecutar_pipeline(
            url_directorio=url,
            selectores_directorio=selectores_directorio,
            selectores_ficha=selectores_ficha,
            usar_ia=usar_ia,
            usar_navegador=usar_navegador,
            max_resultados_maps=max_resultados_maps,
            db_path=DB_PATH,
            verbose=True,
        )
        ESTADO["progreso"] = "Completado"
    except Exception as e:
        ESTADO["error"] = f"{e}\n{traceback.format_exc()}"
        ESTADO["progreso"] = "Error"
    finally:
        ESTADO["procesando"] = False


@app.route("/", methods=["GET"])
@login_requerido
def index():
    filas = _obtener_filas()
    stats = _calcular_stats(filas)
    top = sorted(filas, key=lambda f: f["lead_score"] or 0, reverse=True)
    return render_template("index.html", filas=top, stats=stats, estado=ESTADO)


@app.route("/procesar", methods=["POST"])
@login_requerido
def procesar():
    if ESTADO["procesando"]:
        flash("Ya hay un procesamiento en curso, espera a que termine.", "error")
        return redirect(url_for("index"))

    url = request.form.get("url", "").strip()
    if not url:
        flash("Debes escribir una URL.", "error")
        return redirect(url_for("index"))

    usar_ia = request.form.get("usar_ia") == "on"
    usar_navegador = request.form.get("usar_navegador") == "on"
    try:
        max_resultados_maps = int(request.form.get("max_resultados_maps", "40") or "40")
    except ValueError:
        max_resultados_maps = 40

    selectores_directorio = {}
    selectores_ficha = {}
    config_texto = request.form.get("config_json", "").strip()
    if config_texto:
        try:
            cfg = json.loads(config_texto)
            selectores_directorio = cfg.get("selectores_directorio", {})
            selectores_ficha = cfg.get("selectores_ficha", {})
        except json.JSONDecodeError as e:
            flash(f"El JSON de configuración no es válido: {e}", "error")
            return redirect(url_for("index"))

    hilo = threading.Thread(
        target=_correr_pipeline_en_hilo,
        args=(url, selectores_directorio, selectores_ficha, usar_ia, usar_navegador, max_resultados_maps),
        daemon=True,
    )
    hilo.start()

    flash(f"Procesando {url}... refresca la página en unos segundos para ver el progreso.", "ok")
    return redirect(url_for("index"))


@app.route("/estado")
@login_requerido
def estado():
    """Endpoint simple para consultar el progreso vía JS (polling)."""
    return ESTADO


@app.route("/exportar/<formato>")
@login_requerido
def exportar(formato):
    filas = _obtener_filas()
    if not filas:
        flash("No hay datos todavía para exportar.", "error")
        return redirect(url_for("index"))

    ruta_tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"leads_export.{formato}")
    if formato == "excel":
        ruta = export.exportar_excel(filas, ruta_tmp.replace(".excel", ".xlsx"))
    elif formato == "csv":
        ruta = export.exportar_csv(filas, ruta_tmp)
    elif formato == "json":
        ruta = export.exportar_json(filas, ruta_tmp)
    else:
        flash("Formato no soportado.", "error")
        return redirect(url_for("index"))

    return send_file(ruta, as_attachment=True)


@app.route("/limpiar", methods=["POST"])
@login_requerido
def limpiar():
    """Borra toda la base de datos (útil para empezar de cero en pruebas)."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    flash("Base de datos limpiada.", "ok")
    return redirect(url_for("index"))


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    modo_local = "PORT" not in os.environ  # Render/Railway definen PORT; en tu PC no existe
    if modo_local:
        print("Abre tu navegador en: http://localhost:5000")
    app.run(debug=modo_local, host="0.0.0.0", port=puerto)
