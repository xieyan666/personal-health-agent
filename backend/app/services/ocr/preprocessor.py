"""Conservative image preparation for scanned medical-report OCR."""

from __future__ import annotations

from typing import Any


class ReportImagePreprocessor:
    """Improve legibility without changing document semantics or OCR geometry."""

    def prepare(self, image: Any) -> Any:
        import cv2

        # Most rendered PDF pages already have the correct orientation.  The
        # OCR engines perform their own orientation classification; here we
        # only improve contrast and reduce scan noise.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        gray = cv2.fastNlMeansDenoising(gray, None, 7, 7, 21)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
