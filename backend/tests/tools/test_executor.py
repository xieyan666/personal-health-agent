import pytest
from backend.app.tools import ToolCall, ToolDefinition, ToolExecutionError, ToolExecutor
from backend.app.tools.builtin import CalculateBmiTool

@pytest.mark.asyncio
async def test_bmi_validation_and_execution():
    handler = CalculateBmiTool()
    result = await handler.execute({"weight_kg": 70, "height_cm": 175})
    assert result.structured_data == {"bmi": 22.86}
    for arguments in ({"weight_kg": 0, "height_cm": 175}, {"weight_kg": 70}, {"weight_kg": 70, "height_cm": 175, "x": 1}):
        with pytest.raises(ToolExecutionError): await handler.execute(arguments)

@pytest.mark.asyncio
async def test_executor_rejects_unauthorized_name():
    definition = ToolDefinition("calculate_bmi", "BMI", CalculateBmiTool.parameters_schema)
    with pytest.raises(Exception): await ToolExecutor().execute(definition, ToolCall("x", "other", {}))
