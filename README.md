# NutriScan

NutriScan recibe la foto (o PDF) de una etiqueta nutricional y extrae energía
(kcal), grasas, hidratos de carbono y proteínas por 100 g/ml. La extracción
es **híbrida**: OCR local (Tesseract) + reglas deterministas como camino
principal (gratis, rápido, determinista); si ese camino no encuentra los
cuatro campos con confianza, se repite la extracción con un modelo de IA con
visión (Claude) como respaldo sobre la misma foto. El resultado se muestra
con un semáforo nutricional único del producto y los cuatro valores.

## Arranque con Docker (recomendado)

Requiere Docker y Docker Compose.

```bash
docker compose up --build
```

- Frontend: http://localhost:4200
- API: http://localhost:8000 (`/docs` para Swagger, `/health` para el estado del motor OCR)

El backend incluye Tesseract 5 con los paquetes de idioma `spa` y `eng` ya
instalados en la imagen; no hace falta nada más en el host.

Para que funcione el respaldo de IA necesitas una clave de la API de
Anthropic en la variable `ANTHROPIC_API_KEY` (`docker compose` la pasa al
contenedor si está en tu entorno o en un `.env` en la raíz del repo):

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # o en .env, en la raíz del repo
docker compose up --build
```

Sin esa clave la app sigue arrancando y funcionando: el modo híbrido se
degrada automáticamente a solo-OCR (ver `/health` y la sección de errores).

## Arranque en local (sin Docker)

### Backend

Requiere Python 3.12 y el binario de Tesseract 5 instalado en el sistema con
los idiomas español e inglés (`tesseract-ocr`, `tesseract-ocr-spa`,
`tesseract-ocr-eng` en Debian/Ubuntu; `brew install tesseract tesseract-lang`
en macOS).

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

API en http://localhost:8000.

### Frontend

Requiere Node 22+.

```bash
cd frontend
npm ci
ng serve
```

Frontend en http://localhost:4200, con proxy a `/api` definido en
`proxy.conf.json` apuntando al backend en `:8000`.

### Variables de entorno (backend)

| Variable | Por defecto | Para qué |
|---|---|---|
| `EXTRACTOR` | `hybrid` | Selecciona el extractor en `extraction/factory.py`: `hybrid` (OCR + respaldo de IA, recomendado), `tesseract` (solo OCR, sin red ni coste) o `claude` (solo IA, sin OCR). |
| `ANTHROPIC_API_KEY` | _(ninguna)_ | Clave de la API de Anthropic, leída por el SDK directamente del entorno. Solo hace falta si `EXTRACTOR` es `hybrid` o `claude`; sin ella, `hybrid` se degrada a solo-OCR y `claude` devuelve `OCR_ENGINE_UNAVAILABLE`. |
| `CLAUDE_MODEL` | `claude-opus-5` | Modelo de Claude usado para el respaldo de IA. |
| `MAX_UPLOAD_MB` | `10` | Tamaño máximo de archivo aceptado. |
| `OCR_LANGUAGES` | `spa+eng` | Idiomas pasados a Tesseract. |
| `CORS_ORIGINS` | `["http://localhost:4200"]` | Orígenes permitidos por CORS. |
| `TRAFFIC_LIGHT_CONFIG_PATH` | `backend/config/traffic_light.yaml` | Ruta del YAML de umbrales del semáforo. |

Si `traffic_light.yaml` es inválido (por ejemplo `green_max >= red_min`), la
app **no arranca** y el motivo queda en el log (`app/core/config.py` +
`app/domain/traffic_light.py`).

## Tests

```bash
# Backend
cd backend
pytest                  # todos los tests
pytest -m "not ocr"     # sin Tesseract instalado (unitarios + integración con extractor falso)
pytest -m ocr           # end-to-end con imágenes reales de samples/, requiere Tesseract

# Frontend
cd frontend
npm test
```

Estado actual: 71 tests unitarios/integración pasan sin Tesseract ni clave de
Anthropic (`pytest -m "not ocr"` — el extractor de Claude se testea con el
SDK falseado, nunca contra la API real); con Tesseract real (dentro de
Docker) pasan también los 9 end-to-end marcados `@pytest.mark.ocr` sobre las
fotos de `samples/`. En frontend, 12 tests (`ng test`) cubren el servicio de
API (`HttpTestingController`), el interceptor de errores y el componente de
resultado.

## Endpoints

- `POST /api/v1/labels/extract` — sube un archivo (`multipart/form-data`,
  campo `file`) y devuelve el análisis nutricional.
- `GET /api/v1/traffic-light/config` — devuelve los umbrales del semáforo
  activos. La UI actual no los consume (solo pinta el color ya calculado),
  pero el endpoint se mantiene como parte del contrato público de la API.
- `GET /health` — estado del servicio y del motor OCR (`ok` / `degraded`).

## Esquema de salida

Respuesta de `POST /api/v1/labels/extract` (200, completa o parcial):

```json
{
  "document_id": "b3f1c2a4e5d6",
  "basis": "per_100g",
  "fields": {
    "energy_kcal": {
      "value": 452, "unit": "kcal", "status": "ok", "confidence": 0.91,
      "raw_text": "Valor energético 1891 kJ / 452 kcal", "source": "ocr", "reason": null
    },
    "fat_g": {
      "value": 21.0, "unit": "g", "status": "ok", "confidence": 0.88,
      "raw_text": "Grasas 21 g", "source": "ocr", "reason": null
    },
    "carbohydrates_g": {
      "value": 58.0, "unit": "g", "status": "doubtful", "confidence": 0.54,
      "raw_text": "Hidratos de carbono 5B g", "source": "ocr",
      "reason": "Carácter ambiguo corregido (B→8)"
    },
    "protein_g": {
      "value": null, "unit": "g", "status": "not_found", "confidence": 0.0,
      "raw_text": null, "source": null, "reason": "No se encontró la palabra clave"
    }
  },
  "traffic_light": {
    "energy_kcal": "red", "fat_g": "red", "carbohydrates_g": "amber", "protein_g": null
  },
  "overall_traffic_light": "red",
  "checks": [
    {"name": "atwater_energy", "passed": false, "detail": "kcal declaradas 452 vs calculadas: no evaluable sin proteínas"}
  ],
  "warnings": ["Imagen con baja nitidez"],
  "extractor": "tesseract-rules@1.0",
  "processing_ms": 840
}
```

El campo `extractor` identifica qué motor produjo *ese* resultado concreto:
`tesseract-rules@1.0` (solo OCR, cuando encontró los cuatro campos sin
dudas) o `claude-vision@1.0` (cuando el modo híbrido necesitó el respaldo de
IA sobre la misma foto — en ese caso `warnings` incluye un aviso explícito).
Campos con `source: "claude-vision"` vienen de ese respaldo en vez del OCR.

### Significado de los estados por campo

Los cuatro campos (`energy_kcal`, `fat_g`, `carbohydrates_g`, `protein_g`) se
devuelven **siempre**, nunca se omiten en silencio:

- **`ok`**: leído por OCR y conforme con las validaciones (rango plausible,
  coherencia kJ/kcal, Atwater).
- **`doubtful`**: leído, pero con una corrección de OCR aplicada (p. ej.
  `B→8`) o que falla alguna validación. Lleva el motivo en `reason`.
- **`not_found`**: la palabra clave no aparece en el texto extraído. Sin
  color de semáforo (gris) — nunca verde por defecto.

Un resultado con 1 a 3 campos encontrados sigue siendo un `200` (parcial). La
API solo devuelve un error cuando no hay absolutamente nada aprovechable en
el documento (ver catálogo de errores más abajo).

> La API siempre devuelve el estado, la confianza, el `raw_text` y el
> `reason` de cada campo por separado. La interfaz actual, deliberadamente,
> no los pinta uno a uno: solo muestra el valor de los cuatro campos y un
> semáforo único del producto (ver más abajo), para mantenerla simple.

## Umbrales del semáforo

El semáforo es una regla de dominio pura en el backend
(`app/domain/traffic_light.py`, sin I/O ni imports de FastAPI u OCR); el
frontend únicamente pinta el color que recibe. Los umbrales viven en
[`backend/config/traffic_light.yaml`](backend/config/traffic_light.yaml) y
son configurables sin tocar código.

Umbrales por defecto (por 100 g, sólidos):

| Campo | Verde | Ámbar | Rojo | Sentido | Origen |
|---|---|---|---|---|---|
| Grasas (g) | ≤ 3,0 | > 3,0 y ≤ 17,5 | > 17,5 | menos es mejor | **Semáforo FSA** (Reino Unido) — único con referente oficial |
| Energía (kcal) | ≤ 150 | > 150 y ≤ 400 | > 400 | menos es mejor | Propuesta propia |
| Hidratos (g) | ≤ 15 | > 15 y ≤ 45 | > 45 | menos es mejor | Propuesta propia |
| Proteínas (g) | ≥ 10 | ≥ 3 y < 10 | < 3 | **más es mejor** | Propuesta propia |

Solo grasas tiene un estándar oficial de semáforo (FSA británico, que
también cubre saturadas, azúcares y sal — fuera del alcance de esta prueba).
Kcal, hidratos y proteínas **no tienen semáforo oficial**: son una propuesta
razonable para completar los cuatro campos pedidos, documentada aquí en vez
de presentada como estándar. Proteínas invierte el sentido porque más
proteína es, en general, mejor.

Reglas de negocio fijas, cubiertas por tests (`test_traffic_light.py`,
incluyendo los límites exactos 3,0 g → verde, 17,5 g → ámbar, 17,6 g → rojo):

- `not_found` → sin color, nunca verde por defecto.
- `doubtful` → se calcula igual el color que `ok` (la UI no lo distingue
  visualmente hoy, pero el dato está en la respuesta).
- YAML de umbrales inválido (`green_max >= red_min`) → la app no arranca.

### Semáforo único del producto

Además del color por campo (`traffic_light`), la respuesta incluye
`overall_traffic_light`: un único color para "el producto en conjunto", que
es el que pinta la interfaz (no muestra semáforos por nutriente). La regla
es "el peor color gana" (`app/domain/traffic_light.py::overall_color`, con
tests en `test_traffic_light.py`): si algún nutriente encontrado es rojo, el
producto es rojo; si no, ámbar si alguno lo es; si todos los encontrados son
verdes, verde; si no se encontró ningún campo con color, `null`. Es una
regla propia (razonable, pero no un estándar), igual que los umbrales de
kcal, hidratos y proteínas.

## Catálogo de errores

Formato único de error:

```json
{"error": {"code": "NO_NUTRITION_TABLE", "message": "No se ha encontrado una tabla nutricional en la imagen.", "hint": "Encuadra solo la tabla, con buena luz y sin reflejos."}}
```

| Código | HTTP | Cuándo |
|---|---|---|
| `UNSUPPORTED_FORMAT` | 415 | El tipo real del archivo (por magic bytes, no por extensión) no es JPG/PNG/WEBP/PDF |
| `FILE_TOO_LARGE` | 413 | Supera `MAX_UPLOAD_MB` (10 MB por defecto) |
| `CORRUPT_FILE` | 422 | Pillow/PyMuPDF no pueden abrir el archivo |
| `NO_TEXT_DETECTED` | 422 | El OCR no devuelve texto aprovechable |
| `NO_NUTRITION_TABLE` | 422 | Hay texto pero ningún campo nutricional reconocible |
| `OCR_ENGINE_UNAVAILABLE` | 503 | Falta el binario de Tesseract, o (con `EXTRACTOR=claude`) falta `ANTHROPIC_API_KEY` (también visible en `/health`) |
| `INTERNAL_ERROR` | 500 | Cualquier otro fallo; se devuelve `request_id` para soporte y la traza queda solo en el log del servidor |

Un `exception_handler` global (`app/api/errors.py`) traduce cada excepción
de dominio a este formato; cualquier excepción no prevista se captura como
`INTERNAL_ERROR` sin filtrar la traza al cliente.

En el frontend, un interceptor HTTP traduce `error.code` a un banner con
botón de reintento; hay validación previa de tipo y tamaño en el cliente
(el servidor valida igual, por si se la saltan), timeout de 30 s, y estados
de pantalla explícitos (`idle | uploading | processing | success | partial | error`).

## Arquitectura

```
api/  →  services/  →  extraction/ (Protocol Extractor)
                    →  domain/traffic_light.py (clasificador puro)
```

- `app/api/`: endpoints y esquemas Pydantic. Cero lógica de negocio.
- `app/services/label_analysis.py`: orquesta extractor + semáforo.
- `app/extraction/base.py`: `Extractor` como `Protocol`; `factory.py` elige
  la implementación según `EXTRACTOR`. Añadir un extractor nuevo implica
  escribir una clase que cumpla el `Protocol` y una línea en `factory.py` —
  cero cambios en API, servicio o frontend. Hoy hay tres: `tesseract`,
  `claude` e `hybrid` (compone los otros dos).
- `app/extraction/tesseract/`: `preprocess.py` (OpenCV) → `ocr.py`
  (pytesseract) → `parser.py` + `synonyms.py` (texto → valores), compuestos
  en `extractor.py`.
- `app/extraction/claude/extractor.py`: envía la foto a Claude con visión
  pidiendo salida JSON estructurada con los cuatro campos; es el único
  módulo que conoce el SDK de Anthropic.
- `app/extraction/hybrid.py`: si el OCR encuentra los cuatro campos sin
  dudas, se queda con ese resultado; si no, repite la extracción completa
  con Claude. Si el respaldo de IA falla (sin clave, sin red), se degrada al
  resultado parcial del OCR en vez de romper la petición.
- `app/extraction/magic_bytes.py`: detección de tipo real por magic bytes,
  compartida por los extractores.
- `app/domain/`: modelos, semáforo y validadores físicos (`validators.py`,
  `nutrition_checks.py`: rango plausible, Atwater, kJ/kcal, suma de macros).
  Todo puro, sin I/O ni imports de FastAPI, OCR o el SDK de Anthropic — por
  eso lo reutilizan tanto el extractor OCR como el de IA: el criterio de
  "dudoso" es el mismo sin importar de dónde vino el valor.

## `samples/`

8 fotos propias de etiquetas reales (productos comerciales, sin datos
personales) con su `expected.json` y el acierto medido con Tesseract real:
ver [`samples/README.md`](samples/README.md) para el detalle foto a foto,
qué funciona bien y qué limitaciones se encontraron.

## Cómo se ha usado la IA en el desarrollo

Este proyecto se ha construido con ayuda de un asistente de codificación
(Claude Code), usado así:

- **Planificación de arquitectura**: la separación en capas
  (`api → services → extraction/domain`), el contrato `Extractor` como
  `Protocol`, y el esquema de estados `ok/doubtful/not_found` se discutieron
  y documentaron antes de escribir código, con el asistente generando
  opciones y trade-offs que yo decidí.
- **Generación de esqueleto**: módulos, firmas de función y estructura de
  tests se generaron con el asistente a partir de ese diseño ya acordado.
- **Propuesta de casos de test**: los fixtures de texto OCR "sucio"
  (`tests/fixtures/*.txt`) y los casos límite del semáforo (3,0/17,5/17,6)
  se propusieron con el asistente y se verificaron contra el comportamiento
  real.
- **Medición de acierto sobre `samples/`**: el análisis campo a campo de por
  qué fallan `2.jpg`, `4.jpg` y `5.jpg` se hizo con
  ayuda del asistente para interpretar la salida real del OCR, y esa
  medición fue la que motivó añadir el respaldo de IA descrito abajo.

El asistente se ha usado como herramienta de desarrollo en todo el proyecto;
cada decisión de diseño, cada línea de código y cada test se han revisado y
se pueden defender.

## Uso de IA en el producto (no solo en el desarrollo)

A diferencia del punto anterior —el asistente que ayudó a *escribir* el
código—, esta sección es distinta: el propio NutriScan **llama a la API de
Claude en tiempo de ejecución** como parte del pipeline de extracción,
cuando `EXTRACTOR=hybrid` (el valor por defecto) o `EXTRACTOR=claude`. El
OCR local sigue siendo el camino principal — gratis, rápido, auditable —; la
IA solo entra cuando ese camino no da un resultado completo y fiable, sobre
el mismo `Protocol Extractor`, sin que el servicio ni el frontend sepan qué
motor respondió. El razonamiento completo de esta decisión está en la
reflexión técnica, más abajo.

## Reflexión técnica

### ¿Qué enfoques consideré y por qué este?

- **LLM con visión (Opción A)**: más tolerante a fotos malas, pero añade
  coste por petición, latencia, dependencia externa y respuestas no
  deterministas. Para extraer 4 números de un formato regulado por ley
  (Reglamento UE 1169/2011, orden fijo de nutrientes), usarlo como único
  camino es desproporcionado.
- **OCR + reglas (Opción B)**: determinista, gratis, offline y auditable —
  cada valor lleva el texto exacto del que salió (`raw_text`). La
  validación física (Atwater, kJ/kcal) compensa la fragilidad del OCR y da
  una medida objetiva de "dudoso" en vez de una confianza opaca de caja
  negra. Es el diseño con el que arrancó el proyecto.
- **Híbrido: B primero, A como respaldo (elegido)**: tras medir la Opción B
  sola sobre fotos reales propias y obtener sólo un 28% de aciertos, la pregunta
  pasó de "¿cuál de las dos opciones?" a "¿cómo conservo las ventajas de B
  sin entregar un sistema que falla en fotos reales?". El híbrido responde
  eso: la ruta gratis sigue siendo la primera y la que se usa
  cuando funciona, y solo cuando no da un resultado completo y fiable se
  repite la extracción con IA sobre la misma foto. El coste y la latencia
  extra solo se pagan cuando de verdad hacen falta.


### Limitaciones actuales

- Fotos con envase muy curvo, reflejos fuertes o letra muy pequeña degradan
  el OCR por debajo de lo recuperable.
- Solo español e inglés; los sinónimos (`synonyms.py`) se mantienen a mano.
- La columna "100 g" se elige por posición X de la cabecera; maquetaciones
  muy creativas (o OCR que funde una coma y pierde la unidad `g`, ver
  `2.jpg`) pueden hacer que se elija la columna equivocada sin que ninguna
  validación lo detecte, porque el valor cae dentro de rango plausible.
- Los umbrales de kcal, hidratos y proteínas son una propuesta propia, no un
  estándar oficial.
- No distingue sólidos de líquidos; la FSA usa umbrales distintos para
  bebidas y aquí se aplican siempre los de sólido.
- El respaldo de IA depende de un servicio externo: tiene coste por
  petición, latencia adicional y necesita red y una clave de API — por eso
  el modo `hybrid` se degrada a solo-OCR en vez de fallar cuando esa clave
  no está configurada.
- La condición para activar el respaldo es simple a propósito ("¿los cuatro
  campos están en `ok`?"): no compara la confianza de Claude contra la del
  OCR campo a campo, así que no mezcla lo mejor de cada fuente dentro de una
  misma foto. Es una limitación conocida, no un olvido.
- `overall_traffic_light` usa "el peor color gana": un solo nutriente en
  rojo tiñe todo el producto de rojo, aunque los otros tres sean verdes. Es
  una regla deliberadamente simple (y propia, no un estándar) a cambio de
  dar un veredicto único y fácil de entender en la interfaz.


## Stack

| Capa | Elección |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, pydantic-settings |
| OCR | Tesseract 5 vía pytesseract, idiomas `spa+eng` |
| IA (respaldo) | SDK oficial `anthropic`, modelo Claude con visión (`CLAUDE_MODEL`, por defecto `claude-opus-5`), salida JSON estructurada |
| Imagen | OpenCV (`opencv-python-headless`), Pillow |
| PDF | PyMuPDF |
| Frontend | Angular 18+, componentes standalone, signals |
| UI de resultado | Semáforo único del producto + los 4 valores, sin librerías de gráficos |
| Tests | pytest + pytest-cov (backend), Jasmine/Karma (frontend) |
