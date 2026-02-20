# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SparkAgent is a Python LLM-powered personal assistant framework (~2,500 LOC) for building AI agents with tool access (files, shell, web). It uses an async event-driven architecture with minimal dependencies.

## Development Commands

```bash
# Install in development mode
pip install -e .
pip install -e ".[telegram]"  # With Telegram support
pip install -e ".[all]"       # All optional deps

# Run CLI
sparkagent onboard           # Initialize config & workspace
sparkagent chat              # Interactive chat mode
sparkagent chat -m "..."     # Single message mode
sparkagent gateway           # Start Telegram gateway

# Testing & Linting
pytest                        # Run tests
ruff check .                  # Lint code
ruff format .                 # Format code
```

## Architecture

### Data Flow
1. User message → `MessageBus` (inbound queue)
2. `AgentLoop` receives → `ContextBuilder` assembles prompt + history
3. `OpenAICompatibleProvider` calls LLM with tool schemas
4. Loop executes tool calls → accumulates results
5. LLM returns final response → `Session` saves history
6. `OutboundMessage` → Channel sends response

### Core Modules

- **`agent/loop.py`** - `AgentLoop`: Main processing engine, receives messages, calls LLM, executes tools
- **`agent/context.py`** - `ContextBuilder`: Assembles system prompts from workspace files (AGENTS.md, SOUL.md, USER.md, TOOLS.md)
- **`agent/tools/`** - Tool implementations with `ToolRegistry` for dynamic management
- **`providers/openai_compat.py`** - `OpenAICompatibleProvider`: Works with OpenAI, OpenRouter, vLLM endpoints
- **`bus/events.py`** - `MessageBus`: Async queue-based pub/sub for message routing
- **`session/manager.py`** - `Session`/`SessionManager`: JSONL-based conversation persistence
- **`channels/`** - I/O integrations (CLI, Telegram)
- **`config/schema.py`** - Pydantic models for configuration

### Key Patterns
- **Async-first**: All I/O operations use async/await with httpx
- **ABC pattern**: `Tool`, `LLMProvider`, `BaseChannel` as abstract bases
- **Registry pattern**: `ToolRegistry` for tool management
- **Workspace personalization**: Markdown files at `~/.sparkagent/workspace/` shape agent behavior
- **Safety guards**: `ShellTool` blocks dangerous commands (rm -rf, dd, reboot, etc.)

### File Locations
- Config: `~/.sparkagent/config.json`
- Workspace: `~/.sparkagent/workspace/`
- Sessions: `~/.sparkagent/sessions/`

## Code Style

- Python 3.11+ with type hints (`str | None` union syntax)
- Pydantic v2 for data validation
- Line length: 100 chars (ruff configured)
- Lint rules: E, F, I, W (E501 ignored)
