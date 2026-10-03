from __future__ import annotations

import base64

import httpx
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
    assert data["safe_to_spend_after"] == round(max(min(data["monthly_available_after"], data["biweekly_available_before"] - 80), 0), 2)
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


def test_openrouter_model_cascade_preserves_primary_and_returns_actual_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUKA_OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("LUKA_OPENROUTER_MODELS", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    captured: list[dict] = []

    def post(_url: str, **kwargs: object) -> __import__("httpx").Response:
        captured.append(kwargs["json"])
        return __import__("httpx").Response(200, json={"model": "qwen/qwen3.8-27b:free", "choices": []}, request=__import__("httpx").Request("POST", _url))

    monkeypatch.setattr(luka.httpx, "post", post)
    result = luka._openai_call("openrouter", [{"role": "user", "content": "hi"}], [])
    assert result["model"] == "qwen/qwen3.8-27b:free"
    assert captured[0]["model"] == "openai/gpt-4o-mini"
    assert captured[0]["models"] == [
        "meta-llama/llama-3.3-70b-instruct:free", "qwen/qwen3.8-27b:free",
        "mistralai/mistral-small-3.2-24b-instruct:free",
    ]
    assert len(captured[0]["models"]) <= 3


def test_nvidia_model_cascade_moves_on_429_and_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUKA_NVIDIA_MODEL", raising=False)
    monkeypatch.delenv("LUKA_NVIDIA_MODELS", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    attempts: list[str] = []

    def post(_url: str, **kwargs: object) -> __import__("httpx").Response:
        model = kwargs["json"]["model"]
        attempts.append(model)
        status = 429 if len(attempts) == 1 else 404 if len(attempts) == 2 else 200
        return __import__("httpx").Response(status, json={"model": model, "choices": []}, request=__import__("httpx").Request("POST", _url))

    monkeypatch.setattr(luka.httpx, "post", post)
    result = luka._openai_call("nvidia", [{"role": "user", "content": "hi"}], [])
    assert attempts == ["meta/llama-3.2-11b-vision-instruct", "meta/muse-glimmer-30b", "z-ai/glm-5.3"]
    assert result["model"] == "z-ai/glm-5.3"


@pytest.mark.parametrize("failing_providers,expected", [(["deepseek"], "gemini"), (["deepseek", "gemini"], "groq"), (["deepseek", "gemini", "groq"], "openrouter")])
def test_provider_failover_uses_next_configured_provider(monkeypatch: pytest.MonkeyPatch, failing_providers: list[str], expected: str) -> None:
    for key in ("DEEPSEEK_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setenv(key, "test-key")
    monkeypatch.setenv("LUKA_PROVIDER_ORDER", "deepseek,gemini,groq,openrouter")
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
    for name in ("DEEPSEEK_API_KEY", "KIMI_API_KEY", "MOONSHOT_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
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


def test_openrouter_transcribes_recorded_webm_and_enables_voice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("LUKA_OPENROUTER_STT_MODEL", raising=False)
    captured: list[dict] = []

    def post(url: str, **kwargs: object) -> httpx.Response:
        assert url == "https://openrouter.ai/api/v1/audio/transcriptions"
        captured.append(kwargs["json"])
        return httpx.Response(200, json={"text": "¿Cuánto puedo gastar?"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(luka.httpx, "post", post)
    response = client.post("/api/luka/transcribe", files={"file": ("voice.webm", b"recorded-webm", "audio/webm;codecs=opus")})
    assert response.status_code == 200
    assert response.json()["text"] == "¿Cuánto puedo gastar?"
    assert captured[0]["model"] == "openai/gpt-4o-mini-transcribe"
    assert captured[0]["input_audio"] == {"data": base64.b64encode(b"recorded-webm").decode("ascii"), "format": "webm"}
    assert client.get("/api/luka/status").json()["stt_available"] is True


def test_openrouter_stt_retries_with_whisper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("LUKA_OPENROUTER_STT_MODEL", raising=False)
    models: list[str] = []

    def post(url: str, **kwargs: object) -> httpx.Response:
        model = kwargs["json"]["model"]
        models.append(model)
        status = 503 if len(models) == 1 else 200
        return httpx.Response(status, json={"text": "Hola Luka"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(luka.httpx, "post", post)
    assert luka.transcribe_audio(b"recorded-webm", "audio/webm") == "Hola Luka"
    assert models == ["openai/gpt-4o-mini-transcribe", "openai/whisper-1"]


def test_transcription_unavailable_keeps_text_chat_available(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DEEPSEEK_API_KEY", "KIMI_API_KEY", "MOONSHOT_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    response = client.post("/api/luka/transcribe", files={"file": ("voice.webm", b"audio", "audio/webm")})
    assert response.status_code == 503
    assert response.json()["detail"] == "STT_NOT_AVAILABLE"
    assert client.post("/api/luka/chat", json={"message": "¿Cuánto puedo gastar?"}).status_code == 200


def test_get_peak_spending_days() -> None:
    res = luka.get_peak_spending_days()
    assert "month" in res
    assert "peak_day" in res
    assert "peak_amount_usd" in res
    assert isinstance(res["days"], list)
    if res["days"]:
        top = res["days"][0]
        assert "date" in top and "total_usd" in top and "tx_count" in top
        assert top["total_usd"] == res["peak_amount_usd"]


def test_get_weekly_spending() -> None:
    res = luka.get_weekly_spending()
    assert "month" in res
    assert "weeks" in res
    assert len(res["weeks"]) == 5
    assert "total_month_usd" in res
    if res["peak_week"]:
        assert res["peak_week_amount_usd"] > 0


def test_find_budget_breach_transaction() -> None:
    # Test breach in Salud
    res = luka.find_budget_breach_transaction("Salud")
    assert res["category"].lower() == "salud"
    assert res["budget_usd"] > 0
    if res["breached"]:
        assert res["breach_transaction"] is not None
        assert "date" in res["breach_transaction"]
        assert "amount_usd" in res["breach_transaction"]
        assert res["over_by"] > 0


def test_search_transactions() -> None:
    # Test general search with min_amount
    res = luka.search_transactions(min_amount=10, limit=5)
    assert "items" in res
    assert res["count"] == len(res["items"])
    assert all(item["amount_usd"] >= 10 for item in res["items"])


def test_deterministic_movement_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure keys are clear so deterministic path is tested
    for name in ("DEEPSEEK_API_KEY", "KIMI_API_KEY", "MOONSHOT_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    ans_day = luka.answer("¿Cuál fue el día que más gasté en el mes?")
    assert ans_day["provider"] == "deterministic"
    assert "get_peak_spending_days" in ans_day["tool_calls"]

    ans_week = luka.answer("¿En qué semana gasté más?")
    assert ans_week["provider"] == "deterministic"
    assert "get_weekly_spending" in ans_week["tool_calls"]

    ans_breach = luka.answer("¿En qué movimiento superé el presupuesto de Salud?")
    assert ans_breach["provider"] == "deterministic"
    assert "find_budget_breach_transaction" in ans_breach["tool_calls"]

    ans_today = luka.answer("¿Cuánto había gastado hoy?")
    assert ans_today["provider"] == "deterministic"
    assert "get_daily_spending" in ans_today["tool_calls"]
    assert "$11.54" in ans_today["message"]
    assert "Yummy" in ans_today["message"]


def test_get_daily_spending() -> None:
    res = luka.get_daily_spending("2026-10-03")
    assert res["date"] == "2026-10-03"
    assert res["total_spent_usd"] == 11.54
    assert res["personal_spent_usd"] == 11.54
    assert res["business_spent_usd"] == 0.00
    assert res["total_income_usd"] == 40.00
    assert res["expense_count"] == 7
    # Verify Yummy is classified natively as Transporte
    yummy_item = next(e for e in res["expenses"] if "Yummy" in e["description"])
    assert yummy_item["category"] == "Transporte"
    assert yummy_item["subcategory"] == "Taxis"


def test_premiadosve_spending(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DEEPSEEK_API_KEY", "KIMI_API_KEY", "MOONSHOT_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    ans = luka.answer("cuánto he gastado en total de premiados VE")
    assert ans["provider"] == "deterministic"
    assert "get_spending_by_category" in ans["tool_calls"]
    assert "$205.29" in ans["message"]
    assert "$5.48" in ans["message"]

    cat_data = luka.get_spending_by_category("PremiadosVE")
    assert cat_data["domain"] == "NEGOCIO"
    assert cat_data["all_time_spent_usd"] == 205.29
    assert cat_data["amount_usd"] == 5.48
    assert cat_data["all_time_income_usd"] == 720.78


def test_get_sales_and_income() -> None:
    sales = luka.get_sales_and_income("PremiadosVE")
    assert sales["business_or_category"] == "PremiadosVE"
    assert sales["period_sales_usd"] == 113.50
    assert sales["period_sales_count"] == 3
    assert sales["all_time_sales_usd"] == 720.78
    assert sales["all_time_sales_count"] == 19
    assert sales["period_expenses_usd"] == 5.48
    assert sales["period_net_profit_usd"] == 108.02
    assert sales["all_time_net_profit_usd"] == 515.49
    assert len(sales["recent_sales"]) > 0

    # Test search_transactions with transaction_type="income"
    income_tx = luka.search_transactions(query="PremiadosVE", transaction_type="income", limit=10)
    assert income_tx["count"] > 0
    assert all(item["amount_usd"] > 0 for item in income_tx["items"])


def test_sales_and_income_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DEEPSEEK_API_KEY", "KIMI_API_KEY", "MOONSHOT_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    ans_month = luka.answer("¿Cuáles fueron mis ventas?")
    assert ans_month["provider"] == "deterministic"
    assert "get_sales_and_income" in ans_month["tool_calls"]
    assert "$113.50" in ans_month["message"]
    assert "$720.78" in ans_month["message"]
    assert "+$108.02" in ans_month["message"]

    ans_total = luka.answer("¿Cuánto he vendido en total de PremiadosVE?")
    assert ans_total["provider"] == "deterministic"
    assert "get_sales_and_income" in ans_total["tool_calls"]
    assert "$720.78" in ans_total["message"]



