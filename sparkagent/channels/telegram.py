"""Telegram channel implementation."""

import asyncio
import re
from pathlib import Path

from sparkagent.bus import MessageBus, OutboundMessage
from sparkagent.channels.base import BaseChannel
from sparkagent.config import Config

# Import telegram library (optional dependency)
try:
    from telegram import Update
    from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


def markdown_to_telegram_html(text: str) -> str:
    """Convert markdown to Telegram-safe HTML."""
    if not text:
        return ""
    
    # Protect code blocks
    code_blocks: list[str] = []
    def save_code(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"
    
    text = re.sub(r'```[\w]*\n?([\s\S]*?)```', save_code, text)
    
    # Protect inline code
    inline_codes: list[str] = []
    def save_inline(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"
    
    text = re.sub(r'`([^`]+)`', save_inline, text)
    
    # Remove headers
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)
    
    # Escape HTML
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    
    # Italic
    text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])', r'<i>\1</i>', text)
    
    # Bullet lists
    text = re.sub(r'^[-*]\s+', '• ', text, flags=re.MULTILINE)
    
    # Restore inline code
    for i, code in enumerate(inline_codes):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")
    
    # Restore code blocks
    for i, code in enumerate(code_blocks):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")
    
    return text


class TelegramChannel(BaseChannel):
    """Telegram channel using long polling."""
    
    name = "telegram"
    
    def __init__(self, config: Config, bus: MessageBus):
        super().__init__(bus)
        self.config = config
        self.telegram_config = config.channels.telegram
        self._app: "Application | None" = None
        self._media_dir = Path.home() / ".sparkagent" / "media"
        self._media_dir.mkdir(parents=True, exist_ok=True)
    
    async def start(self) -> None:
        """Start the Telegram bot."""
        if not TELEGRAM_AVAILABLE:
            print("Error: python-telegram-bot not installed")
            return
        
        if not self.telegram_config.token:
            print("Error: Telegram token not configured")
            return
        
        self._running = True
        
        # Build application
        self._app = (
            Application.builder()
            .token(self.telegram_config.token)
            .build()
        )
        
        # Add handlers
        self._app.add_handler(MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            self._on_message
        ))
        self._app.add_handler(CommandHandler("start", self._on_start))
        
        # Start
        await self._app.initialize()
        await self._app.start()
        
        bot_info = await self._app.bot.get_me()
        print(f"Telegram bot @{bot_info.username} connected")
        
        await self._app.updater.start_polling(
            allowed_updates=["message"],
            drop_pending_updates=True,
        )
        
        # Keep running
        while self._running:
            await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Stop the Telegram bot."""
        self._running = False
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message."""
        if not self._app:
            return
        
        try:
            chat_id = int(msg.chat_id)
            html = markdown_to_telegram_html(msg.content)
            await self._app.bot.send_message(chat_id=chat_id, text=html, parse_mode="HTML")
        except Exception as e:
            # Fallback to plain text
            try:
                await self._app.bot.send_message(chat_id=int(msg.chat_id), text=msg.content)
            except Exception:
                print(f"Failed to send message: {e}")
    
    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.message or not update.effective_user:
            return
        
        user = update.effective_user
        await update.message.reply_text(
            f"👋 Hi {user.first_name}! I'm SparkAgent.\nSend me a message!"
        )
    
    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages."""
        if not update.message or not update.effective_user:
            return
        
        message = update.message
        user = update.effective_user
        chat_id = str(message.chat_id)
        sender_id = str(user.id)
        
        # Check allowlist
        if self.telegram_config.allow_from:
            allowed = any(
                sender_id == a or (user.username and user.username == a)
                for a in self.telegram_config.allow_from
            )
            if not allowed:
                return
        
        # Build content
        content_parts = []
        media_paths = []
        
        if message.text:
            content_parts.append(message.text)
        if message.caption:
            content_parts.append(message.caption)
        
        # Handle photos
        if message.photo and self._app:
            try:
                photo = message.photo[-1]  # Largest
                file = await self._app.bot.get_file(photo.file_id)
                path = self._media_dir / f"{photo.file_id[:16]}.jpg"
                await file.download_to_drive(str(path))
                media_paths.append(str(path))
                content_parts.append(f"[image: {path}]")
            except Exception as e:
                content_parts.append("[image: download failed]")
        
        content = "\n".join(content_parts) if content_parts else "[empty]"
        
        # Publish to bus
        await self._publish_inbound(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media_paths,
            metadata={
                "message_id": message.message_id,
                "username": user.username,
                "first_name": user.first_name,
            }
        )
