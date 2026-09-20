import json
from pathlib import Path
from uuid import uuid4

from backend.app.services.health_report_service import ReportParserService


result = ReportParserService().parse_pdf_bytes(uuid4(), Path('/app/体检报告1.pdf').read_bytes())
Path('/tmp/debug_ocr_result.json').write_text(json.dumps({
    'diagnostics': result.diagnostics,
    'items': [item.__dict__ for item in result.items],
    'mode': result.parse_mode,
    'warnings': result.warnings,
}, ensure_ascii=False, default=str), encoding='utf-8')
