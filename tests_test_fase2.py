import sqlite3
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

def test_db_migra_y_contactos(tmp_path):
    ruta = str(tmp_path/"v.db")
    c = sqlite3.connect(ruta); c.execute(database.ESQUEMA); c.execute("INSERT INTO empresas(url_perfil,nombre) VALUES('u','Vieja')"); c.commit(); c.close()
    with database.conectar(ruta) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(empresas)")}
        assert "score_final" in cols and "rating" in cols
        database.registrar_contacto(conn, "u", "diseno_web", "interesado", canal="whatsapp")
        assert database.obtener_contactos(conn)[0]["nombre_empresa"] == "Vieja"
