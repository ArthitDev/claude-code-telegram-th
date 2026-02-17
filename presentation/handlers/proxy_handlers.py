"""Proxy settings handlers for Telegram bot"""

import logging
from typing import Dict, Optional
from aiogram.types import CallbackQuery, Message
from aiogram import Bot
from aiogram.filters import BaseFilter

from application.services.proxy_service import ProxyService
from domain.value_objects.proxy_config import ProxyType
from domain.value_objects.user_id import UserId
from presentation.keyboards.keyboards import Keyboards
from shared.utils.telegram_utils import safe_callback_answer

logger = logging.getLogger(__name__)


# State for storing intermediate proxy setup data
# Structure: {user_id: {"type": "http", "host": "...", "port": 123, "step": "host|credentials"}}
proxy_setup_state: Dict[int, Dict] = {}


def is_proxy_input_active(user_id: int) -> bool:
    """Check if user is in proxy setup input mode"""
    return user_id in proxy_setup_state and "step" in proxy_setup_state[user_id]


def get_proxy_input_step(user_id: int) -> Optional[str]:
    """Get current proxy input step: 'host' or 'credentials'"""
    if user_id in proxy_setup_state:
        return proxy_setup_state[user_id].get("step")
    return None


class ProxyHandlers:
    """Handlers for proxy settings management via Telegram"""

    def __init__(self, proxy_service: ProxyService, account_service=None):
        self.proxy_service = proxy_service
        self.account_service = account_service

    async def _get_user_lang(self, user_id: int) -> str:
        """Get user's language preference"""
        if self.account_service:
            lang = await self.account_service.get_user_language(user_id)
            if lang:
                return lang
        return "en"

    async def handle_proxy_menu(self, callback: CallbackQuery, **kwargs) -> None:
        """Show proxy settings menu"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Get current proxy
        proxy_config = await self.proxy_service.get_effective_proxy(UserId(user_id))

        has_proxy = proxy_config is not None and proxy_config.enabled
        proxy_status = proxy_config.mask_credentials() if has_proxy else t("proxy.no_proxy").replace("📡 ", "")

        keyboard = Keyboards.proxy_settings_menu(has_proxy, proxy_status, lang=lang)

        await callback.message.edit_text(
            f"{t('proxy.title')}\n\n"
            f"{t('proxy.current', proxy=proxy_status)}\n\n"
            f"{t('proxy.description_text')}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await safe_callback_answer(callback)

    async def handle_proxy_setup(self, callback: CallbackQuery, **kwargs) -> None:
        """Start proxy setup wizard"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        keyboard = Keyboards.proxy_type_selection(lang=lang)

        await callback.message.edit_text(
            f"{t('proxy.setup')}\n\n"
            f"{t('proxy.type_select')}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await safe_callback_answer(callback)

    async def handle_proxy_type_selection(
        self,
        callback: CallbackQuery,
        proxy_type: str,
        **kwargs
    ) -> None:
        """Handle proxy type selection"""
        user_id = callback.from_user.id

        # Initialize state
        if user_id not in proxy_setup_state:
            proxy_setup_state[user_id] = {}

        proxy_setup_state[user_id]["type"] = proxy_type
        proxy_setup_state[user_id]["step"] = "host"  # Expecting host:port input

        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        await callback.message.edit_text(
            t("proxy.type_selected", type=proxy_type.upper()),
            parse_mode="HTML"
        )
        await safe_callback_answer(callback)

    async def handle_proxy_host_input(self, message: Message, **kwargs) -> None:
        """Handle proxy host:port input (also accepts full URL format)"""
        user_id = message.from_user.id

        if user_id not in proxy_setup_state:
            lang = await self._get_user_lang(user_id)
            from shared.i18n import get_translator
            t = get_translator(lang)
            await message.answer(t("proxy.session_expired"))
            return

        text = message.text.strip()
        host = None
        port = None
        username = None
        password = None

        try:
            # Try to parse as full URL (http://user:pass@host:port)
            if "://" in text:
                from urllib.parse import urlparse
                parsed = urlparse(text)

                if parsed.hostname:
                    host = parsed.hostname
                if parsed.port:
                    port = parsed.port
                if parsed.username:
                    username = parsed.username
                if parsed.password:
                    password = parsed.password

                # Update proxy type from URL scheme if provided
                scheme = parsed.scheme.lower()
                if scheme in ("http", "https", "socks4", "socks5"):
                    proxy_setup_state[user_id]["type"] = scheme

            # Try to parse as simple host:port format
            else:
                parts = text.split(":")
                if len(parts) == 2:
                    host = parts[0].strip()
                    port = int(parts[1].strip())

            # Validate parsed values
            if not host or not port:
                raise ValueError("Could not parse host or port")

            if not (1 <= port <= 65535):
                raise ValueError("Invalid port number")

            # Save to state
            proxy_setup_state[user_id]["host"] = host
            proxy_setup_state[user_id]["port"] = port
            proxy_setup_state[user_id].pop("step", None)  # Clear input step

            # If credentials were parsed from URL, save and go directly to scope selection
            lang = await self._get_user_lang(user_id)
            from shared.i18n import get_translator
            t = get_translator(lang)

            if username and password:
                proxy_setup_state[user_id]["username"] = username
                proxy_setup_state[user_id]["password"] = password

                keyboard = Keyboards.proxy_scope_selection(lang=lang)
                await message.answer(
                    t("proxy.configured_from_url",
                      type=proxy_setup_state[user_id]['type'].upper(),
                      host=host,
                      port=port,
                      scope_prompt=t('proxy.scope_prompt')),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # Ask about auth
                keyboard = Keyboards.proxy_auth_options(lang=lang)
                await message.answer(
                    t("proxy.address_set", host=host, port=port, auth_prompt=t('proxy.auth_prompt')),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

        except (ValueError, AttributeError) as e:
            logger.debug(f"Proxy input parse error: {e}")
            await message.answer(
                t("proxy.invalid_format"),
                parse_mode="HTML"
            )

    async def handle_proxy_auth_selection(
        self,
        callback: CallbackQuery,
        needs_auth: bool,
        **kwargs
    ) -> None:
        """Handle authentication option"""
        user_id = callback.from_user.id

        if user_id not in proxy_setup_state:
            await safe_callback_answer(callback, "❌ Session expired", show_alert=True)
            return

        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        if needs_auth:
            proxy_setup_state[user_id]["step"] = "credentials"  # Expecting credentials input
            await callback.message.edit_text(
                t("proxy.credentials_prompt"),
                parse_mode="HTML"
            )
        else:
            # No auth, ask for scope
            proxy_setup_state[user_id]["username"] = None
            proxy_setup_state[user_id]["password"] = None

            keyboard = Keyboards.proxy_scope_selection(lang=lang)
            await callback.message.edit_text(
                t("proxy.scope_prompt"),
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await safe_callback_answer(callback)

    async def handle_proxy_credentials_input(self, message: Message, **kwargs) -> None:
        """Handle username:password input"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        if user_id not in proxy_setup_state:
            await message.answer(t("error.session_expired"))
            return

        try:
            parts = message.text.strip().split(":", 1)
            if len(parts) != 2:
                raise ValueError("Invalid format")

            username = parts[0].strip()
            password = parts[1].strip()

            if not username or not password:
                raise ValueError("Empty credentials")

            proxy_setup_state[user_id]["username"] = username
            proxy_setup_state[user_id]["password"] = password
            proxy_setup_state[user_id].pop("step", None)  # Clear input step

            # Ask for scope
            keyboard = Keyboards.proxy_scope_selection(lang=lang)
            await message.answer(
                t("proxy.credentials_saved", scope_prompt=t('proxy.scope_prompt')),
                reply_markup=keyboard
            )

        except ValueError:
            await message.answer(
                t("proxy.invalid_format"),
                parse_mode="HTML"
            )

    async def handle_proxy_scope_selection(
        self,
        callback: CallbackQuery,
        is_global: bool,
        **kwargs
    ) -> None:
        """Handle scope selection and create proxy"""
        user_id = callback.from_user.id
        telegram_user_id = UserId(user_id)

        if user_id not in proxy_setup_state:
            await safe_callback_answer(callback, "❌ Session expired", show_alert=True)
            return

        state = proxy_setup_state[user_id]

        try:
            # Create proxy
            proxy_type = ProxyType(state["type"])
            host = state["host"]
            port = state["port"]
            username = state.get("username")
            password = state.get("password")

            target_user_id = None if is_global else telegram_user_id

            await self.proxy_service.set_custom_proxy(
                proxy_type=proxy_type,
                host=host,
                port=port,
                username=username,
                password=password,
                user_id=target_user_id
            )

            # Test proxy
            proxy_config = await self.proxy_service.get_effective_proxy(telegram_user_id)
            success, message = await self.proxy_service.test_proxy(proxy_config)

            lang = await self._get_user_lang(user_id)
            from shared.i18n import get_translator
            t = get_translator(lang)

            scope_text = t("proxy.scope_global").replace("🌍 ", "") if is_global else t("proxy.scope_user").replace("👤 ", "")

            if success:
                keyboard = Keyboards.proxy_confirm_test(True, lang=lang)
                await callback.message.edit_text(
                    f"{t('proxy.test_success')}\n\n"
                    f"Type: {proxy_type.value.upper()}\n"
                    f"Address: {host}:{port}\n"
                    f"Scope: {scope_text}\n\n"
                    f"Test result:\n{message}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                keyboard = Keyboards.proxy_confirm_test(False, lang=lang)
                await callback.message.edit_text(
                    f"{t('proxy.test_failed')}\n\n"
                    f"Type: {proxy_type.value.upper()}\n"
                    f"Address: {host}:{port}\n\n"
                    f"Error: {message}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

            # Clear state
            del proxy_setup_state[user_id]

        except Exception as e:
            logger.error(f"Error setting up proxy: {e}")
            await callback.message.edit_text(
                f"❌ Error configuring proxy:\n{str(e)}"
            )

        await safe_callback_answer(callback)

    async def handle_proxy_test(self, callback: CallbackQuery, **kwargs) -> None:
        """Test current proxy"""
        user_id = UserId(callback.from_user.id)

        proxy_config = await self.proxy_service.get_effective_proxy(user_id)

        if not proxy_config:
            await safe_callback_answer(callback, "❌ Proxy not configured", show_alert=True)
            return

        await safe_callback_answer(callback, "🧪 Testing proxy...")

        success, message = await self.proxy_service.test_proxy(proxy_config)

        lang = await self._get_user_lang(callback.from_user.id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        if success:
            await callback.message.answer(
                t("proxy.test_success_detail", message=message),
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                t("proxy.test_failed_detail", message=message),
                parse_mode="HTML"
            )

    async def handle_proxy_disable(self, callback: CallbackQuery, **kwargs) -> None:
        """Disable proxy"""
        user_id = UserId(callback.from_user.id)

        await self.proxy_service.disable_user_proxy(user_id)

        await callback.message.edit_text(
            "✅ Proxy disabled"
        )
        await safe_callback_answer(callback)

    async def handle_proxy_save(self, callback: CallbackQuery, **kwargs) -> None:
        """Confirm and save proxy (proxy is already saved, just acknowledge)"""
        user_id = UserId(callback.from_user.id)

        # Proxy is already saved by handle_proxy_scope_selection
        # Just show confirmation and return to menu
        proxy_config = await self.proxy_service.get_effective_proxy(user_id)

        if proxy_config:
            await callback.message.edit_text(
                f"✅ <b>Proxy saved</b>\n\n"
                f"Type: {proxy_config.proxy_type.value.upper()}\n"
                f"Address: {proxy_config.host}:{proxy_config.port}\n"
                f"Auth: {'✓' if proxy_config.username else '✗'}",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text("✅ Settings saved")

        await safe_callback_answer(callback, "✅ Saved")

    async def handle_proxy_change(self, callback: CallbackQuery, **kwargs) -> None:
        """Go back to proxy setup to change settings"""
        # Start fresh setup
        await self.handle_proxy_setup(callback, **kwargs)

    async def handle_proxy_cancel(self, callback: CallbackQuery, **kwargs) -> None:
        """Cancel proxy setup and remove proxy"""
        user_id = callback.from_user.id
        user_id_vo = UserId(user_id)

        # Clear setup state if exists
        if user_id in proxy_setup_state:
            del proxy_setup_state[user_id]

        # Disable/remove user proxy
        await self.proxy_service.disable_user_proxy(user_id_vo)

        await callback.message.edit_text(
            "❌ Proxy setup cancelled"
        )
        await safe_callback_answer(callback)


class ProxyInputFilter(BaseFilter):
    """Filter for proxy text input messages"""

    def __init__(self, step: str):
        self.step = step

    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        user_id = message.from_user.id
        return get_proxy_input_step(user_id) == self.step


def register_proxy_handlers(dp, handlers: ProxyHandlers):
    """Register proxy handlers with dispatcher"""
    from aiogram import F

    # === MESSAGE HANDLERS (must be registered FIRST to intercept proxy input) ===
    # These handlers catch text input when user is in proxy setup mode

    # Handler for host:port input (step="host")
    dp.message.register(
        handlers.handle_proxy_host_input,
        ProxyInputFilter("host")
    )

    # Handler for username:password input (step="credentials")
    dp.message.register(
        handlers.handle_proxy_credentials_input,
        ProxyInputFilter("credentials")
    )

    # === CALLBACK HANDLERS ===

    # Callback для меню настроек прокси
    dp.callback_query.register(
        handlers.handle_proxy_menu,
        F.data == "menu:proxy"
    )

    # Callback для начала настройки
    dp.callback_query.register(
        handlers.handle_proxy_setup,
        F.data == "proxy:setup"
    )

    # Callback для выбора типа прокси - нужен wrapper для извлечения параметра
    async def handle_type(c):
        proxy_type = c.data.split(":")[2]
        await handlers.handle_proxy_type_selection(c, proxy_type)

    dp.callback_query.register(
        handle_type,
        F.data.startswith("proxy:type:")
    )

    # Callback для выбора авторизации
    async def handle_auth(c):
        with_auth = c.data.split(":")[2] == "yes"
        await handlers.handle_proxy_auth_selection(c, with_auth)

    dp.callback_query.register(
        handle_auth,
        F.data.startswith("proxy:auth:")
    )

    # Callback для выбора области (scope)
    async def handle_scope(c):
        is_global = c.data.split(":")[2] == "global"
        await handlers.handle_proxy_scope_selection(c, is_global)

    dp.callback_query.register(
        handle_scope,
        F.data.startswith("proxy:scope:")
    )

    # Callback для теста прокси
    dp.callback_query.register(
        handlers.handle_proxy_test,
        F.data == "proxy:test"
    )

    # Callback для отключения прокси
    dp.callback_query.register(
        handlers.handle_proxy_disable,
        F.data == "proxy:disable"
    )

    # Callback для сохранения прокси (подтверждение после теста)
    dp.callback_query.register(
        handlers.handle_proxy_save,
        F.data == "proxy:save"
    )

    # Callback для изменения настроек прокси
    dp.callback_query.register(
        handlers.handle_proxy_change,
        F.data == "proxy:change"
    )

    # Callback для отмены настройки прокси
    dp.callback_query.register(
        handlers.handle_proxy_cancel,
        F.data == "proxy:cancel"
    )

    logger.info("[OK] Proxy handlers registered")
