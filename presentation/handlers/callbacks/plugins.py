"""
Plugin management callback handlers.

Handles plugin listing, marketplace, enable/disable operations.
"""

import logging
from typing import Optional

from aiogram.types import CallbackQuery

from presentation.handlers.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)


class PluginCallbackHandler(BaseCallbackHandler):
    """Handler for plugin management callbacks."""

    async def handle_plugin_list(self, callback: CallbackQuery) -> None:
        """Show list of enabled plugins"""
        from presentation.keyboards.keyboards import Keyboards
        from shared.i18n import get_translator
        
        # Get user language
        user_id = callback.from_user.id
        user_lang = "th"  # default
        if hasattr(self, 'account_service') and self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "th"
        
        t = get_translator(user_lang)

        if not self.sdk_service:
            await safe_callback_answer(callback, t("plugins.sdk_not_available"))
            return

        plugins = self.sdk_service.get_enabled_plugins_info()

        if not plugins:
            text = (
                f"{t('plugins.claude_code_title')}\n\n"
                f"{t('plugins.no_active')}\n\n"
                f"{t('plugins.click_marketplace')}"
            )
        else:
            text = f"{t('plugins.claude_code_title')}\n\n"
            for p in plugins:
                name = p.get("name", "unknown")
                desc = p.get("description", "")
                source = p.get("source", "official")
                available = p.get("available", True)

                status = "✅" if available else "⚠️"
                source_icon = "🌐" if source == "official" else "📁"
                
                # Try translation first
                trans_key = f"plugins.desc.{name}"
                translated = t(trans_key)
                # If translation exists (doesn't return key itself), use it
                if translated != trans_key:
                    desc_text = translated
                else:
                    desc_text = desc

                text += f"{status} {source_icon} <b>{name}</b>\n"
                if desc_text:
                    text += f"   <i>{desc_text}</i>\n"
                text += "\n"  # Empty line

            text += f"<i>{t('plugins.total', count=len(plugins))}</i>"

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.plugins_menu(plugins, lang=user_lang)
        )
        await safe_callback_answer(callback)

    async def handle_plugin_refresh(self, callback: CallbackQuery) -> None:
        """Refresh plugins list"""
        from shared.i18n import get_translator

        # Get user language
        user_id = callback.from_user.id
        user_lang = "th"  # default
        if hasattr(self, 'account_service') and self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "th"

        t = get_translator(user_lang)
        await safe_callback_answer(callback, t("plugins.refreshed"))
        await self.handle_plugin_list(callback)

    async def handle_plugin_marketplace(self, callback: CallbackQuery) -> None:
        """Show marketplace with available plugins"""
        from presentation.keyboards.keyboards import Keyboards
        from shared.i18n import get_translator
        
        # Get user language
        user_id = callback.from_user.id
        user_lang = "th"  # default
        if hasattr(self, 'account_service') and self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "th"
        
        t = get_translator(user_lang)

        if not self.sdk_service:
            await callback.answer(t("plugins.sdk_not_available"))
            return

        # All available plugins from official marketplace
        # Get descriptions from translator
        plugin_names = [
            "commit-commands",
            "code-review",
            "feature-dev",
            "frontend-design",
            "ralph-loop",
            "security-guidance",
            "pr-review-toolkit",
            "claude-code-setup",
            "hookify",
            "explanatory-output-style",
            "learning-output-style",
        ]
        
        marketplace_plugins = [
            {
                "name": name,
                "desc": t(f"plugins.desc.{name}")
            }
            for name in plugin_names
        ]

        # Get currently enabled plugins
        enabled = self.sdk_service.get_enabled_plugins_info()
        enabled_names = [p.get("name") for p in enabled]

        text = (
            f"{t('plugins.marketplace_title')}\n\n"
            f"{t('plugins.select_to_enable')}\n"
            f"{t('plugins.already_enabled')}\n"
            f"{t('plugins.click_to_enable')}\n\n"
            f"<i>{t('plugins.changes_after_restart')}</i>"
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.plugins_marketplace(marketplace_plugins, enabled_names, lang=user_lang)
        )
        await safe_callback_answer(callback)

    async def handle_plugin_info(self, callback: CallbackQuery) -> None:
        """Show plugin info"""
        from shared.i18n import get_translator
        
        parts = callback.data.split(":")
        plugin_name = parts[2] if len(parts) > 2 else "unknown"

        # Get user language to show info in correct language
        user_id = callback.from_user.id
        user_lang = "th"  # default
        if hasattr(self, 'account_service') and self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "th"
            
        t = get_translator(user_lang)
        
        # Try translation first
        trans_key = f"plugins.desc.{plugin_name}"
        translated = t(trans_key)
        
        # If translation exists, use it
        if translated != trans_key:
            desc = translated
        else:
            # Fallback to English/Default or Generic message
            desc = f"Plugin: {plugin_name}"

        await callback.answer(f"ℹ️ {plugin_name}: {desc[:150]}", show_alert=True)

    async def handle_plugin_enable(self, callback: CallbackQuery) -> None:
        """Enable a plugin"""
        from shared.i18n import get_translator
        
        parts = callback.data.split(":")
        plugin_name = parts[2] if len(parts) > 2 else "unknown"
        
        # Get user language
        user_id = callback.from_user.id
        user_lang = "th"  # default
        if hasattr(self, 'account_service') and self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "th"
        
        t = get_translator(user_lang)

        if not self.sdk_service:
            await safe_callback_answer(callback, t("plugins.sdk_not_available"))
            return

        # Add plugin to enabled list
        if hasattr(self.sdk_service, 'add_plugin'):
            self.sdk_service.add_plugin(plugin_name)
            await safe_callback_answer(callback, t("plugins.enabled_success", name=plugin_name))
            await self.handle_plugin_marketplace(callback)
        else:
            await safe_callback_answer(
                callback,
                t("plugins.add_to_env", name=plugin_name),
                show_alert=True
            )

    async def handle_plugin_disable(self, callback: CallbackQuery) -> None:
        """Disable a plugin"""
        from shared.i18n import get_translator
        
        parts = callback.data.split(":")
        plugin_name = parts[2] if len(parts) > 2 else "unknown"
        
        # Get user language
        user_id = callback.from_user.id
        user_lang = "th"  # default
        if hasattr(self, 'account_service') and self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "th"
        
        t = get_translator(user_lang)

        if not self.sdk_service:
            await safe_callback_answer(callback, t("plugins.sdk_not_available"))
            return

        # Remove plugin from enabled list
        if hasattr(self.sdk_service, 'remove_plugin'):
            self.sdk_service.remove_plugin(plugin_name)
            await safe_callback_answer(callback, t("plugins.disabled_success", name=plugin_name))
            await self.handle_plugin_list(callback)
        else:
            await safe_callback_answer(
                callback,
                t("plugins.remove_from_env", name=plugin_name),
                show_alert=True
            )

    async def handle_plugin_close(self, callback: CallbackQuery) -> None:
        """Close plugins menu"""
        await callback.message.delete()
        await safe_callback_answer(callback)
