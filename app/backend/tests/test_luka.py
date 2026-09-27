from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import luka

client = TestClient(app)


def test_status_does_not_expose_provider_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUKA_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    response = client.get("/api/luka/status")
    assert response.status_code == 200
    assert "test-secret" not in response.text
    assert response.json()["enabled"] is True


def test_financial_summary_reuses_existing_dashboard_metrics() -> None:
    data = luka.get_financial_summary()
    baseline = client.get("/api/dashboard/summary", params={"month": data["current_month"], "scenario": "REALISTIC", "biweekly_period": data["biweekly_period"]}).json()
    assert data["monthly_spent"] == baseline["personal_spend"]
    assert data["monthly_budget"] == baseline["monthly_budget"]
    assert data["safe_to_spend"] == baseline["safe_to_spend"]


def test_top_spending_returns_aggregates_only() -> None:
    data = luka.get_top_spending()
    assert data["items"]
    assert all(set(item) == {"label", "amount_usd"} for item in data["items"])


def test_period_comparison_is_deterministic() -> None:
    data = luka.compare_spending_periods()
    assert data["periods"][0] == luka.get_financial_summary()["current_month"]
    assert data["difference"] == round(data["current"] - data["previous"], 2)
    mtd = luka.compare_spending_periods(period="mtd")
    assert mtd["comparison_type"] == "month_to_date"
    assert len(mtd["periods"]) == 2


def test_cash_purchase_simulation_does_not_mutate_data() -> None:
    data = luka.simulate_cash_purchase(80)
    assert data["monthly_available_after"] == round(data["monthly_available_before"] - 80, 2)
    assert data["safe_to_spend_after"] == max(min(data["monthly_available_after"], data["biweekly_available_before"] - 80), 0)
    assert "items" not in data and "description" not in data
    assert not {"account", "account_number", "transaction_id", "reference", "raw_transactions"}.intersection(data)


def test_cashea_simulation_checks_math_and_projects_commitment() -> None:
    data = luka.simulate_cashea_purchase(300, 120, installments=3, installment_usd=60)
    assert data["financed_amount"] == 180
    assert data["new_future_commitment"] == 180
    assert data["installments"] * data["installment_usd"] == data["financed_amount"]
    assert data["projected_period_impacts"]["calendar_dates_available"] is False
    with pytest.raises(ValueError):
        luka.simulate_cashea_purchase(300, 120, installments=3, installment_usd=50)


def test_budget_simulation_is_not_persisted() -> None:
    data = luka.simulate_budget_change("Alimentación", 220)
    assert "persisted" in data and data["persisted"] is False


def test_safe_to_spend_and_planner_retrieval() -> None:
    assert luka.get_safe_to_spend()["safe_to_spend"] == luka.get_financial_summary()["safe_to_spend"]
    assert luka.get_planner_summary()["planning_enabled"] is True


def test_provider_failover_ends_in_deterministic_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("LUKA_PROVIDER_ORDER", "groq,gemini,openrouter")
    monkeypatch.setattr(luka, "_llm_turn", lambda *_: (_ for _ in ()).throw(__import__("httpx").ConnectError("offline")))
    result = luka.answer("¿Cómo voy este mes?")
    assert result["provider"] == "deterministic"
    assert result["fallback_used"] is True
    assert f"${luka.get_financial_summary()['monthly_spent']:.2f}" in result["message"]


@pytest.mark.parametrize("failing_providers,expected", [(["groq"], "gemini"), (["groq", "gemini"], "openrouter")])
def test_provider_failover_uses_next_configured_provider(monkeypatch: pytest.MonkeyPatch, failing_providers: list[str], expected: str) -> None:
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setenv(key, "test-key")
    monkeypatch.setenv("LUKA_PROVIDER_ORDER", "groq,gemini,openrouter")
    seen: list[str] = []

    def respond(provider: str, *_: object) -> luka.ProviderResult:
        seen.append(provider)
        if provider in failing_providers:
            raise __import__("httpx").ConnectError("offline")
        return luka.ProviderResult("Aquí está el resultado", {"monthly_spent": 0}, [])

    monkeypatch.setattr(luka, "_llm_turn", respond)
    result = luka.answer("Dame el resumen")
    assert result["provider"] == expected
    assert seen[-1] == expected
    assert result["fallback_used"] is False


def test_chat_without_keys_uses_deterministic_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    response = client.post("/api/luka/chat", json={"message": "¿En qué he gastado más?"})
    assert response.status_code == 200
    assert response.json()["provider"] == "deterministic"
    assert response.json()["tool_calls"] == ["get_top_spending"]
    assert response.json()["response_mode"] == "text"
    voice = client.post("/api/luka/chat", json={"message": "¿Cómo voy?", "response_mode": "audio"})
    assert voice.json()["voice_requested"] is True


def test_chat_rejects_oversized_message() -> None:
    response = client.post("/api/luka/chat", json={"message": "x" * 4001})
    assert response.status_code == 422


def test_transcription_rejects_bad_mime_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    response = client.post("/api/luka/transcribe", files={"file": ("x.bin", b"audio", "application/octet-stream")})
    assert response.status_code == 415


def test_transcription_rejects_oversized_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    with pytest.raises(ValueError, match="AUDIO_INVALID_SIZE"):
        luka.transcribe_audio(b"x" * (10 * 1024 * 1024 + 1), "audio/webm")


def test_transcription_unavailable_keeps_text_chat_available(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    response = client.post("/api/luka/transcribe", files={"file": ("voice.webm", b"audio", "audio/webm")})
    assert response.status_code == 503
    assert response.json()["detail"] == "STT_NOT_AVAILABLE"
    assert client.post("/api/luka/chat", json={"message": "¿Cuánto puedo gastar?"}).status_code == 200
