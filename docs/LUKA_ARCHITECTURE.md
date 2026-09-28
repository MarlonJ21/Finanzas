# LUKA V1

LUKA is an optional, read-only financial chat feature in the existing FastAPI and Next.js application. The backend uses the current DuckDB views over Parquet and delegates month summary, category budget, and planner summary to existing backend functions. The LUKA tools aggregate only the rows needed for each answer; no SQL or tool name from a model is evaluated dynamically.

## Request flow

`/luka` sends a message to `POST /api/luka/chat`. A compact system instruction, the current request, and at most three registered tool calls are sent to a configured provider. The backend validates each tool against its fixed registry, runs the calculation locally, and returns the explanation plus a small structured card. Calls without an available provider use the deterministic Spanish router for supported queries. The chat id is ephemeral; no message history or financial data is persisted.

The tool registry includes financial summary, budget and biweekly status, Safe to Spend, category and subcategory totals, merchant text aggregation, month comparison, recent transaction summary, planner summary, category forecast, cash purchase simulation, CASHEA simulation, and budget change simulation. The budget simulation reports `persisted: false`. There are no write tools.

## Providers and configuration

Providers are tried in `LUKA_PROVIDER_ORDER`. OpenRouter sends the configured model first and uses its server-side model fallback list; NVIDIA NIM retries its model list on timeout, network failure, 404, 429, and 5xx responses before advancing to the next provider. The OpenRouter and NVIDIA primaries retain the existing `LUKA_OPENROUTER_MODEL` and `LUKA_NVIDIA_MODEL` overrides. Optional `LUKA_OPENROUTER_MODELS` and `LUKA_NVIDIA_MODELS` values replace the respective fallback lists (comma-separated); otherwise the built-in lists are used. The actual responding model is returned to the chat UI and logs. Model lists are limited to endpoints documented as supporting tool calling.

The default OpenRouter sequence is GPT-4o mini, Llama 3.3 70B, Qwen3.8 27B, Mistral Small 3.2, then OpenRouter's tool-aware free-model router. NVIDIA starts with the currently deployed Llama 3.2 11B and falls through Muse Glimmer 30B and GLM 5.3/5.3 Flash. Older NVIDIA entries that are deprecated or lack function calling are not included in the tool-call cascade.

Set these environment variables in the backend environment (Render for hosted deployment):

```text
LUKA_ENABLED=true
LUKA_PROVIDER_ORDER=openrouter,nvidia,deepseek,kimi
OPENROUTER_API_KEY=
NVIDIA_API_KEY=
DEEPSEEK_API_KEY=
KIMI_API_KEY=
LUKA_OPENROUTER_MODEL=openai/gpt-4o-mini
LUKA_NVIDIA_MODEL=meta/llama-3.2-11b-vision-instruct
```

Only configured providers with a key are reported as available. No provider key is exposed to the browser. Keep secrets in Render's backend environment settings. If no LLM key is configured, deterministic supported queries remain available.

## Privacy and limits

Requests have a 4,000 character limit, audio uploads have a 10 MiB limit, provider calls time out, and a turn can execute at most three tool calls. The model sees aggregate tool results, not CSV content, account numbers, or complete transaction records. Recent transaction retrieval omits descriptions and account names. Conversation state is not persisted.

Audio is recorded in the browser and explicitly sent after user confirmation to `POST /api/luka/transcribe`. The backend validates MIME type and byte size and forwards the bytes to Groq transcription without trusting the filename or keeping a temporary copy. If Groq STT is unconfigured or unavailable, text chat remains usable. Speech output uses browser SpeechSynthesis with Spanish voice preference and text fallback.

## Testing

Run backend checks from `app/backend` using `uv run pytest`. Tests use local Parquet outputs and mocks; they do not require provider API keys. Run frontend `npm run build` from `app/frontend`. The existing Render start command remains `python app/backend/run_server.py` as defined by the project's deployment setup; LUKA is included by the existing FastAPI app.
