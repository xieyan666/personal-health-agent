"""Admin model control center API (JWT + RBAC).

Manages model_configs / model_providers as the AI Model Control Center:
cards, defaults, connection tests, embedding vector checks and usage stats.
Secrets are referenced (env:VAR) or masked on read; full keys never leave
the backend.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import require_role
from backend.app.core.database import get_db
from backend.app.core.qdrant import get_qdrant_client
from backend.app.exceptions import NotFoundError, ValidationError
from backend.app.model_gateway.chat import ChatInput, chat_provider_for, normalize_chat_parameters
from backend.app.model_gateway.embedding import embedding_provider_for
from backend.app.models import Agent, Document, KnowledgeBase, ModelConfig, ModelProvider
from backend.app.services.embedding import EmbeddingService

router = APIRouter(prefix="/models", tags=["admin-models"])
admin = require_role("admin", "company_admin", "system_admin")

MODEL_TYPE_LABELS = {"chat": "Chat", "embedding": "Embedding", "reranker": "Reranker"}
EMBEDDING_WARNING = "尚未配置正式 Embedding 模型，当前 RAG 仅可进行测试链路验证。"


def _mask(value: str | None, tail: int = 4) -> str | None:
    if not value:
        return None
    if value.startswith("env:"):
        return f"env:{'*' * min(len(value) - 4, 8)}{value[-tail:]}"
    return f"{'*' * 8}{value[-tail:]}"


def _resolve_api_key(provider: ModelProvider) -> str | None:
    """Resolve a real API key for connection tests without exposing it to the client."""
    if provider.secret_ref and provider.secret_ref.startswith("env:"):
        return os.environ.get(provider.secret_ref[4:])
    stored = (provider.config or {}).get("api_key")
    return stored if isinstance(stored, str) and stored else None


def _provider_environment(provider: ModelProvider, environment: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(environment) if environment else dict(os.environ)
    key = _resolve_api_key(provider)
    if key:
        env["DEEPSEEK_API_KEY"] = key
        env["MODEL_ADMIN_TEST_KEY"] = key
    return env


async def _config_or_404(session: AsyncSession, config_id: UUID) -> ModelConfig:
    config = await session.get(ModelConfig, config_id)
    if config is None:
        raise HTTPException(404, "模型配置不存在")
    return config


async def _provider_or_404(session: AsyncSession, provider_id: UUID) -> ModelProvider:
    provider = await session.get(ModelProvider, provider_id)
    if provider is None:
        raise HTTPException(404, "模型 Provider 不存在")
    return provider


async def _serialize_config(session_agents: dict, session_kbs: dict, providers: dict, config: ModelConfig) -> dict[str, Any]:
    provider = providers.get(str(config.provider_id))
    return {
        "id": str(config.id),
        "name": config.name,
        "model_name": config.model_name,
        "model_type": config.model_type,
        "model_type_label": MODEL_TYPE_LABELS.get(config.model_type, config.model_type),
        "status": config.status,
        "is_default": config.is_default,
        "vector_dimension": config.vector_dimension,
        "parameters": {
            key: value for key, value in (config.parameters or {}).items()
            if key in {"temperature", "max_tokens", "streaming", "timeout", "batch_size", "top_p"}
        },
        "provider_id": str(config.provider_id),
        "provider_name": provider.name if provider else "未知",
        "provider_type": provider.provider_type if provider else "unknown",
        "used_by_agents": [agent_id for agent_id in session_agents.get(str(config.id), [])],
        "used_by_knowledge_bases": [kb_id for kb_id in session_kbs.get(str(config.id), [])],
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


def _serialize_provider(provider: ModelProvider, model_count: int) -> dict[str, Any]:
    return {
        "id": str(provider.id),
        "name": provider.name,
        "provider_type": provider.provider_type,
        "status": provider.status,
        "endpoint": provider.endpoint,
        "api_key_masked": _mask(_resolve_api_key(provider)) or _mask(provider.secret_ref),
        "secret_ref": provider.secret_ref,
        "model_count": model_count,
        "updated_at": provider.updated_at.isoformat() if provider.updated_at else None,
    }


@router.get("/overview")
async def model_overview(session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    configs = list((await session.scalars(select(ModelConfig).order_by(ModelConfig.model_type, ModelConfig.name))).all())
    providers = list((await session.scalars(select(ModelProvider).order_by(ModelProvider.name))).all())
    agents = list((await session.scalars(select(Agent))).all())
    kbs = list((await session.scalars(select(KnowledgeBase))).all())
    agent_map: dict[str, list[str]] = {}
    for agent in agents:
        if agent.model_config_id:
            agent_map.setdefault(str(agent.model_config_id), []).append(str(agent.id))
    kb_map: dict[str, list[str]] = {}
    for kb in kbs:
        if kb.embedding_model_config_id:
            kb_map.setdefault(str(kb.embedding_model_config_id), []).append(str(kb.id))
    provider_count: dict[str, int] = {}
    for config in configs:
        provider_count[str(config.provider_id)] = provider_count.get(str(config.provider_id), 0) + 1
    provider_map = {str(provider.id): provider for provider in providers}
    defaults = {
        "chat": next((str(c.id) for c in configs if c.model_type == "chat" and c.is_default), None),
        "embedding": next((str(c.id) for c in configs if c.model_type == "embedding" and c.is_default), None),
        "reranker": None,
    }
    return {
        "models": [await _serialize_config(agent_map, kb_map, provider_map, config) for config in configs],
        "providers": [_serialize_provider(provider, provider_count.get(str(provider.id), 0)) for provider in providers],
        "defaults": defaults,
        "warnings": {
            "formal_embedding_missing": not any(config.model_type == "embedding" and config.status == "active" and not _is_fake(config) for config in configs),
            "embedding_note": EMBEDDING_WARNING,
        },
    }


def _is_fake(config: ModelConfig) -> bool:
    return "fake" in (config.model_name or "").lower() or (config.parameters or {}).get("purpose") == "test"


@router.get("/qdrant-dimension")
async def qdrant_dimension(session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    configs = list((await session.scalars(select(ModelConfig).where(ModelConfig.model_type == "embedding"))).all())
    default = next((config for config in configs if config.is_default), None)
    collections: list[dict[str, Any]] = []
    try:
        client = get_qdrant_client()
        existing = await client.get_collections()
        names = [collection.name for collection in existing.collections if collection.name.startswith("knowledge_")]
        for name in names:
            info = await client.get_collection(name)
            vectors = info.config.params.vectors
            size = vectors.size if hasattr(vectors, "size") else None
            collections.append({"collection": name, "dimension": size})
    except Exception:
        collections = []
    return {
        "collections": collections,
        "default_embedding": {
            "id": str(default.id) if default else None,
            "name": default.name if default else None,
            "dimension": default.vector_dimension if default else None,
            "fake": _is_fake(default) if default else None,
        } if default else None,
        "mismatch": [
            {"collection": item["collection"], "dimension": item["dimension"]}
            for item in collections
            if default and default.vector_dimension and item["dimension"] != default.vector_dimension
        ],
    }


@router.post("/{config_id}/test-chat")
async def test_chat(config_id: UUID, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    config = await _config_or_404(session, config_id)
    if config.model_type != "chat":
        raise HTTPException(422, "该模型不是 Chat 模型")
    provider = await session.get(ModelProvider, config.provider_id)
    if provider is None:
        raise HTTPException(404, "Provider 不存在")
    if provider.provider_type == "fake":
        return {"success": True, "model_id": config.model_name, "duration_ms": 1, "response": "Fake provider 本地测试通过", "fake": True}
    try:
        impl = chat_provider_for(
            provider.provider_type,
            secret_ref=provider.secret_ref,
            endpoint=provider.endpoint,
            environment=_provider_environment(provider),
        )
        started = time.monotonic()
        result = await asyncio.to_thread(
            impl.chat,
            [ChatInput("user", "你好，请简短回复一个字。")],
            model_name=config.model_name,
            parameters=normalize_chat_parameters(config.parameters, max_tokens_override=128),
        )
        duration_ms = round((time.monotonic() - started) * 1000, 1)
        return {"success": True, "model_id": config.model_name, "duration_ms": duration_ms, "response": (result.content or "")[:200], "fake": False}
    except Exception as exc:
        return {"success": False, "model_id": config.model_name, "duration_ms": 0, "response": str(exc)[:300], "fake": False}


@router.post("/{config_id}/test-embedding")
async def test_embedding(config_id: UUID, payload: dict | None = None, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    config = await _config_or_404(session, config_id)
    if config.model_type != "embedding":
        raise HTTPException(422, "该模型不是 Embedding 模型")
    text = (payload or {}).get("text") or "甲状腺功能检查"
    started = time.monotonic()
    try:
        vector = await EmbeddingService(session).embed_query(str(text), config_id)
        duration_ms = round((time.monotonic() - started) * 1000, 1)
        return {
            "success": True,
            "model_name": config.name,
            "model_id": config.model_name,
            "dimension": len(vector),
            "duration_ms": duration_ms,
            "vector_head": [round(value, 6) for value in vector[:6]],
            "fake": _is_fake(config),
        }
    except Exception as exc:
        return {"success": False, "model_name": config.name, "model_id": config.model_name, "dimension": 0, "duration_ms": 0, "vector_head": [], "response": str(exc)[:300], "fake": _is_fake(config)}


class DefaultRequest(BaseModel):
    pass


@router.post("/{config_id}/set-default")
async def set_default(config_id: UUID, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    config = await _config_or_404(session, config_id)
    if config.model_type not in ("chat", "embedding"):
        raise HTTPException(422, "仅 Chat / Embedding 模型可设为默认")
    rows = list((await session.scalars(select(ModelConfig).where(ModelConfig.model_type == config.model_type))).all())
    for row in rows:
        row.is_default = row.id == config.id
    if config.model_type == "embedding":
        config.vector_dimension = config.vector_dimension or await _probe_embedding_dimension(session, config)
    await session.commit()
    await session.refresh(config)
    qdrant = await qdrant_dimension(session)
    return {
        "id": str(config.id),
        "name": config.name,
        "model_type": config.model_type,
        "is_default": True,
        "vector_dimension": config.vector_dimension,
        "qdrant_mismatch": qdrant["mismatch"],
        "qdrant_dimensions": [item["dimension"] for item in qdrant["collections"]],
    }


async def _probe_embedding_dimension(session: AsyncSession, config: ModelConfig) -> int | None:
    try:
        provider = await session.get(ModelProvider, config.provider_id)
        if provider is None:
            return None
        impl = embedding_provider_for(provider.provider_type)
        vectors = impl.embed_texts(["探测"])
        return len(vectors[0]) if vectors else None
    except Exception:
        return None


class ConfigUpdateRequest(BaseModel):
    name: str | None = None
    model_name: str | None = None
    status: str | None = None
    is_default: bool | None = None
    vector_dimension: int | None = Field(default=None, ge=1, le=65536)
    parameters: dict[str, Any] | None = None


@router.patch("/{config_id}")
async def update_config(config_id: UUID, payload: ConfigUpdateRequest, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    config = await _config_or_404(session, config_id)
    if payload.name is not None:
        config.name = payload.name
    if payload.model_name is not None:
        config.model_name = payload.model_name
    if payload.status is not None:
        if payload.status not in ("active", "disabled", "test"):
            raise HTTPException(422, "状态仅支持 active / disabled / test")
        config.status = payload.status
    if payload.vector_dimension is not None:
        config.vector_dimension = payload.vector_dimension
    if payload.parameters is not None:
        merged = dict(config.parameters or {})
        merged.update(payload.parameters)
        config.parameters = merged
    if payload.is_default:
        rows = list((await session.scalars(select(ModelConfig).where(ModelConfig.model_type == config.model_type))).all())
        for row in rows:
            row.is_default = row.id == config.id
    await session.commit()
    await session.refresh(config)
    return {"id": str(config.id), "name": config.name, "status": config.status, "is_default": config.is_default, "vector_dimension": config.vector_dimension}


@router.get("/usage")
async def model_usage(session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    from backend.app.models import AgentRun
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=6)

    total_runs = int((await session.scalar(select(func.count(AgentRun.id)))) or 0)
    today_runs = int((await session.scalar(select(func.count(AgentRun.id)).where(AgentRun.created_at >= today))) or 0)
    succeeded = int((await session.scalar(select(func.count(AgentRun.id)).where(AgentRun.status == "succeeded"))) or 0)
    success_rate = round(succeeded / total_runs * 100, 1) if total_runs else 0.0
    prompt_tokens = int((await session.scalar(select(func.coalesce(func.sum(AgentRun.prompt_tokens), 0)))) or 0)
    completion_tokens = int((await session.scalar(select(func.coalesce(func.sum(AgentRun.completion_tokens), 0)))) or 0)

    trend_rows = (
        await session.execute(
            select(func.date_trunc("day", AgentRun.created_at).label("day"), func.count(AgentRun.id))
            .where(AgentRun.created_at >= week_ago)
            .group_by("day")
            .order_by("day")
        )
    ).all()
    trend = [{"date": row[0].strftime("%m-%d") if row[0] else "", "count": int(row[1])} for row in trend_rows]

    recent_errors = list(
        (
            await session.scalars(
                select(AgentRun)
                .where(AgentRun.status != "succeeded")
                .order_by(AgentRun.created_at.desc())
                .limit(5)
            )
        ).all()
    )

    indexed_docs = int((await session.scalar(select(func.count(Document.id)).where(Document.status == "indexed"))) or 0)
    kb_embedding_usage = []
    kbs = list((await session.scalars(select(KnowledgeBase))).all())
    for kb in kbs:
        kb_embedding_usage.append({"knowledge_base": kb.name, "embedding_model_id": str(kb.embedding_model_config_id) if kb.embedding_model_config_id else None})

    return {
        "chat": {
            "total_runs": total_runs,
            "today_runs": today_runs,
            "success_rate": success_rate,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "trend": trend,
            "recent_errors": [
                {"id": str(run.id), "status": run.status, "error_code": run.error_code, "error_message": (run.error_message or "")[:200], "created_at": run.created_at.isoformat() if run.created_at else None}
                for run in recent_errors
            ],
        },
        "embedding": {
            "indexed_documents": indexed_docs,
            "knowledge_bases": kb_embedding_usage,
        },
    }


class ProviderCreateRequest(BaseModel):
    name: str
    provider_type: str = "deepseek"
    endpoint: str | None = None
    api_key: str | None = None
    status: str = "active"


class ProviderUpdateRequest(BaseModel):
    name: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    status: str | None = None


@router.post("/providers", status_code=201)
async def create_provider(payload: ProviderCreateRequest, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    if await session.scalar(select(ModelProvider.id).where(ModelProvider.name == payload.name)):
        raise HTTPException(409, "Provider 名称已存在")
    provider = ModelProvider(
        name=payload.name,
        provider_type=payload.provider_type,
        status=payload.status if payload.status in ("active", "disabled") else "active",
        endpoint=payload.endpoint,
        secret_ref=payload.api_key if payload.api_key and payload.api_key.startswith("env:") else None,
        config={},
    )
    if payload.api_key and not payload.api_key.startswith("env:"):
        provider.config = {"api_key": payload.api_key}
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return _serialize_provider(provider, 0)


@router.patch("/providers/{provider_id}")
async def update_provider(provider_id: UUID, payload: ProviderUpdateRequest, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    provider = await _provider_or_404(session, provider_id)
    if payload.name is not None:
        provider.name = payload.name
    if payload.endpoint is not None:
        provider.endpoint = payload.endpoint
    if payload.status is not None:
        provider.status = payload.status if payload.status in ("active", "disabled") else provider.status
    if payload.api_key:
        if payload.api_key.startswith("env:"):
            provider.secret_ref = payload.api_key
            config = dict(provider.config or {})
            config.pop("api_key", None)
            provider.config = config
        else:
            config = dict(provider.config or {})
            config["api_key"] = payload.api_key
            provider.config = config
    await session.commit()
    await session.refresh(provider)
    model_count = int((await session.scalar(select(func.count(ModelConfig.id)).where(ModelConfig.provider_id == provider.id))) or 0)
    return _serialize_provider(provider, model_count)


class ProviderTestResponse(BaseModel):
    success: bool
    provider_type: str
    duration_ms: int
    detail: str


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: UUID, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    provider = await _provider_or_404(session, provider_id)
    if provider.provider_type == "fake":
        return ProviderTestResponse(success=True, provider_type=provider.provider_type, duration_ms=1, detail="Fake provider 本地测试通过")
    if provider.provider_type != "deepseek":
        return ProviderTestResponse(success=False, provider_type=provider.provider_type, duration_ms=0, detail="暂不支持该 Provider 类型的连接测试")
    key = _resolve_api_key(provider)
    if not key:
        return ProviderTestResponse(success=False, provider_type=provider.provider_type, duration_ms=0, detail="未配置 API Key（请填写 env:VAR 引用或明文 Key）")
    try:
        impl = chat_provider_for("deepseek", secret_ref="env:DEEPSEEK_API_KEY", endpoint=provider.endpoint, environment=_provider_environment(provider))
        started = time.monotonic()
        result = await asyncio.to_thread(
            impl.chat,
            [ChatInput("user", "ping")],
            model_name="deepseek-chat",
            parameters=normalize_chat_parameters({"temperature": 0, "max_tokens": 128}),
        )
        duration_ms = round((time.monotonic() - started) * 1000)
        return ProviderTestResponse(success=True, provider_type=provider.provider_type, duration_ms=int(duration_ms), detail=(result.content or "")[:120])
    except Exception as exc:
        return ProviderTestResponse(success=False, provider_type=provider.provider_type, duration_ms=0, detail=str(exc)[:300])
