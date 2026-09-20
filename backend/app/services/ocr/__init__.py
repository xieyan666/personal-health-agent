"""OCR engine adapters used by the health-report parser."""

from .base import OcrLine, OcrResult
from .paddleocr_provider import PaddleOcrProvider
from .rapidocr_provider import RapidOcrProvider

__all__ = ["OcrLine", "OcrResult", "PaddleOcrProvider", "RapidOcrProvider"]
