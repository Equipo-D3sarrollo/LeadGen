# LeadGen — Pipeline de generación de leads B2B

Herramienta que recorre un directorio de empresas (una URL), extrae la
información de cada una, la analiza y le asigna un **Lead Score**: qué tan
buen cliente potencial es para servicios de diseño/desarrollo web.

Implementa los 11 módulos del documento original:

1. Entrada (URL) → 2. Descubrimiento → 3. Recolección → 4. Normalización →
5. Validación → 6. Análisis Web → 7. IA (opcional) → 8. Lead Score →
9. Base de Datos (sin duplicados) → 10. Exportación → 11. Dashboard.

---

## 1. Instalación

Necesitas Python 3.10 o superior.

```bash
cd leadgen
pip install -r requirements.txt
```

Esto instala: `requests`, `beautifulsoup4`, `pandas`, `openpyxl` y
`anthropic` (esta última solo se usa si activas el Módulo 7 de IA).

---

## 2. Analizar negocios desde Google Maps

Además de directorios web normales, LeadGen detecta automáticamente
cuando le pegas una URL de Google Maps y usa un extractor especializado
(`google_maps.py`) — no necesitas configurar selectores para esto.

### Cómo conseguir la URL correcta

1. Ve a [Google Maps](https://maps.google.com) y busca lo que quieras
   (ej: "restaurantes en Cali", "peluquerías en Bogotá").
2. Espera a que aparezca el panel con una **lista de varios negocios**
   a la izquierda (no la ficha de un solo lugar — tiene que verse la lista).
3. Copia la URL completa de la barra de direcciones y pégala en LeadGen
   (por consola o por la interfaz web), igual que harías con cualquier
   otro directorio:

```bash
python main.py procesar "https://www.google.com/maps/search/restaurantes+en+cali/@3.45,-76.53,13z"
```

Desde la interfaz web es exactamente igual: la pegas en el mismo campo
de "URL del directorio" y le das **Procesar**.

### Qué datos trae y qué NO trae

- ✅ Nombre, categoría, dirección, teléfono, sitio web (si el negocio lo cargó)
- ❌ Casi nunca correo electrónico (Google Maps casi no lo muestra) —
  si el negocio tiene sitio web, el Módulo 6 sí analiza esa web aparte.
- ❌ Facebook/Instagram directos (Maps no los expone de forma estándar)

### Opciones específicas de Google Maps

```bash
python main.py procesar "https://google.com/maps/search/..." --max-resultados 60
python main.py procesar "https://google.com/maps/search/..." --maps-rapido
```

- `--max-resultados`: tope de negocios a traer (default 40). Entre más
  alto, más tarda (tiene que hacer scroll y abrir cada ficha).
- `--maps-rapido`: no abre cada ficha individual — mucho más rápido,
  pero solo trae el nombre (sin teléfono, dirección completa ni web).
  Útil para un primer vistazo rápido del tamaño del mercado.

En la interfaz web, el campo "Máximo de negocios a traer si pegaste una
URL de Google Maps" controla lo mismo que `--max-resultados`.

### Cosas importantes que debes saber

- **Requiere Playwright** (igual que el modo navegador de la Sección 3):
  ```bash
  pip install playwright
  playwright install chromium
  ```
- **Es más lento que un directorio normal**, porque abre cada ficha una
  por una con pausas a propósito (para no parecer un bot agresivo ante
  Google). Para 40 negocios con fichas abiertas, calcula varios minutos.
- **Google puede pedir un captcha** si detecta actividad automatizada
  muy agresiva. Si te pasa, baja `--max-resultados`, espera un rato
  antes de reintentar, y evita correr esto en loops muy seguidos.
- **El HTML de Google Maps cambia sin aviso.** Si un día deja de traer
  datos (por ejemplo, teléfono siempre vacío), lo más probable es que
  Google cambió el marcado interno — en ese caso avísame o revisa los
  selectores en `leadgen/google_maps.py` (función `_rellenar_desde_ficha`).
- **Revisa los Términos de Servicio de Google** antes de usar esto para
  un caso comercial real de volumen. Para pruebas y portafolio en
  volúmenes moderados está bien, pero Google restringe explícitamente
  el scraping masivo de Maps en sus términos.

---

## 3. Lo primero que tienes que entender de directorios normales (no Google Maps): los "selectores"

Cada directorio de empresas en internet tiene una estructura HTML distinta.
El sistema **no puede adivinar mágicamente** dónde está el nombre, el
teléfono o el enlace a cada empresa en un sitio que nunca ha visto — por
eso necesita que le digas, con **selectores CSS**, dónde mirar.

Hay dos formas de usarlo:

### Opción A — Modo genérico (rápido, menos preciso)
Si no le das ningún selector, el sistema intenta adivinar con una
heurística (busca tarjetas típicas: `article`, `li`, `div` con clases como
`card`, `listing`, `item`). Funciona bien en sitios simples, pero puede
fallar en sitios complejos.

```bash
python main.py procesar "https://directorio-de-empresas.com"
```

### Opción B — Modo configurado (recomendado)
1. Abre el directorio en Chrome/Firefox.
2. Clic derecho sobre una tarjeta de empresa → **Inspeccionar**.
3. Identifica la clase CSS de la tarjeta (ej: `<div class="business-card">`).
4. Copia `config_ejemplo.json`, renómbralo (ej: `config_paginaamarilla.json`)
   y reemplaza los selectores por los reales de ese sitio.
5. Corre:

```bash
python main.py procesar "https://directorio-de-empresas.com" --config config_paginaamarilla.json
```

**Tip:** no necesitas rellenar todos los selectores de `selectores_ficha`.
Los que dejes vacíos, el sistema los intenta rellenar solo (busca emails,
teléfonos y enlaces a Facebook/Instagram/WhatsApp automáticamente en el
HTML de la página, sin necesidad de selector).

---

## 4. Interfaz web (recomendado)

En vez de usar comandos, puedes usar un panel visual local:

```bash
pip install -r requirements.txt
python webapp/app.py
```

Esto imprime `Abre tu navegador en: http://localhost:5000`. Ábrelo, y ahí
puedes:

- Pegar la URL del directorio y darle **Procesar directorio**.
- Opcionalmente pegar tu configuración de selectores CSS (Sección 3) en el
  cuadro de "Configuración avanzada" — si lo dejas vacío usa detección
  automática.
- Ver la tabla de resultados y las estadísticas actualizarse en la misma
  página (se refresca sola cada 5 segundos mientras procesa).
- Descargar Excel / CSV / JSON con un clic.
- Botón "Limpiar base de datos" para empezar de cero.

**Notas importantes:**
- Sigue corriendo en tu computador (`localhost`), no en internet público.
  Solo tú puedes verlo, en tu propio navegador.
- El procesamiento corre en segundo plano; si el directorio tiene muchas
  empresas puede tardar varios minutos (hay una pausa entre peticiones
  para no saturar el sitio que estás consultando).
- Si quieres exponerlo en tu red local (ej. para verlo desde el celular
  mientras corre en tu PC), cambia en `webapp/app.py` la línea
  `app.run(debug=True, port=5000)` por `app.run(debug=True, port=5000, host="0.0.0.0")`
  y entra desde otro dispositivo con `http://IP-DE-TU-PC:5000`.

---

## 5. Compartirlo con otras personas (desplegarlo en línea)

Si quieres que tu equipo use la misma herramienta desde un link, sin que
cada uno instale nada, despliega la app web en **Render** (tiene capa
gratuita). Todos comparten la misma base de datos: si alguien procesa un
directorio, los demás ven esos leads al entrar.

### Paso a paso en Render

1. **Sube el proyecto a GitHub** (crea un repositorio nuevo y sube toda
   la carpeta `leadgen/`, incluyendo `Procfile` y `requirements.txt`).
2. Entra a [render.com](https://render.com) y crea una cuenta (puedes usar
   tu cuenta de GitHub para entrar directo).
3. Clic en **New +** → **Web Service** → conecta tu repositorio.
4. Render debería detectar el `Procfile` solo. Si te pide configurarlo a mano:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --chdir webapp --timeout 600 app:app`
5. En la sección **Environment**, agrega estas variables (clic en "Add
   Environment Variable"):
   - `LEADGEN_USER` → el usuario que quieras (ej. `equipo`)
   - `LEADGEN_PASSWORD` → una contraseña que tú definas
   - `SECRET_KEY` → cualquier texto largo y aleatorio
   
   **Esto es importante:** sin `LEADGEN_USER`/`LEADGEN_PASSWORD`, la app
   queda públicamente abierta para cualquiera en internet que encuentre
   la URL — con las variables configuradas, pide usuario y contraseña
   antes de dejar entrar a nadie.
6. En la sección **Disks**, agrega un disco persistente (ej. 1 GB) montado
   en la carpeta del proyecto, para que `leadgen.db` no se borre cada vez
   que Render reinicia el servicio. Sin esto, pierdes los datos guardados
   cada vez que se reinicie o se actualice el servicio.
7. Clic en **Create Web Service**. Cuando termine el despliegue (unos
   minutos), Render te da una URL tipo `https://tu-app.onrender.com`.
   Compártela con tu equipo junto con el usuario/contraseña.

### Limitaciones a tener en cuenta al compartirlo

- **Un procesamiento a la vez:** si dos personas le dan "Procesar
  directorio" al mismo tiempo, uno tiene que esperar a que el otro
  termine (la app avisa "Ya hay un procesamiento en curso").
- **Capa gratuita de Render "duerme"** el servicio si nadie lo usa por un
  rato, y tarda unos segundos en "despertar" en la siguiente visita — es
  normal, no es un error.
- **Nunca subas tu `ANTHROPIC_API_KEY` al código.** Si quieres activar el
  Módulo 7 (IA) en producción, agrégala también como variable de entorno
  en Render, igual que `LEADGEN_USER`.

---

## 6. Comandos de terminal (alternativa a la interfaz web)

### Procesar un directorio (Módulos 1 a 9)
```bash
python main.py procesar "https://directorio.com"
```
Esto descubre las empresas, visita cada ficha, normaliza los datos, valida
qué información tienen, analiza su sitio web (si tienen), calcula el Lead
Score y guarda todo en `leadgen.db` (SQLite). Si vuelves a correrlo sobre
el mismo directorio, **actualiza** los registros existentes en vez de
duplicarlos.

Con observaciones de IA (Módulo 7, opcional):
```bash
export ANTHROPIC_API_KEY="tu-clave-aqui"
python main.py procesar "https://directorio.com" --ia
```
Si no configuras la clave, el sistema sigue funcionando igual: genera una
observación simple basada en reglas en vez de usar IA.

### Exportar resultados (Módulo 10)
```bash
python main.py exportar --formato excel   # genera leads.xlsx
python main.py exportar --formato csv     # genera leads.csv
python main.py exportar --formato json    # genera leads.json
python main.py exportar --formato excel --salida mis_leads.xlsx
```

### Ver el dashboard (Módulo 11)
```bash
python main.py dashboard --abrir
```
Genera `dashboard.html` con las estadísticas (empresas encontradas, sin
web, con web vieja, clientes potenciales, con WhatsApp, con correo) y una
tabla con los mejores leads ordenados por puntaje. `--abrir` lo abre
automáticamente en tu navegador.

---

## 7. ¿Cómo se calcula el Lead Score? (Módulo 8)

| Condición                              | Puntos |
|-----------------------------------------|--------|
| No tiene sitio web                      | +40    |
| Tiene Facebook                          | +15    |
| Tiene Instagram                         | +10    |
| Tiene WhatsApp                          | +10    |
| Tiene teléfono                          | +10    |
| Tiene correo                            | +10    |
| Muchas reseñas (si tu directorio las da)| +20    |
| Su web ya es excelente (puntaje ≥ 80)   | −30    |
| No tiene ninguna red social             | −10    |

Puedes ajustar estos pesos en `leadgen/config.py` (diccionario
`SCORING_WEIGHTS`) sin tocar el resto del código.

**Clasificación automática:**
- 80+ → Cliente potencial muy fuerte
- 50–79 → Cliente potencial bueno
- 25–49 → Cliente potencial moderado
- 0–24 → Baja prioridad

---

## 8. Estructura del proyecto

```
leadgen/
├── main.py                  # CLI: procesar / exportar / dashboard
├── config_ejemplo.json      # Plantilla de selectores CSS
├── requirements.txt
├── leadgen.db                # Se crea solo al primer "procesar"
└── leadgen/
    ├── config.py             # Pesos de scoring y ajustes generales
    ├── discovery.py           # Módulo 2 - Descubrimiento
    ├── scraper.py              # Módulo 3 - Recolección
    ├── normalize.py             # Módulo 4 - Normalización
    ├── validate.py               # Módulo 5 - Validación
    ├── web_analysis.py            # Módulo 6 - Análisis Web
    ├── ai_analysis.py               # Módulo 7 - IA (opcional)
    ├── scoring.py                    # Módulo 8 - Lead Score
    ├── database.py                    # Módulo 9 - Persistencia sin duplicados
    ├── export.py                       # Módulo 10 - Exportación
    ├── dashboard.py                     # Módulo 11 - Dashboard HTML
    └── pipeline.py                       # Orquesta todos los módulos
```

---

## 9. Limitaciones actuales (y cómo extenderlas)

- **Sitios con JavaScript pesado (SPA):** este scraper usa `requests` +
  `BeautifulSoup`, que no ejecutan JavaScript. Si un directorio carga sus
  datos por JS, necesitarás agregar **Playwright** (mencionado en el
  documento original como tecnología recomendada). Te dejo el punto de
  extensión en `discovery.py` y `scraper.py`: reemplaza `requests.get`
  por una carga con Playwright y pásale el HTML renderizado a
  `BeautifulSoup` igual que ahora — el resto del pipeline no cambia.
- **Módulo 12 (aceptar cualquier URL):** ya existe una heurística genérica
  en `discovery.py` (`_heuristica_generica`) que intenta detectar tarjetas
  de empresa sin configuración. Es un punto de partida, no un reemplazo
  completo de un motor de rastreo universal.
- **Reseñas:** el documento menciona "muchas reseñas" como factor de
  score. Como el número de reseñas depende de cada plataforma (Google,
  Facebook, etc.), tendrías que extraerlo en `scraper.py` y pasarlo a
  `scoring.calcular_lead_score(..., numero_resenas=X)`.
- **Automatización futura (Módulo 12):** enviar correos automáticos,
  generar PDFs de diagnóstico, integrar con CRM (HubSpot), etc. no están
  implementados — son las siguientes piezas naturales a construir sobre
  esta base, una vez el pipeline esté validado con datos reales.

---

## 10. Ejemplo de flujo completo

```bash
pip install -r requirements.txt

# 1. Inspecciona el HTML del directorio y llena tu propio config.json
cp config_ejemplo.json config_midirectorio.json
# ... edita config_midirectorio.json con los selectores reales ...

# 2. Corre el pipeline
python main.py procesar "https://midirectorio.com/empresas" --config config_midirectorio.json

# 3. Revisa el dashboard
python main.py dashboard --abrir

# 4. Exporta los mejores leads para tu equipo comercial
python main.py exportar --formato excel --salida leads_para_ventas.xlsx
```
