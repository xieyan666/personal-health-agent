from uuid import uuid4
import pytest
from qdrant_client import AsyncQdrantClient

from backend.app.agent.runtime import AgentRuntimeService
from backend.app.core.config import get_settings
from backend.app.models import Agent, Conversation, Document, DocumentChunk, KnowledgeBase, ModelConfig, ModelProvider, User
from backend.app.services.qdrant_index import QdrantIndexService


@pytest.mark.asyncio
async def test_sub_agent_rag_uses_real_postgres_and_qdrant(service_context):
    session, track = service_context; tag = uuid4().hex
    user = track(User(id=uuid4(), username=f"multi-agent-47-{tag}", display_name="MA", email=f"multi-agent-47-{tag}@example.com", auth_source="local"))
    chat_provider = track(ModelProvider(id=uuid4(), name=f"multi-agent-chat-{tag}", provider_type="fake", status="active", config={}))
    chat = track(ModelConfig(id=uuid4(), provider_id=chat_provider.id, name=f"multi-agent-chat-config-{tag}", model_name="fake", model_type="chat", status="active", parameters={}))
    embedding_provider = track(ModelProvider(id=uuid4(), name=f"multi-agent-embedding-{tag}", provider_type="fake", status="active", config={}))
    embedding = track(ModelConfig(id=uuid4(), provider_id=embedding_provider.id, name=f"multi-agent-embedding-config-{tag}", model_name="fake-8", model_type="embedding", status="active", parameters={}))
    kb = track(KnowledgeBase(id=uuid4(), owner_user_id=user.id, name=f"multi-agent-kb-{tag}", status="active", vector_collection=f"multi_agent_rag_{tag}", retrieval_config={}))
    doc = track(Document(id=uuid4(), knowledge_base_id=kb.id, name="PH-MA-47-RAG", source_type="upload", source_reference={}, status="stored", metadata_={}))
    chunk = track(DocumentChunk(id=uuid4(), document_id=doc.id, chunk_index=0, content="PH-MA-47-RAG 员工建议每日进行30分钟中等强度运动。", char_count=31))
    child = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"multi-agent-rag-child-{tag}", name="Knowledge", category="test", status="active", model_config_id=chat.id, config={"rag":{"enabled":True,"knowledge_base_id":str(kb.id),"embedding_model_config_id":str(embedding.id),"top_k":3}}))
    root = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"multi-agent-rag-root-{tag}", name="Coordinator", category="test", status="active", model_config_id=chat.id, config={"multi_agent":{"enabled":True,"sub_agent_ids":[str(child.id)]}}))
    conversation = track(Conversation(id=uuid4(), user_id=user.id, agent_id=root.id, status="active", context={}))
    session.add_all([user, chat_provider, chat, embedding_provider, embedding, kb, doc, chunk, child, root, conversation]); await session.commit()
    client = AsyncQdrantClient(url=get_settings().qdrant_url, api_key=get_settings().qdrant_api_key)
    try:
        assert (await QdrantIndexService(session, client).index_document(doc.id, embedding.id)).indexed_count == 1
        result = await AgentRuntimeService(session).run(user.id, root.id, conversation.id, "PH-MA-47-RAG 建议是什么？")
        assert result.run_status == "succeeded"
        runs = await AgentRuntimeService(session).runs.list_agent_runs(conversation_id=conversation.id, limit=10)
        assert any(item.agent_id == child.id and item.status == "succeeded" for item in runs)
        messages = await AgentRuntimeService(session).messages.list_messages(conversation.id)
        assert [item.role for item in messages] == ["user", "assistant"]
        for item in [*runs, *messages]: track(item)
    finally:
        if await client.collection_exists(kb.vector_collection): await client.delete_collection(kb.vector_collection)
        await client.close()
