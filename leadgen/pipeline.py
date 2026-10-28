"""
pipeline.py
-----------
Orquesta todo: Módulo 1 (entrada) -> ... -> Módulo 11 (dashboard).

discovery -> scraper -> normalize -> validate -> web_analysis ->
ai_analysis -> scoring (Capa 1) -> senales (Capa 5) -> perfil (Capa 2)
-> perfil_psicologico (Capa 3, núcleo) -> diagnostico (Capa 4) -> database

Si la URL de entrada es una búsqueda de Google Maps, el pipeline la
detecta automáticamente y usa el extractor especializado (google_maps.py)
en vez de discovery.py + scraper.py.

Cambios Fases 2-5 (oct. 2026): ver PLAN.md. Cada capa nueva está
envuelta para que, si falla, la empresa se guarde igual con el Lead
Score (criterio de éxito: el pipeline nunca se rompe).
"""

from __future__ import annotations

from . import ai_analysis, config, database, google_maps, normalize, scoring, senales, validate
from . import catalogo as mod_catalogo
from .scraper import EmpresaCruda, extraer_empresa


def _completar_contacto_desde_web(limpia: EmpresaCruda, analisis) -> None:
    """Rescata WhatsApp/Instagram/Facebook/correo/teléfono del sitio propio si la fuente no los trajo."""
    if analisis is None or not analisis.contacto_escaneado:
        return
    for campo in ("whatsapp", "instagram", "facebook", "correo"):
        if not getattr(limpia, campo) and getattr(analisis, campo):
            setattr(limpia, campo, getattr(analisis, campo))
    if not limpia.telefono and analisis.telefono:
        limpia.telefono = analisis.telefono
    normalize.normalizar_empresa(limpia)  # re-normaliza lo rescatado (idempotente)
    # Un teléfono/WhatsApp válido rescatado de la web reemplaza al corrupto de la fuente:
    # se quita solo la marca de ese campo (las demás se conservan). La re-normalización
    # puede repetir una marca si lo rescatado también es inválido; se cuenta una vez.
    marcas = list(dict.fromkeys(limpia.datos_invalidos))
    limpia.datos_invalidos = [m for m in marcas if not (m in ("telefono", "whatsapp") and getattr(limpia, m))]


def ejecutar_pipeline(
    url_directorio: str,
    selectores_directorio: dict | None = None,
    selectores_ficha: dict | None = None,
    usar_ia: bool = False,
    usar_navegador: bool = False,
    max_resultados_maps: int = 40,
    abrir_fichas_maps: bool = True,
    db_path: str = config.DB_PATH,
    verbose: bool = True,
    catalogo_path: str = config.CATALOGO_PATH,
    consultar_dominio: bool = True,
) -> dict:
    """
    Corre el pipeline completo sobre un directorio (o una búsqueda de
    Google Maps) y guarda todo en la base de datos. Devuelve un resumen
    con conteos.

    selectores_directorio / selectores_ficha: ver discovery.py / scraper.py.
    usar_ia: activa los textos con IA (Módulo 7 y diagnóstico, Fase 5).
    usar_navegador: Playwright para sitios con JavaScript.
    max_resultados_maps / abrir_fichas_maps: solo para URLs de Google Maps.
    catalogo_path: catálogo de productos (Fase 1). Si no existe se usan
        los arquetipos por defecto.
    consultar_dominio: consulta RDAP para la antigüedad del dominio.
    """
    from . import diagnostico, perfil, perfil_psicologico

    catalogo = mod_catalogo.cargar_catalogo(catalogo_path)
    es_maps = google_maps.es_url_google_maps(url_directorio)
    selectores_directorio = dict(selectores_directorio or {})
    selectores_directorio["usar_navegador"] = usar_navegador

    crudas: list[EmpresaCruda] = []
    metadatos: list[tuple[str, str, str]] = []  # (nombre, categoria, url_perfil) - solo modo normal

    if es_maps:
        if verbose:
            print(f"[pipeline] URL de Google Maps detectada. Extrayendo negocios de {url_directorio} ...")
        crudas = google_maps.extraer_negocios_google_maps(
            url_directorio, max_resultados=max_resultados_maps, abrir_cada_ficha=abrir_fichas_maps
        )
        if verbose:
            print(f"[pipeline] Se encontraron {len(crudas)} negocios en Google Maps.")
    else:
        from . import discovery
        if verbose:
            print(f"[pipeline] Módulo 2 - Descubriendo empresas en {url_directorio} ...")
        empresas_descubiertas = discovery.descubrir_empresas(url_directorio, **selectores_directorio)
        metadatos = [(e.nombre, e.categoria, e.url_perfil) for e in empresas_descubiertas]
        if verbose:
            print(f"[pipeline] Se encontraron {len(metadatos)} empresas.")

    total_items = len(crudas) if es_maps else len(metadatos)
    resumen = {"total": 0, "creados": 0, "actualizados": 0, "errores": 0, "no_empresa": 0, "fuera_de_mercado": 0}
    nombres = [c.nombre for c in crudas] if es_maps else [m[0] for m in metadatos]
    sedes = senales.contar_sedes(nombres)

    with database.conectar(db_path) as conn:
        for i in range(total_items):
            nombre_log = ""
            url_actual = ""
            try:
                if es_maps:
                    cruda = crudas[i]
                    nombre_log = cruda.nombre
                    url_actual = cruda.url_perfil
                else:
                    nombre, categoria, url_perfil = metadatos[i]
                    nombre_log = nombre
                    url_actual = url_perfil
                    # Módulo 3 - Recolección
                    cruda = extraer_empresa(
                        url_perfil, nombre, categoria, selectores_ficha, usar_navegador=usar_navegador
                    )

                if verbose:
                    print(f"[pipeline] ({i + 1}/{total_items}) Procesando: {nombre_log}")

                # Módulo 4 - Normalización (+ ciudad/depto/país y validación de teléfono)
                limpia = normalize.normalizar_empresa(cruda)

                # Módulo 5 - Validación (preliminar, para saber si vale la pena analizar la web)
                val = validate.validar_empresa(limpia)

                # Módulo 6 - Análisis Web (solo si tiene sitio web y es una empresa real)
                analisis = None
                if limpia.sitio_web and val.es_empresa:
                    from . import web_analysis
                    analisis = web_analysis.analizar_sitio(limpia.sitio_web)
                    _completar_contacto_desde_web(limpia, analisis)
                    val = validate.validar_empresa(limpia)

                # Módulo 7 - Observación técnica por reglas (sin llamada a IA)
                observacion = ""
                if usar_ia and analisis is not None:
                    observacion = ai_analysis._observacion_por_reglas(analisis)

                # Módulo 8 - Lead Score (Capa 1, lógica intacta)
                lead_score = scoring.calcular_lead_score(val, analisis, int(limpia.numero_resenas or 0))
                clasificacion = scoring.clasificar_lead(lead_score)

                registro = {
                    "url_perfil": limpia.url_perfil,
                    "nombre": limpia.nombre,
                    "direccion": limpia.direccion,
                    "ciudad": limpia.ciudad,
                    "departamento": limpia.departamento,
                    "telefono": limpia.telefono,
                    "whatsapp": limpia.whatsapp,
                    "correo": limpia.correo,
                    "facebook": limpia.facebook,
                    "instagram": limpia.instagram,
                    "sitio_web": limpia.sitio_web,
                    "horario": limpia.horario,
                    "descripcion": limpia.descripcion,
                    "categoria": limpia.categoria,
                    "tiene_web": int(val.tiene_web),
                    "tiene_facebook": int(val.tiene_facebook),
                    "tiene_instagram": int(val.tiene_instagram),
                    "tiene_whatsapp": int(val.tiene_whatsapp),
                    "tiene_telefono": int(val.tiene_telefono),
                    "tiene_correo": int(val.tiene_correo),
                    "web_puntaje": analisis.puntaje if analisis else None,
                    "web_https": int(analisis.https) if analisis else None,
                    "web_responsive": int(analisis.responsive) if analisis else None,
                    "web_cms": analisis.cms if analisis else "",
                    "observacion_ia": observacion,
                    "lead_score": lead_score,
                    "lead_clasificacion": clasificacion,
                    # --- Fase 2 ---
                    "pais": limpia.pais,
                    "es_empresa": int(val.es_empresa),
                    "fuera_de_mercado": int(val.fuera_de_mercado),
                    "datos_invalidos": ",".join(limpia.datos_invalidos),
                    "fuente": "google_maps" if es_maps else "directorio",
                    "rating": limpia.rating,
                    "numero_resenas": limpia.numero_resenas,
                    "web_accesible": int(analisis.accesible) if analisis else None,
                    "web_formulario": int(analisis.tiene_formulario) if analisis and analisis.accesible else None,
                    "web_analytics": int(analisis.google_analytics or analisis.google_tag_manager) if analisis and analisis.accesible else None,
                    "web_tiempo_carga": analisis.tiempo_carga_seg if analisis and analisis.accesible else None,
                    "web_titulo": analisis.titulo if analisis else "",
                    "web_meta_descripcion": int(bool(analisis.meta_descripcion)) if analisis and analisis.accesible else None,
                    "web_pixel_facebook": int(analisis.pixel_facebook) if analisis and analisis.accesible else None,
                    "web_herramientas_pago": ",".join(analisis.herramientas_pago) if analisis else "",
                    "contacto_web_escaneado": int(bool(analisis and analisis.contacto_escaneado)),
                    "sedes_detectadas": sedes.get(senales.llave_cadena(limpia.nombre), 1),
                }
                if limpia.sitio_web and consultar_dominio and val.es_empresa:
                    registro["dominio_antiguedad_anios"] = senales.antiguedad_dominio(limpia.sitio_web)

                # Capa 5 - Contexto de negocio
                registro.update(senales.contexto_negocio(
                    texto_web=analisis.texto if analisis else "",
                    herramientas_pago=analisis.herramientas_pago if analisis else None,
                    pixel_facebook=analisis.pixel_facebook if analisis and analisis.accesible else None,
                    sedes=registro["sedes_detectadas"],
                    numero_resenas=limpia.numero_resenas,
                ))

                # Capas 2, 3 y 4 - perfil, núcleo psicológico y diagnóstico (nunca rompen el guardado)
                try:
                    per = perfil.calcular_perfil(registro)
                    res = perfil_psicologico.analizar(per, catalogo, lead_score, val.es_empresa, val.fuera_de_mercado)
                    registro.update(perfil_psicologico.a_columnas(per, res))
                    registro["diagnostico"], registro["diagnostico_origen"] = diagnostico.diagnosticar_con_origen(
                        per, res, registro, usar_ia=usar_ia)
                except Exception as ex:
                    print(f"[pipeline] Análisis psicológico no disponible para {nombre_log}: {ex}")

                resumen["no_empresa"] += int(not val.es_empresa)
                resumen["fuera_de_mercado"] += int(val.fuera_de_mercado)

                # Módulo 9 - Guardar sin duplicar
                accion = database.guardar_o_actualizar(conn, registro)
                resumen["creados" if accion == "creado" else "actualizados"] += 1
                resumen["total"] += 1

            except Exception as ex:
                resumen["errores"] += 1
                print(f"[pipeline] Error procesando {url_actual or nombre_log}: {ex}")

    if verbose:
        print(f"[pipeline] Terminado. Resumen: {resumen}")

    return resumen
