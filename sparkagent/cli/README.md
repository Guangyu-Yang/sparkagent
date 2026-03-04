# cli — Command-Line Interface

Typer-based CLI with commands for onboarding, chatting, and starting the gateway.

## Files

| File | Purpose |
|------|---------|
| `main.py` | `app` (Typer instance) — `onboard`, `login`, `chat`, `gateway`, `status` commands |
| `providers.py` | `PROVIDERS` list — static registry of provider/model options for the onboarding wizard |
| `telegram.py` | `telegram_app` — Telegram-specific onboarding sub-command |

## Commands

| Command | Description |
|---------|-------------|
| `sparkagent onboard` | Interactive setup wizard: provider → model → API key/OAuth → web search → workspace templates |
| `sparkagent login` | Authenticate with Anthropic via browser-based OAuth |
| `sparkagent chat` | Interactive chat mode (or single-message with `-m`) |
| `sparkagent gateway` | Start Telegram channel + agent loop |
| `sparkagent status` | Show current configuration |

## Key Details

### Provider Registry (`providers.py`)

`PROVIDERS: list[ProviderOption]` defines available providers and their models:

| Provider | Models |
|----------|--------|
| OpenAI | gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, o3, o4-mini |
| Gemini | gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite |
| Anthropic | claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5 |

`ModelOption` and `ProviderOption` are frozen dataclasses with slots.

### Onboarding

`onboard()` creates default workspace template files: `AGENTS.md`, `SOUL.md`, `USER.md`, `HEARTBEAT.md`, `MEMORY.md`.

### Provider Factory

`create_provider(config)` uses lazy imports to instantiate the correct `LLMProvider` subclass based on the active provider in the config.
