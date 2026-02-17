"""
OS Settings Handler

Handles OS selection and working directory configuration.
Allows users to select their OS type for proper path handling.
"""

import logging
import os
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from domain.value_objects.project_path import ProjectPath
from shared.utils.telegram_utils import safe_callback_answer

logger = logging.getLogger(__name__)


class OSSettingsHandler:
    """Handles OS selection and working directory settings."""

    OS_OPTIONS = {
        "windows": {
            "name": "🪟 Windows",
            "default_path": "C:\\Users\\{username}\\projects",
            "description": "Windows with C: drive"
        },
        "linux": {
            "name": "🐧 Linux",
            "default_path": "/root/projects",  # Kept for display purposes
            "description": "Linux (root user)"
        },
        "linux_user": {
            "name": "🐧 Linux (User)",
            "default_path": "/home/{username}/projects",
            "description": "Linux (regular user)"
        },
        "macos": {
            "name": "🍎 macOS",
            "default_path": "/Users/{username}/projects",
            "description": "macOS"
        },
        "auto": {
            "name": "🔍 Auto Detect",
            "default_path": "auto",
            "description": "Auto-detect from system"
        }
    }

    def __init__(self, account_service=None):
        self.account_service = account_service

    async def show_os_menu(self, callback: CallbackQuery, user_id: int) -> None:
        """Show OS selection menu."""
        # Get current OS setting
        current_os = "auto"
        custom_path = None
        if self.account_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                settings = await self.account_service.get_account_settings(uid)
                if settings:
                    current_os = getattr(settings, 'os_type', 'auto')
                    custom_path = getattr(settings, 'custom_working_dir', None)
            except Exception as e:
                logger.warning(f"Error getting OS settings: {e}")

        # Build keyboard
        keyboard_rows = []
        for os_key, os_info in self.OS_OPTIONS.items():
            prefix = "✅ " if os_key == current_os else ""
            btn_text = f"{prefix}{os_info['name']}"
            callback_data = f"os:select:{os_key}"
            keyboard_rows.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])

        # Add custom path option
        if custom_path:
            keyboard_rows.append([InlineKeyboardButton(text=f"📁 Custom: {custom_path}", callback_data="os:custom")])
        else:
            keyboard_rows.append([InlineKeyboardButton(text="📁 Set Custom Path", callback_data="os:custom")])

        keyboard_rows.append([InlineKeyboardButton(text="🔙 Back", callback_data="menu:settings")])

        # Get current path info
        current_path = self._get_working_dir_for_os(current_os, user_id)

        text = (
            f"<b>🖥️ Operating System Settings</b>\n\n"
            f"Current: <code>{current_os}</code>\n"
            f"Working Dir: <code>{current_path}</code>\n\n"
            f"Select your OS for proper path handling:"
        )

        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        )
        await safe_callback_answer(callback)

    async def handle_os_select(self, callback: CallbackQuery, user_id: int) -> None:
        """Handle OS selection."""
        # Parse: os:select:<os_type>
        parts = callback.data.split(":")
        os_type = parts[2] if len(parts) > 2 else "auto"

        # Save to database
        if self.account_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                await self.account_service.set_os_type(uid, os_type)
            except Exception as e:
                logger.error(f"Error saving OS type: {e}")

        # Show confirmation
        os_info = self.OS_OPTIONS.get(os_type, self.OS_OPTIONS["auto"])
        working_dir = self._get_working_dir_for_os(os_type, user_id)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖥️ OS Settings", callback_data="os:menu")],
            [InlineKeyboardButton(text="🔙 Back to Settings", callback_data="menu:settings")]
        ])

        await callback.message.edit_text(
            f"✅ <b>OS Selected</b>\n\n"
            f"{os_info['name']}\n"
            f"Working Directory: <code>{working_dir}</code>\n\n"
            f"The bot will use this path for all file operations.",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        await safe_callback_answer(callback, f"✅ {os_info['name']}")

    def _get_working_dir_for_os(self, os_type: str, user_id: int) -> str:
        """Get working directory for selected OS."""
        import getpass
        username = getpass.getuser()

        if os_type == "auto":
            # Auto-detect from current system
            return ProjectPath.ROOT
        elif os_type == "windows":
            return f"C:\\Users\\{username}\\projects"
        elif os_type == "linux":
            return "/root/projects"
        elif os_type == "linux_user":
            return f"/home/{username}/projects"
        elif os_type == "macos":
            return f"/Users/{username}/projects"
        else:
            return os.path.join(os.path.expanduser("~"), "projects")

    async def handle_custom_path(self, callback: CallbackQuery, user_id: int) -> None:
        """Handle custom path setting."""
        # TODO: Implement custom path input flow
        await safe_callback_answer(callback, "Custom path - not implemented yet")
