"""
app.py
------
Interfaz web local para el pipeline de LeadGen.

Uso:
    pip install -r requirements.txt
    python webapp/app.py
    -> abre http://localhost:5000 en tu navegador

Seguro por defecto: escucha solo en 127.0.0.1 y sin modo debug. Variables
de entorno opcionales:
  - LEADGEN_HOST=0.0.0.0  -> exponerlo en la red local (actívalo junto con
                             LEADGEN_USER/LEADGEN_PASSWORD).
  - LEADGEN_DEBUG=1       -> modo debug de Flask (nunca en una red compartida).
  - SECRET_KEY            -> clave estable; OBLIGATORIA en producción.
  - LEADGEN_ORIGENES_PERMITIDOS -> orígenes extra aceptados en los POST,
                             separados por coma (ej. https://tu-app.onrender.com
                             cuando un proxy termina el HTTPS).

Desde ahí puedes:
  - Pegar la URL de un directorio y procesarla (con selectores opcionales).
  - Ver la tabla de resultados y las estadísticas en la misma página.
  - Descargar Excel / CSV / JSON.
  - Regenerar el dashboard.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import sys
import threading
from functools import wraps
from urllib.parse import urlsplit

from flask import Flask, Response, flash, redirect, render_template, request, send_file, url_for

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leadgen import config, database, export
from leadgen.pipeline import ejecutar_pipeline

app = Flask(__name__)
# En producción, define SECRET_KEY como variable de entorno con un valor estable.
# Sin ella se genera una clave aleatoria por proceso: sirve en local, pero los
# mensajes de la sesión se invalidan en cada reinicio.
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print("[app] Aviso: SECRET_KEY no está definida; se usa una clave aleatoria temporal. "
          "En producción configura SECRET_KEY como variable de entorno.", file=sys.stderr)
app.secret_key = SECRET_KEY

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
        if not auth:
            return _requiere_auth()
        # Comparación en tiempo constante (se evalúan ambas para no filtrar cuál falló)
        usuario_ok = hmac.compare_digest((auth.username or "").encode(), LEADGEN_USER.encode())
        clave_ok = hmac.compare_digest((auth.password or "").encode(), LEADGEN_PASSWORD.encode())
        if not (usuario_ok and clave_ok):
            return _requiere_auth()
        return f(*args, **kwargs)
    return decorada


# --- Protección CSRF por origen ---------------------------------------------
# Todo POST debe venir de la propia app: se compara esquema, host y puerto del
# Origin (o del Referer si el navegador no envía Origin) con los de la petición.
# Sin origen verificable se rechaza. Orígenes extra (ej. la URL https pública
# cuando un proxy como Render termina el TLS) van en LEADGEN_ORIGENES_PERMITIDOS.
_PUERTOS_POR_DEFECTO = {"http": 80, "https": 443}


def _normalizar_origen(url: str) -> tuple[str, str, int] | None:
    """'https://Ejemplo.com' -> ('https', 'ejemplo.com', 443). None si no es válido."""
    try:
        partes = urlsplit(url.strip())
        esquema = partes.scheme.lower()
        if esquema not in _PUERTOS_POR_DEFECTO or not partes.hostname:
            return None
        return esquema, partes.hostname.lower(), partes.port or _PUERTOS_POR_DEFECTO[esquema]
    except ValueError:  # puerto inválido, etc.
        return None


ORIGENES_PERMITIDOS = {
    o for o in (_normalizar_origen(u) for u in os.environ.get("LEADGEN_ORIGENES_PERMITIDOS", "").split(","))
    if o
}


def _origen_valido() -> bool:
    enviado = request.headers.get("Origin") or request.headers.get("Referer")
    if not enviado:
        return False
    origen = _normalizar_origen(enviado)
    if origen is None:  # incluye "Origin: null"
        return False
    propio = _normalizar_origen(f"{request.scheme}://{request.host}")
    return origen == propio or origen in ORIGENES_PERMITIDOS


@app.before_request
def _verificar_origen_post():
    if request.method == "POST" and not _origen_valido():
        return Response("Petición rechazada: origen no verificado.", 403)

# Estado simple en memoria para saber si hay un procesamiento en curso
ESTADO = {"procesando": False, "url": "", "progreso": "", "error": ""}


def _obtener_filas():
    with database.conectar(DB_PATH) as conn:
        return database.obtener_todas(conn)


def _calcular_stats(validas, excluidas):
    """Estadísticas sobre los prospectos válidos; las excluidas solo se cuentan aparte."""
    total = len(validas)
    sin_web = sum(1 for f in validas if not f["tiene_web"])
    web_vieja = sum(1 for f in validas if f["tiene_web"] and (f["web_puntaje"] or 0) < 50)
    potenciales = sum(1 for f in validas if f["pasa_filtro"] == 1)
    con_whatsapp = sum(1 for f in validas if f["tiene_whatsapp"])
    con_correo = sum(1 for f in validas if f["tiene_correo"])
    return {
        "total": total,
        "sin_web": sin_web,
        "web_vieja": web_vieja,
        "potenciales": potenciales,
        "con_whatsapp": con_whatsapp,
        "con_correo": con_correo,
        "excluidas": len(excluidas),
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
    except Exception:
        # El detalle (excepción + traza) va solo al registro del servidor; al usuario, un mensaje genérico
        app.logger.exception("Error procesando %s", url)
        ESTADO["error"] = "Error interno al procesar. El detalle quedó en el registro del servidor."
        ESTADO["progreso"] = "Error"
    finally:
        ESTADO["procesando"] = False


@app.route("/", methods=["GET"])
@login_requerido
def index():
    # obtener_todas ya ordena por score_final (desc); aquí solo se separan las excluidas
    validas, excluidas = database.separar_prospectos(_obtener_filas())
    stats = _calcular_stats(validas, excluidas)
    return render_template("index.html", filas=validas, excluidas=excluidas, stats=stats, estado=ESTADO)


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


def _opciones_servidor() -> tuple[str, int, bool]:
    """(host, puerto, debug) para `python webapp/app.py`. Seguro por defecto: solo local y sin debug."""
    host = os.environ.get("LEADGEN_HOST", "127.0.0.1")
    puerto = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("LEADGEN_DEBUG") == "1"
    return host, puerto, debug


if __name__ == "__main__":
    host, puerto, debug = _opciones_servidor()
    if host in ("127.0.0.1", "localhost"):
        print(f"Abre tu navegador en: http://localhost:{puerto}")
    else:
        print(f"[app] Aviso: escuchando en {host}:{puerto}, accesible desde otros equipos de la red.")
    app.run(debug=debug, host=host, port=puerto)
