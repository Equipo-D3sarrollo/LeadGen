"""
browser.py
----------
Utilidad para renderizar páginas que cargan su contenido con
JavaScript (apps modernas hechas en React/Next.js/Vue, etc.) usando
Playwright, que controla un navegador real (Chromium) sin interfaz
gráfica.

Se usa cuando `requests` + BeautifulSoup no alcanza porque el HTML
inicial no trae los datos (ej: Páginas Amarillas, la mayoría de
directorios modernos).

Requiere instalar, una sola vez:
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import time


def obtener_html_renderizado(
    url: str,
    esperar_selector: str | None = None,
    click_selector: str | None = None,
    max_clicks: int = 0,
    hacer_scroll: bool = True,
    tiempo_espera_extra: float = 2.0,
    timeout_ms: int = 30000,
) -> str:
    """
    Abre `url` en un navegador headless, espera a que cargue el
    contenido dinámico y devuelve el HTML final ya renderizado.

    esperar_selector: si lo das, espera explícitamente a que ese
        elemento aparezca (ej: el selector de la tarjeta de empresa).
    click_selector: selector de un botón tipo "Cargar más" / "Ver más"
        que se debe hacer clic repetidamente para traer más resultados
        (alternativa a la paginación por URL, típica en SPAs).
    max_clicks: cuántas veces hacer clic en click_selector como máximo.
    hacer_scroll: si True, hace scroll hasta el final varias veces
        antes de leer el HTML, para disparar cargas "lazy" por scroll
        infinito.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright no está instalado. Corre:\n"
            "    pip install playwright\n"
            "    playwright install chromium"
        ) from e

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        pagina = navegador.new_page()
        try:
            pagina.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except Exception as e:
            print(f"[browser] Aviso al cargar {url}: {e}")

        if esperar_selector:
            try:
                pagina.wait_for_selector(esperar_selector, timeout=10000)
            except Exception:
                pass  # seguimos igual; puede que el selector esté mal, se reporta en el HTML final

        if hacer_scroll:
            for _ in range(5):
                pagina.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(0.8)

        clics_hechos = 0
        while click_selector and clics_hechos < max_clicks:
            boton = pagina.query_selector(click_selector)
            if not boton:
                break
            try:
                boton.click()
                time.sleep(1.5)
                clics_hechos += 1
            except Exception:
                break

        time.sleep(tiempo_espera_extra)
        html = pagina.content()
        navegador.close()
        return html
