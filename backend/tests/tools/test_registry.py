import pytest
from backend.app.exceptions import ValidationError
from backend.app.tools import ToolRegistry
from backend.app.tools.builtin import CalculateBmiTool

def test_registry_has_bmi_and_rejects_unknown_and_duplicates():
    registry = ToolRegistry()
    assert registry.get("calculate_bmi").name == "calculate_bmi"
    with pytest.raises(ValidationError): registry.get("not_registered")
    with pytest.raises(ValidationError): registry.register(CalculateBmiTool())
