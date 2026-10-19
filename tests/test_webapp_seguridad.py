"""Seguridad mínima de webapp/app.py: arranque, SECRET_KEY, autenticación y origen de los POST.

Nunca toca leadgen.db: cada prueba usa una base temporal en tmp_path.
"""
import hashlib
import importlib
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "webapp"))

from leadgen import database


def _huella(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _filas(ruta):
    with database.conectar(ruta) as conn:
        return len(database.obtener_todas(conn))


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("LEADGEN_ORIGENES_PERMITIDOS", raising=False)
    import app as modulo
    modulo = importlib.reload(modulo)
    db = str(tmp_path / "prueba.db")
    with database.conectar(db) as conn:
        database.guardar_o_actualizar(conn, {"url_perfil": "u1", "nombre": "Empresa Prueba"})
    monkeypatch.setattr(modulo, "DB_PATH", db)
    monkeypatch.setattr(modulo, "LEADGEN_USER", None)
    monkeypatch.setattr(modulo, "LEADGEN_PASSWORD", None)
    modulo.ESTADO.update(procesando=False, url="", progreso="", error="")
    return modulo, db


# --- Arranque local -----------------------------------------------------------
def test_opciones_servidor_por_defecto(web, monkeypatch):
    modulo, _ = web
    for v in ("LEADGEN_HOST", "PORT", "LEADGEN_DEBUG"):
        monkeypatch.delenv(v, raising=False)
    assert modulo._opciones_servidor() == ("127.0.0.1", 5000, False)


def test_opciones_servidor_por_entorno(web, monkeypatch):
    modulo, _ = web
    monkeypatch.setenv("LEADGEN_HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("LEADGEN_DEBUG", "1")
    assert modulo._opciones_servidor() == ("0.0.0.0", 8080, True)


def test_debug_solo_con_valor_explicito(web, monkeypatch):
    modulo, _ = web
    monkeypatch.setenv("LEADGEN_DEBUG", "true")
    assert modulo._opciones_servidor()[2] is False


# --- SECRET_KEY -----------------------------------------------------------------
def test_secret_key_aleatoria_sin_variable(web):
    modulo, _ = web
    assert modulo.app.secret_key != "leadgen-dev-key-cambiame"
    assert len(modulo.app.secret_key) == 64


def test_secret_key_desde_entorno(web, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "clave-estable-de-prueba")
    import app as modulo
    modulo = importlib.reload(modulo)
    assert modulo.app.secret_key == "clave-estable-de-prueba"


# --- POST rechazados: no modifican ni borran la base ---------------------------
@pytest.mark.parametrize("cabeceras", [
    {},                                             # sin Origin ni Referer
    {"Origin": "http://evil.example"},              # otro host
    {"Origin": "https://localhost"},                # otro esquema
    {"Origin": "http://localhost:5000"},            # otro puerto
    {"Origin": "http://localhost.evil.example"},    # host que solo empieza igual
    {"Origin": "null"},                             # origen opaco
    {"Origin": "http://localhost:99999"},           # puerto inválido
    {"Referer": "http://evil.example/pagina"},      # Referer ajeno
])
def test_limpiar_rechaza_origen_no_verificado(web, cabeceras):
    modulo, db = web
    antes = _huella(db)
    r = modulo.app.test_client().post("/limpiar", headers=cabeceras)
    assert r.status_code == 403
    assert os.path.exists(db)
    assert _huella(db) == antes
    assert _filas(db) == 1


def test_procesar_rechazado_no_inicia_pipeline(web):
    modulo, db = web
    antes = _huella(db)
    r = modulo.app.test_client().post("/procesar", data={"url": "https://directorio.example"},
                                      headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert modulo.ESTADO["procesando"] is False and modulo.ESTADO["url"] == ""
    assert _huella(db) == antes


def test_origen_ajeno_rechazado_aunque_haya_credenciales(web, monkeypatch):
    modulo, db = web
    monkeypatch.setattr(modulo, "LEADGEN_USER", "equipo")
    monkeypatch.setattr(modulo, "LEADGEN_PASSWORD", "secreto")
    antes = _huella(db)
    r = modulo.app.test_client().post("/limpiar", auth=("equipo", "secreto"),
                                      headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert _huella(db) == antes


def test_limpiar_sin_credenciales_rechazado(web, monkeypatch):
    modulo, db = web
    monkeypatch.setattr(modulo, "LEADGEN_USER", "equipo")
    monkeypatch.setattr(modulo, "LEADGEN_PASSWORD", "secreto")
    antes = _huella(db)
    r = modulo.app.test_client().post("/limpiar", headers={"Origin": "http://localhost"})
    assert r.status_code == 401
    assert _huella(db) == antes


# --- POST legítimos -----------------------------------------------------------------
def test_limpiar_mismo_origen_borra_base_temporal(web):
    modulo, db = web
    r = modulo.app.test_client().post("/limpiar", headers={"Origin": "http://localhost"})
    assert r.status_code == 302
    assert not os.path.exists(db)


def test_limpiar_con_referer_propio(web):
    modulo, db = web
    r = modulo.app.test_client().post("/limpiar", headers={"Referer": "http://localhost/"})
    assert r.status_code == 302
    assert not os.path.exists(db)


def test_origen_de_la_lista_permitida(web, monkeypatch):
    modulo, db = web
    monkeypatch.setattr(modulo, "ORIGENES_PERMITIDOS", {modulo._normalizar_origen("https://tu-app.onrender.com")})
    r = modulo.app.test_client().post("/limpiar", headers={"Origin": "https://tu-app.onrender.com"})
    assert r.status_code == 302
    assert not os.path.exists(db)


def test_procesar_mismo_origen_sin_url_no_lanza_pipeline(web):
    modulo, _ = web
    r = modulo.app.test_client().post("/procesar", data={"url": ""}, headers={"Origin": "http://localhost"})
    assert r.status_code == 302
    assert modulo.ESTADO["procesando"] is False


# --- Autenticación ------------------------------------------------------------------
@pytest.mark.parametrize("credenciales, esperado", [
    (None, 401),
    (("equipo", "incorrecta"), 401),
    (("otro", "secreto"), 401),
    (("equipo", "secreto"), 200),
])
def test_autenticacion_basica(web, monkeypatch, credenciales, esperado):
    modulo, _ = web
    monkeypatch.setattr(modulo, "LEADGEN_USER", "equipo")
    monkeypatch.setattr(modulo, "LEADGEN_PASSWORD", "secreto")
    r = modulo.app.test_client().get("/", auth=credenciales)
    assert r.status_code == esperado


def test_autenticacion_con_caracteres_no_ascii(web, monkeypatch):
    modulo, _ = web
    monkeypatch.setattr(modulo, "LEADGEN_USER", "equipo")
    monkeypatch.setattr(modulo, "LEADGEN_PASSWORD", "contraseña")
    c = modulo.app.test_client()
    assert c.get("/", auth=("equipo", "contraseña")).status_code == 200
    assert c.get("/", auth=("equipo", "contrasena")).status_code == 401


def test_sin_credenciales_configuradas_sigue_abierto_en_local(web):
    modulo, _ = web
    assert modulo.app.test_client().get("/").status_code == 200
