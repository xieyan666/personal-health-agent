from uuid import uuid4

import pytest

from backend.app.agent.multi_agent import MultiAgentExecutionContext, MultiAgentOrchestrator
from backend.app.exceptions import ValidationError
from backend.app.models import Agent, Conversation, User
from backend.app.services.execution import AgentRunService


def test_execution_context_preserves_tree_state():
    root, child = uuid4(), uuid4()
    ctx = MultiAgentExecutionContext(root, child, depth=2, handoff_count=2, visited_agents={root, child}, parent_run_id=uuid4())
    assert ctx.root_agent_id == root
    assert ctx.current_agent_id == child
    assert ctx.depth == 2
    assert ctx.handoff_count == 2
    assert ctx.visited_agents == {root, child}


def test_orchestrator_limits_are_bounded():
    assert MultiAgentOrchestrator.MAX_DEPTH == 3
    assert MultiAgentOrchestrator.MAX_RESULT_CHARS == 12000


def test_context_cycle_membership_is_explicit():
    agent = uuid4()
    ctx = MultiAgentExecutionContext(agent, agent, visited_agents={agent})
    assert agent in ctx.visited_agents


@pytest.mark.asyncio
async def test_internal_child_run_reuses_coordinator_conversation(service_context):
    session, track = service_context
    tag = uuid4().hex
    user = track(User(id=uuid4(), username=f"multi-agent-47-{tag}", email=f"multi-agent-47-{tag}@example.com", display_name="test", auth_source="local"))
    coordinator = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"multi-agent-47-root-{tag}", name="Coordinator", category="test", status="active", config={}))
    child = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"multi-agent-47-child-{tag}", name="Child", category="test", status="active", config={}))
    coordinator.config = {"multi_agent": {"enabled": True, "sub_agent_ids": [str(child.id)]}}
    conversation = track(Conversation(id=uuid4(), user_id=user.id, agent_id=coordinator.id, status="active", context={}))
    session.add_all([user, coordinator, child, conversation]); await session.commit()
    runs = AgentRunService(session)
    root = track(await runs.create_agent_run(user_id=user.id, agent_id=coordinator.id, conversation_id=conversation.id, trigger_message_id=None, parent_run_id=None, model_config_id=None, status="pending", input_summary="root", risk_level="low", safety_status="safe"))
    child_run = track(await runs.create_child_agent_run(user_id=user.id, child_agent_id=child.id, conversation_id=conversation.id, parent_run_id=root.id, root_agent_id=coordinator.id, model_config_id=None, input_summary="internal", risk_level="low", safety_status="safe"))
    assert child_run.agent_id == child.id
    assert child_run.conversation_id == conversation.id
    assert child_run.parent_run_id == root.id
