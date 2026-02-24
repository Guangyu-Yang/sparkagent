"""CLI commands for SparkAgent."""

import asyncio
import webbrowser
from pathlib import Path

import typer
from rich.console import Console

from sparkagent import __version__
from sparkagent.cli.telegram import telegram_app

app = typer.Typer(
    name="sparkagent",
    help="SparkAgent - A lightweight LLM-powered assistant",
    no_args_is_help=True,
)
app.add_typer(telegram_app, name="telegram")

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"SparkAgent v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """SparkAgent - Personal AI Assistant."""
    pass


# ============================================================================
# Provider Factory
# ============================================================================


def create_provider(config):
    """Instantiate the correct LLM provider from config.

    Uses lazy imports so a missing SDK only errors when that provider is selected.
    """
    from sparkagent.providers import OpenAICompatibleProvider

    provider_name = config.agent.provider
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    model = config.agent.model

    if provider_name == "anthropic":
        from sparkagent.config import save_config
        from sparkagent.providers.anthropic import AnthropicProvider

        provider_config = config.get_provider_config()

        def on_token_refresh(access_token, refresh_token, expires_at):
            provider_config.api_key = access_token
            provider_config.refresh_token = refresh_token
            provider_config.expires_at = expires_at
            save_config(config)

        return AnthropicProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=model,
            refresh_token=provider_config.refresh_token or None,
            expires_at=provider_config.expires_at or None,
            token_type=provider_config.token_type or None,
            on_token_refresh=on_token_refresh if provider_config.token_type == "oauth" else None,
        )
    elif provider_name == "gemini":
        from sparkagent.providers.gemini import GeminiProvider

        return GeminiProvider(api_key=api_key, api_base=api_base, default_model=model)
    else:
        return OpenAICompatibleProvider(
            api_key=api_key, api_base=api_base, default_model=model
        )


# ============================================================================
# OAuth Flow Helper
# ============================================================================


def _run_oauth_flow(config):
    """Run the browser-based Anthropic OAuth flow.

    Opens the browser for authorization, prompts the user to paste the code,
    exchanges it for tokens, and stores them in config.

    Modifies ``config`` in place but does NOT save it — caller is responsible
    for calling ``save_config(config)``.
    """
    from sparkagent.auth.oauth import (
        build_authorization_url,
        compute_expires_at,
        exchange_code_for_tokens,
        generate_pkce_pair,
    )

    code_verifier, code_challenge = generate_pkce_pair()

    auth_url = build_authorization_url(code_challenge, code_verifier)

    console.print("\n[bold]OAuth Login[/bold]\n")
    console.print("  1. A browser window will open. Log in and authorize SparkAgent.")
    console.print("  2. After authorizing, copy the authorization code from the page.")
    console.print(f"\n  [dim]URL: {auth_url}[/dim]\n")

    # Attempt to open the browser
    webbrowser.open(auth_url)

    auth_code = typer.prompt("Paste the authorization code here")
    if not auth_code.strip():
        console.print("[red]Authorization code cannot be empty.[/red]")
        raise typer.Exit(1)

    # Exchange code for tokens
    console.print("  Exchanging code for tokens...")

    async def do_exchange():
        return await exchange_code_for_tokens(auth_code.strip(), code_verifier)

    try:
        tokens = asyncio.run(do_exchange())
    except Exception as e:
        console.print(f"[red]OAuth failed: {e}[/red]")
        raise typer.Exit(1)

    # Store tokens in config
    provider_config = config.providers.anthropic
    provider_config.api_key = tokens.access_token
    provider_config.refresh_token = tokens.refresh_token
    provider_config.expires_at = compute_expires_at(tokens.expires_in)
    provider_config.token_type = "oauth"

    config.agent.provider = "anthropic"

    console.print("  [green]>[/green] OAuth tokens saved\n")


# ============================================================================
# Setup / Onboard
# ============================================================================


@app.command()
def onboard():
    """Interactive setup wizard for provider, model, and API key."""
    from sparkagent.cli.providers import PROVIDERS
    from sparkagent.config import Config, get_config_path, load_config, save_config

    config_path = get_config_path()

    # Load existing config or create new one
    if config_path.exists():
        config = load_config()
        console.print(f"[dim]Updating existing config at {config_path}[/dim]\n")
    else:
        config = Config()

    # --- Step 1: Select provider ---
    console.print("[bold]Step 1:[/bold] Choose your LLM provider\n")
    for i, p in enumerate(PROVIDERS, 1):
        console.print(f"  [cyan]{i}[/cyan]. {p.label}")
    console.print()

    provider_idx = typer.prompt("Select provider", type=int, default=1) - 1
    if provider_idx < 0 or provider_idx >= len(PROVIDERS):
        console.print("[red]Invalid selection.[/red]")
        raise typer.Exit(1)

    provider = PROVIDERS[provider_idx]
    config.agent.provider = provider.key
    console.print(f"  [green]>[/green] {provider.label}\n")

    # --- Step 2: Select model ---
    console.print("[bold]Step 2:[/bold] Choose a model\n")
    for i, m in enumerate(provider.models, 1):
        console.print(f"  [cyan]{i}[/cyan]. {m.label}  [dim]{m.description}[/dim]")
    console.print()

    model_idx = typer.prompt("Select model", type=int, default=1) - 1
    if model_idx < 0 or model_idx >= len(provider.models):
        console.print("[red]Invalid selection.[/red]")
        raise typer.Exit(1)

    model = provider.models[model_idx]
    config.agent.model = model.id
    console.print(f"  [green]>[/green] {model.label} ({model.id})\n")

    # --- Step 3: Enter credential ---
    if provider.key == "anthropic":
        # Offer OAuth option for Anthropic
        console.print("[bold]Step 3:[/bold] Choose authentication method\n")
        console.print("  [cyan]1[/cyan]. Paste an API key or token")
        console.print("  [cyan]2[/cyan]. Log in via browser (Claude Max/Pro)")
        console.print()

        auth_choice = typer.prompt("Select auth method", type=int, default=1)

        if auth_choice == 2:
            _run_oauth_flow(config)
        else:
            console.print(
                f"\n  Get one at: "
                f"[link={provider.key_url_hint}]{provider.key_url_hint}[/link]\n"
            )
            api_key = typer.prompt("API key / token", hide_input=True)
            if not api_key.strip():
                console.print("[red]Credential cannot be empty.[/red]")
                raise typer.Exit(1)

            provider_config = getattr(config.providers, provider.key)
            provider_config.api_key = api_key.strip()
            # Clear any previous OAuth state
            provider_config.refresh_token = ""
            provider_config.expires_at = ""
            provider_config.token_type = ""
            console.print("  [green]>[/green] Credential saved\n")
    else:
        console.print("[bold]Step 3:[/bold] Enter your API key or token\n")
        console.print(
            f"  Get one at: "
            f"[link={provider.key_url_hint}]{provider.key_url_hint}[/link]\n"
        )

        api_key = typer.prompt("API key / token", hide_input=True)
        if not api_key.strip():
            console.print("[red]Credential cannot be empty.[/red]")
            raise typer.Exit(1)

        # Save the credential to the correct provider slot
        provider_config = getattr(config.providers, provider.key)
        provider_config.api_key = api_key.strip()
        console.print("  [green]>[/green] Credential saved\n")

    # --- Step 4: Save config ---
    save_config(config)
    console.print(f"[green]>[/green] Config saved to {config_path}")

    # --- Step 5: Create workspace + templates ---
    workspace = config.workspace_path
    workspace.mkdir(parents=True, exist_ok=True)
    _create_templates(workspace)

    console.print("\n[bold green]Setup complete![/bold green]")
    console.print(f"\nProvider: [cyan]{provider.label}[/cyan]")
    console.print(f"Model:    [cyan]{model.id}[/cyan]")
    console.print("\nTry it out: [cyan]sparkagent chat -m \"Hello!\"[/cyan]")


def _create_templates(workspace: Path):
    """Create default workspace templates."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines
- Explain what you're doing before taking actions
- Ask for clarification when needed
- Use tools to help accomplish tasks
""",
        "SOUL.md": """# Soul

I am SparkAgent, a lightweight AI assistant.

## Personality
- Helpful and friendly
- Concise and to the point
- Curious and eager to learn
""",
        "USER.md": """# User

Information about the user.

## Preferences
- Communication style: casual
- Timezone: (your timezone)
""",
    }

    for filename, content in templates.items():
        path = workspace / filename
        if not path.exists():
            path.write_text(content)

    # Create memory directory
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("# Long-term Memory\n\nImportant information to remember.\n")


# ============================================================================
# Login Command
# ============================================================================


@app.command()
def login():
    """Authenticate with Anthropic via OAuth (for Claude Max/Pro subscribers)."""
    from sparkagent.cli.providers import get_provider
    from sparkagent.config import Config, get_config_path, load_config, save_config

    config_path = get_config_path()
    config = load_config() if config_path.exists() else Config()

    # Warn if current provider is not Anthropic
    if config.agent.provider and config.agent.provider != "anthropic":
        current = get_provider(config.agent.provider)
        label = current.label if current else config.agent.provider
        console.print(
            f"[yellow]Current provider is {label}. "
            f"This will switch to Anthropic.[/yellow]\n"
        )

    # Run the OAuth flow
    _run_oauth_flow(config)

    # Prompt for model if not set
    if not config.agent.model or config.agent.provider != "anthropic":
        anthropic_provider = get_provider("anthropic")
        if anthropic_provider:
            console.print("[bold]Select a model:[/bold]\n")
            for i, m in enumerate(anthropic_provider.models, 1):
                console.print(f"  [cyan]{i}[/cyan]. {m.label}  [dim]{m.description}[/dim]")
            console.print()

            model_idx = typer.prompt("Select model", type=int, default=1) - 1
            if 0 <= model_idx < len(anthropic_provider.models):
                config.agent.model = anthropic_provider.models[model_idx].id
            else:
                config.agent.model = anthropic_provider.models[0].id

    # Save
    save_config(config)
    console.print(f"[green]>[/green] Config saved to {config_path}")

    # Create workspace if needed
    workspace = config.workspace_path
    workspace.mkdir(parents=True, exist_ok=True)
    _create_templates(workspace)

    console.print("\n[bold green]Login complete![/bold green]")
    console.print("\nProvider: [cyan]Anthropic[/cyan]")
    console.print(f"Model:    [cyan]{config.agent.model}[/cyan]")
    console.print("Auth:     [cyan]OAuth (Claude Max/Pro)[/cyan]")
    console.print("\nTry it out: [cyan]sparkagent chat -m \"Hello!\"[/cyan]")


# ============================================================================
# Chat Command
# ============================================================================


@app.command()
def chat(
    message: str = typer.Option(None, "--message", "-m", help="Message to send"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
):
    """Chat with the agent."""
    from sparkagent.agent import AgentLoop
    from sparkagent.bus import MessageBus
    from sparkagent.config import load_config

    config = load_config()

    api_key = config.get_api_key()
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Run [cyan]sparkagent onboard[/cyan] to set up a provider.")
        raise typer.Exit(1)

    bus = MessageBus()
    provider = create_provider(config)

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agent.model,
        max_iterations=config.agent.max_iterations,
        brave_api_key=config.tools.web_search.api_key or None,
        execution_mode=config.agent.execution_mode,
        memory_config=config.memory,
    )

    if message:
        # Single message mode
        async def run_once():
            response = await agent.process_direct(message, session_id)
            console.print(f"\n{response}")

        asyncio.run(run_once())
    else:
        # Interactive mode
        console.print("Interactive mode (Ctrl+C to exit)\n")

        async def run_interactive():
            while True:
                try:
                    user_input = console.input("[bold blue]You:[/bold blue] ")
                    if not user_input.strip():
                        continue

                    response = await agent.process_direct(user_input, session_id)
                    console.print(f"\n{response}\n")
                except KeyboardInterrupt:
                    console.print("\nGoodbye!")
                    break

        asyncio.run(run_interactive())


# ============================================================================
# Gateway Command
# ============================================================================


@app.command()
def gateway():
    """Start the gateway (for Telegram/WhatsApp)."""
    from sparkagent.agent import AgentLoop
    from sparkagent.bus import MessageBus
    from sparkagent.channels import TelegramChannel
    from sparkagent.config import load_config

    config = load_config()

    api_key = config.get_api_key()
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Run [cyan]sparkagent onboard[/cyan] to set up a provider.")
        raise typer.Exit(1)

    console.print("Starting SparkAgent gateway...")

    bus = MessageBus()
    provider = create_provider(config)

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agent.model,
        brave_api_key=config.tools.web_search.api_key or None,
        execution_mode=config.agent.execution_mode,
        memory_config=config.memory,
    )

    # Setup Telegram if enabled
    telegram = None
    if config.channels.telegram.enabled:
        telegram = TelegramChannel(config, bus)
        bus.on_outbound(telegram.send)
        console.print("[green]>[/green] Telegram enabled")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")

    async def run():
        tasks = [agent.run()]
        if telegram:
            tasks.append(telegram.start())

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            agent.stop()
            if telegram:
                await telegram.stop()

    asyncio.run(run())


# ============================================================================
# Status Command
# ============================================================================


@app.command()
def status():
    """Show status and configuration."""
    from sparkagent.cli.providers import get_provider
    from sparkagent.config import get_config_path, load_config

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print("SparkAgent Status\n")

    console.print(
        f"Config:    {config_path} "
        f"{'[green]>[/green]' if config_path.exists() else '[red]x[/red]'}"
    )
    console.print(
        f"Workspace: {workspace} "
        f"{'[green]>[/green]' if workspace.exists() else '[red]x[/red]'}"
    )

    # Provider info
    provider_key = config.agent.provider
    if provider_key:
        provider_info = get_provider(provider_key)
        provider_label = provider_info.label if provider_info else provider_key
        console.print(f"Provider:  [cyan]{provider_label}[/cyan]")
    else:
        console.print("Provider:  [dim]not set[/dim]")

    console.print(f"Model:     {config.agent.model or '[dim]not set[/dim]'}")

    # API key / OAuth status
    has_key = bool(config.get_api_key())
    provider_config = config.get_provider_config()

    if provider_config and provider_config.token_type == "oauth":
        from sparkagent.auth.oauth import is_token_expired

        expired = is_token_expired(provider_config.expires_at)
        token_status = "[red]expired[/red]" if expired else "[green]valid[/green]"
        console.print(f"Auth:      OAuth ({token_status})")
        if provider_config.expires_at:
            console.print(f"Expires:   {provider_config.expires_at}")
    else:
        console.print(
            f"API Key:   {'[green]configured[/green]' if has_key else '[dim]not set[/dim]'}"
        )

    # Telegram
    console.print(
        f"Telegram:  "
        f"{'[green]enabled[/green]' if config.channels.telegram.enabled else '[dim]disabled[/dim]'}"
    )

    if not provider_key:
        console.print(
            "\n[yellow]Run [cyan]sparkagent onboard[/cyan] to set up a provider.[/yellow]"
        )


if __name__ == "__main__":
    app()
