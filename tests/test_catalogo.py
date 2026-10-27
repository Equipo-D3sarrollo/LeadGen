import json, types
from leadgen import catalogo, config

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
    cli = types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **k: types.SimpleNamespace(
        content=[types.SimpleNamespace(text="Aquí va:\n"+json.dumps(resp))])))
    cat = catalogo.leer_catalogo_desde_links(["https://ej.co/"], descargar=lambda u: SITIO.get(u,""), cliente_ia=cli)
    p = cat["productos"][0]
    assert cat["metodo"]=="ia" and p["vector_ideal"]["madurez_digital"]==100 and p["afinidad"]["miedo"]==0.9
    assert p["vector_ideal"]["dolor_urgencia"]==60  # relleno con arquetipo de la familia
    malo = types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **k: (_ for _ in ()).throw(RuntimeError("x"))))
    cat2 = catalogo.leer_catalogo_desde_links(["https://ej.co/"], descargar=lambda u: SITIO.get(u,""), cliente_ia=malo)
    assert cat2["metodo"]=="reglas" and cat2["productos"]

def test_links_caidos_no_rompen():
    cat = catalogo.leer_catalogo_desde_links(["https://no-existe.co/"], usar_ia=False, descargar=lambda u: "")
    assert cat["productos"] == []
    assert catalogo.cargar_catalogo("/no/existe.json")["metodo"] == "arquetipo"
