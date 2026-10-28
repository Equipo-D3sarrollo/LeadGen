import json, types
from leadgen import ai_usage, catalogo, config

SITIO = {
 "https://ej.co/": """<html><body><nav><a href='/servicios'>Servicios</a><a href='/blog'>Blog</a></nav>
   <h1>Ejemplo SAS</h1><p>Somos integradores.</p></body></html>""",
 "https://ej.co/servicios": """<html><body>
   <script type='application/ld+json'>{"@context":"https://schema.org","@type":"Service","name":"Internet dedicado por fibra óptica","description":"Canal dedicado simétrico para empresas"}</script>
   <div class='service-card'><h3>Diseño de páginas web</h3><p>Creamos tu sitio web autoadministrable y landing pages.</p></div>
   <h2>Cableado estructurado</h2><p>Certificación de puntos de red, racks y switches.</p>
   <h2>Chatbot para WhatsApp</h2><p>Automatización de atención con inteligencia artificial.</p>
   <h2>Contacto</h2><p>Escríbenos.</p>
   <a href='/servicios/camaras'>Cámaras</a></body></html>""",
 "https://ej.co/servicios/camaras": "<html><body><h1>Cámaras de seguridad CCTV</h1><p>Videovigilancia y control de acceso.</p></body></html>",
}

def fake(url): return SITIO.get(url.rstrip('/') if url.rstrip('/')+'/' not in SITIO else url, SITIO.get(url,""))

def test_reglas_detecta_productos(tmp_path):
    cat = catalogo.leer_catalogo_desde_links(["https://ej.co/"], usar_ia=False, descargar=lambda u: SITIO.get(u, ""))
    fams = {p["familia"] for p in cat["productos"]}
    assert {"conectividad","diseno_web","redes_cableado","chatbot_automatizacion","seguridad_electronica"} <= fams
    assert not any(p["nombre"]=="Contacto" for p in cat["productos"])
    for p in cat["productos"]:
        assert set(p["vector_ideal"]) == set(config.DIMENSIONES)
        assert set(p["afinidad"]) == set(config.EMOCIONES)
        assert p["estado"] == "borrador" and p["consultas_busqueda"]
    assert cat["opciones_adicionales"]  # investigación amplia: complementarios no cubiertos
    ruta = tmp_path/"c.json"
    catalogo.guardar_catalogo(cat, str(ruta))
    assert catalogo.cargar_catalogo(str(ruta))["productos"]

def test_fusion_protege_aprobados(tmp_path):
    ruta = tmp_path/"c.json"
    base = catalogo.catalogo_por_defecto()
    base["productos"][0]["estado"] = "aprobado"; base["productos"][0]["vector_ideal"]["dinamismo"] = 99
    catalogo.guardar_catalogo(base, str(ruta), fusionar=False)
    catalogo.guardar_catalogo(catalogo.catalogo_por_defecto(), str(ruta))
    p0 = [p for p in json.loads(ruta.read_text())["productos"] if p["id"]==base["productos"][0]["id"]][0]
    assert p0["vector_ideal"]["dinamismo"] == 99

def test_ia_con_cliente_falso_y_fallback():
    resp = {"productos":[{"nombre":"Plan Fibra Pyme","familia":"conectividad","vector_ideal":{"madurez_digital":150},
             "afinidad":{"miedo":0.9},"consultas_busqueda":["hoteles en Cali"]}],
            "opciones_adicionales":[{"oportunidad":"WiFi para hoteles","por_que":"x"}]}
    cli = types.SimpleNamespace(responses=types.SimpleNamespace(create=lambda **k: types.SimpleNamespace(
        output_text="Aquí va:\n"+json.dumps(resp))))
    cat = catalogo.leer_catalogo_desde_links(["https://ej.co/"], descargar=lambda u: SITIO.get(u,""), cliente_ia=cli)
    p = cat["productos"][0]
    assert cat["metodo"]=="ia" and p["vector_ideal"]["madurez_digital"]==100 and p["afinidad"]["miedo"]==0.9
    assert p["vector_ideal"]["dolor_urgencia"]==60  # relleno con arquetipo de la familia
    malo = types.SimpleNamespace(responses=types.SimpleNamespace(create=lambda **k: (_ for _ in ()).throw(RuntimeError("x"))))
    cat2 = catalogo.leer_catalogo_desde_links(["https://ej.co/"], descargar=lambda u: SITIO.get(u,""), cliente_ia=malo)
    assert cat2["metodo"]=="reglas" and cat2["productos"]

def test_construir_con_ia_valida_parametros_y_registra_uso(tmp_path, monkeypatch):
    llamadas = []
    ruta_uso = tmp_path / "uso.jsonl"
    monkeypatch.setattr(ai_usage, "USAGE_LOG_PATH", ruta_uso)
    datos = {"productos":[{"nombre":"Plan Fibra Pyme","familia":"conectividad"}], "opciones_adicionales":[]}
    respuesta = types.SimpleNamespace(
        output_text=json.dumps(datos),
        usage=types.SimpleNamespace(input_tokens=21, output_tokens=7),
    )

    class Cliente:
        class Responses:
            def create(self, **kwargs):
                llamadas.append(kwargs)
                return respuesta
        responses = Responses()

    productos, opciones = catalogo.construir_con_ia(
        {"https://ej.co/": "<html><h1>Internet empresarial</h1></html>"}, Cliente()
    )

    assert len(llamadas) == 1
    solicitud = llamadas[0]
    assert solicitud["model"] == config.CATALOGO_MODELO_IA
    assert solicitud["max_output_tokens"] == config.CATALOGO_MAX_OUTPUT_TOKENS
    assert isinstance(solicitud["input"], str)
    formato = solicitud["text"]["format"]
    assert formato["type"] == "json_schema"
    assert formato["strict"] is True
    assert formato["schema"]["additionalProperties"] is False
    producto_schema = formato["schema"]["properties"]["productos"]["items"]
    assert set(producto_schema["required"]) == {
        "nombre", "descripcion", "familia", "dolor_que_resuelve",
        "sectores_objetivo", "tamano_empresa_objetivo", "vector_ideal",
        "afinidad", "consultas_busqueda", "productos_complementarios",
        "justificacion",
    }
    assert set(producto_schema["properties"]["vector_ideal"]["properties"]) == set(config.DIMENSIONES)
    assert set(producto_schema["properties"]["afinidad"]["properties"]) == set(config.EMOCIONES)
    assert productos[0].familia == "conectividad" and opciones == []

    registro = json.loads(ruta_uso.read_text(encoding="utf-8"))
    assert registro["flujo"] == "catalogo"
    assert registro["input_tokens"] == 21 and registro["output_tokens"] == 7
    assert "prompt" not in registro and "respuesta" not in registro and "content" not in registro

def test_catalogo_fallback_con_bad_request_registra_error(tmp_path, monkeypatch):
    ruta_uso = tmp_path / "uso.jsonl"
    monkeypatch.setattr(ai_usage, "USAGE_LOG_PATH", ruta_uso)

    class BadRequestErrorSimulado(Exception):
        pass

    class Cliente:
        class Responses:
            def create(self, **kwargs):
                raise BadRequestErrorSimulado("solicitud inválida simulada")
        responses = Responses()

    cat = catalogo.leer_catalogo_desde_links(
        ["https://ej.co/"], descargar=lambda u: SITIO.get(u, ""), cliente_ia=Cliente()
    )

    assert cat["metodo"] == "reglas" and cat["productos"]
    registro = json.loads(ruta_uso.read_text(encoding="utf-8"))
    assert registro["flujo"] == "catalogo"
    assert registro["estado"] == "error"
    assert registro["tipo_error"] == "BadRequestErrorSimulado"

def test_links_caidos_no_rompen():
    cat = catalogo.leer_catalogo_desde_links(["https://no-existe.co/"], usar_ia=False, descargar=lambda u: "")
    assert cat["productos"] == []
    assert catalogo.cargar_catalogo("/no/existe.json")["metodo"] == "arquetipo"
