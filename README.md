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
- **Dynamic Memory** — Learnable memory skills that extract, consolidate, and prune knowledge across conversations
- **Workspace Files** — Customizable agent personality (AGENTS.md, SOUL.md)

## Supported Providers

SparkAgent works with any model available through these provider SDKs:

- **OpenAI** — via the OpenAI Python SDK
- **Google Gemini** — via the Google GenAI SDK
- **Anthropic** — via the Anthropic Python SDK (API key or OAuth with Claude Max/Pro)

The onboarding wizard (`sparkagent onboard`) suggests popular models for each provider, but you can use any model by setting the `model` field in `~/.sparkagent/config.json`.

See [`sparkagent/providers/README.md`](sparkagent/providers/README.md) for provider details and the `LLMProvider` interface.

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

The setup wizard walks you through token and access configuration:

```bash
uv run sparkagent telegram onboard
```

```
Telegram Bot Setup

  1. Open Telegram and search for @BotFather
  2. Send /newbot and follow the prompts to create a bot
  3. Copy the bot token (looks like 123456:ABC-xyz...)

Bot token: ****
  > Token saved

Restrict access (recommended):

  To find your user ID, send /start to @userinfobot on Telegram.

Your user ID (leave blank to allow everyone): 123456789
  > Access restricted to: 123456789

Telegram bot configured!
Run `sparkagent gateway` to start.
```

### 3. Run

```bash
uv run sparkagent gateway
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `uv run sparkagent onboard` | Interactive setup wizard |
| `uv run sparkagent login` | OAuth login for Claude Max/Pro |
| `uv run sparkagent telegram onboard` | Interactive Telegram bot setup |
| `uv run sparkagent chat -m "..."` | Send a message |
| `uv run sparkagent chat` | Interactive chat |
| `uv run sparkagent gateway` | Start Telegram gateway |
| `uv run sparkagent status` | Show status and auth info |

## Dynamic Memory

SparkAgent includes an opt-in dynamic memory system. Instead of relying on a static memory file, the agent uses **learnable memory skills** — structured routines that decide what to remember, update, or forget after each conversation turn.

### How it works

1. **Selector** — After each turn, an LLM call picks the most relevant memory skills to apply.
2. **Executor** — A second LLM call generates concrete memory operations (insert, update, delete, noop) guided by the selected skills.
3. **Designer** — When enough failures accumulate, a third LLM call analyzes them and evolves the skill bank — proposing new skills or refining existing ones.

Memory skills are stored as markdown files in `~/.sparkagent/memory/skills/`, and memory entries are persisted as JSONL in `~/.sparkagent/memory/entries.jsonl`.

### Enable it

Add to your `~/.sparkagent/config.json`:

```json
{
  "memory": {
    "enabled": true
  }
}
```

See [`sparkagent/memory/README.md`](sparkagent/memory/README.md) for configuration options, storage layout, and the full memory pipeline.

## Built-in Tools

SparkAgent ships with file operations (`read_file`, `write_file`, `edit_file`, `list_directory`), a shell executor, and web tools (`web_search`, `web_fetch`). The shell tool blocks dangerous commands before execution.

See [`sparkagent/agent/tools/README.md`](sparkagent/agent/tools/README.md) for the full tool API, registry system, and safety details.

## Configuration

The recommended way to configure SparkAgent is via the onboarding wizard:

```bash
uv run sparkagent onboard
```

Configuration is stored at `~/.sparkagent/config.json` and is managed automatically by the CLI commands (`onboard`, `login`, `telegram onboard`). See [`sparkagent/config/README.md`](sparkagent/config/README.md) for the full schema reference.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Inspired by [nanobot](https://github.com/HKUDS/nanobot) and [OpenClaw](https://github.com/openclaw/openclaw).
