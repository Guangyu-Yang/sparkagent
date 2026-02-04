"""CLI commands for MyAutoAgent."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from myautoagent import __version__

app = typer.Typer(
    name="myautoagent",
    help="🤖 MyAutoAgent - A lightweight LLM-powered assistant",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"🤖 MyAutoAgent v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """MyAutoAgent - Personal AI Assistant."""
    pass


# ============================================================================
# Setup / Onboard
# ============================================================================


@app.command()
def onboard():
    """Initialize configuration and workspace."""
    from myautoagent.config import Config, save_config, get_config_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()
    
    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")
    
    # Create workspace
    workspace = config.workspace_path
    workspace.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]✓[/green] Created workspace at {workspace}")
    
    # Create template files
    _create_templates(workspace)
    
    console.print(f"\n🤖 MyAutoAgent is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.myautoagent/config.json[/cyan]")
    console.print("  2. Chat: [cyan]myautoagent chat -m \"Hello!\"[/cyan]")


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

I am MyAutoAgent, a lightweight AI assistant.

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
            console.print(f"  [dim]Created {filename}[/dim]")
    
    # Create memory directory
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("# Long-term Memory\n\nImportant information to remember.\n")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")


# ============================================================================
# Chat Command
# ============================================================================


@app.command()
def chat(
    message: str = typer.Option(None, "--message", "-m", help="Message to send"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
):
    """Chat with the agent."""
    from myautoagent.config import load_config
    from myautoagent.bus import MessageBus
    from myautoagent.providers import OpenAICompatibleProvider
    from myautoagent.agent import AgentLoop
    
    config = load_config()
    
    api_key = config.get_api_key()
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Add one to ~/.myautoagent/config.json under providers.openrouter.api_key")
        raise typer.Exit(1)
    
    bus = MessageBus()
    provider = OpenAICompatibleProvider(
        api_key=api_key,
        api_base=config.get_api_base(),
        default_model=config.agent.model,
    )
    
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agent.model,
        max_iterations=config.agent.max_iterations,
        brave_api_key=config.tools.web_search.api_key or None,
    )
    
    if message:
        # Single message mode
        async def run_once():
            response = await agent.process_direct(message, session_id)
            console.print(f"\n🤖 {response}")
        
        asyncio.run(run_once())
    else:
        # Interactive mode
        console.print("🤖 Interactive mode (Ctrl+C to exit)\n")
        
        async def run_interactive():
            while True:
                try:
                    user_input = console.input("[bold blue]You:[/bold blue] ")
                    if not user_input.strip():
                        continue
                    
                    response = await agent.process_direct(user_input, session_id)
                    console.print(f"\n🤖 {response}\n")
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
    from myautoagent.config import load_config
    from myautoagent.bus import MessageBus
    from myautoagent.providers import OpenAICompatibleProvider
    from myautoagent.agent import AgentLoop
    from myautoagent.channels import TelegramChannel
    
    config = load_config()
    
    api_key = config.get_api_key()
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    console.print("🤖 Starting MyAutoAgent gateway...")
    
    bus = MessageBus()
    provider = OpenAICompatibleProvider(
        api_key=api_key,
        api_base=config.get_api_base(),
        default_model=config.agent.model,
    )
    
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agent.model,
        brave_api_key=config.tools.web_search.api_key or None,
    )
    
    # Setup Telegram if enabled
    telegram = None
    if config.channels.telegram.enabled:
        telegram = TelegramChannel(config, bus)
        bus.on_outbound(telegram.send)
        console.print("[green]✓[/green] Telegram enabled")
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
    from myautoagent.config import load_config, get_config_path
    
    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path
    
    console.print("🤖 MyAutoAgent Status\n")
    
    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")
    console.print(f"Model: {config.agent.model}")
    
    has_openrouter = bool(config.providers.openrouter.api_key)
    has_openai = bool(config.providers.openai.api_key)
    
    console.print(f"OpenRouter API: {'[green]✓[/green]' if has_openrouter else '[dim]not set[/dim]'}")
    console.print(f"OpenAI API: {'[green]✓[/green]' if has_openai else '[dim]not set[/dim]'}")
    console.print(f"Telegram: {'[green]enabled[/green]' if config.channels.telegram.enabled else '[dim]disabled[/dim]'}")


if __name__ == "__main__":
    app()
