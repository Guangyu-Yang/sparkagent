# config — Configuration Schema and Loading

Pydantic v2 models for the entire application configuration, loaded from `~/.sparkagent/config.json`.

> Configuration is managed via CLI commands. See [Configuration](../../README.md#configuration) in the main README.

## Files

| File | Purpose |
|------|---------|
| `schema.py` | All Pydantic models, `load_config()`, `save_config()`, `get_config_path()` |

## Key Abstractions

### Config (root model)

```
Config
├── agent: AgentConfig          # workspace path, provider, model, max_iterations, execution_mode
├── providers: ProvidersConfig
│   ├── openai: ProviderConfig  # api_key, api_base, refresh_token, expires_at, token_type
│   ├── gemini: ProviderConfig
│   └── anthropic: ProviderConfig
├── channels: ChannelsConfig
│   └── telegram: TelegramConfig  # enabled, token, allow_from
├── tools: ToolsConfig
│   ├── web_search: WebSearchConfig  # api_key (Brave)
│   └── tavily: TavilyConfig         # api_key
├── memory: MemoryConfig        # enabled, top_k_skills, max_memories_in_context, etc.
└── heartbeat: HeartbeatConfig  # enabled, interval_minutes, notify_chat_id
```

Helper methods on `Config`:
- `workspace_path` (property) — expanded `Path` from `agent.workspace`
- `get_api_key()` — active provider's API key
- `get_provider_config()` — active provider's full config
- `get_api_base()` — active provider's base URL

### Functions

- `get_config_path() -> Path` — returns `~/.sparkagent/config.json`
- `load_config() -> Config` — loads from file or returns defaults
- `save_config(config)` — writes config to JSON
