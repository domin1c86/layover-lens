from app.agents.search_agent_models import AgentModelUsage
from app.agents.token_usage import TokenUsageRecorder


def test_token_usage_recorder_keeps_unavailable_streaming_usage_in_memory(monkeypatch) -> None:
    monkeypatch.setattr(TokenUsageRecorder, "_initialize_mysql", lambda self: False)
    recorder = TokenUsageRecorder()

    recorder.record(
        user_id="user_1",
        session_id="ai_1",
        request_id="req_1",
        call_type="stream_reply",
        usage=AgentModelUsage(
            provider="openai_compatible",
            model="mimo-test",
            usage_unavailable=True,
        ),
    )

    rows = recorder.aggregate_by_provider_day()
    assert rows[-1]["provider"] == "openai_compatible"
    assert rows[-1]["model"] == "mimo-test"
    assert rows[-1]["call_type"] == "stream_reply"
    assert rows[-1]["input_tokens"] is None


def test_token_usage_cache_hit_ratio_is_preserved_in_memory(monkeypatch) -> None:
    monkeypatch.setattr(TokenUsageRecorder, "_initialize_mysql", lambda self: False)
    recorder = TokenUsageRecorder()

    recorder.record(
        user_id="user_1",
        session_id="ai_1",
        request_id="req_2",
        call_type="reply",
        usage=AgentModelUsage(
            provider="openai_compatible",
            model="mimo-test",
            input_tokens=200,
            output_tokens=20,
            total_tokens=220,
            cached_input_tokens=150,
            uncached_input_tokens=50,
            cache_hit_ratio=0.75,
            raw_usage_json={"prompt_tokens": 200},
        ),
    )

    rows = recorder.aggregate_by_provider_day()
    assert rows[-1]["input_tokens"] == 200
    assert rows[-1]["cached_input_tokens"] == 150
    assert rows[-1]["uncached_input_tokens"] == 50
    assert rows[-1]["cache_hit_ratio"] == 0.75
