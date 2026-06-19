import pytest

from core.guardrails import GuardrailError, assert_no_anthropic_api_key


def test_guardrail_passes_when_unset(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert_no_anthropic_api_key()  # should not raise


def test_guardrail_fails_when_api_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-something")
    with pytest.raises(GuardrailError):
        assert_no_anthropic_api_key()
