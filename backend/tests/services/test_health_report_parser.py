from backend.app.services.health_report_service import ReportIndicatorExtractor


def test_extracts_text_layer_report_metrics_and_flags():
    text = """
    FPG 5.1 mmol/L 3.9-6.1
    TG 2.10 mmol/L 0.45-1.69 H
    ALT 22 U/L 9-50
    """

    items = {item.code: item for item in ReportIndicatorExtractor().extract(text)}

    assert set(items) == {"fasting_glucose", "triglyceride", "alt"}
    assert items["fasting_glucose"].flag == "normal"
    assert items["triglyceride"].flag == "high"
    assert items["triglyceride"].reference_text == "0.45-1.69"
    assert items["alt"].unit == "U/L"


def test_extractor_keeps_rows_isolated_when_docling_flattens_a_table():
    """A later row's H flag must not mark an earlier normal value as high."""
    text = "FPG 5.1 mmol/L 3.9-6.1 TG 2.10 mmol/L 0.45-1.69 H ALT 22 U/L 9-50"

    items = {item.code: item for item in ReportIndicatorExtractor().extract(text, source_type="table")}

    assert items["fasting_glucose"].flag == "normal"
    assert items["triglyceride"].flag == "high"
    assert all(item.source_type == "table" for item in items.values())


def test_extractor_keeps_unknown_but_verifiable_markdown_table_rows():
    text = "| 检查项目 | 结果 | 参考范围 | 单位 |\n| 自定义检验项 | 2.10 | 0.45-1.69 | mmol/L |"

    items = ReportIndicatorExtractor().extract(text, source_type="table")

    assert len(items) == 1
    assert items[0].category == "其他指标"
    assert items[0].value == 2.10
    assert items[0].flag == "high"
    assert items[0].source_type == "table"
