"""RapidOCR adapter with the same result contract as PaddleOCR."""

from __future__ import annotations

from typing import Any

from .base import OcrLine, OcrResult


class RapidOcrProvider:
    """A lightweight OCR first pass for rendered report pages."""

    def __init__(self) -> None:
        from rapidocr import RapidOCR

        self._ocr = RapidOCR()

    def extract(self, image: Any, page_number: int) -> OcrResult:
        result = self._ocr(image)
        texts = _as_list(getattr(result, "txts", None))
        scores = _as_list(getattr(result, "scores", None))
        boxes = _as_list(getattr(result, "boxes", None))
        lines: list[OcrLine] = []
        for index, text in enumerate(texts):
            if not str(text).strip():
                continue
            box = boxes[index] if index < len(boxes) else []
            score = scores[index] if index < len(scores) else 0.0
            lines.append(OcrLine(str(text), _flatten_box(box), float(score), page_number))
        return OcrResult(engine="rapidocr", lines=lines)


def _flatten_box(box: Any) -> list[float]:
    """Accept RapidOCR's polygon or rectangle boxes without assuming a version."""
    if hasattr(box, "tolist"):
        box = box.tolist()
    if not box:
        return []
    if isinstance(box[0], (list, tuple)):
        return [float(value) for point in box for value in point]
    return [float(value) for value in box]


def _as_list(value: Any) -> list[Any]:
    """Avoid boolean evaluation of numpy arrays returned by RapidOCR."""
    if value is None:
        return []
    return value.tolist() if hasattr(value, "tolist") else list(value)
