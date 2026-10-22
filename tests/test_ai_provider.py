import sys
import types

import pytest

from leadgen import ai_provider


def _fake_openai(monkeypatch):
    recibido = []

    class OpenAI:
        def __init__(self, api_key):
            recibido.append(api_key)

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=OpenAI))
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None))
    return recibido


def test_cliente_de_prueba_requiere_clave_independiente(monkeypatch):
    recibido = _fake_openai(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "clave-produccion-simulada")
    monkeypatch.delenv("OPENAI_API_KEY_TEST", raising=False)

    with pytest.raises(RuntimeError, match="de prueba"):
        ai_provider.crear_cliente(test=True)

    assert recibido == []


def test_cliente_de_prueba_usa_solo_variable_de_prueba(monkeypatch):
    recibido = _fake_openai(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "clave-produccion-simulada")
    monkeypatch.setenv("OPENAI_API_KEY_TEST", "clave-prueba-simulada")

    ai_provider.crear_cliente(test=True)

    assert recibido == ["clave-prueba-simulada"]
