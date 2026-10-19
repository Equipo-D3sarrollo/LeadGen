"""Mejoras comerciales 1-3: presentación por score_final con excluidas aparte,
filas excluidas sin recomendación y rescate de contactos que limpia su marca de invalidez.

Solo bases temporales (tmp_path) y datos sintéticos.
"""
import importlib
import json
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "webapp"))

from leadgen import (catalogo, dashboard, database, diagnostico, google_maps, normalize, perfil,
                     perfil_psicologico as pp, pipeline, web_analysis)
from leadgen.scraper import EmpresaCruda

CAT = catalogo.catalogo_por_defecto()
TEL_CORRUPTO = "5076507550745073507250715070"

# --- Mejora 1: presentación ---------------------------------------------------------
REGISTROS = [
    # nombre, lead_score, score_final, pasa_filtro, es_empresa, fuera_de_mercado, pais
    ("Valida Alta", 30, 80.0, 1, 1, 0, "Colombia"),
    ("Valida Baja", 90, 50.0, 0, 1, 0, "Colombia"),
    ("Antigua Sin Score", 95, None, None, None, None, ""),     # fila previa a la Fase 2
    ("Categoria Restaurantes", 75, None, 1, 0, 0, ""),         # página del directorio (pasa_filtro heredado)
    ("Fresno Co", 100, None, 0, 1, 1, "Estados Unidos"),       # fuera de mercado
]


@pytest.fixture
def db_mixta(tmp_path):
    ruta = str(tmp_path / "mixta.db")
    with database.conectar(ruta) as conn:
        for i, (nombre, lead, final, filtro, emp, fuera, pais) in enumerate(REGISTROS):
            database.guardar_o_actualizar(conn, {
                "url_perfil": f"https://dir.example/{i}", "nombre": nombre, "lead_score": lead,
                "score_final": final, "pasa_filtro": filtro, "es_empresa": emp, "fuera_de_mercado": fuera,
                "pais": pais, "tiene_web": 0, "tiene_whatsapp": 1, "tiene_correo": 0, "tiene_telefono": 1,
                "lead_clasificacion": "x",
            })
    return ruta


def test_separar_prospectos_orden_y_exclusion(db_mixta):
    with database.conectar(db_mixta) as conn:
        validas, excluidas = database.separar_prospectos(database.obtener_todas(conn))
    assert [f["nombre"] for f in validas] == ["Valida Alta", "Valida Baja", "Antigua Sin Score"]
    assert {f["nombre"] for f in excluidas} == {"Categoria Restaurantes", "Fresno Co"}


@pytest.fixture
def web(db_mixta, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import app as modulo
    modulo = importlib.reload(modulo)
    monkeypatch.setattr(modulo, "DB_PATH", db_mixta)
    monkeypatch.setattr(modulo, "LEADGEN_USER", None)
    monkeypatch.setattr(modulo, "LEADGEN_PASSWORD", None)
    return modulo


def test_web_ordena_por_score_final_y_separa_excluidas(web):
    html = web.app.test_client().get("/").get_data(as_text=True)
    principal, _, bloque_excluidas = html.partition("Registros excluidos")
    # orden por score_final, no por lead_score
    assert principal.index("Valida Alta") < principal.index("Valida Baja") < principal.index("Antigua Sin Score")
    # excluidas solo en su bloque
    for nombre in ("Categoria Restaurantes", "Fresno Co"):
        assert nombre not in principal and nombre in bloque_excluidas
    assert "Resultados (3)" in principal


def test_web_estadisticas_solo_validas(web):
    validas, excluidas = database.separar_prospectos(web._obtener_filas())
    stats = web._calcular_stats(validas, excluidas)
    assert stats["total"] == 3
    assert stats["potenciales"] == 1          # solo pasa_filtro=1 entre válidas (no la página del directorio)
    assert stats["excluidas"] == 2
    assert stats["con_whatsapp"] == 3


def test_dashboard_por_score_final_sin_excluidas(db_mixta, tmp_path):
    with database.conectar(db_mixta) as conn:
        filas = database.obtener_todas(conn)
    ruta = dashboard.generar_dashboard(list(reversed(filas)), str(tmp_path / "d.html"))  # orden de entrada alterado
    html = open(ruta, encoding="utf-8").read()
    assert html.index("Valida Alta") < html.index("Valida Baja") < html.index("Antigua Sin Score")
    assert "Categoria Restaurantes" not in html and "Fresno Co" not in html
    assert '<div class="num">1</div><div class="label">Clientes potenciales' in html
    assert '<div class="num">2</div><div class="label">Excluidas' in html


# --- Mejora 2: filas excluidas ------------------------------------------------------
SIN_WEB = {"fuente": "directorio", "url_perfil": "https://dir.example/empresa/1", "tiene_telefono": 1,
           "tiene_whatsapp": 1, "tiene_facebook": 1, "sedes_detectadas": 1}


@pytest.mark.parametrize("kwargs", [{"es_empresa": False}, {"fuera_de_mercado": True}])
def test_excluida_sin_recomendacion_comercial(kwargs):
    per = perfil.calcular_perfil(SIN_WEB)
    r = pp.analizar(per, CAT, 75, **kwargs)
    assert r.excluida
    assert r.mejor_producto == "" and r.mejor_producto_nombre == ""
    assert r.compatibilidad_pct is None and r.fit_pct is None and r.productos == {}
    assert r.score_final is None and r.pasa_filtro is False
    assert abs(sum(r.p.values()) - 1) < 1e-3          # el perfil descriptivo se conserva
    col = pp.a_columnas(per, r)
    assert col["mejor_producto"] == "" and col["compatibilidad_pct"] is None
    assert json.loads(col["compatibilidades"]) == {} and col["pasa_filtro"] == 0
    assert diagnostico.diagnosticar(per, r, SIN_WEB).startswith("No se analiza")


def test_valida_sigue_recibiendo_recomendacion():
    r = pp.analizar(perfil.calcular_perfil(SIN_WEB), CAT, 75)
    assert r.mejor_producto and r.compatibilidad_pct is not None and r.score_final is not None


# --- Mejora 3: rescate de contactos -------------------------------------------------
def _analisis(**contacto):
    return web_analysis.AnalisisWeb(url="https://x.co", accesible=True, contacto_escaneado=True, **contacto)


def _limpia(**campos):
    return normalize.normalizar_empresa(EmpresaCruda(url_perfil="https://dir.example/e", nombre="X", **campos))


def test_rescate_telefono_quita_solo_su_marca():
    e = _limpia(telefono=TEL_CORRUPTO, whatsapp="31117", correo="no-es-correo")
    assert e.datos_invalidos == ["telefono", "whatsapp", "correo"]
    pipeline._completar_contacto_desde_web(e, _analisis(telefono="+57 300 123 4567"))
    assert e.telefono == "3001234567"
    assert e.datos_invalidos == ["whatsapp", "correo"]


def test_rescate_whatsapp_quita_su_marca():
    e = _limpia(telefono=TEL_CORRUPTO, whatsapp="31117")
    pipeline._completar_contacto_desde_web(e, _analisis(whatsapp="573001234567"))
    assert e.whatsapp and e.datos_invalidos == ["telefono"]


def test_rescate_invalido_conserva_marca_una_vez():
    e = _limpia(telefono=TEL_CORRUPTO)
    pipeline._completar_contacto_desde_web(e, _analisis(telefono="31117"))
    assert e.telefono == "" and e.datos_invalidos == ["telefono"]


def test_sin_escaneo_no_toca_marcas():
    e = _limpia(telefono=TEL_CORRUPTO)
    pipeline._completar_contacto_desde_web(e, web_analysis.AnalisisWeb(url="https://x.co", telefono="3001234567"))
    assert e.telefono == "" and e.datos_invalidos == ["telefono"]


def test_pipeline_usa_contacto_rescatado_en_perfil_y_score(tmp_path, monkeypatch):
    """Teléfono corrupto en la fuente + teléfono válido en la web = mismo resultado que una fuente correcta."""
    comun = dict(direccion="Cra 1 #2-3, Pereira, Risaralda", sitio_web="https://taller.co")
    crudas = [EmpresaCruda(nombre="Taller Uno", url_perfil="https://www.google.com/maps/place/1",
                           telefono=TEL_CORRUPTO, **comun),
              EmpresaCruda(nombre="Taller Dos", url_perfil="https://www.google.com/maps/place/2",
                           telefono="3001234567", **comun)]
    monkeypatch.setattr(google_maps, "extraer_negocios_google_maps", lambda *a, **k: crudas)

    def fake_web(url):
        a = web_analysis.AnalisisWeb(url=url, accesible=True, https=True, tiempo_carga_seg=1.0)
        web_analysis.analizar_html(a, "<html><title>T</title><a href='tel:+573001234567'>llámanos</a></html>")
        a.puntaje = web_analysis._calcular_puntaje(a)
        return a
    monkeypatch.setattr(web_analysis, "analizar_sitio", fake_web)

    db = str(tmp_path / "p.db")
    res = pipeline.ejecutar_pipeline("https://www.google.com/maps/search/talleres", db_path=db, verbose=False,
                                     catalogo_path=str(tmp_path / "no.json"), consultar_dominio=False)
    assert res["errores"] == 0
    with database.conectar(db) as conn:
        filas = {f["nombre"]: dict(f) for f in database.obtener_todas(conn)}
    uno, dos = filas["Taller Uno"], filas["Taller Dos"]
    assert uno["telefono"] == "3001234567" and uno["datos_invalidos"] == ""
    assert uno["tiene_telefono"] == 1 and uno["lead_score"] == dos["lead_score"]
    assert uno["dim_apertura_comercial"] == dos["dim_apertura_comercial"]
    assert uno["score_final"] is not None and uno["score_final"] == dos["score_final"]
    assert "corrupto" not in uno["diagnostico"]
