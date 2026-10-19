import math, json, subprocess, sys
from leadgen import perfil, perfil_psicologico as pp, catalogo, config, diagnostico, pipeline, google_maps, web_analysis, database
from leadgen.scraper import EmpresaCruda

CAT = catalogo.catalogo_por_defecto()
SIN_WEB = {"url_perfil":"https://www.google.com/maps/place/a","nombre":"A","tiene_web":0,"tiene_telefono":1}
WEB_OK = {"url_perfil":"https://www.google.com/maps/place/b","nombre":"B","sitio_web":"https://b.co","tiene_web":1,"tiene_telefono":1,
          "web_puntaje":90,"web_accesible":1,"web_https":1,"web_responsive":1,"web_formulario":1,"web_analytics":1,
          "web_tiempo_carga":1.0,"contacto_web_escaneado":1,"tiene_whatsapp":1,"tiene_correo":1,"tiene_facebook":1,
          "rating":4.7,"numero_resenas":350,"web_titulo":"B","web_meta_descripcion":1,"fase_crecimiento":"expansion"}

def test_perfil_nunca_rellena_con_cero():
    p = perfil.calcular_perfil(SIN_WEB)
    assert p.dimensiones["dolor_urgencia"] == 100 and p.dimensiones["madurez_digital"] < 20
    assert p.dimensiones["confianza_reputacion"] is None and p.cobertura["confianza_reputacion"] == 0
    assert p.cobertura["apertura_comercial"] < 1   # WhatsApp/correo de Maps = faltante, no "No"
    q = perfil.calcular_perfil(WEB_OK)
    assert q.dimensiones["madurez_digital"] > 85 and q.dimensiones["dolor_urgencia"] < 20 and q.confianza == "alta"

def test_softmax_y_formulas():
    p = pp.softmax([1,2,3], 0.5); assert abs(sum(p)-1) < 1e-9 and p[2] > p[1]
    # empresa neutra -> perfil uniforme y S% = 50 en todo producto (D-04, D-06)
    neutro = perfil.Perfil(dimensiones={d:None for d in config.DIMENSIONES}, cobertura={d:0 for d in config.DIMENSIONES})
    r = pp.analizar(neutro, CAT, 0)
    assert all(abs(v-0.125) < 1e-3 for v in r.p.values())
    assert all(abs(x["compatibilidad_pct"]-50) < 0.2 for x in r.productos.values())
    # ejemplo numérico del documento técnico: punto (x,y,z,w)
    pe = dict(zip(config.EMOCIONES,[.10,.45,.08,.03,.03,.03,.03,.25]))
    assert round(pe["alegria"]-pe["tristeza"],2)==0.07 and round(pe["anticipacion"]-pe["sorpresa"],2)==0.22
    S, pct = pp.puntaje_venta([0,0,0,0,0,0,0,1], {e:(1.0 if e=="anticipacion" else 0.0) for e in config.EMOCIONES})
    assert S == 1.0 and pct == 100.0

def test_sin_web_recomienda_diseno_y_excluidos():
    r = pp.analizar(perfil.calcular_perfil(SIN_WEB), CAT, 50)
    assert r.mejor_producto == "diseno_web" and r.score_final is not None and r.pasa_filtro
    r2 = pp.analizar(perfil.calcular_perfil(SIN_WEB), CAT, 50, es_empresa=False)
    assert r2.score_final is None and r2.excluida
    inval = dict(SIN_WEB, datos_invalidos="telefono")
    r3 = pp.analizar(perfil.calcular_perfil(inval), CAT, 50)
    assert r3.score_final < r.score_final   # scoring negativo por dato inválido

def test_diagnostico_legible_sin_emociones():
    per = perfil.calcular_perfil(SIN_WEB); r = pp.analizar(per, CAT, 50)
    txt = diagnostico.diagnosticar(per, r, SIN_WEB)
    assert "No tiene sitio web" in txt and "Ofrecer primero" in txt
    assert not any(e in txt.lower() for e in ["miedo","tristeza","alegría","aversión"])

def test_pipeline_maps_sin_red(tmp_path, monkeypatch):
    crudas = [EmpresaCruda(nombre="Clínica Uno", url_perfil="https://www.google.com/maps/place/1",
                           direccion="Cra 1 #2-3, Pereira, Risaralda", telefono="(6) 3251783", rating=4.5, numero_resenas=40),
              EmpresaCruda(nombre="Clínica Dos", url_perfil="https://www.google.com/maps/place/2", sitio_web="https://dos.co",
                           direccion="1 Main St, Fresno, CA 93722, Estados Unidos", telefono="+1 559-320-1300")]
    monkeypatch.setattr(google_maps, "extraer_negocios_google_maps", lambda *a, **k: crudas)
    def fake_web(url):
        a = web_analysis.AnalisisWeb(url=url, accesible=True, https=True, tiempo_carga_seg=1.2)
        web_analysis.analizar_html(a, "<html><title>Dos</title><a href='https://wa.me/573001234567'>wa</a><form></form>Somos más de 60 colaboradores</html>")
        a.puntaje = web_analysis._calcular_puntaje(a); return a
    monkeypatch.setattr(web_analysis, "analizar_sitio", fake_web)
    db = str(tmp_path/"t.db")
    res = pipeline.ejecutar_pipeline("https://www.google.com/maps/search/clinicas", db_path=db, verbose=False,
                                     catalogo_path=str(tmp_path/"no.json"), consultar_dominio=False)
    assert res["total"] == 2 and res["errores"] == 0 and res["fuera_de_mercado"] == 1
    with database.conectar(db) as conn:
        filas = {f["nombre"]: dict(f) for f in database.obtener_todas(conn)}
    uno, dos = filas["Clínica Uno"], filas["Clínica Dos"]
    assert uno["ciudad"] == "Pereira" and uno["telefono"] == "6063251783" and uno["score_final"] is not None
    assert uno["mejor_producto"] and uno["diagnostico"] and uno["dim_confianza_reputacion"] is not None
    assert dos["whatsapp"] == "3001234567" and dos["contacto_web_escaneado"] == 1 and dos["score_final"] is None
    assert dos["tamano_estimado"] == "mediana"

def test_cli_reprocesar_excel_y_contacto(tmp_path):
    out = tmp_path/"a.xlsx"
    r = subprocess.run([sys.executable, "main.py", "--catalogo", str(tmp_path/"x.json"), "reprocesar", "--excel",
                        "datos/leads_export.xlsx", "--salida", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    import pandas as pd
    df = pd.read_excel(out); assert len(df) == 484 and df.columns[0] == "nombre" and "diagnostico" in df
    db = str(tmp_path/"c.db")
    with database.conectar(db) as conn:
        database.guardar_o_actualizar(conn, {"url_perfil":"u1","nombre":"E"})
    r = subprocess.run([sys.executable, "main.py", "--db", db, "contacto", "u1", "diseno_web", "--resultado", "reunion"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([sys.executable, "main.py", "--db", db, "--catalogo", str(tmp_path/"x.json"), "reprocesar"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
