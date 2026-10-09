"""Preprocesado de imagen con OpenCV antes de pasar por OCR.

Funciones pequeñas y puras sobre arrays de numpy (sin leer ni escribir
ficheros) para que cada paso se pueda testear por separado si hace falta.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

MIN_WIDTH_PX = 1800
SHARPNESS_THRESHOLD = 60.0
BLUR_WARNING = "Imagen con baja nitidez"


@dataclass(frozen=True)
class PreprocessResult:
    """Tres variantes de la misma imagen, de menos a más procesada.

    En pruebas con fotos reales ninguna variante gana siempre: el contraste
    local (CLAHE) ayuda con luz desigual pero amplifica ruido de fondo en
    envases de color, y la binarización ayuda con buena luz uniforme pero
    puede romper el texto con brillos o fondos con textura. extractor.py
    prueba OCR en las tres y se queda con la que encuentre más campos, en
    vez de apostar por una sola.
    """

    plain_gray: np.ndarray
    enhanced_gray: np.ndarray
    binary: np.ndarray
    warnings: list[str] = field(default_factory=list)


def resize_if_small(image: np.ndarray, min_width: int = MIN_WIDTH_PX) -> np.ndarray:
    height, width = image.shape[:2]
    if width >= min_width:
        return image
    scale = min_width / width
    return cv2.resize(image, (min_width, round(height * scale)), interpolation=cv2.INTER_CUBIC)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def measure_sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def apply_clahe(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def binarize(gray: np.ndarray) -> np.ndarray:
    denoised = cv2.medianBlur(gray, 3)
    return cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )


def deskew(binary: np.ndarray) -> np.ndarray:
    ink_pixels = np.column_stack(np.where(binary < 255))
    if ink_pixels.shape[0] < 10:
        return binary

    angle = cv2.minAreaRect(ink_pixels)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.1:
        return binary

    height, width = binary.shape[:2]
    center = (width // 2, height // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        binary, rotation_matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def preprocess_image(image: np.ndarray) -> PreprocessResult:
    warnings: list[str] = []

    resized = resize_if_small(image)
    gray = to_grayscale(resized)
    if measure_sharpness(gray) < SHARPNESS_THRESHOLD:
        warnings.append(BLUR_WARNING)

    enhanced = apply_clahe(gray)
    binary = deskew(binarize(enhanced))

    return PreprocessResult(plain_gray=gray, enhanced_gray=enhanced, binary=binary, warnings=warnings)
