"""
Project Callback Handlers

Handles project management and file browser callbacks:
- Project selection, creation, deletion
- Folder browsing and navigation
- Working directory management
"""

import os
import re
import logging
import shutil
import html
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from domain.value_objects.project_path import ProjectPath
from presentation.handlers.callbacks.base import BaseCallbackHandler
from presentation.keyboards.keyboards import CallbackData, Keyboards
from shared.utils.telegram_utils import safe_callback_answer
from shared.i18n import get_translator

logger = logging.getLogger(__name__)


class ProjectCallbackHandler(BaseCallbackHandler):
    """Handles project management callbacks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user_states = {}  # For tracking mkdir input state

    def get_user_state(self, user_id: int) -> dict | None:
        """Get current user state if any."""
        return self._user_states.get(user_id)

    async def process_user_input(self, message) -> bool:
        """
        Process user input based on current state.
        Returns True if input was consumed, False otherwise.
        """
        user_id = message.from_user.id
        state = self._user_states.get(user_id)

        if not state:
            return False

        state_name = state.get("state")
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        if state_name == "waiting_project_mkdir":
            return await self.handle_project_mkdir_input(message, message.text.strip(), t)

        return False

    # ============== Project Selection ==============

    async def handle_project_select(self, callback: CallbackQuery) -> None:
        """Handle project selection."""
        data = CallbackData.parse_project_callback(callback.data)
        action = data.get("action")
        path = data.get("path", "")
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        try:
            if action == "select" and path:
                # Set working directory
                if hasattr(self.message_handlers, 'set_working_dir'):
                    self.message_handlers.set_working_dir(user_id, path)

                project_name = os.path.basename(path) or "root"
                
                await callback.message.edit_text(
                    t('project.working_dir_set', path=html.escape(path), project=html.escape(project_name)),
                    parse_mode=ParseMode.HTML
                )
                await safe_callback_answer(callback, f"✅ {project_name}")

            elif action == "custom":
                # Prompt for custom path input
                if hasattr(self.message_handlers, 'set_expecting_path'):
                    self.message_handlers.set_expecting_path(user_id, True)

                await callback.message.edit_text(
                    f"📂 {t('projects.path_prompt')}\n\n{t('projects.path_prompt')}", # Using prompt twice as title and body for simplicity or better UI
                    parse_mode=None
                )
                await safe_callback_answer(callback, t("projects.path_prompt"))

        except Exception as e:
            logger.error(f"Error handling project select: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    async def handle_project_switch(self, callback: CallbackQuery) -> None:
        """Handle project switch (from /change command)."""
        project_id = callback.data.split(":")[-1]
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        if not self.project_service:
            await safe_callback_answer(callback, f"⚠️ {t('error.service_unavailable')}")
            return

        try:
            from domain.value_objects.user_id import UserId

            uid = UserId.from_int(user_id)
            project = await self.project_service.switch_project(uid, project_id)

            if project:
                # Also update working directory in message handlers
                if hasattr(self.message_handlers, 'set_working_dir'):
                    self.message_handlers.set_working_dir(user_id, project.working_dir)

                await callback.message.edit_text(
                    t('project.working_dir_set', path=html.escape(project.working_dir), project=html.escape(project.name)),
                    parse_mode=ParseMode.HTML
                )
                await safe_callback_answer(callback, t("projects.switched", name=project.name))
            else:
                await safe_callback_answer(callback, t("error.not_found"))

        except Exception as e:
            logger.error(f"Error switching project: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    # ============== Project Creation ==============

    async def handle_project_create(self, callback: CallbackQuery) -> None:
        """Handle project create - show folder browser."""
        await self.handle_project_browse(callback)

    async def handle_project_browse(self, callback: CallbackQuery) -> None:
        """Handle project browse - show folders in projects root."""
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)
        
        try:
            root_path = ProjectPath.ROOT

            # Check if path specified in callback
            if ":" in callback.data and callback.data.count(":") > 1:
                path = ":".join(callback.data.split(":")[2:])
                if path and os.path.isdir(path):
                    root_path = path

            # Ensure directory exists
            if not os.path.exists(root_path):
                os.makedirs(root_path, exist_ok=True)

            # Get folders
            folders = []
            try:
                for entry in os.scandir(root_path):
                    if entry.is_dir() and not entry.name.startswith('.'):
                        folders.append(entry.path)
            except OSError:
                pass

            folders.sort()

            if folders:
                text = (
                    f"📂 <b>{t('projects.browse')}</b>\n\n"
                    f"{t('start.path', path=html.escape(root_path))}\n\n"
                    f"{t('projects.select')}"
                )
            else:
                text = (
                    f"📂 <b>{t('projects.list_empty')}</b>\n\n"
                    f"{t('start.path', path=html.escape(root_path))}\n\n"
                    f"{t('projects.create_or_open')}"
                )

            try:
                await callback.message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=Keyboards.folder_browser(folders, root_path, lang=user_lang)
                )
            except Exception as edit_err:
                # Ignore "message is not modified" error
                if "message is not modified" not in str(edit_err):
                    raise edit_err
            await safe_callback_answer(callback)

        except Exception as e:
            logger.error(f"Error browsing projects: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    async def handle_project_folder(self, callback: CallbackQuery) -> None:
        """Handle folder selection - create project from folder."""
        folder_path = ":".join(callback.data.split(":")[2:])
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        if not folder_path or not os.path.isdir(folder_path):
            await safe_callback_answer(callback, t("error.invalid_input"))
            return

        if not self.project_service:
            await safe_callback_answer(callback, f"⚠️ {t('error.service_unavailable')}")
            return

        try:
            from domain.value_objects.user_id import UserId

            uid = UserId.from_int(user_id)
            name = os.path.basename(folder_path)

            # Create or get project
            project = await self.project_service.get_or_create(uid, folder_path, name)

            # Switch to it
            await self.project_service.switch_project(uid, project.id)

            # Update working directory
            if hasattr(self.message_handlers, 'set_working_dir'):
                self.message_handlers.set_working_dir(user_id, folder_path)

            # Create keyboard with project actions
            project_created_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=f"📁 {t('menu.projects')}", callback_data="project:back"),
                    InlineKeyboardButton(text=f"📂 {t('menu.main_title')}", callback_data="menu:main")
                ]
            ])

            await callback.message.edit_text(
                f"{t('projects.created', name=html.escape(project.name))}\n\n"
                f"{t('start.path', path=f'<code>{html.escape(project.working_dir)}</code>')}\n\n"
                f"{t('start.ready')}",
                parse_mode="HTML",
                reply_markup=project_created_keyboard
            )
            await safe_callback_answer(callback, t("projects.created", name=project.name))

        except Exception as e:
            logger.error(f"Error creating project from folder: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    # ============== Folder Creation ==============

    async def handle_project_mkdir(self, callback: CallbackQuery) -> None:
        """Handle create folder - prompt for folder name."""
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        # Set state to wait for folder name
        self._user_states[user_id] = {
            "state": "waiting_project_mkdir",
            "message_id": callback.message.message_id
        }

        text = (
            f"📁 <b>{t('keyboard.mkdir')}</b>\n\n"
            f"{t('projects.name_prompt')}\n"
            f"<i>(a-z, 0-9, -, _)</i>"
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.menu_back_only("project:browse", lang=user_lang)
        )
        await safe_callback_answer(callback)

    async def handle_project_mkdir_input(self, message, folder_name: str, t) -> bool:
        """Process folder name input for project creation."""
        user_id = message.from_user.id

        # Validate folder name
        if not re.match(r'^[a-zA-Z0-9_-]+$', folder_name):
            await message.reply(
                f"{t('error.invalid_input')}\n"
                "a-z, 0-9, -, _"
            )
            return True  # Consumed, but keep waiting

        folder_path = os.path.join(ProjectPath.ROOT, folder_name)

        if os.path.exists(folder_path):
            await message.reply(f"❌ {t('error.invalid_input')} (Exists)") # Simplified
            return True

        try:
            os.makedirs(folder_path, exist_ok=True)

            # Clear state
            self._user_states.pop(user_id, None)

            # Create project from this folder
            if self.project_service:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                project = await self.project_service.get_or_create(uid, folder_path, folder_name)
                await self.project_service.switch_project(uid, project.id)

                if hasattr(self.message_handlers, 'set_working_dir'):
                    self.message_handlers.set_working_dir(user_id, folder_path)

                # Create keyboard with project actions
                project_created_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text=f"📁 {t('menu.projects')}", callback_data="project:back"),
                        InlineKeyboardButton(text=f"📂 {t('menu.main_title')}", callback_data="menu:main")
                    ]
                ])

                await message.reply(
                    f"{t('projects.created', name=html.escape(folder_name))}\n\n"
                    f"{t('start.path', path=f'<code>{html.escape(folder_path)}</code>')}\n\n"
                    f"{t('start.ready')}",
                    parse_mode="HTML",
                    reply_markup=project_created_keyboard
                )
            else:
                await message.reply(f"✅ Created: <code>{html.escape(folder_path)}</code>", parse_mode="HTML")

            return True

        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            await message.reply(t("error.unknown", error=str(e)))
            return True

    # ============== Project Deletion ==============

    async def handle_project_delete(self, callback: CallbackQuery) -> None:
        """Handle project delete - show confirmation dialog."""
        project_id = callback.data.split(":")[-1]
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        if not self.project_service:
            await safe_callback_answer(callback, f"⚠️ {t('error.service_unavailable')}")
            return

        try:
            from domain.value_objects.user_id import UserId

            uid = UserId.from_int(user_id)
            project = await self.project_service.get_by_id(project_id)

            if not project:
                await safe_callback_answer(callback, t("error.not_found"))
                return

            if int(project.user_id) != user_id:
                await safe_callback_answer(callback, t("error.permission_denied"))
                return

            text = (
                f"⚠️ {t('menu.delete')}\n\n"
                f"{t('start.project', name=project.name)}\n"
                f"{t('start.path', path=project.working_dir)}\n\n"
                f"{t('projects.delete_warning')}"
            )

            await callback.message.edit_text(
                text,
                parse_mode=None,
                reply_markup=Keyboards.project_delete_confirm(project_id, project.name, lang=user_lang)
            )
            await safe_callback_answer(callback)

        except Exception as e:
            logger.error(f"Error showing delete confirmation: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    async def handle_project_delete_confirm(self, callback: CallbackQuery) -> None:
        """Handle confirmed project deletion."""
        # Parse callback: project:delete_confirm:<id>:<mode>
        parts = callback.data.split(":")
        project_id = parts[2] if len(parts) > 2 else ""
        delete_mode = parts[3] if len(parts) > 3 else "db"
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        if not self.project_service:
            await safe_callback_answer(callback, f"⚠️ {t('error.service_unavailable')}")
            return

        try:
            from domain.value_objects.user_id import UserId

            uid = UserId.from_int(user_id)
            project = await self.project_service.get_by_id(project_id)

            if not project:
                await safe_callback_answer(callback, t("error.not_found"))
                return

            if int(project.user_id) != user_id:
                await safe_callback_answer(callback, t("error.permission_denied"))
                return

            project_name = project.name
            project_path = project.working_dir

            # Delete from database
            deleted = await self.project_service.delete_project(uid, project_id)

            if not deleted:
                await safe_callback_answer(callback, t("error.unknown", error="Delete failed"))
                return

            # Delete files if requested
            files_deleted = False
            if delete_mode == "all":
                try:
                    if os.path.exists(project_path) and project_path.startswith(str(ProjectPath.ROOT)):
                        shutil.rmtree(project_path)
                        files_deleted = True
                except Exception as e:
                    logger.error(f"Error deleting project files: {e}")

            # Show result
            if files_deleted:
                result_text = t("projects.deleted", name=project_name) + " (Files deleted)"
            else:
                result_text = t("projects.deleted", name=project_name) + " (DB only)"

            # Show updated project list
            projects = await self.project_service.list_projects(uid)
            current = await self.project_service.get_current(uid)
            current_id = current.id if current else None

            await callback.message.edit_text(
                result_text + f"\n\n📁 {t('projects.title')}:",
                parse_mode=None,
                reply_markup=Keyboards.project_list(projects, current_id, show_back=True, back_to="menu:projects", lang=user_lang)
            )
            await safe_callback_answer(callback, t("projects.deleted", name=project_name))

        except Exception as e:
            logger.error(f"Error deleting project: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    # ============== Navigation ==============

    async def handle_project_back(self, callback: CallbackQuery) -> None:
        """Handle back to project list."""
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        if not self.project_service:
            await safe_callback_answer(callback, f"⚠️ {t('error.service_unavailable')}")
            return

        try:
            from domain.value_objects.user_id import UserId

            uid = UserId.from_int(user_id)
            projects = await self.project_service.list_projects(uid)
            current = await self.project_service.get_current(uid)
            current_id = current.id if current else None

            if projects:
                text = f"📁 {t('projects.title')}:\n\n{t('projects.select')}"
            else:
                text = f"📁 {t('projects.list_empty')}\n\n{t('projects.create')}"

            await callback.message.edit_text(
                text,
                parse_mode=None,
                reply_markup=Keyboards.project_list(projects, current_id, show_back=True, back_to="menu:projects", lang=user_lang)
            )
            await safe_callback_answer(callback)

        except Exception as e:
            logger.error(f"Error going back to project list: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    # ============== File Browser (cd:*) ==============

    async def handle_cd_goto(self, callback: CallbackQuery) -> None:
        """Handle folder navigation in /cd command."""
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)
        
        # Extract path from callback data (cd:goto:/path/to/folder)
        path = callback.data.split(":", 2)[-1] if callback.data.count(":") >= 2 else ""

        if not self.file_browser_service:
            from application.services.file_browser_service import FileBrowserService
            self.file_browser_service = FileBrowserService()

        # Validate path is within root
        if not self.file_browser_service.is_within_root(path):
            await safe_callback_answer(callback, t("error.permission_denied"))
            return

        # Check if directory exists
        if not os.path.isdir(path):
            await safe_callback_answer(callback, t("error.not_found"))
            return

        try:
            # Get content and tree view
            content = await self.file_browser_service.list_directory(path)
            tree_view = await self.file_browser_service.get_tree_view(path)

            # Update message
            try:
                await callback.message.edit_text(
                    tree_view,
                    parse_mode=ParseMode.HTML,
                    reply_markup=Keyboards.file_browser(content, lang=user_lang)
                )
            except Exception as edit_error:
                # If message not modified, just answer the callback
                if "message is not modified" in str(edit_error).lower():
                    pass  # Ignore this error
                else:
                    raise
            await safe_callback_answer(callback)

        except Exception as e:
            logger.error(f"Error navigating to {path}: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    async def handle_cd_root(self, callback: CallbackQuery) -> None:
        """Handle going to root directory."""
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        if not self.file_browser_service:
            from application.services.file_browser_service import FileBrowserService
            self.file_browser_service = FileBrowserService()

        try:
            root_path = self.file_browser_service.ROOT_PATH

            # Ensure root exists
            os.makedirs(root_path, exist_ok=True)

            # Get content and tree view
            content = await self.file_browser_service.list_directory(root_path)
            tree_view = await self.file_browser_service.get_tree_view(root_path)

            # Update message
            try:
                await callback.message.edit_text(
                    tree_view,
                    parse_mode=ParseMode.HTML,
                    reply_markup=Keyboards.file_browser(content, lang=user_lang)
                )
            except Exception as edit_error:
                # If message not modified, just answer the callback
                if "message is not modified" in str(edit_error).lower():
                    pass  # Ignore this error
                else:
                    raise
            await safe_callback_answer(callback, "🏠 Root")

        except Exception as e:
            logger.error(f"Error going to root: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    async def handle_cd_select(self, callback: CallbackQuery) -> None:
        """Handle selecting folder as working directory."""
        # Extract path from callback data (cd:select:/path/to/folder)
        path = callback.data.split(":", 2)[-1] if callback.data.count(":") >= 2 else ""
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)

        if not self.file_browser_service:
            from application.services.file_browser_service import FileBrowserService
            self.file_browser_service = FileBrowserService()

        # Validate path
        if not self.file_browser_service.is_within_root(path):
            await safe_callback_answer(callback, t("error.permission_denied"))
            return

        if not os.path.isdir(path):
            await safe_callback_answer(callback, t("error.not_found"))
            return

        try:
            # Set working directory
            if self.message_handlers:
                self.message_handlers.set_working_dir(user_id, path)

            # Create/switch project if project_service available
            project_name = os.path.basename(path) or "root"
            if self.project_service:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)

                # First check if project with exact path exists
                existing = await self.project_service.project_repository.find_by_path(uid, path)
                if existing:
                    # Use existing project
                    project = existing
                else:
                    # Create new project for this exact path (don't use parent)
                    project = await self.project_service.create_project(uid, project_name, path)

                await self.project_service.switch_project(uid, project.id)
                project_name = project.name

            # Update message with confirmation
            await callback.message.edit_text(
                t('project.working_dir_set', path=html.escape(path), project=html.escape(project_name)),
                parse_mode=ParseMode.HTML
            )
            await safe_callback_answer(callback, f"✅ {project_name}")

        except Exception as e:
            logger.error(f"Error selecting folder {path}: {e}")
            await safe_callback_answer(callback, t("error.unknown", error=str(e)))

    async def handle_cd_close(self, callback: CallbackQuery) -> None:
        """Handle closing the file browser."""
        user_id = callback.from_user.id
        user_lang = await self._get_user_lang(user_id)
        t = get_translator(user_lang)
        try:
            await callback.message.delete()
            await safe_callback_answer(callback, t("menu.close"))
        except Exception as e:
            logger.error(f"Error closing file browser: {e}")
            await safe_callback_answer(callback, t("menu.close"))
