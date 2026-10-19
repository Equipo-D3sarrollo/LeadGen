"""Regresión de seguridad: escape de datos dinámicos (XSS) en la web y el dashboard,
y errores internos sin trazas para el usuario (el detalle va al registro).

Solo bases temporales; el pipeline se reemplaza por funciones simuladas (sin red).
"""
import importlib
import logging
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "webapp"))

from leadgen import dashboard, database

SCRIPT = "<script>alert(1)</script>"
ATRIBUTO = '"><img src=x onerror=alert(1)>'
COMILLA = "' onmouseover='alert(1)"
CRUDOS = (SCRIPT, "<img", "<b>", "onerror=alert(1)>")


def _sin_crudos(html):
    return not any(c in html for c in CRUDOS)


@pytest.fixture
def db_maliciosa(tmp_path):
    db = str(tmp_path / "xss.db")
    with database.conectar(db) as conn:
        database.guardar_o_actualizar(conn, {
            "url_perfil": "https://dir.example/empresa/1", "nombre": SCRIPT, "ciudad": ATRIBUTO,
            "lead_clasificacion": "<b>fuerte</b>", "score_final": 70.0, "pasa_filtro": 1,
            "es_empresa": 1, "fuera_de_mercado": 0, "tiene_web": 0, "tiene_whatsapp": 1,
        })
        database.guardar_o_actualizar(conn, {
            "url_perfil": "https://dir.example/categoria/" + ATRIBUTO, "nombre": COMILLA + SCRIPT,
            "pais": "<img src=x onerror=alert(2)>", "es_empresa": 0, "fuera_de_mercado": 0,
        })
    return db


# --- Dashboard ----------------------------------------------------------------------
def test_dashboard_escapa_datos_dinamicos(db_maliciosa, tmp_path):
    with database.conectar(db_maliciosa) as conn:
        filas = database.obtener_todas(conn)
    html = open(dashboard.generar_dashboard(filas, str(tmp_path / "d.html")), encoding="utf-8").read()
    assert _sin_crudos(html)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&quot;&gt;&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&lt;b&gt;fuerte&lt;/b&gt;" in html


def test_dashboard_escapa_comillas_simples():
    assert dashboard._e(COMILLA) == "&#x27; onmouseover=&#x27;alert(1)"
    assert dashboard._e(None) == ""


# --- Web (Jinja) -------------------------------------------------------------------------
@pytest.fixture
def web(db_maliciosa, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import app as modulo
    modulo = importlib.reload(modulo)
    monkeypatch.setattr(modulo, "DB_PATH", db_maliciosa)
    monkeypatch.setattr(modulo, "LEADGEN_USER", None)
    monkeypatch.setattr(modulo, "LEADGEN_PASSWORD", None)
    modulo.ESTADO.update(procesando=False, url="", progreso="", error="")
    return modulo


def test_web_escapa_filas_validas_y_excluidas(web):
    html = web.app.test_client().get("/").get_data(as_text=True)
    assert _sin_crudos(html) and "onerror=alert(2)>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Registros excluidos" in html and "&#39; onmouseover=&#39;alert(1)" in html


def test_web_escapa_url_en_estado_y_flash(web, monkeypatch):
    monkeypatch.setattr(web, "ejecutar_pipeline", lambda **k: None)
    c = web.app.test_client()
    r = c.post("/procesar", data={"url": "https://x.example/" + SCRIPT}, headers={"Origin": "http://localhost"},
               follow_redirects=True)
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and SCRIPT not in html and "&lt;script&gt;" in html
    web.ESTADO.update(procesando=True, url=SCRIPT)
    assert SCRIPT not in c.get("/").get_data(as_text=True)


# --- Errores internos ---------------------------------------------------------------------
SECRETO = r"detalle interno C:\secreto\leadgen.db"


def test_error_del_pipeline_no_se_muestra_y_queda_en_el_registro(web, monkeypatch, caplog):
    def falla(**_):
        raise RuntimeError(SECRETO)
    monkeypatch.setattr(web, "ejecutar_pipeline", falla)
    with caplog.at_level(logging.ERROR):
        web._correr_pipeline_en_hilo("https://x.example", {}, {}, False, False, 10)

    assert web.ESTADO["progreso"] == "Error" and web.ESTADO["procesando"] is False
    assert "secreto" not in web.ESTADO["error"] and "Traceback" not in web.ESTADO["error"]
    # el detalle completo sí queda en el registro del servidor
    registro = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert registro and registro[0].exc_info is not None and SECRETO in caplog.text

    c = web.app.test_client()
    pagina = c.get("/").get_data(as_text=True)
    estado = c.get("/estado").get_data(as_text=True)
    for cuerpo in (pagina, estado):
        assert "secreto" not in cuerpo and "Traceback" not in cuerpo and "RuntimeError" not in cuerpo
    assert "Error interno al procesar" in pagina
