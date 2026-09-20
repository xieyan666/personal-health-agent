"""Hybrid Docling parsing and deterministic extraction for health reports.

The service stops at auditable structured medical data.  It never calls an LLM,
never makes a diagnosis, and uses OCR only as a document-reading fallback for
scan/image regions that have no native PDF text layer.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import PurePosixPath
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.database import AsyncSessionFactory
from backend.app.core.minio import get_minio_client
from backend.app.exceptions import NotFoundError, ServiceError, ValidationError
from backend.app.models import HealthCheckIndicator, HealthCheckReport
from backend.app.schemas.health_reports import HealthCheckReportCreate
from backend.app.services.ocr import PaddleOcrProvider, RapidOcrProvider
from backend.app.services.ocr.base import OcrLine, OcrResult
from backend.app.services.ocr.preprocessor import ReportImagePreprocessor


ALLOWED_REPORT_SUFFIXES = {".pdf"}


class ReportParseError(ServiceError):
    """A safe, user-facing report parsing failure."""


@dataclass(frozen=True)
class ParsedIndicator:
    item_name: str
    code: str
    value: float | None
    value_text: str
    unit: str | None
    reference_min: float | None
    reference_max: float | None
    reference_text: str | None
    flag: str
    category: str
    source_page: int | None = None
    source_type: str = "text"
    confidence: float | None = None
    method: str | None = None


@dataclass(frozen=True)
class ParsedReport:
    report_id: UUID
    raw_text: str
    items: list[ParsedIndicator]
    parse_mode: str
    pages: int
    ocr_used: bool
    text_blocks: int
    tables: int
    pictures: list[dict[str, object]]
    warnings: list[str]
    parse_method: str = "docling_hybrid"
    diagnostics: dict[str, object] | None = None


@dataclass(frozen=True)
class IndicatorDefinition:
    code: str
    item_name: str
    aliases: tuple[str, ...]
    category: str


INDICATOR_DEFINITIONS = (
    # Used only as a category/category hint for known metrics.  Extraction no
    # longer filters on this table; any row with a name and a value is kept.
    IndicatorDefinition("fasting_glucose", "空腹血糖", ("空腹血糖", "血糖(空腹)", "FPG"), "血糖"),
    IndicatorDefinition("triglyceride", "甘油三酯", ("甘油三酯", "TG"), "血脂"),
    IndicatorDefinition("ldl_c", "LDL-C", ("LDL-C", "低密度脂蛋白胆固醇", "低密度脂蛋白"), "血脂"),
    IndicatorDefinition("hdl_c", "HDL-C", ("HDL-C", "高密度脂蛋白胆固醇", "高密度脂蛋白"), "血脂"),
    IndicatorDefinition("total_cholesterol", "总胆固醇", ("总胆固醇", "TC"), "血脂"),
    IndicatorDefinition("alt", "ALT", ("ALT", "谷丙转氨酶"), "肝功能"),
    IndicatorDefinition("ast", "AST", ("AST", "谷草转氨酶"), "肝功能"),
    IndicatorDefinition("uric_acid", "尿酸", ("尿酸", "UA"), "肾功能"),
    IndicatorDefinition("creatinine", "肌酐", ("肌酐", "Cr"), "肾功能"),
    IndicatorDefinition("hemoglobin", "血红蛋白", ("血红蛋白", "HGB"), "血常规"),
    IndicatorDefinition("bmi", "BMI", ("BMI", "体质指数"), "基础指标"),
)

# Flatten for hint lookup: any alias found in a discovered name yields a
# category hint, but never blocks the row from being kept.
_KNOWN_HINTS: dict[str, tuple[str, str]] = {}
for _definition in INDICATOR_DEFINITIONS:
    for _alias in _definition.aliases:
        _KNOWN_HINTS[_alias.lower()] = (_definition.code, _definition.category)
del _definition, _alias

NUMBER = r"(?:\d+(?:\.\d+)?)"
RANGE_RE = re.compile(rf"(?:(?P<min>{NUMBER})\s*(?:-|~|～|—|至)\s*(?P<max>{NUMBER})|(?P<op>[<>≤≥])\s*(?P<bound>{NUMBER}))")
UNIT_RE = re.compile(
    r"(?P<unit>mmol/L|umol/L|μmol/L|U/L|IU/L|uIU/L|mIU/L|g/L|g/dL|mg/L|mg/dL|ng/mL|ng/ml|pg/mL|pmol/L|fmol/L|mL/min|bpm|%|10\^?\d+/L)",
    re.IGNORECASE,
)


def _normalise_line(line: str) -> str:
    # Preserve ``|`` so the table-row extractor can still split cells.  Only
    # collapse general whitespace.
    return re.sub(r"\s+", " ", line).strip()


def _flag_from_line(line: str, value: float | None, minimum: float | None, maximum: float | None) -> str:
    marker = line.upper()
    # Only accept a standalone laboratory flag.  A substring check would treat
    # ordinary prose or Markdown as a high/low marker and create false alerts.
    if "↑" in marker or "偏高" in marker or re.search(r"(?:^|[\s|])(?:H|HIGH)(?:$|[\s|])", marker):
        return "high"
    if "↓" in marker or "偏低" in marker or re.search(r"(?:^|[\s|])(?:L|LOW)(?:$|[\s|])", marker):
        return "low"
    if value is not None and maximum is not None and value > maximum:
        return "high"
    if value is not None and minimum is not None and value < minimum:
        return "low"
    return "normal" if value is not None else "unknown"


def _range_values(match: re.Match[str] | None) -> tuple[float | None, float | None, str | None]:
    if match is None:
        return None, None, None
    if match.group("bound") is not None:
        bound = float(match.group("bound")); op = match.group("op")
        return (bound, None, match.group(0)) if op in {">", "≥"} else (None, bound, match.group(0))
    return float(match.group("min")), float(match.group("max")), match.group(0)


class ReportIndicatorExtractor:
    """Generic, vocabulary-free indicator discovery.

    The extractor inspects every line / table-row of the parser output, keeps
    anything that has both a candidate name and a value, and never rejects a
    row for being outside a curated list.  Known aliases only provide a
    category hint so the previously recognised metrics keep a sensible
    category label without acting as a whitelist.
    """

    def extract(
        self,
        raw_text: str,
        source_type: str = "text",
        ocr_used: bool = False,
        source_page: int | None = None,
    ) -> list[ParsedIndicator]:
        items: list[ParsedIndicator] = []
        seen: set[tuple[str, str, int | None]] = set()
        effective_source_type = "ocr" if ocr_used and source_type == "image" else source_type
        for raw_line in raw_text.splitlines():
            line = _normalise_line(raw_line)
            if not line:
                continue
            if "|" in line:
                item = self._parse_table_row(line, effective_source_type, source_page)
                if item is not None:
                    key = (item.item_name, item.value_text, item.source_page)
                    if key not in seen:
                        items.append(item)
                        seen.add(key)
                continue
            item = self._parse_text_row(line, effective_source_type, source_page)
            if item is not None:
                key = (item.item_name, item.value_text, item.source_page)
                if key not in seen:
                    items.append(item)
                    seen.add(key)
        return items

    def _make_code(self, name: str) -> str:
        return f"report_metric_{hashlib.sha1(name.encode('utf-8')).hexdigest()[:12]}"

    def _hint(self, name: str) -> tuple[str, str, str]:
        for alias, (code, category) in _KNOWN_HINTS.items():
            if alias in name.lower():
                return code, category, name
        return self._make_code(name), "其他指标", name

    def _parse_value(self, raw: str) -> tuple[float | None, str]:
        """Return (numeric_value_or_None, kept_raw_text).

        raw may be 1.45, <4.0, >=90, 阴性, 弱阳性, ++, ++++ etc. We keep the
        raw text untouched so audit logs / DB rows reflect the printed form,
        and only populate the numeric field when a defensible number exists.
        """
        if raw is None:
            return None, ""
        text = raw.strip()
        if not text:
            return None, ""
        # Detect relations like <, <=, >, >=, =, ≤, ≥ so the symbol survives.
        relation = re.match(r"^\s*([<>≤≥]=?|=)\s*", text)
        remainder = text[relation.end():] if relation else text
        number_match = re.match(r"^\s*(\d+(?:\.\d+)?)", remainder)
        if relation and number_match:
            numeric = float(number_match.group(1))
            return numeric, text
        plain = re.match(r"^\s*(\d+(?:\.\d+)?)\s*$", text)
        if plain:
            return float(plain.group(1)), text
        return None, text

    def _parse_table_row(
        self,
        line: str,
        effective_source_type: str,
        source_page: int | None,
    ) -> ParsedIndicator | None:
        cells = [_normalise_line(cell) for cell in line.strip().strip("|").split("|")]
        cells = [cell for cell in cells if cell and not re.fullmatch(r"[-: ]+", cell)]
        if len(cells) < 2:
            return None
        # Skip table header rows.
        joined = " ".join(cells)
        if any(header in joined for header in (
            "项目名称", "检验项目", "检查项目", "检测项目", "项目", "结果", "检验结果", "检测结果",
            "测定结果", "参考值", "参考区间", "参考范围", "正常范围", "单位", "计量单位",
            "提示", "标志", "异常提示", "检测方法", "检验方法", "试验方法", "序号",
        )):
            return None
        # Find the value cell: the first cell that contains a numeric symbol
        # (e.g. 5.36), a relational form (<4.0, ≥90), or a textual flag
        # (阴性, 阳性, 弱阳性, 未检出, +, ++, +++).
        value_index = self._detect_value_index(cells, start=1)
        if value_index is None:
            return None
        # Pick the descriptive item name: the last cell to the left of the
        # value that is not a serial number or a short code.
        name_candidates = [
            cell for cell in cells[:value_index]
            if not re.fullmatch(r"\d+", cell)
            and not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{0,15}", cell)
        ]
        if not name_candidates:
            return None
        item_name = name_candidates[-1].strip()
        if not item_name or len(item_name) > 60:
            return None
        value_raw = cells[value_index]
        numeric_value, kept_value_text = self._parse_value(value_raw)
        # Reference range: the first cell to the right of the value that
        # matches a numeric range or a relational form.
        reference_text: str | None = None
        minimum: float | None = None
        maximum: float | None = None
        for index in range(value_index + 1, len(cells)):
            cell = cells[index]
            if not cell or re.fullmatch(r"[-: ]+", cell):
                continue
            range_match = RANGE_RE.fullmatch(cell.replace(" ", ""))
            if range_match is None:
                # Allow a unit like g/L to also be present here.
                if UNIT_RE.fullmatch(cell) and reference_text is None:
                    continue
                if not UNIT_RE.fullmatch(cell) and not re.fullmatch(r"[<>≤≥=]", cell):
                    continue
            minimum, maximum, reference_text = _range_values(range_match)
            if reference_text:
                break
        if reference_text is None:
            # Some hospital exports use a single combined cell like 40.0-55.0
            # without a value column boundary. Try any cell containing '-'.
            for index in range(value_index + 1, len(cells)):
                cell = cells[index]
                if re.search(r"\d", cell) and re.search(r"[-~～—至]", cell):
                    range_match = RANGE_RE.search(cell.replace(" ", ""))
                    if range_match is not None:
                        minimum, maximum, reference_text = _range_values(range_match)
                        break
        # Unit: any cell matching the unit vocabulary, in any position to the
        # right of the value (common order: value, unit, range, method).
        unit: str | None = None
        for cell in cells[value_index + 1:]:
            unit_match = UNIT_RE.fullmatch(cell)
            if unit_match is not None:
                unit = unit_match.group("unit")
                break
            unit_match = UNIT_RE.search(cell)
            if unit_match is not None and not re.fullmatch(r"\d", cell):
                unit = unit_match.group("unit")
                break
        # Method: a free-form short string after the range (e.g. "电化学法",
        # "免疫比浊法", "速率法", "酶法").  Capture the first non-range cell.
        method: str | None = None
        for index in range(value_index + 1, len(cells)):
            cell = cells[index]
            if not cell or cell == unit or cell == reference_text:
                continue
            if re.fullmatch(r"\d", cell) or re.fullmatch(r"[<>≤≥]\s*\d+", cell):
                continue
            if re.fullmatch(r"[-: ]+", cell):
                continue
            method = cell
            break
        # Status flag: a 1-char +/- or "high"/"low"/"normal" cell anywhere.
        flag = self._detect_flag(cells, numeric_value, minimum, maximum)
        code, category, _ = self._hint(item_name)
        return ParsedIndicator(
            item_name=item_name,
            code=code,
            value=numeric_value,
            value_text=kept_value_text,
            unit=unit,
            reference_min=minimum,
            reference_max=maximum,
            reference_text=reference_text,
            flag=flag,
            category=category,
            source_type=effective_source_type,
            source_page=source_page,
            confidence=None,
            method=method,
        )

    def _parse_text_row(
        self,
        line: str,
        effective_source_type: str,
        source_page: int | None,
    ) -> ParsedIndicator | None:
        """Pick a candidate indicator from a free-text line (e.g. OCR layout)."""
        # Reject lines that are clearly narrative (e.g. a long sentence). A
        # report row tends to be short, contain a value-like token, and have
        # no sentence punctuation beyond the value.
        if len(line) > 80 or line.count("。") or line.count("，") > 2:
            return None
        value_match = re.search(r"(?:[<>≤≥]=?\s*)?(?:\d+(?:\.\d+)?|阴性|阳性|弱阳性|未检出|[+]+)", line)
        if value_match is None:
            return None
        value_raw = value_match.group(0)
        numeric_value, kept_value_text = self._parse_value(value_raw)
        before_value = line[:value_match.start()].rstrip(" ：:")
        after_value = line[value_match.end():]
        # Item name: the trailing contiguous text segment of `before_value`,
        # stopping at any of the alias separators common in OCR outputs.
        name_match = re.search(r"([\u4e00-\u9fffA-Za-z0-9()/·.\-]{2,40})\s*$", before_value)
        if name_match is None:
            return None
        item_name = name_match.group(1).strip()
        if len(item_name) < 2:
            return None
        range_match = RANGE_RE.search(after_value.replace(" ", ""))
        minimum, maximum, reference_text = _range_values(range_match)
        unit_match = UNIT_RE.search(after_value) or UNIT_RE.search(before_value)
        unit = unit_match.group("unit") if unit_match else None
        flag = _flag_from_line(line, numeric_value, minimum, maximum)
        code, category, _ = self._hint(item_name)
        return ParsedIndicator(
            item_name=item_name,
            code=code,
            value=numeric_value,
            value_text=kept_value_text,
            unit=unit,
            reference_min=minimum,
            reference_max=maximum,
            reference_text=reference_text,
            flag=flag,
            category=category,
            source_type=effective_source_type,
            source_page=source_page,
            confidence=None,
        )

    def _detect_value_index(self, cells: list[str], start: int) -> int | None:
        for index in range(start, len(cells)):
            cell = cells[index]
            if not cell:
                continue
            if re.fullmatch(r"\d+(?:\.\d+)?", cell):
                return index
            if re.fullmatch(r"[<>≤≥]\s*\d+(?:\.\d+)?", cell):
                return index
            if re.fullmatch(r"[<>≤≥]=?\s*\d+(?:\.\d+)?", cell):
                return index
            if cell in {"阴性", "阳性", "弱阳性", "未检出"}:
                return index
            if re.fullmatch(r"\++", cell):
                return index
            if re.fullmatch(r"-{1,3}", cell):
                return index
            if re.fullmatch(r"±?\d+", cell):
                return index
        return None

    def _detect_flag(
        self,
        cells: list[str],
        value: float | None,
        minimum: float | None,
        maximum: float | None,
    ) -> str:
        joined = " | ".join(cells).lower()
        if "↑" in joined or "偏高" in joined or "high" in joined or "h" in joined.lower().split():
            return "high"
        if "↓" in joined or "偏低" in joined or "low" in joined or "l" in joined.lower().split():
            return "low"
        if value is not None and maximum is not None and value > maximum:
            return "high"
        if value is not None and minimum is not None and value < minimum:
            return "low"
        return "normal" if value is not None else "unknown"


class GenericReportIndicatorExtractor(ReportIndicatorExtractor):
    """Generic, vocabulary-independent extractor for report rows.

    The curated definitions above improve naming for known metrics, while this
    extractor intentionally keeps any structurally reliable table item found in
    a report instead of applying a medical whitelist.
    """

    pass


class ReportParserService:
    """Hybrid Docling parser for native-text, table, scanned and mixed PDFs."""

    def __init__(self, extractor: ReportIndicatorExtractor | None = None) -> None:
        self.extractor = extractor or GenericReportIndicatorExtractor()

    @staticmethod
    def _render_pdf_pages(data: bytes, dpi: int = 350) -> list[object]:
        """Render source PDF pages for OCR, including image-only scan PDFs."""
        try:
            import fitz
            import numpy as np
            import cv2
        except ImportError as exc:
            raise ReportParseError("扫描 PDF 渲染组件尚未就绪") from exc
        document = fitz.open(stream=data, filetype="pdf")
        scale = dpi / 72
        pages: list[object] = []
        try:
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
                pages.append(cv2.cvtColor(image, cv2.COLOR_RGB2BGR) if pixmap.n == 3 else image)
        finally:
            document.close()
        return pages

    @staticmethod
    def _layout_rows(lines: list[OcrLine]) -> str:
        """Recover OCR table-like rows from positioned words without a table model."""
        positioned: list[tuple[float, float, OcrLine]] = []
        for line in lines:
            if len(line.bbox) < 4:
                continue
            xs = line.bbox[0::2]
            ys = line.bbox[1::2]
            positioned.append((sum(ys) / len(ys), min(xs), line))
        if not positioned:
            return ""
        positioned.sort(key=lambda item: (item[0], item[1]))
        rows: list[list[tuple[float, OcrLine]]] = []
        # At 350 DPI, a tolerance of 22px joins cells on the same report row
        # while keeping neighbouring result rows separate.
        for y, x, line in positioned:
            if not rows or abs(y - sum(cell_y for cell_y, _ in rows[-1]) / len(rows[-1])) > 22:
                rows.append([(y, line)])
            else:
                rows[-1].append((y, line))
        rendered: list[str] = []
        for row in rows:
            cells = [line.text.strip() for _, line in sorted(row, key=lambda item: min(item[1].bbox[0::2])) if line.text.strip()]
            if len(cells) >= 2:
                rendered.append("| " + " | ".join(cells) + " |")
        return "\n".join(rendered)

    def _run_scanned_ocr(self, data: bytes, pages: int) -> tuple[OcrResult, OcrResult, OcrResult]:
        """Run high-resolution RapidOCR then PaddleOCR when Rapid quality is low."""
        rendered_pages = self._render_pdf_pages(data, dpi=350)
        preprocessor = ReportImagePreprocessor()
        rapid = RapidOcrProvider()
        paddle = PaddleOcrProvider()
        rapid_lines: list[OcrLine] = []
        paddle_lines: list[OcrLine] = []
        for page_number, image in enumerate(rendered_pages, start=1):
            prepared = preprocessor.prepare(image)
            rapid_lines.extend(rapid.extract(prepared, page_number).lines)
        rapid_result = OcrResult(engine="rapidocr", lines=rapid_lines)
        # Always run the independent PaddleOCR path for a scanned report.  The
        # provider keeps one lazily-loaded model for the process, so it is not
        # reloaded per page. This guarantees a genuine OCR layout fallback
        # rather than treating a weak RapidOCR result as a terminal failure.
        for page_number, image in enumerate(rendered_pages, start=1):
            prepared = preprocessor.prepare(image)
            paddle_lines.extend(paddle.extract(prepared, page_number).lines)
        paddle_result = OcrResult(engine="paddleocr", lines=paddle_lines)
        selected = paddle_result if paddle_result.chars >= rapid_result.chars else rapid_result
        logger.info(
            "report_parse_scanned_ocr pages=%s dpi=350 rapid_chars=%s rapid_confidence=%.3f paddle_chars=%s paddle_confidence=%.3f selected=%s lines=%s",
            pages, rapid_result.chars, rapid_result.confidence, paddle_result.chars,
            paddle_result.confidence, selected.engine, len(selected.lines),
        )
        return rapid_result, paddle_result, selected

    @staticmethod
    def detect_parse_mode(data: bytes) -> tuple[str, int, bool, int]:
        """Classify by real PDF page text and embedded image resources.

        The classification is deliberately conservative: Docling remains the
        unified parser, while this inspection decides whether full-page OCR is
        necessary.  It never relies on filename or extension alone.
        """
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            pages = len(reader.pages)
            page_texts = [(page.extract_text() or "") for page in reader.pages]
            native_text = "".join(page_texts)
            # Count actual image XObjects instead of searching raw PDF bytes.
            # A byte search misclassified ordinary ReportLab text PDFs because
            # font/image-related metadata may contain the string "/Image".
            images = 0
            for page in reader.pages:
                resources = page.get("/Resources") or {}
                xobjects = resources.get("/XObject")
                if xobjects is None:
                    continue
                for reference in xobjects.values():
                    xobject = reference.get_object()
                    if xobject.get("/Subtype") == "/Image":
                        images += 1
        except Exception as exc:
            raise ReportParseError("PDF 无法读取，文件可能已损坏或受密码保护") from exc
        native_chars = len(re.sub(r"\s+", "", native_text))
        text_pages = sum(bool(re.sub(r"\s+", "", page_text)) for page_text in page_texts)
        logger.info("report_parse_detect pages=%s native_text=%s native_chars=%s images=%s", pages, bool(native_chars), native_chars, images)
        if native_chars < max(24, pages * 12) and images:
            return "OCR_TABLE", pages, True, images
        if images and (text_pages < pages or native_chars):
            return "HYBRID", pages, True, images
        return "TEXT", pages, False, images

    def parse_pdf_bytes(self, report_id: UUID, data: bytes) -> ParsedReport:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:
            raise ReportParseError("PDF 解析组件尚未就绪，请联系系统管理员") from exc
        if not data.startswith(b"%PDF"):
            raise ReportParseError("文件不是有效的 PDF 格式")
        mode, pages, ocr_required, picture_count = self.detect_parse_mode(data)
        raw_text = ""
        docling_error: Exception | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temporary_file:
                temporary_file.write(data)
                temporary_file.flush()
                options = PdfPipelineOptions()
                # Docling preserves native text when present.  Full-page OCR is
                # reserved for image-only PDFs; mixed PDFs let Docling apply OCR
                # only to regions whose native text is absent.
                options.do_ocr = True
                options.ocr_options = RapidOcrOptions(
                    # Docling expects a list here. RapidOCR selects Chinese as
                    # its single recognition model; it also covers Latin
                    # letters, numbers and common laboratory units.
                    lang=["chinese"],
                    backend="onnxruntime",
                    force_full_page_ocr=mode == "OCR_TABLE",
                )
                options.do_table_structure = True
                options.generate_picture_images = True
                converter = DocumentConverter(
                    allowed_formats=[InputFormat.PDF],
                    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
                )
                document = converter.convert(temporary_file.name).document
                raw_text = document.export_to_markdown().strip()
        except Exception as exc:
            docling_error = exc
            logger.warning("report_parse_docling_failed type=%s", type(exc).__name__)

        diagnostics: dict[str, object] = {
            "page_count": pages,
            "text_layer": not ocr_required,
            "render_dpi": 350 if ocr_required else None,
            "docling_chars": len(re.sub(r"\s+", "", raw_text)),
            "docling_error": type(docling_error).__name__ if docling_error else None,
            "rapidocr_chars": 0,
            "paddleocr_chars": 0,
            "selected_ocr_engine": None,
            "ocr_lines": 0,
        }
        # For every scanned or mixed report, run the independent OCR chain.
        # Docling's table object is useful when present, but must not be the
        # only way an image-only PDF reaches the indicator extractor.
        if ocr_required:
            try:
                rapid_result, paddle_result, selected_result = self._run_scanned_ocr(data, pages)
                diagnostics.update({
                    "rapidocr_chars": rapid_result.chars,
                    "paddleocr_chars": paddle_result.chars,
                    "selected_ocr_engine": selected_result.engine,
                    "ocr_lines": len(selected_result.lines),
                })
                recovered_layout = self._layout_rows(selected_result.lines)
                recovered_text = selected_result.text
                raw_text = "\n".join(part for part in (raw_text, recovered_layout, recovered_text) if part).strip()
            except Exception as ocr_exc:
                diagnostics["ocr_error"] = type(ocr_exc).__name__
                logger.exception("report_parse_scanned_ocr_failed type=%s", type(ocr_exc).__name__)
        if not raw_text:
            if diagnostics.get("ocr_error"):
                raise ReportParseError("OCR 引擎未能启动或识别到有效文字")
            raise ReportParseError("未识别到文本内容；请确认扫描件清晰且不受密码保护")
        table_count = raw_text.count("|") // 2
        if mode == "TEXT" and table_count:
            mode = "TEXT_TABLE"
        source_type = "image" if ocr_required else ("table" if table_count else "text")
        items = self.extractor.extract(
            raw_text,
            source_type=source_type,
            ocr_used=ocr_required,
            # A one-page report has an unambiguous source page. Multi-page
            # Markdown cannot safely be mapped back to a page without guessing.
            source_page=1 if pages == 1 else None,
        )
        # Keep every discovered item that has both a name and a non-empty
        # value.  Anything weaker is reported in diagnostics as a candidate.
        accepted = [item for item in items if item.item_name and item.value_text]
        diagnostics.update({
            "table_count": table_count,
            "candidate_items": len(items),
            "accepted_items": len(accepted),
        })
        logger.info("report_parse_extract mode=%s ocr=%s chars=%s tables=%s items=%s diagnostics=%s", mode, ocr_required, len(raw_text), table_count, len(accepted), diagnostics)
        if not accepted:
            if ocr_required and diagnostics.get("selected_ocr_engine"):
                raise ReportParseError("已识别文字，但未恢复出可确认的检验指标；建议人工核对扫描清晰度和表格版式")
            raise ReportParseError("未从 PDF 中识别到可可靠提取的体检指标")
        warnings: list[str] = []
        if ocr_required:
            warnings.append("扫描件指标来自 OCR，建议人工核对数值、单位和参考范围")
        if picture_count:
            warnings.append(f"检测到 {picture_count} 个图片资源；仅提取其中的文字与表格，不进行医学影像诊断")
        pictures = [
            {
                "picture_id": index + 1,
                # PDF resource-level inspection cannot safely infer the visual
                # page for a reused XObject, so leave it explicit/unknown.
                "page": None,
                "source": "embedded_pdf_image",
            }
            for index in range(picture_count)
        ]
        if ocr_required and len(accepted) < 3:
            warnings.append("仅部分指标识别成功，建议人工确认")
        return ParsedReport(report_id=report_id, raw_text=raw_text, items=accepted, parse_mode=mode, pages=pages, ocr_used=ocr_required, text_blocks=len([line for line in raw_text.splitlines() if line.strip()]), tables=table_count, pictures=pictures, warnings=warnings, diagnostics=diagnostics)


def serialise_indicator(item: HealthCheckIndicator) -> dict:
    return {
        "id": item.id, "category": item.category, "code": item.code,
        "item_name": item.item_name, "value": float(item.value),
        "value_text": item.value_text, "unit": item.unit,
        "reference_min": float(item.reference_min) if item.reference_min is not None else None,
        "reference_max": float(item.reference_max) if item.reference_max is not None else None,
        "reference_text": item.reference_text, "flag": item.flag,
        "source_page": item.source_page, "source_type": item.source_type,
        "confidence": float(item.confidence) if item.confidence is not None else None,
    }


def serialise_report(report: HealthCheckReport, items: list[HealthCheckIndicator]) -> dict:
    return {
        "id": report.id, "report_name": report.report_name, "hospital": report.hospital,
        "report_date": report.report_date, "file_name": report.file_name,
        "parse_status": report.parse_status, "parse_error": report.parse_error,
        "parse_progress": report.parse_progress,
        "parse_mode": report.parse_mode, "ocr_used": report.ocr_used,
        "parse_warnings": report.parse_warnings or [], "parsed_at": report.parsed_at,
        "created_at": report.created_at, "updated_at": report.updated_at,
        "indicators": [serialise_indicator(item) for item in items],
        "analysis": report.analysis_content,
    }


async def report_indicators(session: AsyncSession, report_id: UUID) -> list[HealthCheckIndicator]:
    return list((await session.scalars(select(HealthCheckIndicator).where(HealthCheckIndicator.report_id == report_id).order_by(HealthCheckIndicator.category, HealthCheckIndicator.item_name))).all())


async def create_report(session: AsyncSession, user_id: UUID, payload: HealthCheckReportCreate) -> HealthCheckReport:
    report = HealthCheckReport(user_id=user_id, report_name=payload.report_name, hospital=payload.hospital, report_date=payload.report_date, parse_status="parsed", parse_progress=100, parse_method="manual_structured")
    session.add(report)
    await session.flush()
    for raw in payload.indicators:
        flag = _flag_from_line("", raw.value, raw.reference_min, raw.reference_max)
        session.add(HealthCheckIndicator(report_id=report.id, category=raw.category, code=raw.code, item_name=raw.item_name, value=raw.value, value_text=raw.value_text or str(raw.value), unit=raw.unit, reference_min=raw.reference_min, reference_max=raw.reference_max, reference_text=raw.reference_text, flag=flag, source_page=raw.source_page, source_type=raw.source_type, confidence=raw.confidence))
    await session.commit()
    await session.refresh(report)
    return report


async def upload_original_report(session: AsyncSession, user_id: UUID, filename: str, content_type: str | None, data: bytes) -> HealthCheckReport:
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if suffix not in ALLOWED_REPORT_SUFFIXES:
        raise ValidationError("本阶段仅支持 PDF 体检报告")
    settings = get_settings()
    max_bytes = settings.max_knowledge_file_size_mb * 1024 * 1024
    if not data or len(data) > max_bytes:
        raise ValidationError(f"报告文件必须介于 1 字节和 {settings.max_knowledge_file_size_mb} MB 之间")
    report = HealthCheckReport(user_id=user_id, report_name=PurePosixPath(filename).stem[:200] or "体检报告", report_date=datetime.now(timezone.utc).date(), file_name=filename[:255], parse_status="uploaded", parse_progress=5)
    session.add(report)
    await session.flush()
    object_key = f"health-reports/{user_id}/{report.id}/{uuid4().hex}{suffix}"
    client = get_minio_client()
    bucket = settings.minio_knowledge_bucket
    try:
        await asyncio.to_thread(lambda: client.make_bucket(bucket) if not client.bucket_exists(bucket) else None)
        await asyncio.to_thread(client.put_object, bucket, object_key, BytesIO(data), len(data), content_type=content_type or "application/pdf")
    except Exception as exc:
        await session.rollback()
        raise ServiceError("体检报告文件保存失败，请稍后重试") from exc
    report.object_key = object_key
    await session.commit()
    await session.refresh(report)
    return report


async def get_owned_report(session: AsyncSession, report_id: UUID, user_id: UUID) -> HealthCheckReport:
    report = await session.scalar(select(HealthCheckReport).where(HealthCheckReport.id == report_id, HealthCheckReport.user_id == user_id))
    if report is None:
        raise NotFoundError("体检报告不存在或无权访问")
    return report


# FastAPI BackgroundTasks run in the API process.  If that process is restarted
# while Docling/OCR is working, PostgreSQL can otherwise be left with a report
# that looks permanently "parsing".  Keep the recovery decision server-side so
# the Electron client never has to guess task health.
PARSE_STALE_AFTER = timedelta(minutes=5)


def is_stale_parse(report: HealthCheckReport, now: datetime | None = None) -> bool:
    """Return true only for a parse state abandoned by a previous API process."""
    if report.parse_status != "parsing" or report.updated_at is None:
        return False
    current = now or datetime.now(timezone.utc)
    updated = report.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return current - updated >= PARSE_STALE_AFTER


def _download_report_pdf(object_key: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(get_settings().minio_knowledge_bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def stream_original_report(object_key: str):
    """Yield a private MinIO report in bounded chunks for an authenticated API.

    The browser/Electron renderer never receives a MinIO credential, object key
    or presigned URL.  Ownership is checked by the route before this generator
    is created.
    """
    response = get_minio_client().get_object(get_settings().minio_knowledge_bucket, object_key)
    try:
        while chunk := response.read(1024 * 64):
            yield chunk
    finally:
        response.close()
        response.release_conn()


async def parse_report(session: AsyncSession, report: HealthCheckReport) -> HealthCheckReport:
    """Transition uploaded -> parsing -> parsed/failed and persist extracted items."""
    report_id = report.id
    if not report.object_key:
        report.parse_status = "failed"; report.parse_progress = 100; report.parse_error = "报告原始文件不存在"
        await session.commit(); return report
    if report.parse_status == "parsing":
        return report
    report.parse_status = "parsing"; report.parse_progress = 15; report.parse_error = None
    report.parse_mode = None; report.ocr_used = False; report.parse_warnings = None; report.parsed_at = None
    await session.commit()
    try:
        data = await asyncio.to_thread(_download_report_pdf, report.object_key)
        report.parse_progress = 35
        await session.commit()
        parsed = await asyncio.to_thread(ReportParserService().parse_pdf_bytes, report.id, data)
        report.parse_progress = 80
        await session.commit()
        await session.execute(delete(HealthCheckIndicator).where(HealthCheckIndicator.report_id == report.id))
        for item in parsed.items:
            session.add(HealthCheckIndicator(report_id=report.id, category=item.category, code=item.code, item_name=item.item_name, value=item.value, value_text=item.value_text, unit=item.unit, reference_min=item.reference_min, reference_max=item.reference_max, reference_text=item.reference_text, flag=item.flag, source_page=item.source_page, source_type=item.source_type, confidence=item.confidence))
        # The migration stores parsed_at as PostgreSQL TIMESTAMP WITHOUT TIME
        # ZONE.  Persist a matching naive UTC value rather than leaving a
        # successful OCR run stuck at 80% because its final transaction fails.
        report.parse_status = "parsed"; report.parse_progress = 100; report.parse_error = None; report.parse_method = parsed.parse_method; report.parse_mode = parsed.parse_mode; report.ocr_used = parsed.ocr_used; report.parse_warnings = parsed.warnings; report.parsed_at = datetime.utcnow()
    except ReportParseError as exc:
        # A failed flush leaves the current SQLAlchemy transaction unusable.
        # Roll it back before recording the safe user-facing failure state.
        await session.rollback()
        report = await session.get(HealthCheckReport, report_id)
        if report is None:
            raise
        report.parse_status = "failed"; report.parse_progress = 100; report.parse_error = str(exc); report.parse_method = "docling_hybrid"
    except Exception:
        await session.rollback()
        report = await session.get(HealthCheckReport, report_id)
        if report is None:
            raise
        report.parse_status = "failed"; report.parse_progress = 100; report.parse_error = "PDF 解析服务异常，请稍后重试"; report.parse_method = "docling_hybrid"
    await session.commit()
    await session.refresh(report)
    return report


async def parse_report_background(report_id: UUID) -> None:
    """FastAPI BackgroundTasks worker using its own database session."""
    async with AsyncSessionFactory() as session:
        report = await session.get(HealthCheckReport, report_id)
        if report is not None:
            await parse_report(session, report)
