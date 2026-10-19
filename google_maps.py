"""
google_maps.py
---------------
Extrae negocios directamente desde una búsqueda de Google Maps.

Cómo obtener la URL correcta:
    1. Ve a Google Maps y busca algo como "restaurantes en Cali".
    2. Espera a que aparezca el panel con la LISTA de varios negocios
       a la izquierda (no la ficha de un solo lugar).
    3. Copia la URL de la barra de direcciones tal cual (algo como
       https://www.google.com/maps/search/restaurantes+en+cali/@3.45,-76.53,13z)
       y pégala en LeadGen.

Requiere Playwright:
    pip install playwright
    playwright install chromium

Limitaciones importantes (léelas antes de usar esto en producción):
- Google Maps casi nunca muestra correo electrónico en la ficha; solo
  teléfono, dirección y, si el negocio lo cargó, su sitio web.
- El HTML de Google Maps usa nombres de clase generados/ofuscados que
  Google cambia sin aviso. Aquí se usan atributos más estables
  (role="feed", data-item-id, aria-label) para reducir el riesgo, pero
  si un día deja de funcionar, probablemente Google cambió el marcado
  y hay que ajustar los selectores en este archivo.
- Abrir muchas fichas seguidas y muy rápido puede hacer que Google
  te muestre un captcha. Este módulo mete pausas a propósito; no las
  quites si vas a correr esto contra volúmenes grandes.
- Revisa los Términos de Servicio de Google Maps antes de usar esto
  para un caso comercial real. Para volúmenes pequeños de prueba /
  portafolio está bien, pero Google prohíbe explícitamente el scraping
  masivo de Maps en sus términos. Alternativa recomendada a futuro:
  Google Places API oficial (rating, reseñas, teléfono, web, horarios).

Cambios Fase 2 (oct. 2026):
  - Extrae rating y número de reseñas de la ficha (señales de la
    dimensión Confianza/reputación). Antes scoring.py tenía el bono
    "muchas_resenas" pero nunca recibía el dato.
  - Extrae el horario cuando la ficha lo muestra (señal de Dinamismo).
  - Teléfono: se toma del atributo data-item-id="phone:tel:..." (un
    solo número, sin texto alrededor) y solo si falta se usa el texto.
"""

from __future__ import annotations

import re
import time

from .scraper import EmpresaCruda


def es_url_google_maps(url: str) -> bool:
    """Detecta si una URL corresponde a Google Maps."""
    url = (url or "").lower()
    return "google.com/maps" in url or "goo.gl/maps" in url or "maps.app.goo.gl" in url


def _limpiar_telefono(texto: str) -> str:
    m = re.search(r"(\+?\(?\d{1,4}\)?(?:[ \-.]?\d){6,12})", texto or "")
    return m.group(1) if m else ""


def _numero(txt: str) -> float:
    """'1.234' -> 1234 ; '4,6' -> 4.6 ; '1,2 mil' -> 1200."""
    txt = txt.strip().lower()
    mult = 1000 if re.search(r"\s?(mil|k)$", txt) else 1
    txt = re.sub(r"\s?(mil|k)$", "", txt)
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", txt):
        return float(re.sub(r"[.,]", "", txt)) * mult
    return float(txt.replace(",", ".")) * mult


def parsear_rating_resenas(texto: str) -> tuple[float | None, int | None]:
    """
    Extrae (rating, numero_resenas) de textos como:
      "4,6 estrellas 1.234 reseñas", "4.6 stars 1,234 Reviews", "4,6(1.234)".
    Devuelve None en lo que no encuentre.
    """
    if not texto:
        return None, None
    rating = resenas = None
    m = re.search(r"(\d[.,]\d)\s*(?:estrellas|stars|★)", texto, re.I)
    if m:
        rating = _numero(m.group(1))
    m = re.search(r"([\d.,]+(?:\s?mil)?)\s*(?:reseñas|opiniones|reviews|reseña|review)", texto, re.I)
    if m:
        resenas = int(_numero(m.group(1)))
    if rating is None or resenas is None:
        m = re.search(r"(\d[.,]\d)\s*\(([\d.,]+)\)", texto)
        if m:
            rating = rating if rating is not None else _numero(m.group(1))
            resenas = resenas if resenas is not None else int(_numero(m.group(2)))
    if rating is not None and not (1.0 <= rating <= 5.0):
        rating = None
    return rating, resenas


def extraer_negocios_google_maps(
    url: str,
    max_resultados: int = 40,
    abrir_cada_ficha: bool = True,
    max_scrolls: int = 25,
    pausa_entre_fichas: float = 1.5,
) -> list[EmpresaCruda]:
    """
    Abre una búsqueda de Google Maps, hace scroll en el panel de
    resultados para cargar varios negocios, y (opcionalmente) abre cada
    ficha para sacar teléfono, dirección completa y sitio web.

    abrir_cada_ficha=False es más rápido pero solo trae nombre y lo que
    alcance a leerse desde la lista (sin teléfono ni sitio web).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright no está instalado. Corre:\n"
            "    pip install playwright\n"
            "    playwright install chromium"
        ) from e

    resultados: list[EmpresaCruda] = []

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        pagina = navegador.new_page(locale="es-CO")

        try:
            pagina.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[google_maps] Aviso al cargar la búsqueda: {e}")

        # Cierra el diálogo de cookies/consentimiento si aparece
        for texto_boton in ("Aceptar todo", "Accept all", "Rechazar todo", "Reject all"):
            try:
                boton = pagina.query_selector(f"button:has-text('{texto_boton}')")
                if boton:
                    boton.click()
                    time.sleep(1)
                    break
            except Exception:
                pass

        try:
            pagina.wait_for_selector('div[role="feed"]', timeout=15000)
        except Exception:
            navegador.close()
            raise RuntimeError(
                "No se encontró la lista de resultados de Google Maps. "
                "Verifica que la URL sea una BÚSQUEDA con varios negocios "
                "(el panel izquierdo debe mostrar una lista), no la ficha "
                "de un solo lugar."
            )

        panel = pagina.query_selector('div[role="feed"]')

        # Scroll dentro del panel de resultados para ir cargando más negocios
        conteo_previo = 0
        for _ in range(max_scrolls):
            pagina.evaluate("(el) => el.scrollTo(0, el.scrollHeight)", panel)
            time.sleep(1.2)
            enlaces_actuales = pagina.query_selector_all('div[role="feed"] a[href*="/maps/place/"]')
            if len(enlaces_actuales) >= max_resultados:
                break
            if len(enlaces_actuales) == conteo_previo:
                break  # no cargó nada nuevo, probablemente llegamos al final
            conteo_previo = len(enlaces_actuales)

        enlaces = pagina.query_selector_all('div[role="feed"] a[href*="/maps/place/"]')
        vistos = set()
        candidatos = []
        for a in enlaces:
            href = a.get_attribute("href")
            nombre = a.get_attribute("aria-label") or ""
            if not href or href in vistos:
                continue
            vistos.add(href)
            candidatos.append((nombre, href))
            if len(candidatos) >= max_resultados:
                break

        print(f"[google_maps] {len(candidatos)} negocios encontrados en la lista.")

        for i, (nombre, href) in enumerate(candidatos, start=1):
            empresa = EmpresaCruda(nombre=nombre, url_perfil=href)

            if abrir_cada_ficha:
                print(f"[google_maps] ({i}/{len(candidatos)}) Abriendo ficha: {nombre}")
                exito = False
                for intento in range(2):  # 1 intento + 1 reintento
                    try:
                        # "domcontentloaded" en vez de "networkidle": Google Maps
                        # mantiene tráfico de fondo que nunca "queda quieto".
                        pagina.goto(href, wait_until="domcontentloaded", timeout=20000)
                        pagina.wait_for_selector("h1", timeout=15000)
                        time.sleep(pausa_entre_fichas)
                        _rellenar_desde_ficha(pagina, empresa)
                        exito = True
                        break
                    except Exception as e:
                        if intento == 0:
                            print(f"[google_maps] Timeout en {nombre}, reintentando una vez...")
                            time.sleep(2)
                        else:
                            print(f"[google_maps] No se pudo abrir la ficha de {nombre} tras reintentar: {e}")
                if not exito:
                    pass  # queda guardado solo con nombre + link, el resto del pipeline sigue normal

            resultados.append(empresa)

        navegador.close()

    return resultados


def _rellenar_desde_ficha(pagina, empresa: EmpresaCruda) -> None:
    """Extrae teléfono, dirección, sitio web, categoría, rating, reseñas y horario de la ficha abierta."""
    tel_el = pagina.query_selector('button[data-item-id^="phone:"]')
    if tel_el:
        item_id = tel_el.get_attribute("data-item-id") or ""
        m = re.match(r"phone:tel:(\+?\d+)", item_id)
        if m:
            empresa.telefono = m.group(1)
        else:
            texto = tel_el.get_attribute("aria-label") or tel_el.inner_text() or ""
            empresa.telefono = _limpiar_telefono(texto)

    web_el = pagina.query_selector('a[data-item-id="authority"]')
    if web_el:
        empresa.sitio_web = web_el.get_attribute("href") or ""

    dir_el = pagina.query_selector('button[data-item-id="address"]')
    if dir_el:
        texto = dir_el.get_attribute("aria-label") or dir_el.inner_text() or ""
        empresa.direccion = texto.replace("Dirección: ", "").replace("Address: ", "").strip()

    cat_el = pagina.query_selector('button[jsaction*="category"]')
    if cat_el:
        empresa.categoria = (cat_el.inner_text() or "").strip()

    nombre_el = pagina.query_selector('h1')
    if nombre_el and nombre_el.inner_text().strip():
        empresa.nombre = nombre_el.inner_text().strip()

    # Rating y reseñas: se juntan los aria-label de estrellas/reseñas y el texto bajo el título
    try:
        etiquetas = pagina.eval_on_selector_all(
            '[aria-label*="estrellas"], [aria-label*="stars"], [aria-label*="reseñas"], [aria-label*="reviews"]',
            "els => els.slice(0, 6).map(e => e.getAttribute('aria-label')).join(' ')",
        )
    except Exception:
        etiquetas = ""
    texto_cabecera = ""
    try:
        texto_cabecera = pagina.eval_on_selector(
            "h1", "h => (h.parentElement && h.parentElement.parentElement) ? h.parentElement.parentElement.innerText : ''"
        ) or ""
    except Exception:
        pass
    rating, resenas = parsear_rating_resenas(f"{etiquetas} {texto_cabecera}")
    empresa.rating = rating
    empresa.numero_resenas = resenas

    # Horario (si la ficha lo muestra en un aria-label de la tabla de horario)
    try:
        hor_el = pagina.query_selector('[aria-label*="Horario"], [aria-label*="Hours"], div[data-hide-tooltip-on-mouse-move] table')
        if hor_el:
            empresa.horario = (hor_el.get_attribute("aria-label") or hor_el.inner_text() or "").strip()[:300]
    except Exception:
        pass
