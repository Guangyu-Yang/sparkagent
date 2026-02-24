"""Telegram plugin CLI commands."""

import typer
from rich.console import Console

from sparkagent.config import Config, get_config_path, load_config, save_config

telegram_app = typer.Typer(
    name="telegram",
    help="Telegram bot plugin.",
    no_args_is_help=True,
)

console = Console()


@telegram_app.command()
def onboard():
    """Interactive setup for the Telegram bot."""
    config_path = get_config_path()
    config = load_config() if config_path.exists() else Config()

    console.print("\n[bold]Telegram Bot Setup[/bold]\n")
    console.print("  1. Open Telegram and search for [cyan]@BotFather[/cyan]")
    console.print("  2. Send [cyan]/newbot[/cyan] and follow the prompts to create a bot")
    console.print("  3. Copy the bot token (looks like [dim]123456:ABC-xyz...[/dim])")
    console.print()

    # --- Bot token ---
    token = typer.prompt("Bot token", hide_input=True)
    if not token.strip():
        console.print("[red]Bot token cannot be empty.[/red]")
        raise typer.Exit(1)

    config.channels.telegram.token = token.strip()
    console.print("  [green]>[/green] Token saved\n")

    # --- User ID allow-list ---
    console.print("[bold]Restrict access[/bold] (recommended)\n")
    console.print(
        "  To find your user ID, send [cyan]/start[/cyan] "
        "to [cyan]@userinfobot[/cyan] on Telegram.\n"
    )

    user_id = typer.prompt("Your user ID (leave blank to allow everyone)", default="")
    if user_id.strip():
        config.channels.telegram.allow_from = [user_id.strip()]
        console.print(f"  [green]>[/green] Access restricted to: {user_id.strip()}\n")
    else:
        config.channels.telegram.allow_from = []
        console.print(
            "  [yellow]>[/yellow] No restriction — any user can interact with the bot\n"
        )

    # --- Enable and save ---
    config.channels.telegram.enabled = True
    save_config(config)

    console.print(f"[green]>[/green] Config saved to {config_path}")
    console.print("\n[bold green]Telegram bot configured![/bold green]")
    console.print("Run [cyan]sparkagent gateway[/cyan] to start.\n")
