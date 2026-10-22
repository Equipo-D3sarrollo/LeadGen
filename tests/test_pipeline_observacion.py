from types import SimpleNamespace

from leadgen import ai_provider, config, database, google_maps, pipeline, web_analysis
from leadgen.scraper import EmpresaCruda


def test_pipeline_genera_observacion_por_reglas_sin_llamar_claude(tmp_path, monkeypatch):
    cruda = EmpresaCruda(
        nombre="Empresa Sintetica",
        url_perfil="https://www.google.com/maps/place/empresa-sintetica",
        sitio_web="https://empresa-sintetica.example",
        direccion="Cra 1 #2-3, Pereira, Risaralda",
        telefono="3001234567",
    )
    monkeypatch.setattr(google_maps, "extraer_negocios_google_maps", lambda *args, **kwargs: [cruda])

    analisis = web_analysis.AnalisisWeb(
        url=cruda.sitio_web,
        accesible=True,
        https=False,
        responsive=False,
        tiempo_carga_seg=5.0,
        tiene_formulario=False,
        google_analytics=False,
        google_tag_manager=False,
    )
    monkeypatch.setattr(web_analysis, "analizar_sitio", lambda url: analisis)
    monkeypatch.setenv("OPENAI_API_KEY", "clave-simulada")

    llamadas = []

    class ClienteSimulado:
        responses = None

        def create(self, **kwargs):
            llamadas.append(kwargs)
            return SimpleNamespace(output_text="Diagnostico IA simulado.")

    cliente = ClienteSimulado()
    cliente.responses = cliente
    monkeypatch.setattr(ai_provider, "crear_cliente", lambda: cliente)

    db_path = str(tmp_path / "pipeline.db")
    resultado = pipeline.ejecutar_pipeline(
        "https://www.google.com/maps/search/empresas",
        usar_ia=True,
        db_path=db_path,
        catalogo_path=str(tmp_path / "catalogo.json"),
        consultar_dominio=False,
        verbose=False,
    )

    assert resultado["errores"] == 0
    with database.conectar(db_path) as conn:
        fila = dict(database.obtener_todas(conn)[0])

    assert fila["observacion_ia"] == (
        "Este negocio podría mejorar su web: no usa HTTPS, no está adaptado a móviles, "
        "carga lenta, no tiene formulario de contacto, no mide tráfico con analítica."
    )
    assert fila["diagnostico"] == "Diagnostico IA simulado."
    assert len(llamadas) == 1
    assert llamadas[0]["max_output_tokens"] == config.DIAGNOSTICO_MAX_OUTPUT_TOKENS
