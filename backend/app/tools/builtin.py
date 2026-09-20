from __future__ import annotations
from typing import Any, Mapping
from backend.app.tools.base import ToolExecutionError, ToolHandler, ToolResult


class CalculateBmiTool(ToolHandler):
    name = "calculate_bmi"
    description = "Calculate body mass index from weight in kilograms and height in centimeters."
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"weight_kg": {"type": "number", "description": "Weight in kilograms"}, "height_cm": {"type": "number", "description": "Height in centimeters"}},
        "required": ["weight_kg", "height_cm"], "additionalProperties": False,
    }

    async def execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        if set(arguments) != {"weight_kg", "height_cm"}:
            raise ToolExecutionError("BMI arguments must contain only weight_kg and height_cm")
        weight, height = arguments["weight_kg"], arguments["height_cm"]
        if isinstance(weight, bool) or isinstance(height, bool) or not isinstance(weight, (int, float)) or not isinstance(height, (int, float)) or weight <= 0 or height <= 0:
            raise ToolExecutionError("BMI weight_kg and height_cm must be positive numbers")
        bmi = round(float(weight) / (float(height) / 100) ** 2, 2)
        return ToolResult(True, '{"bmi": ' + f"{bmi:.2f}" + "}", {"bmi": bmi})
