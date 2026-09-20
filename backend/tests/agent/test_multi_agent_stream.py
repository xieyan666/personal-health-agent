from backend.app.agent.multi_agent import MultiAgentExecutionContext


def test_stream_context_has_stable_agent_identity():
    context = MultiAgentExecutionContext(None, None)
    assert context.depth == 0
    assert context.handoff_count == 0
