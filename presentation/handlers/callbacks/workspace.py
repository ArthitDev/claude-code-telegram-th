"""
Workspace Callback Handlers

Manages workspace selection and switching:
- Add new workspace (browse any folder)
- Switch between workspaces
- Remove workspaces
"""

import os
import html
import logging
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from presentation.handlers.callbacks.base import BaseCallbackHandler
from presentation.keyboards.keyboards import CallbackData, Keyboards
from shared.utils.telegram_utils import safe_callback_answer

logger = logging.getLogger(__name__)


class WorkspaceCallbackHandler(BaseCallbackHandler):
    """Handles workspace management callbacks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._browse_states = {}  # Track browsing state per user

    # ============== Workspace Menu ==============

    async def handle_workspace_menu(self, callback: CallbackQuery) -> None:
        """Show workspace selection menu."""
        user_id = callback.from_user.id

        if not self.workspace_service:
            await safe_callback_answer(callback, "⚠️ Workspace service not available")
            return

        workspaces = self.workspace_service.list_workspaces()
        current = self.workspace_service.get_current_workspace()

        # Build keyboard with workspaces
        keyboard_rows = []

        for ws in workspaces:
            is_current = current and ws.id == current.id
            prefix = "✅ " if is_current else "📁 "
            btn_text = f"{prefix}{ws.name}"
            callback_data = f"workspace:switch:{ws.id}"
            keyboard_rows.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])

        # Add action buttons
        keyboard_rows.extend([
            [InlineKeyboardButton(text="➕ Add Workspace", callback_data="workspace:browse")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="menu:main")]
        ])

        current_text = f"\n📂 Current: <code>{html.escape(current.path)}</code>" if current else "\n📂 No workspace selected"

        text = (
            f"<b>📁 Workspaces</b>\n\n"
            f"Select a workspace to work in:\n"
            f"{current_text}\n\n"
            f"<i>Workspaces are folders where Claude can work on your projects.</i>"
        )

        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        )
        await safe_callback_answer(callback)

    async def handle_workspace_switch(self, callback: CallbackQuery) -> None:
        """Switch to selected workspace."""
        # Parse: workspace:switch:<workspace_id>
        parts = callback.data.split(":")
        workspace_id = parts[2] if len(parts) > 2 else None
        user_id = callback.from_user.id

        if not workspace_id or not self.workspace_service:
            await safe_callback_answer(callback, "❌ Invalid workspace")
            return

        workspace = self.workspace_service.get_workspace(workspace_id)
        if not workspace:
            await safe_callback_answer(callback, "❌ Workspace not found")
            return

        # Switch workspace
        if self.workspace_service.set_current_workspace(workspace_id):
            # Update working directory in message handlers
            if self.message_handlers:
                self.message_handlers.set_working_dir(user_id, workspace.path)

            # Also update project service if available
            if self.project_service:
                try:
                    from domain.value_objects.user_id import UserId
                    uid = UserId.from_int(user_id)
                    project = await self.project_service.get_or_create(uid, workspace.path, workspace.name)
                    await self.project_service.switch_project(uid, project.id)
                except Exception as e:
                    logger.warning(f"Error updating project for workspace: {e}")

            # Show confirmation
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📁 Workspaces", callback_data="workspace:menu")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:main")]
            ])

            await callback.message.edit_text(
                f"✅ <b>Workspace Switched</b>\n\n"
                f"📁 <b>{html.escape(workspace.name)}</b>\n"
                f"📂 <code>{html.escape(workspace.path)}</code>\n\n"
                f"Ready to work! Send a message to start.",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            await safe_callback_answer(callback, f"✅ {workspace.name}")
        else:
            await safe_callback_answer(callback, "❌ Failed to switch workspace")

    # ============== Browse for New Workspace ==============

    async def handle_workspace_browse(self, callback: CallbackQuery) -> None:
        """Start browsing for a new workspace."""
        user_id = callback.from_user.id

        # On Windows, show drive selection first
        if os.name == 'nt':
            await self._show_drive_selection(callback)
        else:
            # Linux/Mac - start from root
            start_path = "/"
            self._browse_states[user_id] = {
                "path": start_path,
                "mode": "workspace_select"
            }
            await self._show_browse_keyboard(callback, start_path)
        await safe_callback_answer(callback, "Browse for workspace folder")

    async def _show_drive_selection(self, callback: CallbackQuery) -> None:
        """Show available drives on Windows."""
        import string
        import ctypes

        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive_path = f"{letter}:\\"
                try:
                    # Get drive label
                    label = ctypes.create_unicode_buffer(1024)
                    ctypes.windll.kernel32.GetVolumeInformationW(
                        drive_path, label, 1024, None, None, None, None, 0
                    )
                    label_text = label.value or "Local Disk"
                    drives.append((drive_path, f"{label_text} ({letter}:)"))
                except:
                    drives.append((drive_path, f"Drive {letter}:"))
            bitmask >>= 1

        keyboard_rows = []
        for drive_path, display_name in drives:
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"💾 {display_name}",
                    callback_data=f"workspace:nav:{drive_path}"
                )
            ])

        keyboard_rows.append([
            InlineKeyboardButton(text="❌ Cancel", callback_data="workspace:menu")
        ])

        await callback.message.edit_text(
            "<b>💾 Select Drive</b>\n\nChoose a drive to browse:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        )

    async def _show_browse_keyboard(self, callback: CallbackQuery, path: str, page: int = 0) -> None:
        """Show folder browser keyboard with pagination."""
        user_id = callback.from_user.id
        ITEMS_PER_PAGE = 30  # Increased from 20

        if not os.path.exists(path):
            path = "/" if os.name != 'nt' else "C:\\"

        try:
            entries = []
            for entry in os.scandir(path):
                if entry.name.startswith('.'):
                    continue
                if entry.is_dir():
                    entries.append(entry)

            # Sort: folders first, then by name
            entries.sort(key=lambda e: e.name.lower())

            # Pagination
            total_entries = len(entries)
            total_pages = (total_entries + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_entries > 0 else 1
            page = max(0, min(page, total_pages - 1))

            start_idx = page * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            page_entries = entries[start_idx:end_idx]

            # Build keyboard
            keyboard_rows = []

            # Parent directory button
            parent = os.path.dirname(path)
            if parent and parent != path:
                keyboard_rows.append([
                    InlineKeyboardButton(text="⬆️ .. (Parent)", callback_data=f"workspace:nav:{parent}")
                ])

            # Folder buttons
            for entry in page_entries:
                # Truncate long names
                display_name = entry.name[:25] + "..." if len(entry.name) > 28 else entry.name
                btn_text = f"📁 {display_name}"
                callback_data = f"workspace:nav:{entry.path}"
                keyboard_rows.append([
                    InlineKeyboardButton(text=btn_text, callback_data=callback_data)
                ])

            # Pagination controls
            if total_pages > 1:
                pagination_row = []
                if page > 0:
                    pagination_row.append(
                        InlineKeyboardButton(text="◀️ Prev", callback_data=f"workspace:page:{path}:{page-1}")
                    )
                pagination_row.append(
                    InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="workspace:noop")
                )
                if page < total_pages - 1:
                    pagination_row.append(
                        InlineKeyboardButton(text="Next ▶️", callback_data=f"workspace:page:{path}:{page+1}")
                    )
                keyboard_rows.append(pagination_row)

            # Stats row
            if total_entries > ITEMS_PER_PAGE:
                keyboard_rows.append([
                    InlineKeyboardButton(text=f"📊 {total_entries} folders", callback_data="workspace:noop")
                ])

            # Current path info and select button
            keyboard_rows.append([
                InlineKeyboardButton(text=f"✅ Select This Folder",
                                   callback_data=f"workspace:add:{path}")
            ])

            # Drive selection button (Windows only)
            if os.name == 'nt':
                keyboard_rows.append([
                    InlineKeyboardButton(text="💾 Change Drive", callback_data="workspace:drives")
                ])

            # Cancel button
            keyboard_rows.append([
                InlineKeyboardButton(text="❌ Cancel", callback_data="workspace:menu")
            ])

            text = (
                f"<b>📂 Select Workspace Folder</b>\n\n"
                f"Current: <code>{html.escape(path)}</code>\n"
                f"Showing: {start_idx+1}-{min(end_idx, total_entries)} of {total_entries} folders\n\n"
                f"Navigate and click '✅ Select This Folder' to add as workspace."
            )

            await callback.message.edit_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
            )

        except PermissionError:
            await callback.message.edit_text(
                f"❌ <b>Access Denied</b>\n\n"
                f"Cannot access: <code>{html.escape(path)}</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back", callback_data="workspace:menu")]
                ])
            )
        except Exception as e:
            logger.error(f"Error browsing {path}: {e}")
            await callback.message.edit_text(
                f"❌ <b>Error</b>\n\n{html.escape(str(e))}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back", callback_data="workspace:menu")]
                ])
            )

    async def handle_workspace_page(self, callback: CallbackQuery) -> None:
        """Handle pagination in folder browser."""
        # Parse: workspace:page:<path>:<page_number>
        parts = callback.data.split(":")
        if len(parts) >= 4:
            # Rejoin path parts (path may contain colons on Windows)
            path = ":".join(parts[2:-1])
            try:
                page = int(parts[-1])
            except ValueError:
                page = 0
        else:
            path = "/"
            page = 0

        user_id = callback.from_user.id
        self._browse_states[user_id] = {
            "path": path,
            "mode": "workspace_select"
        }

        await self._show_browse_keyboard(callback, path, page)
        await safe_callback_answer(callback)

    async def handle_workspace_nav(self, callback: CallbackQuery) -> None:
        """Handle navigation in folder browser."""
        # Parse: workspace:nav:<path>
        parts = callback.data.split(":", 2)
        path = parts[2] if len(parts) > 2 else "/"
        user_id = callback.from_user.id

        self._browse_states[user_id] = {
            "path": path,
            "mode": "workspace_select"
        }

        await self._show_browse_keyboard(callback, path)
        await safe_callback_answer(callback)

    async def handle_workspace_add(self, callback: CallbackQuery) -> None:
        """Add selected folder as workspace."""
        # Parse: workspace:add:<path>
        parts = callback.data.split(":", 2)
        path = parts[2] if len(parts) > 2 else None
        user_id = callback.from_user.id

        if not path or not self.workspace_service:
            await safe_callback_answer(callback, "❌ Invalid path")
            return

        # Validate path
        if not os.path.isdir(path):
            await safe_callback_answer(callback, "❌ Not a valid directory")
            return

        # Add workspace
        name = os.path.basename(path) or path
        workspace = self.workspace_service.add_workspace(path, name)

        if workspace:
            # Switch to new workspace
            self.workspace_service.set_current_workspace(workspace.id)

            if self.message_handlers:
                self.message_handlers.set_working_dir(user_id, path)

            # Show confirmation
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📁 Workspaces", callback_data="workspace:menu")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:main")]
            ])

            await callback.message.edit_text(
                f"✅ <b>Workspace Added</b>\n\n"
                f"📁 <b>{html.escape(workspace.name)}</b>\n"
                f"📂 <code>{html.escape(workspace.path)}</code>\n\n"
                f"This folder is now your active workspace.",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            await safe_callback_answer(callback, f"✅ Added {workspace.name}")
        else:
            await safe_callback_answer(callback, "❌ Failed to add workspace")

    async def handle_workspace_drives(self, callback: CallbackQuery) -> None:
        """Show drive selection (Windows only)."""
        await self._show_drive_selection(callback)
        await safe_callback_answer(callback, "Select drive")

    async def handle_workspace_remove(self, callback: CallbackQuery) -> None:
        """Remove a workspace."""
        # Parse: workspace:remove:<workspace_id>
        parts = callback.data.split(":")
        workspace_id = parts[2] if len(parts) > 2 else None

        if not workspace_id or not self.workspace_service:
            await safe_callback_answer(callback, "❌ Invalid workspace")
            return

        workspace = self.workspace_service.get_workspace(workspace_id)
        if not workspace:
            await safe_callback_answer(callback, "❌ Workspace not found")
            return

        if workspace.is_default:
            await safe_callback_answer(callback, "❌ Cannot remove default workspace")
            return

        if self.workspace_service.remove_workspace(workspace_id):
            await self.handle_workspace_menu(callback)
            await safe_callback_answer(callback, f"✅ Removed {workspace.name}")
        else:
            await safe_callback_answer(callback, "❌ Failed to remove workspace")
