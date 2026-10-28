import json
import types

from leadgen import ai_analysis, ai_usage, catalogo, config, diagnostico, perfil, perfil_psicologico as pp
from leadgen.web_analysis import AnalisisWeb


def _respuesta(texto, **uso):
    usage = types.SimpleNamespace(**uso) if uso else None
    return types.SimpleNamespace(output_text=texto, usage=usage)


def _leer_registros(ruta):
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]


def test_registra_tokens_y_cache_opcional(tmp_path):
    ruta = tmp_path / "uso.jsonl"
    respuesta = _respuesta(
        "ok",
        input_tokens=12,
        output_tokens=4,
        input_token_details=types.SimpleNamespace(cached_tokens=5),
    )

    ai_usage.registrar_uso("catalogo", config.CATALOGO_MODELO_IA, respuesta, ruta)

    registro = _leer_registros(ruta)[0]
    assert registro["flujo"] == "catalogo"
    assert registro["proveedor"] == "openai"
    assert registro["modelo"] == config.CATALOGO_MODELO_IA
    assert registro["input_tokens"] == 12 and registro["output_tokens"] == 4
    assert registro["cached_input_tokens"] == 5
    assert set(registro) == {
        "fecha_hora", "proveedor", "flujo", "modelo", "input_tokens", "output_tokens",
        "cached_input_tokens", "estado",
    }
    assert registro["estado"] == "success"


def test_sin_usage_registra_exito_sin_tokens(tmp_path):
    ruta = tmp_path / "uso.jsonl"

    ai_usage.registrar_uso("catalogo", "modelo", types.SimpleNamespace(), ruta)

    registro = _leer_registros(ruta)[0]
    assert registro["estado"] == "success"
    assert registro["input_tokens"] is None and registro["output_tokens"] is None


def test_error_de_escritura_no_interrumpe(monkeypatch, capsys, tmp_path):
    respuesta = _respuesta("ok", input_tokens=1, output_tokens=1)
    ruta = tmp_path / "carpeta" / "uso.jsonl"

    def falla(*args, **kwargs):
        raise OSError("no escribir")

    monkeypatch.setattr(type(ruta), "open", falla)
    ai_usage.registrar_uso("catalogo", "modelo", respuesta, ruta)

    assert "No se pudo registrar uso de catalogo: OSError" in capsys.readouterr().out


def test_catalogo_registra_uso_y_conserva_resultado(tmp_path, monkeypatch):
    ruta = tmp_path / "uso.jsonl"
    monkeypatch.setattr(ai_usage, "USAGE_LOG_PATH", ruta)
    datos = {"productos": [{"nombre": "Plan", "familia": "conectividad"}], "opciones_adicionales": []}
    respuesta = _respuesta("prefacio\n" + json.dumps(datos), input_tokens=20, output_tokens=8)
    cliente = types.SimpleNamespace(
        responses=types.SimpleNamespace(create=lambda **kwargs: respuesta)
    )

    productos, opciones = catalogo.construir_con_ia({"https://ej.co/": "<h1>Internet</h1>"}, cliente)

    assert productos[0].familia == "conectividad" and opciones == []
    assert _leer_registros(ruta)[0]["flujo"] == "catalogo"


def test_observacion_web_registra_uso_y_conserva_resultado(monkeypatch, tmp_path):
    ruta = tmp_path / "uso.jsonl"
    monkeypatch.setattr(ai_usage, "USAGE_LOG_PATH", ruta)
    monkeypatch.setenv("OPENAI_API_KEY", "prueba")
    respuesta = _respuesta("Observación.", input_tokens=10, output_tokens=3)
    cliente = types.SimpleNamespace(
        responses=types.SimpleNamespace(create=lambda **kwargs: respuesta)
    )
    monkeypatch.setattr(ai_analysis.ai_provider, "crear_cliente", lambda: cliente)
    analisis = AnalisisWeb(accesible=True, https=True, responsive=True, tiene_formulario=True)

    assert ai_analysis.generar_observacion(analisis) == "Observación."
    assert _leer_registros(ruta)[0]["flujo"] == "observacion_web"


def test_observacion_web_delega_carga_de_env_a_proveedor(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    respuesta = _respuesta("Observación.", input_tokens=10, output_tokens=3)
    cliente = types.SimpleNamespace(
        responses=types.SimpleNamespace(create=lambda **kwargs: respuesta)
    )
    proveedor = []

    def crear_cliente():
        proveedor.append("crear_cliente")
        return cliente

    monkeypatch.setattr(ai_analysis.ai_provider, "crear_cliente", crear_cliente)
    analisis = AnalisisWeb(accesible=True, https=True, responsive=True, tiene_formulario=True)

    assert ai_analysis.generar_observacion(analisis) == "Observación."
    assert proveedor == ["crear_cliente"]


def test_diagnostico_registra_uso_y_conserva_resultado(monkeypatch, tmp_path):
    ruta = tmp_path / "uso.jsonl"
    monkeypatch.setattr(ai_usage, "USAGE_LOG_PATH", ruta)
    per = perfil.calcular_perfil({"nombre": "Empresa", "tiene_whatsapp": 1, "fuente": "directorio"})
    res = pp.analizar(per, catalogo.catalogo_por_defecto(), 50)
    res.pasa_filtro = False
    respuesta = _respuesta("Diagnóstico.", input_tokens=14, output_tokens=5)
    cliente = types.SimpleNamespace(
        responses=types.SimpleNamespace(create=lambda **kwargs: respuesta)
    )

    texto, origen = diagnostico.diagnosticar_con_origen(per, res, {"nombre": "Empresa"},
                                                        usar_ia=True, cliente=cliente)

    assert (texto, origen) == ("Diagnóstico.", "ia")
    assert _leer_registros(ruta)[0]["flujo"] == "diagnostico"


def test_diagnostico_no_duplica_lectura_por_reglas_en_prompt(monkeypatch):
    per = perfil.calcular_perfil({"nombre": "Empresa", "tiene_whatsapp": 1, "fuente": "directorio"})
    res = pp.analizar(per, catalogo.catalogo_por_defecto(), 50)
    res.pasa_filtro = False
    llamadas = []
    respuesta = _respuesta("Diagnóstico.", input_tokens=14, output_tokens=5)
    cliente = types.SimpleNamespace(
        responses=types.SimpleNamespace(
            create=lambda **kwargs: (llamadas.append(kwargs), respuesta)[1]
        )
    )

    diagnostico.diagnosticar_con_origen(
        per, res, {"nombre": "Empresa"}, usar_ia=True, cliente=cliente
    )

    assert len(llamadas) == 1
    assert "lectura_por_reglas" not in llamadas[0]["input"]
