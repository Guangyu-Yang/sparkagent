# 🤖 MyAutoAgent

A lightweight LLM-powered personal assistant built from scratch.

**~2,500 lines of Python** — minimal dependencies, maximum functionality.

## ✨ Features

- 🧠 **Agent Loop** — LLM ↔ tool execution cycle
- 🔧 **Built-in Tools** — File operations, shell, web search/fetch
- 💬 **Chat Channels** — Telegram integration (more coming)
- 💾 **Session Memory** — Persistent conversation history
- 🎯 **Workspace Files** — Customizable agent personality (AGENTS.md, SOUL.md)

## 📦 Installation

**From source (recommended for development):**

```bash
git clone https://github.com/Guangyu-Yang/MyAutoAgent.git
cd MyAutoAgent
pip install -e .
```

**With Telegram support:**

```bash
pip install -e ".[telegram]"
```

## 🚀 Quick Start

### 1. Initialize

```bash
myautoagent onboard
```

### 2. Configure

Edit `~/.myautoagent/config.json`:

```json
{
  "providers": {
    "openrouter": {
      "api_key": "sk-or-v1-xxx"
    }
  },
  "agent": {
    "model": "anthropic/claude-sonnet-4"
  }
}
```

Get an API key at: [openrouter.ai](https://openrouter.ai/keys)

### 3. Chat

```bash
# Single message
myautoagent chat -m "What is 2+2?"

# Interactive mode
myautoagent chat
```

## 💬 Telegram Bot

### 1. Create a bot

- Open Telegram, search `@BotFather`
- Send `/newbot`, follow prompts
- Copy the token

### 2. Configure

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
myautoagent gateway
```

## 🛠️ CLI Reference

| Command | Description |
|---------|-------------|
| `myautoagent onboard` | Initialize config & workspace |
| `myautoagent chat -m "..."` | Send a message |
| `myautoagent chat` | Interactive chat |
| `myautoagent gateway` | Start Telegram gateway |
| `myautoagent status` | Show status |

## 📁 Project Structure

```
myautoagent/
├── agent/           # 🧠 Core agent logic
│   ├── loop.py      #    Agent loop (LLM ↔ tools)
│   ├── context.py   #    Prompt builder
│   └── tools/       #    Built-in tools
├── providers/       # 🤖 LLM providers
├── session/         # 💾 Conversation history
├── channels/        # 📱 Chat integrations
├── bus/             # 🚌 Message routing
├── config/          # ⚙️ Configuration
└── cli/             # 🖥️ Commands
```

## 🔧 Built-in Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `write_file` | Write/create files |
| `edit_file` | Replace text in files |
| `list_directory` | List directory contents |
| `shell` | Execute shell commands |
| `web_search` | Search the web (Brave API) |
| `web_fetch` | Fetch web page content |

## ⚙️ Configuration

Full config example (`~/.myautoagent/config.json`):

```json
{
  "agent": {
    "workspace": "~/.myautoagent/workspace",
    "model": "anthropic/claude-sonnet-4",
    "max_iterations": 20
  },
  "providers": {
    "openrouter": {
      "api_key": "sk-or-v1-xxx"
    },
    "openai": {
      "api_key": "sk-xxx"
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

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

Inspired by [nanobot](https://github.com/HKUDS/nanobot) and [OpenClaw](https://github.com/openclaw/openclaw).
