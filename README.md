# SparkAgent

An LLM-powered personal assistant framework for building AI agents with tool access.

**Multi-provider** — works with OpenAI, Google Gemini, and Anthropic (including Claude Max/Pro via OAuth).

## Features

- **Agent Loop** — LLM ↔ tool execution cycle
- **Multi-Provider** — OpenAI, Google Gemini, and Anthropic via official SDKs
- **OAuth Login** — Use your Claude Max/Pro subscription via browser-based OAuth
- **Built-in Tools** — File operations, shell, web search/fetch
- **Chat Channels** — Telegram integration (more coming)
- **Session Memory** — Persistent conversation history
- **Workspace Files** — Customizable agent personality (AGENTS.md, SOUL.md)

## Supported Models

| Provider | Models |
|----------|--------|
| **OpenAI** | GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano, o3, o4-mini |
| **Google Gemini** | Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.5 Flash Lite |
| **Anthropic** | Claude Opus 4.6, Claude Sonnet 4.6, Claude Haiku 4.5 |

## Installation

**From source (recommended for development):**

```bash
git clone https://github.com/Guangyu-Yang/sparkagent.git
cd sparkagent
uv sync
```

**With a specific provider SDK:**

```bash
uv sync --extra openai      # OpenAI
uv sync --extra gemini      # Google Gemini
uv sync --extra anthropic   # Anthropic
uv sync --extra all-providers  # All providers
```

**With Telegram support:**

```bash
uv sync --extra telegram
```

**Everything:**

```bash
uv sync --extra all
```

## Quick Start

### 1. Set up

The interactive onboarding wizard walks you through provider selection, model choice, and API key configuration:

```bash
uv run sparkagent onboard
```

```
Step 1: Choose your LLM provider

  1. OpenAI
  2. Google Gemini
  3. Anthropic

Select provider [1]:

Step 2: Choose a model

  1. GPT-4.1         Smartest non-reasoning model, 1M context
  2. GPT-4.1 Mini    Fast and affordable
  3. GPT-4.1 Nano    Cheapest and fastest
  4. o3              Reasoning model for complex tasks
  5. o4-mini         Fast, cost-efficient reasoning

Select model [1]:

Step 3: Enter your API key or token

  Get one at: https://platform.openai.com/api-keys

API key / token: ****
```

This saves everything to `~/.sparkagent/config.json` automatically. Run `onboard` again at any time to switch providers or models.

> **Anthropic users:** When you select Anthropic in Step 3, you'll get an additional option to log in via browser using your Claude Max/Pro subscription — see [OAuth Login](#oauth-login) below.

### 2. Chat

```bash
# Single message
uv run sparkagent chat -m "What is 2+2?"

# Interactive mode
uv run sparkagent chat
```

## OAuth Login

If you have a Claude Max or Pro subscription, you can authenticate with your existing account instead of a separate API key. SparkAgent uses the same OAuth flow as Claude Code's `setup-token` command.

```bash
uv run sparkagent login
```

This will:

1. Open your browser to Anthropic's authorization page (`claude.ai`)
2. You log in and click "Authorize"
3. Copy the full authorization code from the callback page (it looks like `abc123...#xyz789...` — copy the entire string including the `#` part)
4. Paste it back into the CLI

```
OAuth Login

  1. A browser window will open. Log in and authorize SparkAgent.
  2. After authorizing, copy the authorization code from the page.

Paste the authorization code here: ****
  > OAuth tokens saved

Select a model:

  1. Claude Opus 4.6     Most capable, highest quality
  2. Claude Sonnet 4.6   Best balance of speed and quality
  3. Claude Haiku 4.5    Fastest and most affordable

Select model [1]:

Login complete!
```

The OAuth token auto-refreshes every 8 hours. Check your auth status with:

```bash
uv run sparkagent status
```

> **Note:** You can also choose OAuth login during `sparkagent onboard` when selecting Anthropic as your provider.

## Telegram Bot

### 1. Create a bot

- Open Telegram, search `@BotFather`
- Send `/newbot`, follow prompts
- Copy the token

### 2. Configure

Add the Telegram section to `~/.sparkagent/config.json`:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allow_from": ["YOUR_USER_ID"]
    }
  }
}
```

Get your user ID from `@userinfobot` on Telegram.

### 3. Run

```bash
uv run sparkagent gateway
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `uv run sparkagent onboard` | Interactive setup wizard |
| `uv run sparkagent login` | OAuth login for Claude Max/Pro |
| `uv run sparkagent chat -m "..."` | Send a message |
| `uv run sparkagent chat` | Interactive chat |
| `uv run sparkagent gateway` | Start Telegram gateway |
| `uv run sparkagent status` | Show status and auth info |

## Project Structure

```
sparkagent/
├── agent/           # Core agent logic
│   ├── loop.py      #   Agent loop (LLM ↔ tools)
│   ├── context.py   #   Prompt builder
│   └── tools/       #   Built-in tools
├── auth/            # OAuth authentication (PKCE, token refresh)
├── providers/       # LLM providers (OpenAI, Gemini, Anthropic)
├── session/         # Conversation history
├── channels/        # Chat integrations
├── bus/             # Message routing
├── config/          # Configuration
└── cli/             # Commands & onboarding
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `write_file` | Write/create files |
| `edit_file` | Replace text in files |
| `list_directory` | List directory contents |
| `shell` | Execute shell commands |
| `web_search` | Search the web (Brave API) |
| `web_fetch` | Fetch web page content |

## Configuration

The recommended way to configure SparkAgent is via the onboarding wizard:

```bash
uv run sparkagent onboard
```

The config file lives at `~/.sparkagent/config.json`. Here's a full example for reference:

```json
{
  "agent": {
    "workspace": "~/.sparkagent/workspace",
    "provider": "openai",
    "model": "gpt-4.1",
    "max_iterations": 20
  },
  "providers": {
    "openai": {
      "api_key": "sk-xxx"
    },
    "gemini": {
      "api_key": "AIza-xxx"
    },
    "anthropic": {
      "api_key": "sk-ant-xxx"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "123456:ABC...",
      "allow_from": ["123456789"]
    }
  },
  "tools": {
    "web_search": {
      "api_key": "BSA-xxx"
    }
  }
}
```

The `agent.provider` field determines which provider's API key and SDK are used. Set it to `"openai"`, `"gemini"`, or `"anthropic"`.

When using OAuth login (`sparkagent login`), the Anthropic provider config will also include `refresh_token`, `expires_at`, and `token_type` fields that are managed automatically.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Inspired by [nanobot](https://github.com/HKUDS/nanobot) and [OpenClaw](https://github.com/openclaw/openclaw).
