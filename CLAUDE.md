# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SparkAgent is a Python LLM-powered personal assistant framework (~2,500 LOC) for building AI agents with tool access (files, shell, web). It uses an async event-driven architecture with minimal dependencies.

## Development Commands

```bash
# Install dependencies (uv creates venv automatically)
uv sync                      # Install all deps
uv sync --extra telegram     # With Telegram support
uv sync --extra all          # All optional deps

# Run CLI
uv run sparkagent onboard    # Initialize config & workspace
uv run sparkagent chat       # Interactive chat mode
uv run sparkagent chat -m "..."  # Single message mode
uv run sparkagent gateway    # Start Telegram gateway

# Testing & Linting
uv run pytest                 # Run tests
uv run ruff check .           # Lint code
uv run ruff format .          # Format code
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

## Design Principles

### Orchestration Language: Python
The core agentic loop (state management, history, model calls) is written in Python. Python is chosen for rapid prototyping and deep integration with existing ML libraries. For future production deployments requiring high concurrency and distributed agent fleets, Go may be considered as an alternative.

### Generated Scripts: TypeScript via Bun
Scripts that the agent generates to access APIs and perform CLI tasks should use TypeScript executed via the Bun runtime. TypeScript's type system provides a safety layer for LLM-generated outputs, while Bun's near-instant startup time and native shell API make it more efficient and secure than Node.js or Bash for high-frequency tool calls.

### Native Platform Bridge
Agents should include platform-specific bridges to interact with native desktop applications, exposed as tools through a protocol like MCP:
- **macOS**: AppleScript or JXA for structured interaction with apps (e.g., Messages, Xcode) not accessible via standard CLI tools
- **Linux**: D-Bus for communicating with desktop services and applications (e.g., Nautilus, GNOME Settings, system notifications)

The bridge layer should present a unified tool interface to the agent, abstracting platform differences so the core orchestration logic remains cross-platform.

### Mandatory OS-Level Sandboxing
No agent-generated script should ever be executed directly on the host system. Kernel-level isolation is required:
- **Linux**: Use `bubblewrap` with deny-by-default policies
- **macOS**: Use `sandbox-exec` with deny-by-default policies

Sandboxes must only grant access to the specific directories and network domains necessary for the current task.

### Verifiable Feedback Loops for Self-Correction
The execution environment should return rich error data to the reasoning model. Capture stderr and leverage static analysis tools (e.g., Rust compiler, TypeScript type checker) as feedback signals. This iterative refinement loop enables the agent to self-correct its scripts and handle unpredictable real-world system tasks.
