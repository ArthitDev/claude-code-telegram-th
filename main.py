#!/usr/bin/env python3
"""
Claude Code Telegram Proxy - Control Claude Code via Telegram

This bot acts as a proxy to Claude Code CLI, forwarding:
- User prompts to Claude Code
- Claude Code output back to Telegram
- HITL (Human-in-the-Loop) requests for approval/questions

Architecture:
- Domain: Business entities and logic
- Application: Use cases and orchestration
- Infrastructure: External dependencies (Claude Code CLI, DB)
- Presentation: Telegram bot interface

Refactored to use Dependency Injection Container for better testability
and maintainability (fixes DI violations from code review).
"""

# Disable Python bytecode caching to prevent stale .pyc issues
import sys
sys.dont_write_bytecode = True

import asyncio
import logging
import os
import signal
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand

from shared.config.settings import settings
from shared.container import Container, Config
from infrastructure.claude_code.diagnostics import run_and_log_diagnostics
from presentation.middleware.auth import AuthMiddleware, CallbackAuthMiddleware
from presentation.handlers.state.update_coordinator import init_coordinator

# Configure logging with rotation for production
Path("logs").mkdir(exist_ok=True)

# Use RotatingFileHandler for production (prevents huge log files)
from logging.handlers import RotatingFileHandler

log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO"))

# Console handler (UTF-8 for Windows compatibility)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(log_level)
console_handler.setFormatter(logging.Formatter(log_format))

# File handler with rotation (10MB per file, keep 5 backups)
file_handler = RotatingFileHandler(
    "logs/bot.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(log_level)
file_handler.setFormatter(logging.Formatter(log_format))

logging.basicConfig(
    level=log_level,
    format=log_format,
    handlers=[console_handler, file_handler]
)

logger = logging.getLogger(__name__)


class Application:
    """
    Main application class.

    Uses Dependency Injection Container for all service creation,
    following Dependency Inversion Principle.
    """

    def __init__(self, container: Container = None):
        self.container = container or Container()
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self._shutdown_event = asyncio.Event()

    async def setup(self):
        """Initialize application components"""
        logger.info("Initializing Claude Code Telegram Proxy...")

        # Ensure directories exist
        Path("logs").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)

        # Initialize container (database, repositories)
        logger.info("Initializing container...")
        await self.container.init()

        # Check Claude Code backends
        claude_proxy = self.container.claude_proxy()
        claude_sdk = self.container.claude_sdk()

        # Check CLI backend
        installed, message = await claude_proxy.check_claude_installed()
        if installed:
            logger.info(f"[OK] CLI: {message}")
            await run_and_log_diagnostics(claude_proxy.claude_path)
        else:
            logger.warning(f"[WARN] CLI: {message}")

        # Check SDK backend
        if claude_sdk:
            sdk_ok, sdk_msg = await claude_sdk.check_sdk_available()
            if sdk_ok:
                logger.info(f"[OK] SDK: {sdk_msg}")
                plugins_info = claude_sdk.get_enabled_plugins_info()
                available_plugins = [p["name"] for p in plugins_info if p.get("available")]
                if available_plugins:
                    logger.info(f"[OK] Plugins: {', '.join(available_plugins)}")
            else:
                logger.warning(f"[WARN] SDK: {sdk_msg}")

        # Initialize bot
        self.bot = Bot(
            token=settings.telegram.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()

        # ВАЖНО: Инициализировать координатор обновлений ПЕРЕД хэндлерами!
        # Координатор гарантирует минимум 2 секунды между обновлениями сообщений
        coordinator = init_coordinator(self.bot)
        logger.info(f"[OK] MessageUpdateCoordinator initialized (min interval: {coordinator.MIN_UPDATE_INTERVAL}s)")

        # Register handlers (using container)
        self._register_handlers()

        # Register middleware
        # Rate limiting FIRST (before auth to prevent DoS)
        from presentation.middleware.rate_limit import RateLimitMiddleware
        admin_ids = self.container.config.admin_ids or []
        self.dp.message.middleware(RateLimitMiddleware(
            rate_limit=0.5,  # 2 сообщения в секунду
            burst=5,  # Максимум 5 сообщений мгновенно
            admin_ids=admin_ids,  # Admins без ограничений
        ))
        logger.info("[OK] RateLimitMiddleware registered (0.5s per message, burst=5)")

        self.dp.message.middleware(AuthMiddleware(self.container.bot_service()))
        self.dp.callback_query.middleware(CallbackAuthMiddleware(self.container.bot_service()))

        # Register bot commands
        await self._register_bot_commands()

        logger.info("Bot initialized successfully")
        logger.info(f"Default working directory: {self.container.config.claude_working_dir}")

    def _register_handlers(self):
        """Register all handlers using container"""
        # CRITICAL: Verify Keyboards class has all required methods before proceeding
        from presentation.keyboards.keyboards import Keyboards
        required_methods = ['proxy_settings_menu', 'proxy_type_selection', 'proxy_auth_options']
        missing = [m for m in required_methods if not hasattr(Keyboards, m)]
        if missing:
            logger.error(f"FATAL: Keyboards class missing methods: {missing}")
            logger.error(f"Available methods: {[m for m in dir(Keyboards) if not m.startswith('_')]}")
            raise RuntimeError(f"Keyboards class missing required methods: {missing}")
        logger.info(f"[OK] Keyboards class verified (has {len([m for m in dir(Keyboards) if not m.startswith('_')])} methods)")

        from presentation.handlers.commands import register_handlers as register_cmd_handlers
        # REFACTORED VERSION - modular architecture
        from presentation.handlers.message import register_handlers as register_msg_handlers
        from presentation.handlers.callbacks import register_handlers as register_callback_handlers
        from presentation.handlers.account_handlers import register_account_handlers
        from presentation.handlers.menu_handlers import register_menu_handlers
        from presentation.handlers.proxy_handlers import register_proxy_handlers

        # Account handlers (for /account command and mode switching)
        register_account_handlers(self.dp, self.container.account_handlers())

        # Command handlers
        register_cmd_handlers(self.dp, self.container.command_handlers())

        # Menu handlers - main inline menu system
        register_menu_handlers(self.dp, self.container.menu_handlers())

        # Proxy handlers - proxy settings management
        register_proxy_handlers(self.dp, self.container.proxy_handlers())

        # Message handlers (after commands - commands take priority)
        register_msg_handlers(self.dp, self.container.message_handlers())

        # Callback handlers
        register_callback_handlers(self.dp, self.container.callback_handlers())

    async def _register_bot_commands(self):
        """Register bot commands in Telegram menu for all supported languages"""
        from aiogram.types import BotCommandScopeAllPrivateChats
        
        # Define commands for each language
        commands_by_lang = {
            "th": [
                BotCommand(command="start", description="📱 เปิดเมนูหลัก"),
                BotCommand(command="yolo", description="⚡ โหมด YOLO (ไม่อนุมัติ)"),
                BotCommand(command="cancel", description="🛑 ยกเลิกงาน"),
            ],
            "en": [
                BotCommand(command="start", description="📱 เปิดเมนูหลัก"),
                BotCommand(command="yolo", description="⚡ โหมด YOLO (ไม่อนุมัติ)"),
                BotCommand(command="cancel", description="🛑 ยกเลิกงาน"),
            ],
            "ru": [
                BotCommand(command="start", description="📱 Главное меню"),
                BotCommand(command="yolo", description="⚡ Режим YOLO"),
                BotCommand(command="cancel", description="🛑 Отмена"),
            ],
            "zh": [
                BotCommand(command="start", description="📱 主菜单"),
                BotCommand(command="yolo", description="⚡ YOLO模式"),
                BotCommand(command="cancel", description="🛑 取消"),
            ],
        }

        try:
            # First, delete all existing commands to clear cache
            await self.bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())

            # Set default commands (Thai) - for users with no language set or unsupported language
            await self.bot.set_my_commands(
                commands_by_lang["th"],
                scope=BotCommandScopeAllPrivateChats(),
                language_code=""  # Empty string = default
            )

            # Set commands for each specific language
            for lang_code, commands in commands_by_lang.items():
                await self.bot.set_my_commands(
                    commands,
                    scope=BotCommandScopeAllPrivateChats(),
                    language_code=lang_code
                )

            logger.info(f"[OK] Registered bot commands for {len(commands_by_lang)} languages (th, en, ru, zh) + default (th)")
        except Exception as e:
            logger.warning(f"[WARN] Failed to register bot commands: {e}")

    async def _notify_admins_startup(self, bot_info):
        """
        Notify admins that bot has started successfully.

        Uses admin_ids from configuration instead of hardcoded value.
        """
        admin_ids = self.container.config.admin_ids
        if not admin_ids:
            logger.warning("No admin IDs configured, skipping startup notification")
            return

        # Build status message
        claude_sdk = self.container.claude_sdk()
        claude_proxy = self.container.claude_proxy()
        account_service = self.container.account_service()

        sdk_status = "[ON] SDK" if claude_sdk else "[OFF] SDK"
        cli_ok, _ = await claude_proxy.check_claude_installed()
        cli_status = "[ON] CLI" if cli_ok else "[OFF] CLI"

        creds_info = account_service.get_credentials_info()
        creds_status = (
            f"[OK] {creds_info.subscription_type}" if creds_info.exists
            else "[MISSING] not found"
        )

        message = (
            f"<b>Bot Started!</b>\n\n"
            f"@{bot_info.username}\n"
            f"{sdk_status} | {cli_status}\n"
            f"Claude creds: {creds_status}\n"
            f"Work dir: {self.container.config.claude_working_dir}\n\n"
            f"<i>Ready for work</i>"
        )

        # Notify all admins
        for admin_id in admin_ids:
            try:
                await self.bot.send_message(admin_id, message)
                logger.info(f"[OK] Admin {admin_id} notified about startup")
            except Exception as e:
                error_msg = str(e)
                if "chat not found" in error_msg.lower():
                    logger.warning(f"[WARN] Cannot notify admin {admin_id}: User has not started conversation with bot yet. Ask them to send /start to the bot first.")
                else:
                    logger.warning(f"[WARN] Failed to notify admin {admin_id}: {e}")

    async def start(self):
        """Start the bot"""
        await self.setup()

        logger.info("Starting bot polling...")
        info = await self.bot.get_me()
        logger.info(f"Bot: @{info.username} (ID: {info.id})")

        # Notify admins that bot started
        await self._notify_admins_startup(info)

        # Set up signal handlers (Unix only)
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        # Start polling
        await self.dp.start_polling(
            self.bot,
            handle_signals=sys.platform == "win32"
        )

    async def shutdown(self):
        """Graceful shutdown"""
        if self._shutdown_event.is_set():
            return

        logger.info("Shutting down...")
        self._shutdown_event.set()

        # Stop polling
        if self.dp:
            await self.dp.stop_polling()

        # Close container resources
        await self.container.close()

        # Close bot session
        if self.bot:
            await self.bot.session.close()

        logger.info("Shutdown complete")


async def main():
    """Main entry point"""
    # Create container with configuration
    config = Config.from_env()
    container = Container(config)

    app = Application(container)

    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
