"""OCR provider primitives shared by report parsing engines."""
from dataclasses import dataclass


@dataclass
class OcrLine:
    text: str
    bbox: list[float]
    confidence: float
    page_number: int


@dataclass
class OcrResult:
    engine: str
    lines: list[OcrLine]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def chars(self) -> int:
        return len("".join(line.text for line in self.lines))

    @property
    def confidence(self) -> float:
        return sum(line.confidence for line in self.lines) / len(self.lines) if self.lines else 0.0
