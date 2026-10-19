"""
config.py
---------
Configuración central del sistema: pesos del Lead Score, headers HTTP,
tiempos de espera y otras constantes que puedes ajustar sin tocar el
resto del código.

A partir de la Fase 1 (oct. 2026) también contiene los parámetros del
análisis psicológico-matemático (Capas 2, 3 y score final). TODOS esos
valores son SUPUESTOS INICIALES hasta la calibración de la Fase 7; el
porqué de cada uno está en DECISIONES.md.
"""

# ---------------------------------------------------------------------------
# MÓDULO 8 - Pesos del Lead Score (según el documento original) -- Capa 1
# ---------------------------------------------------------------------------
SCORING_WEIGHTS = {
    "sin_web": 40,          # No tiene sitio web -> es un cliente potencial fuerte
    "tiene_facebook": 15,
    "tiene_instagram": 10,
    "tiene_whatsapp": 10,
    "tiene_telefono": 10,
    "tiene_correo": 10,
    "muchas_resenas": 20,   # umbral definido en RESENAS_UMBRAL
    "web_excelente": -30,   # el sitio ya es muy bueno -> poco interesante
    "sin_redes": -10,       # no tiene ninguna red social
}

# Cuántas reseñas se consideran "muchas" (Módulo 8)
RESENAS_UMBRAL = 20

# Umbral de puntaje web (Módulo 6) a partir del cual se considera "excelente"
WEB_SCORE_EXCELENTE = 80  # sobre 100

# ---------------------------------------------------------------------------
# Configuración de red / scraping
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 LeadGenBot/1.0"
    )
}

REQUEST_TIMEOUT = 12          # segundos por request
DELAY_BETWEEN_REQUESTS = 1.5  # segundos entre visitas (sé respetuoso con los sitios)
MAX_PAGINAS_DIRECTORIO = 50   # límite de seguridad al paginar un directorio

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
DB_PATH = "leadgen.db"

# ---------------------------------------------------------------------------
# FASE 1 - Catálogo de productos (catalogo.py)
# ---------------------------------------------------------------------------
CATALOGO_PATH = "catalogo_productos.json"
CATALOGO_MAX_PAGINAS = 15          # páginas internas a recorrer por cada link de catálogo
CATALOGO_MODELO_IA = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# FASE 2 - Señales
# ---------------------------------------------------------------------------
PAIS_OBJETIVO = "Colombia"         # direcciones de otro país se marcan fuera_de_mercado
RATING_PRIOR_MEDIA = 4.2           # C del rating bayesiano (media global supuesta)
RATING_PRIOR_PESO = 10             # m del rating bayesiano
RESENAS_SATURACION = 500           # v_max de la saturación logarítmica

# ---------------------------------------------------------------------------
# FASE 3 - Perfil conductual (Capa 2). Orden fijo de las 6 dimensiones.
# ---------------------------------------------------------------------------
DIMENSIONES = [
    "madurez_digital",
    "dolor_urgencia",
    "confianza_reputacion",
    "dinamismo",
    "apertura_comercial",
    "sofisticacion_marca",
]
# Dimensiones de INTENT (momento) vs FIT (encaje), sección 9.1 del OBJETIVO
DIMENSIONES_INTENT = ["dolor_urgencia", "dinamismo"]
COBERTURA_MINIMA = 0.35            # por debajo, el perfil se marca "confianza baja"

# ---------------------------------------------------------------------------
# FASE 4 - Núcleo psicológico (Capa 3): z = b + W·s ; p = softmax(z/T)
# Orden de emociones: alegría, confianza, miedo, sorpresa, tristeza,
#                     aversión, ira, anticipación
# Columnas de W = DIMENSIONES (mismo orden).  SUPUESTOS INICIALES.
# ---------------------------------------------------------------------------
EMOCIONES = ["alegria", "confianza", "miedo", "sorpresa", "tristeza", "aversion", "ira", "anticipacion"]
#            madurez dolor  confianza dinamismo apertura sofistic.
W_PSICO = [
    [0.8,   -0.6,  1.0,      1.0,      0.4,     0.6],   # alegría
    [0.6,   -0.4,  1.6,      0.3,      0.9,     0.5],   # confianza
    [-0.8,   1.6, -0.6,     -0.3,     -0.2,    -0.4],   # miedo
    [0.0,    0.5,  0.0,      0.6,      0.2,     0.0],   # sorpresa
    [-0.6,   1.2, -0.8,     -1.0,     -0.3,    -0.3],   # tristeza
    [-0.2,   0.3, -0.6,     -0.2,     -1.4,    -0.2],   # aversión
    [-0.2,   0.8, -0.8,      0.1,     -0.4,     0.0],   # ira
    [0.6,    0.4,  0.3,      1.4,      0.6,     0.7],   # anticipación
]
# Línea base centrada (DECISIONES D-04): una empresa "neutra" (todas las
# dimensiones en 0.5) da z = 0 en las 8 emociones -> perfil uniforme, sin
# emoción favorecida de antemano. Equivale a z = W·(s − 0.5). Se calcula
# más abajo, después de VALOR_NEUTRO_DIMENSION.
T_PSICO = 0.5
VALOR_NEUTRO_DIMENSION = 0.5       # dimensión no medida -> punto medio (NO cero); ver DECISIONES.md
B_PSICO = [-VALOR_NEUTRO_DIMENSION * sum(fila) for fila in W_PSICO]
# Contracción por cobertura (DECISIONES D-05): s = 0.5 + cobertura·(valor − 0.5).
# Una dimensión medida con 1 de 5 señales no puede empujar el perfil igual que una completa.
CONTRAER_POR_COBERTURA = True
UMBRAL_P1 = 0.25                   # filtro: prob. mínima de la emoción principal
UMBRAL_DELTA = 0.05                # filtro: claridad mínima
UMBRAL_S_PCT = 55                  # filtro: compatibilidad mínima (%), por defecto

# Score final = ALFA * lead_score_norm + BETA * compatibilidad del mejor producto
ALFA_LEAD = 0.4
BETA_PSICO = 0.6
LEAD_SCORE_MAX = 100               # para normalizar el Lead Score (se recorta a 100)
PENALIZACION_DATO_INVALIDO = 5     # puntos que resta cada dato inválido (sección 9.2)
DIAGNOSTICO_MOSTRAR_EMOCION = False   # Capa 4: True para ver también la etiqueta emocional cruda
