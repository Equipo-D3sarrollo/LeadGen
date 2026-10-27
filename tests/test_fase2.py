import sqlite3
from unittest.mock import Mock, patch

from leadgen import normalize, validate, senales, google_maps, database
from leadgen.scraper import EmpresaCruda, extraer_empresa_desde_html

def test_telefonos():
    f = normalize.normalizar_telefono_detalle
    assert f("+57 300-123-45-67") == ("3001234567","celular")
    assert f("(2) 551 0506") == ("6025510506","fijo")
    assert f("602 5510506") == ("6025510506","fijo")
    assert f("01 8000 428800")[1] == "linea_gratuita"
    assert f("+1 818-753-4867") == ("+18187534867","extranjero")
    assert f("5076507550745073507250715070")[1] == "invalido"
    assert f("20092026")[1] == "fijo"  # 8 dígitos empieza por 2: formato válido (no distinguible)
    assert f("3001234567.0") == ("3001234567","celular")
    assert f("31117")[1] == "invalido"

def test_scraper_no_concatena():
    html = "<p>Resultados: 5076 5075 5074 5073 5072 5071 5070</p><p>Tel: 300 123 4567</p>"
    e = extraer_empresa_desde_html(html, EmpresaCruda(url_perfil="x"))
    assert len(normalize.normalizar_telefono(e.telefono)) in (0,7,10)
    e2 = extraer_empresa_desde_html("<a href='tel:+573001234567'>llámanos</a> 5076 5075 5074 5073", EmpresaCruda())
    assert normalize.normalizar_telefono(e2.telefono) == "3001234567"

def test_ubicacion():
    d = normalize.derivar_ubicacion
    assert d("Cra 20 #25 - 38, Manizales, Caldas") == {"ciudad":"Manizales","departamento":"Caldas","pais":"Colombia"}
    assert d("Av. 4 Nte. #8N-67 Oficina 101, Granada, Cali, Valle del Cauca")["ciudad"] == "Cali"
    r = d("4368 W Shaw Ave, Fresno, CA 93722, Estados Unidos")
    assert r["pais"] == "Estados Unidos" and r["ciudad"] == "Fresno"
    assert d("Calle 5 # 3-2, Pereira")["departamento"] == "Risaralda"
    assert d("Cl. 9 #62A-06, Bogotá")["departamento"] == "Bogotá"

def test_normalizar_y_validar_marca_invalidos():
    e = EmpresaCruda(nombre="Lotería X", url_perfil="https://yelu.com.co/lottery/results/x", telefono="50765075507450735072")
    e = normalize.normalizar_empresa(e); v = validate.validar_empresa(e)
    assert e.telefono == "" and "telefono" in e.datos_invalidos and v.datos_invalidos == 1
    assert not v.es_empresa and not v.tiene_telefono
    e = normalize.normalizar_empresa(EmpresaCruda(nombre="Clinic", url_perfil="https://www.google.com/maps/place/x", direccion="1 Main St, Fresno, CA 93722, Estados Unidos"))
    assert validate.validar_empresa(e).fuera_de_mercado

def test_rating_maps():
    p = google_maps.parsear_rating_resenas
    assert p("4,6 estrellas 1.234 reseñas") == (4.6, 1234)
    assert p("4.8 stars 87 Reviews") == (4.8, 87)
    assert p("Dentix 4,5(2.310) Clínica dental") == (4.5, 2310)
    assert p("sin datos") == (None, None)

def test_contexto_y_rdap():
    c = senales.contexto_negocio("Somos más de 120 colaboradores. Trabaja con nosotros. Gerente General: Ana", ["HubSpot"], True)
    assert c["tamano_estimado"]=="mediana" and c["fase_crecimiento"]=="expansion" and c["senal_presupuesto"]=="alta"
    assert "gerente general" in c["cargos_decision"] and c["cobertura_contexto"]==1.0
    assert senales.contexto_negocio()["cobertura_contexto"]==0.0
    f = senales.fecha_registro_desde_rdap({"events":[{"eventAction":"registration","eventDate":"2010-03-01T00:00:00Z"}]})
    assert f.year == 2010
    assert senales.llave_cadena("Dentix - Sede Norte") == senales.llave_cadena("Dentix")


def test_antiguedad_dominio_reutiliza_resultado_positivo_y_normaliza_www():
    respuesta = Mock(ok=True)
    respuesta.json.return_value = {
        "events": [{"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"}]
    }
    senales._limpiar_cache_rdap()
    try:
        with patch("requests.get", return_value=respuesta) as get:
            primero = senales.antiguedad_dominio("https://WWW.ejemplo.test")
            segundo = senales.antiguedad_dominio("ejemplo.test")

        assert isinstance(primero, float)
        assert segundo == primero
        assert get.call_count == 1
        assert get.call_args.args == ("https://rdap.org/domain/ejemplo.test",)
    finally:
        senales._limpiar_cache_rdap()


def test_antiguedad_dominio_reutiliza_resultado_none():
    respuesta = Mock(ok=False)
    senales._limpiar_cache_rdap()
    try:
        with patch("requests.get", return_value=respuesta) as get:
            primero = senales.antiguedad_dominio("ejemplo.test")
            segundo = senales.antiguedad_dominio("www.ejemplo.test")

        assert primero is None
        assert segundo is None
        assert get.call_count == 1
    finally:
        senales._limpiar_cache_rdap()


def test_antiguedad_dominio_a_isla_dominios_diferentes():
    respuesta_a = Mock(ok=True)
    respuesta_a.json.return_value = {
        "events": [{"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"}]
    }
    respuesta_b = Mock(ok=True)
    respuesta_b.json.return_value = {
        "events": [{"eventAction": "registration", "eventDate": "2010-01-01T00:00:00Z"}]
    }
    senales._limpiar_cache_rdap()
    try:
        with patch("requests.get", side_effect=[respuesta_a, respuesta_b]) as get:
            resultado_a = senales.antiguedad_dominio("a.ejemplo.test")
            resultado_b = senales.antiguedad_dominio("b.ejemplo.test")
            resultado_a_repetido = senales.antiguedad_dominio("A.EJEMPLO.TEST")

        assert resultado_a != resultado_b
        assert resultado_a_repetido == resultado_a
        assert get.call_count == 2
    finally:
        senales._limpiar_cache_rdap()


def test_antiguedad_dominio_eviction_lru_limitada_a_256_entradas():
    respuesta = Mock(ok=False)
    senales._limpiar_cache_rdap()
    try:
        with patch("requests.get", return_value=respuesta) as get:
            dominios = [f"dominio-{i}.test" for i in range(256)]
            for dominio in dominios:
                senales.antiguedad_dominio(dominio)

            senales.antiguedad_dominio(dominios[0])
            senales.antiguedad_dominio("dominio-adicional.test")

        assert len(senales._CACHE_RDAP) == 256
        assert dominios[0] in senales._CACHE_RDAP
        assert dominios[1] not in senales._CACHE_RDAP
        assert "dominio-adicional.test" in senales._CACHE_RDAP
        assert get.call_count == 257
    finally:
        senales._limpiar_cache_rdap()


def test_db_migra_y_contactos(tmp_path):
    ruta = str(tmp_path/"v.db")
    c = sqlite3.connect(ruta); c.execute(database.ESQUEMA); c.execute("INSERT INTO empresas(url_perfil,nombre) VALUES('u','Vieja')"); c.commit(); c.close()
    with database.conectar(ruta) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(empresas)")}
        assert "score_final" in cols and "rating" in cols
        database.registrar_contacto(conn, "u", "diseno_web", "interesado", canal="whatsapp")
        assert database.obtener_contactos(conn)[0]["nombre_empresa"] == "Vieja"
