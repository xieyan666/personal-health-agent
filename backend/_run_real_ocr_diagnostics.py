"""Temporary, container-only diagnostic runner for supplied PDF reports."""
import json
from pathlib import Path
from uuid import uuid4

from backend.app.services.health_report_service import ReportParserService


def main() -> None:
    reports = sorted(Path("/app").glob("*.pdf"))
    service = ReportParserService()
    output: list[dict[str, object]] = []
    for report in reports:
        row: dict[str, object] = {"file": report.name}
        try:
            parsed = service.parse_pdf_bytes(uuid4(), report.read_bytes())
            diagnostics = parsed.diagnostics or {}
            row.update({
                "page_count": diagnostics.get("page_count"),
                "text_layer": diagnostics.get("text_layer"),
                "render_dpi": diagnostics.get("render_dpi"),
                "rapidocr_chars": diagnostics.get("rapidocr_chars"),
                "paddleocr_chars": diagnostics.get("paddleocr_chars"),
                "selected_ocr_engine": diagnostics.get("selected_ocr_engine"),
                "ocr_lines": diagnostics.get("ocr_lines"),
                "table_count": diagnostics.get("table_count"),
                "candidate_items": diagnostics.get("candidate_items"),
                "accepted_items": diagnostics.get("accepted_items"),
                "parse_mode": parsed.parse_mode,
                "parse_status": "partial" if parsed.warnings else "completed",
                "warnings": parsed.warnings,
            })
        except Exception as exc:  # diagnostics must continue for all reports
            row.update({"error_type": type(exc).__name__, "error": str(exc)})
        output.append(row)
        Path("/tmp/ocr_real_reports.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
