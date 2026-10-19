"""
dashboard.py
------------
MÓDULO 11 - Dashboard

Genera un archivo HTML autocontenido con las estadísticas generales:
empresas encontradas, sin web, con web vieja, clientes potenciales,
con WhatsApp, con correo, y una tabla con los mejores leads.
"""

from __future__ import annotations

import sqlite3

PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Dashboard de Leads</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#0f1115; color:#e7e7ea; margin:0; padding:32px; }}
  h1 {{ font-weight:600; margin-bottom:4px; }}
  .subtitulo {{ color:#9a9aa5; margin-bottom:32px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(180px,1fr)); gap:16px; margin-bottom:40px; }}
  .card {{ background:#1a1d24; border:1px solid #2a2d35; border-radius:12px; padding:20px; }}
  .card .num {{ font-size:32px; font-weight:700; color:#8b7cf6; }}
  .card .label {{ color:#9a9aa5; font-size:13px; margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; background:#1a1d24; border-radius:12px; overflow:hidden; }}
  th, td {{ text-align:left; padding:10px 14px; border-bottom:1px solid #2a2d35; font-size:13px; }}
  th {{ background:#20232b; color:#9a9aa5; text-transform:uppercase; font-size:11px; }}
  tr:hover {{ background:#20232b; }}
  .score {{ font-weight:700; color:#8b7cf6; }}
</style>
</head>
<body>
  <h1>Dashboard de Leads</h1>
  <div class="subtitulo">Generado automáticamente por el pipeline</div>

  <div class="grid">
    <div class="card"><div class="num">{total}</div><div class="label">Empresas encontradas</div></div>
    <div class="card"><div class="num">{sin_web}</div><div class="label">Sin página web</div></div>
    <div class="card"><div class="num">{web_vieja}</div><div class="label">Con web de baja calidad</div></div>
    <div class="card"><div class="num">{potenciales}</div><div class="label">Clientes potenciales (score ≥ 50)</div></div>
    <div class="card"><div class="num">{con_whatsapp}</div><div class="label">Con WhatsApp</div></div>
    <div class="card"><div class="num">{con_correo}</div><div class="label">Con correo</div></div>
  </div>

  <h2>Top leads</h2>
  <table>
    <tr><th>Empresa</th><th>Ciudad</th><th>Score</th><th>Clasificación</th><th>Web</th><th>WhatsApp</th><th>Correo</th></tr>
    {filas}
  </table>
</body>
</html>
"""


def generar_dashboard(filas: list[sqlite3.Row], ruta_salida: str = "dashboard.html") -> str:
    total = len(filas)
    sin_web = sum(1 for f in filas if not f["tiene_web"])
    web_vieja = sum(1 for f in filas if f["tiene_web"] and (f["web_puntaje"] or 0) < 50)
    potenciales = sum(1 for f in filas if (f["lead_score"] or 0) >= 50)
    con_whatsapp = sum(1 for f in filas if f["tiene_whatsapp"])
    con_correo = sum(1 for f in filas if f["tiene_correo"])

    top = sorted(filas, key=lambda f: f["lead_score"] or 0, reverse=True)[:30]
    filas_html = "\n".join(
        f"<tr><td>{f['nombre']}</td><td>{f['ciudad'] or '-'}</td>"
        f"<td class='score'>{f['lead_score']}</td><td>{f['lead_clasificacion']}</td>"
        f"<td>{'Sí' if f['tiene_web'] else 'No'}</td>"
        f"<td>{'Sí' if f['tiene_whatsapp'] else 'No'}</td>"
        f"<td>{'Sí' if f['tiene_correo'] else 'No'}</td></tr>"
        for f in top
    )

    html = PLANTILLA.format(
        total=total,
        sin_web=sin_web,
        web_vieja=web_vieja,
        potenciales=potenciales,
        con_whatsapp=con_whatsapp,
        con_correo=con_correo,
        filas=filas_html or "<tr><td colspan='7'>Sin datos todavía</td></tr>",
    )

    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(html)
    return ruta_salida
