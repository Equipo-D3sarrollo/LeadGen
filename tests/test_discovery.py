from unittest.mock import patch

from bs4 import BeautifulSoup

from leadgen import discovery


def _pagina(*, perfiles=(), siguiente=None):
    enlaces = "".join(
        f'<article><a href="{href}">{nombre}</a></article>'
        for href, nombre in perfiles
    )
    siguiente_html = f'<a class="next" href="{siguiente}">Siguiente</a>' if siguiente else ""
    return BeautifulSoup(f"<html><body>{enlaces}{siguiente_html}</body></html>", "html.parser")


def _descubrir_anterior(url_directorio, paginas, max_paginas=10):
    resultados = []
    url_actual = url_directorio
    paginas_recorridas = 0
    while url_actual and paginas_recorridas < max_paginas:
        soup = paginas.get(url_actual)
        if soup is None:
            break
        resultados.extend(discovery._heuristica_generica(soup, url_actual))
        url_actual = None
        sig = soup.select_one("a.next")
        if sig and sig.get("href"):
            url_actual = discovery.urljoin(url_directorio, sig["href"])
        paginas_recorridas += 1

    vistos = set()
    unicos = []
    for empresa in resultados:
        if empresa.url_perfil not in vistos:
            vistos.add(empresa.url_perfil)
            unicos.append(empresa)
    return unicos


def _ejecutar(paginas, url_directorio="https://directorio.test/inicio", max_paginas=10):
    solicitudes = []
    with patch.object(discovery, "_get", side_effect=lambda url: solicitudes.append(url) or paginas.get(url)), \
         patch.object(discovery.time, "sleep") as dormir:
        resultado = discovery.descubrir_empresas(
            url_directorio,
            selector_siguiente_pagina="a.next",
            max_paginas=max_paginas,
        )
    return resultado, solicitudes, dormir


def test_paginacion_lineal_conserva_orden_y_resultados():
    paginas = {
        "https://directorio.test/inicio": _pagina(perfiles=[("/uno", "Uno")], siguiente="/pagina/2"),
        "https://directorio.test/pagina/2": _pagina(perfiles=[("/dos", "Dos")], siguiente="/pagina/3"),
        "https://directorio.test/pagina/3": _pagina(perfiles=[("/tres", "Tres")]),
    }

    resultado, solicitudes, dormir = _ejecutar(paginas)

    assert solicitudes == list(paginas)
    assert [empresa.url_perfil for empresa in resultado] == [
        "https://directorio.test/uno",
        "https://directorio.test/dos",
        "https://directorio.test/tres",
    ]
    assert dormir.call_count == 3


def test_autoenlace_no_repite_solicitud():
    paginas = {
        "https://directorio.test/inicio": _pagina(perfiles=[("/uno", "Uno")], siguiente="/inicio"),
    }

    resultado, solicitudes, _ = _ejecutar(paginas)

    assert len(resultado) == 1
    assert solicitudes == ["https://directorio.test/inicio"]


def test_ciclo_a_b_a_se_detiene_y_no_repite_paginas():
    paginas = {
        "https://directorio.test/inicio": _pagina(perfiles=[("/uno", "Uno")], siguiente="/pagina/2"),
        "https://directorio.test/pagina/2": _pagina(perfiles=[("/dos", "Dos")], siguiente="/inicio"),
    }

    resultado, solicitudes, _ = _ejecutar(paginas)

    assert [empresa.url_perfil for empresa in resultado] == [
        "https://directorio.test/uno",
        "https://directorio.test/dos",
    ]
    assert solicitudes == [
        "https://directorio.test/inicio",
        "https://directorio.test/pagina/2",
    ]


def test_max_paginas_sigue_limitando_paginas_distintas():
    paginas = {
        "https://directorio.test/inicio": _pagina(siguiente="/pagina/2"),
        "https://directorio.test/pagina/2": _pagina(siguiente="/pagina/3"),
        "https://directorio.test/pagina/3": _pagina(siguiente="/pagina/4"),
        "https://directorio.test/pagina/4": _pagina(),
    }

    _, solicitudes, _ = _ejecutar(paginas, max_paginas=2)

    assert solicitudes == [
        "https://directorio.test/inicio",
        "https://directorio.test/pagina/2",
    ]


def test_perfiles_duplicados_conservan_deduplicacion_actual():
    paginas = {
        "https://directorio.test/inicio": _pagina(perfiles=[("/uno", "Primero")], siguiente="/pagina/2"),
        "https://directorio.test/pagina/2": _pagina(perfiles=[("/uno", "Segundo")]),
    }

    resultado, _, _ = _ejecutar(paginas)

    assert len(resultado) == 1
    assert resultado[0].nombre == "Primero"


def test_respuesta_none_detiene_la_paginacion():
    paginas = {
        "https://directorio.test/inicio": _pagina(siguiente="/pagina/2"),
    }

    resultado, solicitudes, dormir = _ejecutar(paginas)

    assert resultado == []
    assert solicitudes == [
        "https://directorio.test/inicio",
        "https://directorio.test/pagina/2",
    ]
    assert dormir.call_count == 1


def test_referencia_anterior_y_nueva_son_equivalentes_sin_ciclos():
    paginas = {
        "https://directorio.test/inicio": _pagina(perfiles=[("/uno", "Uno")], siguiente="/pagina/2"),
        "https://directorio.test/pagina/2": _pagina(perfiles=[("/dos", "Dos")]),
    }

    esperado = _descubrir_anterior("https://directorio.test/inicio", paginas)
    resultado, _, _ = _ejecutar(paginas)

    assert [(e.nombre, e.url_perfil, e.categoria) for e in resultado] == [
        (e.nombre, e.url_perfil, e.categoria) for e in esperado
    ]
