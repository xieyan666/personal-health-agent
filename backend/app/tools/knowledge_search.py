"""Runtime-safe KnowledgeSearchTool backed by the existing RetrievalService."""
from __future__ import annotations
from uuid import UUID
from backend.app.services.retrieval import RetrievalService
from backend.app.tools.base import ToolHandler, ToolResult


class KnowledgeSearchTool(ToolHandler):
    """Search only the explicitly configured knowledge base for an Agent."""
    name = "knowledge_search"
    description = "检索当前 Agent 已绑定的企业知识库。"
    parameters_schema = {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}

    def __init__(self, session, knowledge_base_id: UUID, embedding_model_config_id: UUID) -> None:
        self.retrieval = RetrievalService(session)
        self.knowledge_base_id = knowledge_base_id
        self.embedding_model_config_id = embedding_model_config_id

    async def execute(self, arguments):
        query = str(arguments.get("query", "")).strip()
        items = await self.retrieval.retrieve(self.knowledge_base_id, query, self.embedding_model_config_id, 5)
        return ToolResult(True, "\n\n".join(item.content for item in items), {"knowledge_base_id": str(self.knowledge_base_id), "hits": len(items)})
