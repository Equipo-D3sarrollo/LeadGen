from unittest.mock import Mock, patch

import pytest
import requests

from leadgen import web_analysis


def _respuesta(texto="<html><title>Prueba</title></html>", ok=True, url=None, status_code=200):
    respuesta = Mock(ok=ok, url=url or "https://ejemplo.test", text=texto, status_code=status_code)
    return respuesta


@pytest.fixture(autouse=True)
def limpiar_cache_http():
    web_analysis._limpiar_cache_http()
    yield
    web_analysis._limpiar_cache_http()


def test_analizar_sitio_reutiliza_respuesta_principal_y_auxiliares():
    respuestas = [
        _respuesta(),
        _respuesta(status_code=200),
        _respuesta(status_code=200),
    ]
    with patch("requests.get", side_effect=respuestas) as get:
        primero = web_analysis.analizar_sitio("https://ejemplo.test")
        segundo = web_analysis.analizar_sitio("https://ejemplo.test")

    assert get.call_count == 3
    assert segundo.to_dict() == primero.to_dict()


def test_analizar_sitio_no_comparte_analisis_entre_urls_distintas():
    respuestas = [
        _respuesta(texto="<html><title>Uno</title></html>"),
        _respuesta(status_code=200),
        _respuesta(status_code=200),
        _respuesta(texto="<html><title>Dos</title></html>"),
        _respuesta(status_code=200),
        _respuesta(status_code=200),
    ]
    with patch("requests.get", side_effect=respuestas) as get:
        primero = web_analysis.analizar_sitio("https://ejemplo.test/uno")
        segundo = web_analysis.analizar_sitio("https://ejemplo.test/dos")

    assert get.call_count == 4
    assert primero.titulo == "Uno"
    assert segundo.titulo == "Dos"


def test_analizar_sitio_reutiliza_respuesta_principal_no_exitosa():
    respuesta = _respuesta(texto="<html><title>Error</title></html>", ok=False, status_code=503)
    auxiliares = [_respuesta(status_code=404), _respuesta(status_code=500)]
    with patch("requests.get", side_effect=[respuesta, *auxiliares]) as get:
        primero = web_analysis.analizar_sitio("https://ejemplo.test")
        segundo = web_analysis.analizar_sitio("https://ejemplo.test")

    assert get.call_count == 3
    assert primero.accesible is False
    assert segundo.accesible is False
    assert primero.titulo == segundo.titulo == "Error"
    assert primero.tiene_robots_txt is False
    assert primero.tiene_sitemap is False


def test_analizar_sitio_no_cachea_excepciones():
    respuesta = _respuesta()
    with patch(
        "requests.get",
        side_effect=[requests.RequestException("fallo"), respuesta, _respuesta(), _respuesta()],
    ) as get:
        primero = web_analysis.analizar_sitio("https://ejemplo.test")
        segundo = web_analysis.analizar_sitio("https://ejemplo.test")

    assert primero.accesible is False
    assert get.call_count == 4
    assert segundo.accesible is True


def test_analizar_sitio_preserva_redireccion_https():
    respuesta = _respuesta(url="https://ejemplo.test/final")
    with patch("requests.get", side_effect=[respuesta, _respuesta(), _respuesta()]) as get:
        resultado = web_analysis.analizar_sitio("http://ejemplo.test/inicio")

    assert get.call_count == 3
    assert resultado.https is True


def test_cache_http_tiene_limite_lru_de_256_entradas():
    respuesta = _respuesta(ok=False, status_code=503)
    with patch("requests.get", return_value=respuesta) as get:
        urls = [f"https://ejemplo-{i}.test" for i in range(256)]
        for url in urls:
            web_analysis._obtener_respuesta(url, "principal")
        web_analysis._obtener_respuesta(urls[0], "principal")
        web_analysis._obtener_respuesta("https://ejemplo-adicional.test", "principal")

    assert len(web_analysis._CACHE_HTTP) == 256
    assert ("principal", urls[0]) in web_analysis._CACHE_HTTP
    assert ("principal", urls[1]) not in web_analysis._CACHE_HTTP
    assert ("principal", "https://ejemplo-adicional.test") in web_analysis._CACHE_HTTP
    assert get.call_count == 257
