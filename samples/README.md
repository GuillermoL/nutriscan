# Banco de pruebas (samples/)

8 fotos propias de etiquetas nutricionales reales (productos comerciales,
sin datos personales), usadas para dos cosas:

1. Afinar el preprocesado (`extraction/tesseract/preprocess.py`) con casos difíciles de verdad.
2. Medir el acierto del sistema: `tests/integration/test_e2e_ocr.py` (marcado `@pytest.mark.ocr`)
   compara la extracción real contra `expected.json` y exige un mínimo del 70% de acierto por foto.

## Resultado medido (con Tesseract real, dentro de Docker)

**9/32 campos correctos (28%)** sobre las 8 fotos, con tolerancia del 5%. Es una
cifra honesta para fotos reales y deliberadamente difíciles (varias de baja
resolución, fondos ilustrados o con reflejos) — no un escaparate de casos fáciles.

| Foto | Qué demuestra | Resultado |
|---|---|---|
| `1.jpg` (palomitas, columnas 100g+ración) | Elección de columna | 2/4 — kcal y grasas correctos |
| `2.jpg` (tomate frito, fondo ilustrado pequeño) | Caso difícil / fondo con ruido | 0/4 — ver limitación de columna más abajo |
| `3.jpg` (queso curado, subcampos saturadas/azúcares) | Exclusión de subcampos | 1/4 — proteínas correctas |
| `4.jpg` (cereales, foto exterior con bokeh) | Caso difícil / foco y fondo | 0/4 — `NO_NUTRITION_TABLE` (falla honesto) |
| `5.jpg` (paquete verde, close-up) | Caso difícil / nitidez | 0/4 — `NO_TEXT_DETECTED` (falla honesto) |
| `6.jpg` (paquete verde #2, con calcio) | Camino feliz, una sola columna | 2/4 — kcal y grasas correctos |
| `7.jpg` (bilingüe ES/PT, valores "&lt;0,5 g") | Sinónimos + valores límite | 2/4 — kcal y proteínas correctas |
| `8.jpg` (margarina, columnas 100g+ración, "&lt;0,5 g") | Columnas + valor límite + coma perdida | 2/4 — kcal e hidratos correctos |

## Qué funciona bien

- **Energía**: 4/8 fotos exactas (con tolerancia de redondeo kJ→kcal).
- **Multi-variante de preprocesado**: probar la imagen en gris plano, gris+CLAHE
  y binarizada, y quedarnos con la que más campos encuentra, rescata fotos que
  con una sola estrategia fallaban por completo (`1.jpg` pasó de 0 a 2 campos
  correctos al añadir la variante sin CLAHE).
- **Coma decimal perdida**: cuando el OCR funde "0,5 g" en "05g", se interpreta
  como 0,5 y no como 5 (bug real encontrado y corregido en `8.jpg`).

## Limitaciones encontradas (reales, con ejemplo)

- **Columna equivocada sin aviso**: en `2.jpg`, el OCR funde la coma de la
  columna "100 g" ("3,3g" → "339", sin el `g` pegado) así que el regex no la
  reconoce y cae a la siguiente columna que sí conserva la unidad ("1,7g" →
  leído como "17g" por pérdida de la coma). El resultado (`fat_g = 17.0`) pasa
  los rangos plausibles y Atwater no es evaluable (faltan hidratos/proteínas),
  así que queda marcado `ok` en vez de `doubtful`. Es la limitación más
  importante del banco: el validador de rango no atrapa un valor "plausible
  pero de la columna incorrecta".
- **Pérdida de dígitos del OCR**: en `3.jpg`, "31 g" se lee "3g" (falta un
  dígito). No es un fallo del parser — Tesseract directamente no ve ese
  carácter en esa foto concreta.
- **Fondos ilustrados o fotos borrosas** (`4.jpg`, `5.jpg`): el sistema prefiere
  fallar explícitamente (`NO_NUTRITION_TABLE` / `NO_TEXT_DETECTED`) antes que
  inventar un valor. Es el comportamiento buscado, aunque baja el acierto.

## Cómo añadir más fotos

1. Guarda la foto aquí (p. ej. `9.jpg`).
2. Añade una entrada en `expected.json` con los cuatro valores reales por 100 g.
3. Corre `pytest -m ocr` (requiere Tesseract instalado, o usa el contenedor Docker:
   `docker compose up -d backend` y sube la foto a `/api/v1/labels/extract`).
