"""Lazy CPU-safe PaddleOCR provider for scanned document pages."""
from __future__ import annotations
from threading import Lock
from typing import Any
from .base import OcrLine, OcrResult


class PaddleOcrProvider:
    _instance: Any = None
    _lock = Lock()

    @classmethod
    def _ocr(cls) -> Any:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    import os

                    # PaddleOCR 3.7 defaults to PaddleX's MKLDNN backend on
                    # CPU.  PaddlePaddle 3.3.1 can reject some OCR model PIR
                    # attributes there, so use the standard CPU predictor.
                    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
                    from paddleocr import PaddleOCR
                    # PDF pages are rendered upright by PyMuPDF.  Disable the
                    # optional orientation/unwarping pipelines so a normal
                    # health report loads only detection + recognition models.
                    cls._instance = PaddleOCR(
                        lang="ch",
                        use_doc_orientation_classify=False,
                        use_doc_unwarping=False,
                        use_textline_orientation=False,
                    )
        return cls._instance

    def extract(self, image: Any, page_number: int) -> OcrResult:
        lines: list[OcrLine] = []
        for result in self._ocr().predict(image):
            payload = result.json if hasattr(result, "json") else result
            if callable(payload):
                payload = payload()
            data = payload.get("res", payload) if isinstance(payload, dict) else {}
            texts = _as_list(data.get("rec_texts"))
            scores = _as_list(data.get("rec_scores"))
            boxes = _as_list(data.get("rec_boxes"))
            for text, score, box in zip(texts, scores, boxes):
                if text:
                    lines.append(OcrLine(str(text), [float(v) for v in box], float(score), page_number))
        return OcrResult(engine="paddleocr", lines=lines)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value.tolist() if hasattr(value, "tolist") else list(value)
