# NutriScan

Prueba técnica Zebra (Full Stack Software Engineer, ref. `260930_ZEBRA_TEC_PRUEBA_TECNICA_FULLSTACK`).

NutriScan recibe la foto (o PDF) de una etiqueta nutricional y extrae energía
(kcal), grasas, hidratos de carbono y proteínas por 100 g/ml **sin usar IA**:
OCR local (Tesseract) + reglas deterministas. El resultado se muestra con un
semáforo nutricional configurable.

## Arranque con Docker (recomendado)

Requiere Docker y Docker Compose.

```bash
docker compose up --build
```

- Frontend: http://localhost:4200
- API: http://localhost:8000 (`/docs` para Swagger, `/health` para el estado del motor OCR)

El backend incluye Tesseract 5 con los paquetes de idioma `spa` y `eng` ya
instalados en la imagen; no hace falta nada más en el host.

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
| `EXTRACTOR` | `tesseract` | Selecciona el extractor en `extraction/factory.py`. Cambiarlo por otro valor (p. ej. un futuro extractor LLM) no requiere tocar API, servicio ni frontend. |
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

Estado actual: 51 tests unitarios/integración pasan sin Tesseract
(`pytest -m "not ocr"`); con Tesseract real (dentro de Docker) pasan también
los 9 end-to-end marcados `@pytest.mark.ocr` sobre las fotos de `samples/`.
En frontend, 22 tests (`ng test`) cubren el servicio de API
(`HttpTestingController`), el interceptor de errores y los componentes de
resultado.

## Endpoints

- `POST /api/v1/labels/extract` — sube un archivo (`multipart/form-data`,
  campo `file`) y devuelve el análisis nutricional.
- `GET /api/v1/traffic-light/config` — devuelve los umbrales del semáforo
  activos, para que el frontend pueda mostrar la leyenda con los límites
  reales.
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
  "checks": [
    {"name": "atwater_energy", "passed": false, "detail": "kcal declaradas 452 vs calculadas: no evaluable sin proteínas"}
  ],
  "warnings": ["Imagen con baja nitidez"],
  "extractor": "tesseract-rules@1.0",
  "processing_ms": 840
}
```

### Significado de los estados por campo

Los cuatro campos (`energy_kcal`, `fat_g`, `carbohydrates_g`, `protein_g`) se
devuelven **siempre**, nunca se omiten en silencio:

- **`ok`**: leído por OCR y conforme con las validaciones (rango plausible,
  coherencia kJ/kcal, Atwater).
- **`doubtful`**: leído, pero con una corrección de OCR aplicada (p. ej.
  `B→8`) o que falla alguna validación. El campo se pinta con color de
  semáforo igualmente, pero con borde discontinuo, icono de aviso y el
  motivo (`reason`) visible.
- **`not_found`**: la palabra clave no aparece en el texto extraído. Sin
  color de semáforo (gris) — nunca verde por defecto.

Un resultado con 1 a 3 campos encontrados sigue siendo un `200` (parcial). La
API solo devuelve un error cuando no hay absolutamente nada aprovechable en
el documento (ver catálogo de errores más abajo).

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
- `doubtful` → color calculado, pero marcado visualmente como dudoso.
- YAML de umbrales inválido (`green_max >= red_min`) → la app no arranca.

`GET /api/v1/traffic-light/config` expone estos umbrales para que el
frontend pueda mostrar la leyenda con los límites reales en vez de tenerlos
hardcodeados.

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
| `OCR_ENGINE_UNAVAILABLE` | 503 | Falta el binario de Tesseract (también visible en `/health`) |
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
  la implementación según `EXTRACTOR`. Sustituir Tesseract por otra cosa
  (incluido un extractor LLM) implica escribir una clase que cumpla el
  `Protocol` y una línea en `factory.py` — cero cambios en API, servicio o
  frontend.
- `app/extraction/tesseract/`: `preprocess.py` (OpenCV) → `ocr.py`
  (pytesseract) → `parser.py` + `synonyms.py` (texto → valores) →
  `validators.py` (rangos, Atwater, kJ↔kcal), compuestos en `extractor.py`.
- `app/domain/`: modelos y semáforo. Sin I/O, sin imports de FastAPI ni de OCR.

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
  qué fallan `2.jpg`, `4.jpg` y `5.jpg` (ver `samples/README.md`) se hizo
  con ayuda del asistente para interpretar la salida real del OCR.

Importante: **no se ha usado ningún LLM como parte del pipeline de
extracción** — toda la extracción es OCR local (Tesseract) + reglas
deterministas, tal como pedía la prueba. El asistente se ha usado solo como
herramienta de desarrollo; cada decisión de diseño, cada línea de código y
cada test se han revisado y se pueden defender.

## Reflexión técnica

### ¿Qué enfoques consideré y por qué este?

- **LLM con visión (Opción A)**: más tolerante a fotos malas, pero añade
  coste por petición, latencia, dependencia externa y respuestas no
  deterministas. Para extraer 4 números de un formato regulado por ley
  (Reglamento UE 1169/2011, orden fijo de nutrientes) es desproporcionado.
- **OCR + reglas (Opción B, elegido)**: determinista, gratis, offline y
  auditable — cada valor lleva el texto exacto del que salió
  (`raw_text`). La validación física (Atwater, kJ/kcal) compensa la
  fragilidad del OCR y da una medida objetiva de "dudoso" en vez de una
  confianza opaca de caja negra.
- **Bases de datos por código de barras (Open Food Facts)**: descartado como
  núcleo porque no es extraer del documento que sube el usuario, pero es una
  buena mejora futura como verificación cruzada.

### Limitaciones actuales

- Fotos con envase muy curvo, reflejos fuertes o letra muy pequeña degradan
  el OCR por debajo de lo recuperable (ver `4.jpg`/`5.jpg` en
  `samples/README.md`).
- Solo español e inglés; los sinónimos (`synonyms.py`) se mantienen a mano.
- La columna "100 g" se elige por posición X de la cabecera; maquetaciones
  muy creativas (o OCR que funde una coma y pierde la unidad `g`, ver
  `2.jpg`) pueden hacer que se elija la columna equivocada sin que ninguna
  validación lo detecte, porque el valor cae dentro de rango plausible.
- Los umbrales de kcal, hidratos y proteínas son una propuesta propia, no un
  estándar oficial (solo grasas lo tiene).
- No distingue sólidos de líquidos; la FSA usa umbrales distintos para
  bebidas y aquí se aplican siempre los de sólido.

### Si fuera a producción

- Extractor híbrido: OCR primero y un extractor LLM solo como respaldo
  cuando la confianza baja de un umbral, detrás del mismo `Protocol
  Extractor` — sin tocar el resto de capas.
- Recorte asistido en el frontend (el usuario marca la tabla) y detección
  automática de la región de interés.
- Persistencia de resultados y corrección manual por el usuario, que
  además sirve como dataset para medir y mejorar el acierto con el tiempo.
- Banco de evaluación con 100+ etiquetas y métrica de acierto por campo en
  CI, en vez de las 8 fotos actuales.
- Procesamiento asíncrono (cola) si el volumen crece, y observabilidad
  (tiempos de procesado, tasa de `doubtful` por campo).

### Preguntas probables en la defensa

- **¿Cómo cambiarías Tesseract por Claude o Gemini?** Una nueva clase que
  cumpla `Extractor` (`extraction/base.py`), una línea en `factory.py`. Cero
  cambios en API, servicio o frontend.
- **¿Qué pasa si el OCR lee "5B g"?** Se corrige `B→8` en contexto numérico,
  el campo queda `doubtful` con el motivo en `reason`, y la validación
  Atwater lo confirma o lo tumba.
- **¿Por qué el semáforo vive en el backend?** Es una regla de negocio; el
  frontend no debe decidir qué umbral hace que algo sea "rojo".
- **¿Por qué un `200` con campos vacíos y no un error?** Un resultado
  parcial sigue siendo útil para el usuario; el error se reserva para
  cuando no hay absolutamente nada aprovechable en el documento.

## Stack

| Capa | Elección |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, pydantic-settings |
| OCR | Tesseract 5 vía pytesseract, idiomas `spa+eng` |
| Imagen | OpenCV (`opencv-python-headless`), Pillow |
| PDF | PyMuPDF |
| Frontend | Angular 18+, componentes standalone, signals |
| Gráficos | SVG propio (anillo de macros y barras de semáforo), sin librerías |
| Tests | pytest + pytest-cov (backend), Jasmine/Karma (frontend) |
