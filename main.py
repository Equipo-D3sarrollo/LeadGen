"""
main.py
-------
Punto de entrada. Ejemplos de uso al final de este archivo y en el README.md.

Uso básico:
    python main.py procesar "https://directorio-de-empresas.com"

Fase 1 - Catálogo de productos desde links (uno o varios):
    python main.py catalogo https://telcobras.com/servicios https://otro-link.com/catalogo.pdf --ia
    python main.py catalogo --mostrar

Reprocesar leads ya guardados (Fases 2-5, sin volver a hacer scraping):
    python main.py reprocesar                                   # sobre la base de datos
    python main.py reprocesar --excel leads_export.xlsx --salida leads_analizados.xlsx

Registrar qué se le ofreció a una empresa y qué pasó (insumo de la calibración):
    python main.py contacto "<url_perfil>" diseno_web --resultado interesado --canal whatsapp --notas "..."

Exportar lo que ya está en la base de datos:
    python main.py exportar --formato excel
    python main.py exportar --formato csv
    python main.py exportar --formato json

Generar el dashboard HTML:
    python main.py dashboard
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path

from leadgen import config, database, export
from leadgen.pipeline import ejecutar_pipeline


def cmd_procesar(args: argparse.Namespace) -> None:
    selectores_directorio = {}
    selectores_ficha = {}

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        selectores_directorio = cfg.get("selectores_directorio", {})
        selectores_ficha = cfg.get("selectores_ficha", {})

    ejecutar_pipeline(
        url_directorio=args.url,
        selectores_directorio=selectores_directorio,
        selectores_ficha=selectores_ficha,
        usar_ia=args.ia,
        usar_navegador=args.navegador,
        max_resultados_maps=args.max_resultados,
        abrir_fichas_maps=not args.maps_rapido,
        db_path=args.db,
        catalogo_path=args.catalogo,
    )


def cmd_catalogo(args: argparse.Namespace) -> None:
    from leadgen import catalogo

    if args.mostrar or not args.urls:
        print(catalogo.resumen_texto(catalogo.cargar_catalogo(args.catalogo)))
        return
    nuevo = catalogo.leer_catalogo_desde_links(args.urls, usar_ia=args.ia, usar_navegador=args.navegador,
                                               max_paginas=args.max_paginas)
    ruta = catalogo.guardar_catalogo(nuevo, args.catalogo, fusionar=not args.reemplazar)
    print(catalogo.resumen_texto(catalogo.cargar_catalogo(ruta)))
    print(f"\nCatálogo guardado en: {Path(ruta).resolve()}")
    print("Revisa los vectores y cambia 'estado' a 'aprobado' en los productos validados por Telcobras.")


def cmd_reprocesar(args: argparse.Namespace) -> None:
    import pandas as pd
    from leadgen import catalogo, reprocesar

    cat = catalogo.cargar_catalogo(args.catalogo)
    if args.excel:
        filas = pd.read_excel(args.excel).to_dict("records")
        salida = reprocesar.reprocesar_filas(filas, cat)
        ruta = export.exportar_excel(salida, args.salida or "leads_analizados.xlsx")
        print(f"{len(salida)} empresas reprocesadas -> {Path(ruta).resolve()}")
        return
    with database.conectar(args.db) as conn:
        filas = [dict(f) for f in database.obtener_todas(conn)]
        salida = reprocesar.reprocesar_filas(filas, cat)
        for f in salida:
            f.pop("id", None)
            f.pop("lead_score_original", None)
            f.pop("fecha_creacion", None)
            f.pop("fecha_actualizacion", None)
            database.guardar_o_actualizar(conn, f)
    print(f"{len(salida)} empresas reprocesadas en {args.db}")


def cmd_contacto(args: argparse.Namespace) -> None:
    with database.conectar(args.db) as conn:
        cid = database.registrar_contacto(conn, args.url_perfil, args.producto, args.resultado,
                                          canal=args.canal, notas=args.notas, registrado_por=args.por)
    print(f"Contacto #{cid} registrado.")


def cmd_exportar(args: argparse.Namespace) -> None:
    with database.conectar(args.db) as conn:
        filas = database.obtener_todas(conn)
        contactos = database.obtener_contactos(conn)

    if not filas:
        print("No hay datos en la base de datos todavía. Corre primero: python main.py procesar <url>")
        return

    if args.formato == "excel":
        ruta = export.exportar_excel(filas, args.salida or "leads.xlsx", contactos=contactos)
    elif args.formato == "csv":
        ruta = export.exportar_csv(filas, args.salida or "leads.csv")
    else:
        ruta = export.exportar_json(filas, args.salida or "leads.json")

    print(f"Exportado a: {Path(ruta).resolve()}")


def cmd_dashboard(args: argparse.Namespace) -> None:
    from leadgen import dashboard

    with database.conectar(args.db) as conn:
        filas = database.obtener_todas(conn)

    ruta = dashboard.generar_dashboard(filas, args.salida or "dashboard.html")
    ruta_absoluta = Path(ruta).resolve()
    print(f"Dashboard generado en: {ruta_absoluta}")
    if args.abrir:
        webbrowser.open(f"file://{ruta_absoluta}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline de generación de leads B2B")
    parser.add_argument("--db", default=config.DB_PATH, help="Ruta al archivo de base de datos SQLite")
    parser.add_argument("--catalogo", default=config.CATALOGO_PATH, help="Ruta al catálogo de productos (JSON)")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    p_procesar = subparsers.add_parser("procesar", help="Corre el pipeline completo sobre un directorio")
    p_procesar.add_argument("url", help="URL del directorio de empresas (Módulo 1)")
    p_procesar.add_argument("--config", help="Ruta a un archivo JSON con selectores CSS para este sitio")
    p_procesar.add_argument("--ia", action="store_true", help="Activa el Módulo 7 y el diagnóstico con IA")
    p_procesar.add_argument(
        "--navegador", action="store_true",
        help="Usa Playwright para renderizar JavaScript (sitios React/Next.js/Vue). Requiere: pip install playwright && playwright install chromium",
    )
    p_procesar.add_argument("--max-resultados", type=int, default=40,
                            help="Tope de negocios a traer si la URL es de Google Maps (default: 40)")
    p_procesar.add_argument("--maps-rapido", action="store_true",
                            help="Si la URL es de Google Maps, no abre cada ficha individual (más rápido, menos datos)")
    p_procesar.set_defaults(func=cmd_procesar)

    p_cat = subparsers.add_parser("catalogo", help="Fase 1: lee el catálogo de productos desde uno o varios links")
    p_cat.add_argument("urls", nargs="*", help="Links del catálogo (páginas de servicios, PDF, tienda...)")
    p_cat.add_argument("--ia", action="store_true", help="Usa Claude para leer el catálogo (requiere ANTHROPIC_API_KEY)")
    p_cat.add_argument("--navegador", action="store_true", help="Renderiza con Playwright (sitios con JavaScript)")
    p_cat.add_argument("--max-paginas", type=int, default=config.CATALOGO_MAX_PAGINAS)
    p_cat.add_argument("--reemplazar", action="store_true", help="No conserva productos anteriores (salvo nada)")
    p_cat.add_argument("--mostrar", action="store_true", help="Solo muestra el catálogo actual")
    p_cat.set_defaults(func=cmd_catalogo)

    p_rep = subparsers.add_parser("reprocesar", help="Aplica Fases 2-5 a leads ya guardados, sin scraping")
    p_rep.add_argument("--excel", help="Excel exportado a reprocesar (si se omite, usa la base de datos)")
    p_rep.add_argument("--salida", help="Excel de salida (solo con --excel)")
    p_rep.set_defaults(func=cmd_reprocesar)

    p_con = subparsers.add_parser("contacto", help="Registra una oferta hecha a una empresa y su resultado")
    p_con.add_argument("url_perfil")
    p_con.add_argument("producto", help="id del producto del catálogo")
    p_con.add_argument("--resultado", default="pendiente", choices=database.RESULTADOS_VALIDOS)
    p_con.add_argument("--canal", default="")
    p_con.add_argument("--notas", default="")
    p_con.add_argument("--por", default="", help="Quién registra")
    p_con.set_defaults(func=cmd_contacto)

    p_exportar = subparsers.add_parser("exportar", help="Exporta la base de datos a un archivo")
    p_exportar.add_argument("--formato", choices=["excel", "csv", "json"], default="excel")
    p_exportar.add_argument("--salida", help="Nombre del archivo de salida")
    p_exportar.set_defaults(func=cmd_exportar)

    p_dashboard = subparsers.add_parser("dashboard", help="Genera el dashboard HTML (Módulo 11)")
    p_dashboard.add_argument("--salida", help="Nombre del archivo HTML de salida")
    p_dashboard.add_argument("--abrir", action="store_true", help="Abre el dashboard en el navegador al terminar")
    p_dashboard.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
