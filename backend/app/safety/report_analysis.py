"""Safety Guard for AI health report interpretation output.

The guard is a post-processing layer over the validated structured result.
It never diagnoses, never overstates a single abnormal metric, treats OCR
data as best-effort, and keeps the medical-boundary disclaimer intact.
"""

from __future__ import annotations

import re

from backend.app.schemas.health_report_analysis import ReportAnalysisResponse

# Phrases that imply a definitive diagnosis or fear; replaced or softened.
_DIAGNOSTIC_PATTERNS = (
    (re.compile(r"确诊|诊断为|患有.{0,8}病|患上了|得了|癌症|恶性肿瘤", re.IGNORECASE), "可能需要专业评估"),
    (re.compile(r"非常危险|极其严重|恶化迅速|后果严重|会死|致命", re.IGNORECASE), "需要关注"),
    (re.compile(r"肯定|一定|必然|百分百", re.IGNORECASE), "建议"),
)

_OCR_NOTE = "该指标来自 OCR 识别，建议与原始报告核对。"
_OCR_LOW_CONFIDENCE_NOTE = "该指标 OCR 识别置信度较低，请务必与原始报告核对。"
_PROFESSIONAL_SUGGESTION = {
    "title": "必要时寻求专业评估",
    "description": "结合个人情况咨询专业医疗人员，获取进一步评估与指导。",
}
_DISCLAIMER = "AI健康解读仅用于健康管理辅助，不替代专业医疗诊断。"


def _soften(text: str) -> str:
    for pattern, replacement in _DIAGNOSTIC_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _guard_attention_text(item) -> None:
    item.description = _soften(item.description or "")
    if item.source_type == "ocr":
        note = _OCR_LOW_CONFIDENCE_NOTE if (item.confidence is not None and item.confidence < 0.85) else _OCR_NOTE
        if note not in item.description:
            item.description = f"{item.description.rstrip('。')}。{note}"


class ReportAnalysisSafetyGuard:
    """Apply medical-boundary safety rules to a structured report analysis."""

    def guard(self, analysis: ReportAnalysisResponse) -> ReportAnalysisResponse:
        # 1. Soften diagnostic/fear language everywhere.
        analysis.overall.title = _soften(analysis.overall.title)
        analysis.overall.description = _soften(analysis.overall.description)
        for finding in analysis.findings:
            finding.description = _soften(finding.description or "")
        for suggestion in analysis.suggestions:
            suggestion.title = _soften(suggestion.title or "")
            suggestion.description = _soften(suggestion.description or "")
        # 2. OCR provenance notes on attention items.
        for attention in analysis.attention:
            _guard_attention_text(attention)
        # 3. Ensure the disclaimer is present and unmodified.
        analysis.disclaimer = _DISCLAIMER
        # 4. Caution-level results must include a professional-evaluation
        #    suggestion so the user is directed to a professional.
        titles = {s.title for s in analysis.suggestions}
        if analysis.overall.level == "caution" and _PROFESSIONAL_SUGGESTION["title"] not in titles:
            analysis.suggestions.append(_PROFESSIONAL_SUGGESTION)
        return analysis


def guard_report_analysis(analysis: ReportAnalysisResponse) -> ReportAnalysisResponse:
    """Convenience wrapper used by the analysis service."""
    return ReportAnalysisSafetyGuard().guard(analysis)
