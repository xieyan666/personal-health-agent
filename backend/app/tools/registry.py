from __future__ import annotations
from backend.app.exceptions import ValidationError
from backend.app.tools.base import ToolHandler
from backend.app.tools.builtin import CalculateBmiTool


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self.register(CalculateBmiTool())

    def register(self, handler: ToolHandler) -> None:
        if handler.name in self._handlers:
            raise ValidationError(f"Tool handler already registered: {handler.name}")
        self._handlers[handler.name] = handler

    def get(self, name: str) -> ToolHandler:
        try:
            return self._handlers[name]
        except KeyError as exc:
            raise ValidationError("Tool handler is not registered") from exc
