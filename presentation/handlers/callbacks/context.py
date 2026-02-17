"""
Context Callback Handlers

Handles context/session management callbacks:
- Context list and switching
- Context creation and clearing
- Context menu navigation
"""

import logging
from aiogram.types import CallbackQuery

from presentation.handlers.callbacks.base import BaseCallbackHandler
from presentation.keyboards.keyboards import Keyboards
from shared.utils.telegram_utils import safe_callback_answer
from shared.i18n import get_translator

logger = logging.getLogger(__name__)


class ContextCallbackHandler(BaseCallbackHandler):
    """Handles context management callbacks."""

    def _get_translator(self, callback: CallbackQuery):
        """Get translator for user's language."""
        from shared.i18n import get_translator
        user_lang = None
        if hasattr(self, 'account_service') and self.account_service:
            try:
                user_lang = self.account_service.get_user_language_sync(callback.from_user.id)
            except:
                pass
        return get_translator(user_lang)

    async def _get_context_data(self, callback: CallbackQuery):
        """Helper to get project, context and user data for context operations."""
        user_id = callback.from_user.id
        t = self._get_translator(callback)

        if not self.project_service or not self.context_service:
            await safe_callback_answer(callback, t('error.service_unavailable'))
            return None, None, None, None

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        project = await self.project_service.get_current(uid)
        if not project:
            await safe_callback_answer(callback, t('error.no_project'))
            return None, None, None, None

        current_ctx = await self.context_service.get_current(project.id)
        return uid, project, current_ctx, self.context_service

    # ============== Context Menu ==============

    async def handle_context_menu(self, callback: CallbackQuery) -> None:
        """Show context main menu."""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            t = self._get_translator(callback)
            ctx_name = current_ctx.name if current_ctx else t('context.not_selected')
            msg_count = current_ctx.message_count if current_ctx else 0
            has_session = current_ctx.has_session if current_ctx else False

            session_status = t('context.has_session') if has_session else t('context.clean')
            text = (
                f"💬 {t('context.management')}\n\n"
                f"📂 {t('context.project')}: {project.name}\n"
                f"💬 {t('context.name')}: {ctx_name}\n"
                f"📝 {t('context.messages')}: {msg_count}\n"
                f"📌 {t('context.status')}: {session_status}"
            )

            keyboard = Keyboards.context_menu(
                ctx_name, project.name, msg_count,
                show_back=True, back_to="menu:context"
            )
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await safe_callback_answer(callback)

        except Exception as e:
            logger.error(f"Error showing context menu: {e}")
            t = self._get_translator(callback)
            await safe_callback_answer(callback, f"❌ {t('errors.error')}: {e}")

    # ============== Context List ==============

    async def handle_context_list(self, callback: CallbackQuery) -> None:
        """Show list of contexts."""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            contexts = await ctx_service.list_contexts(project.id)
            current_id = current_ctx.id if current_ctx else None

            t = self._get_translator(callback)
            if contexts:
                text = f"💬 {t('context.project_contexts', project=project.name)}\n\n{t('context.select')}"
                keyboard = Keyboards.context_list(contexts, current_id)
            else:
                # Create default context if none exist
                context = await ctx_service.create_new(project.id, uid, "main", set_as_current=True)
                text = f"✨ {t('context.created')}: {context.name}"
                keyboard = Keyboards.context_menu(
                    context.name, project.name, 0,
                    show_back=True, back_to="menu:context"
                )

            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await safe_callback_answer(callback)

        except Exception as e:
            logger.error(f"Error listing contexts: {e}")
            t = self._get_translator(callback)
            await safe_callback_answer(callback, f"❌ {t('errors.error')}: {e}")

    # ============== Context Switch ==============

    async def handle_context_switch(self, callback: CallbackQuery) -> None:
        """Handle context switch."""
        context_id = callback.data.split(":")[-1]

        try:
            uid, project, _, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            context = await ctx_service.switch_context(project.id, context_id)

            t = self._get_translator(callback)
            if context:
                session_status = t('context.has_session') if context.has_session else t('context.clean')
                text = (
                    f"💬 {t('context.switched_to')}\n\n"
                    f"📝 {context.name}\n"
                    f"📊 {t('context.messages')}: {context.message_count}\n"
                    f"📂 {t('context.project')}: {project.name}\n"
                    f"📌 {t('context.status')}: {session_status}"
                )
                keyboard = Keyboards.context_menu(
                    context.name, project.name, context.message_count,
                    show_back=True, back_to="menu:context"
                )
                await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
                await safe_callback_answer(callback, f"{t('context.name')}: {context.name}")
            else:
                await safe_callback_answer(callback, t('error.context_not_found'))

        except Exception as e:
            logger.error(f"Error switching context: {e}")
            t = self._get_translator(callback)
            await safe_callback_answer(callback, f"❌ {t('errors.error')}: {e}")

    # ============== Context Creation ==============

    async def handle_context_new(self, callback: CallbackQuery) -> None:
        """Handle new context creation."""
        try:
            uid, project, _, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            context = await ctx_service.create_new(project.id, uid, set_as_current=True)

            t = self._get_translator(callback)
            text = (
                f"✨ {t('context.new_created')}\n\n"
                f"📝 {context.name}\n"
                f"📂 {t('context.project')}: {project.name}\n\n"
                f"{t('context.clean_start')}\n"
                f"{t('context.send_first')}"
            )
            keyboard = Keyboards.context_menu(
                context.name, project.name, 0,
                show_back=True, back_to="menu:context"
            )
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await safe_callback_answer(callback, f"{t('context.created')} {context.name}")

        except Exception as e:
            logger.error(f"Error creating context: {e}")
            t = self._get_translator(callback)
            await safe_callback_answer(callback, f"❌ {t('errors.error')}: {e}")

    # ============== Context Clearing ==============

    async def handle_context_clear(self, callback: CallbackQuery) -> None:
        """Show clear confirmation."""
        try:
            uid, project, current_ctx, _ = await self._get_context_data(callback)
            if not project:
                return

            t = self._get_translator(callback)
            if not current_ctx:
                await safe_callback_answer(callback, t('error.no_active_context'))
                return

            text = (
                f"🗑️ {t('context.clear_confirm')}?\n\n"
                f"📝 {current_ctx.name}\n"
                f"📊 {t('context.messages')}: {current_ctx.message_count}\n\n"
                f"⚠️ {t('context.history_will_be_deleted')}!"
            )
            keyboard = Keyboards.context_clear_confirm()
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await safe_callback_answer(callback)

        except Exception as e:
            logger.error(f"Error showing clear confirm: {e}")
            t = self._get_translator(callback)
            await safe_callback_answer(callback, f"❌ {t('errors.error')}: {e}")

    async def handle_context_clear_confirm(self, callback: CallbackQuery) -> None:
        """Confirm and clear context - creates NEW context for fresh start."""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            t = self._get_translator(callback)
            if not current_ctx:
                await safe_callback_answer(callback, t('error.no_active_context'))
                return

            # 1. Create new context (auto-generated name, set as current)
            new_context = await ctx_service.create_new(
                project_id=project.id,
                user_id=uid,
                name=None,  # Auto-generate name
                set_as_current=True
            )

            # 2. Clear in-memory session cache to ensure fresh start
            user_id = callback.from_user.id
            if self.message_handlers:
                self.message_handlers.clear_session_cache(user_id)

            text = (
                f"✅ {t('context.new_created')}\n\n"
                f"📝 {new_context.name}\n"
                f"📂 {t('context.project')}: {project.name}\n\n"
                f"{t('context.start_new_dialog')}"
            )
            keyboard = Keyboards.context_menu(
                new_context.name, project.name, 0,
                show_back=True, back_to="menu:context"
            )
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await safe_callback_answer(callback, t('context.new_context_created'))

        except Exception as e:
            logger.error(f"Error clearing context: {e}")
            t = self._get_translator(callback)
            await safe_callback_answer(callback, f"❌ {t('errors.error')}: {e}")

    # ============== Navigation ==============

    async def handle_context_close(self, callback: CallbackQuery) -> None:
        """Close context menu."""
        try:
            await callback.message.delete()
            await safe_callback_answer(callback)
        except Exception as e:
            logger.debug(f"Error closing context menu: {e}")
            await safe_callback_answer(callback)
