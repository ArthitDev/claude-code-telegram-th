"""
Main streaming handler for Telegram.

Manages streaming output to Telegram with rate limiting:
- Debouncing updates to avoid API rate limits
- Splitting long messages that exceed Telegram's 4096 char limit
- Graceful handling of rate limit errors with exponential backoff
- Adaptive update intervals based on message size
"""

import asyncio
import logging
import re
import time
from typing import Optional, TYPE_CHECKING

from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

from presentation.handlers.streaming.formatting import (
    markdown_to_html,
    prepare_html_for_telegram,
    StableHTMLFormatter,
    IncrementalFormatter,
)
from presentation.handlers.streaming.trackers import FileChangeTracker

if TYPE_CHECKING:
    from presentation.handlers.state.update_coordinator import MessageUpdateCoordinator

logger = logging.getLogger(__name__)


class StreamingHandler:
    """
    Manages streaming output to Telegram with rate limiting.

    ВАЖНО: Все обновления теперь проходят через MessageUpdateCoordinator!

    Handles the complexities of:
    - Debouncing updates to avoid API rate limits
    - Splitting long messages that exceed Telegram's 4096 char limit
    - Graceful handling of rate limit errors with exponential backoff
    - Adaptive update intervals based on message size
    """

    # Telegram limits - IMPORTANT: Telegram allows ~30 edits/min per chat
    # With heartbeat every 3s + content updates, we need careful timing
    MAX_MESSAGE_LENGTH = 4000  # Leave buffer from 4096
    DEBOUNCE_INTERVAL = 2.0  # Base seconds between updates (avoid rate limits)
    MIN_UPDATE_INTERVAL = 2.0  # УВЕЛИЧЕНО до 2 секунд! Синхронизировано с координатором

    # Adaptive interval thresholds (bytes) - increase interval for large messages
    LARGE_TEXT_BYTES = 2500  # >2.5KB → 2.5s interval
    VERY_LARGE_TEXT_BYTES = 3500  # >3.5KB → 3.0s interval

    # Rate limit backoff settings
    MAX_RATE_LIMIT_RETRIES = 3  # Max retries before giving up on update
    RATE_LIMIT_BACKOFF_MULTIPLIER = 1.5  # Multiply retry_after by this

    # Token estimation constants
    CHARS_PER_TOKEN = 4  # Approximate: 1 token ≈ 4 characters
    DEFAULT_CONTEXT_LIMIT = 200_000  # Claude Opus/Sonnet context window

    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        initial_message: Optional[Message] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        context_limit: int = DEFAULT_CONTEXT_LIMIT,
        coordinator: Optional["MessageUpdateCoordinator"] = None,
        translator = None
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.current_message = initial_message
        self.buffer = ""
        self.last_update_time = 0.0
        self.messages: list[Message] = []  # All sent messages
        self.is_finalized = False
        self._update_lock = asyncio.Lock()
        self._pending_update: Optional[asyncio.Task] = None
        self.reply_markup = reply_markup  # Cancel button etc.
        self._message_index = 1  # Current message number (for "Part N" indicator)
        self._just_created_continuation = False  # Flag to prevent immediate overflow after creating continuation
        self._translator = translator  # Translation helper
        # Status line - will be set properly after translator is available
        self._status_line = "🤖 <b>Starting...</b> ⠋ (0s)"  # Default, will update with translation
        self._formatter = IncrementalFormatter()  # Anti-flicker formatter
        self._todo_message: Optional[Message] = None  # Separate message for todo list (legacy, not used)
        self._plan_mode_message: Optional[Message] = None  # Plan mode indicator message
        self._is_plan_mode: bool = False  # Whether Claude is in plan mode
        self._last_todo_html: str = ""  # Cache last todo HTML to avoid "not modified" errors
        self._current_todo_html: str = ""  # Current todo HTML to show at bottom of message

        # Token tracking for context usage display
        self._estimated_tokens: int = 0  # Accumulated token estimate
        self._context_limit:int = context_limit  # Max context window

        # File change tracking for end-of-session summary
        self._file_change_tracker: Optional[FileChangeTracker] = None

        # ЦЕНТРАЛИЗОВАННЫЙ КООРДИНАТОР ОБНОВЛЕНИЙ
        # Если не передан - получаем глобальный
        self._coordinator = coordinator
        if self._coordinator is None:
            from presentation.handlers.state.update_coordinator import get_coordinator
            self._coordinator = get_coordinator()

        # COMPONENT-BASED UI STATE
        # Structured state for tools, thinking, etc. (replaces string manipulation)
        from presentation.handlers.streaming_ui import StreamingUIState
        self.ui = StreamingUIState()
        self.ui._translator = self._translator

        if initial_message:
            self.messages.append(initial_message)

        # Initialize status line with translation if available
        if self._translator:
            self._status_line = f"🤖 <b>{self._t('status.starting')}</b> ⠋ (0s)"

    def _t(self, key: str, **kwargs) -> str:
        """Get translated string by key."""
        if self._translator:
            return self._translator.get(key, **kwargs)
        # Fallback to English if no translator
        fallbacks = {
            "error.title": "❌ <b>Error</b>",
            "status.done_html": "✅ <b>Done</b>",
            "status.completed_with_issues": "⚠️ <b>Completed with issues</b>",
            "status.continuing": "🤖 <b>Continuing...</b>",
            "status.starting": "Starting...",
            "status.loading": "Loading...",
            "action.default": "Working",
            "action.thinking": "Thinking",
            "action.reading": "Reading",
            "action.writing": "Writing",
            "action.editing": "Editing",
            "action.searching": "Searching",
            "action.executing": "Executing",
            "action.planning": "Planning",
            "action.analyzing": "Analyzing",
            "action.waiting": "Waiting",
        }
        return fallbacks.get(key, key)

    def add_tokens(self, text: str, multiplier: float = 1.0) -> int:
        """Add estimated tokens from text to the running total.

        Args:
            text: Text to estimate tokens for
            multiplier: Weight factor (e.g., 0.5 for tool results which are compressed)

        Returns:
            Number of tokens added
        """
        if not text:
            return 0
        tokens = int(len(text) / self.CHARS_PER_TOKEN * multiplier)
        self._estimated_tokens += tokens
        return tokens

    def get_context_usage(self) -> tuple[int, int, int]:
        """Get current context usage stats.

        Returns:
            Tuple of (estimated_tokens, context_limit, percentage)
        """
        pct = int(100 * self._estimated_tokens / self._context_limit) if self._context_limit > 0 else 0
        return self._estimated_tokens, self._context_limit, min(pct, 100)

    def get_file_tracker(self) -> FileChangeTracker:
        """Get or create file change tracker for this session."""
        if self._file_change_tracker is None:
            self._file_change_tracker = FileChangeTracker()
        return self._file_change_tracker

    def track_file_change(self, tool_name: str, tool_input: dict) -> None:
        """Track a file-modifying tool use."""
        tracker = self.get_file_tracker()
        tracker.track_tool_use(tool_name, tool_input)

    async def show_file_changes_summary(self) -> Optional[Message]:
        """
        Show summary of all file changes at end of session.

        Sends a separate message with Cursor-style file change summary
        showing all files that were created, edited, or deleted.

        Returns:
            Sent message or None if no changes
        """
        if self._file_change_tracker is None or not self._file_change_tracker.has_changes():
            return None

        summary = self._file_change_tracker.get_summary(translator=self._t)
        if not summary:
            return None

        try:
            msg = await self.bot.send_message(
                self.chat_id,
                summary,
                parse_mode="HTML"
            )
            return msg
        except TelegramBadRequest as e:
            logger.warning(f"Failed to send file changes summary: {e}")
            # Try without formatting
            try:
                plain_summary = self._file_change_tracker.get_summary()
                # Strip HTML tags for plain text
                plain_summary = re.sub(r'<[^>]+>', '', plain_summary)
                msg = await self.bot.send_message(
                    self.chat_id,
                    plain_summary,
                    parse_mode=None
                )
                return msg
            except Exception:
                return None
        except Exception as e:
            logger.error(f"Error sending file changes summary: {e}")
            return None

    async def start(self, initial_text: str = "🤖 Starting...") -> Message:
        """Start streaming with an initial message"""
        if not self.current_message:
            html_text = markdown_to_html(initial_text)
            try:
                self.current_message = await self.bot.send_message(
                    self.chat_id,
                    html_text,
                    parse_mode="HTML",
                    reply_markup=self.reply_markup
                )
            except TelegramBadRequest:
                # Fallback without formatting if parsing fails
                self.current_message = await self.bot.send_message(
                    self.chat_id,
                    initial_text,
                    parse_mode=None,
                    reply_markup=self.reply_markup
                )
            self.messages.append(self.current_message)
        self.buffer = initial_text
        self.last_update_time = time.time()
        return self.current_message

    async def append(self, text: str):
        """
        Append text to the stream buffer.
        Обновление через координатор - он обеспечивает rate limiting.
        """
        if self.is_finalized:
            logger.debug(f"Streaming: append ignored, already finalized")
            return

        self.buffer += text
        logger.debug(f"Streaming: appended {len(text)} chars, buffer now {len(self.buffer)} chars")

        # Отправляем в координатор - он сам решит когда обновить
        await self._do_update()

    async def append_line(self, text: str):
        """Append text followed by a newline"""
        await self.append(text + "\n")

    async def replace_last_line(self, old_line: str, new_line: str) -> bool:
        """
        Replace the last occurrence of old_line with new_line in the buffer.

        Used for in-place updates like changing progress icons to completion icons.
        """
        if self.is_finalized:
            return False

        idx = self.buffer.rfind(old_line)
        if idx != -1:
            self.buffer = self.buffer[:idx] + new_line + self.buffer[idx + len(old_line):]
            await self._do_update()  # Координатор обеспечит rate limiting
            return True
        return False

    async def force_update(self):
        """
        Force an update - просто вызывает _do_update().
        Координатор обеспечивает rate limiting.
        """
        await self._do_update()

    async def immediate_update(self):
        """
        Immediately update - просто вызывает _do_update().
        Координатор обеспечивает rate limiting.
        """
        await self._do_update()

    async def set_status(self, status: str):
        """Set a status line at the bottom of the current message.

        ВАЖНО: Координатор обеспечивает rate limiting (2с между обновлениями).
        """
        self._status_line = status
        await self._do_update()

    def _get_display_buffer(self) -> str:
        """Get buffer content only (without status).

        Returns raw content for HTML formatting.
        Status line is added separately after HTML formatting.
        """
        # NOTE: Sync now happens in _edit_current_message via ui._content_buffer
        return self.buffer

    def _get_status_line(self) -> str:
        """Get status line (already HTML formatted).

        Returns empty string if finalized or no status.
        """
        if self.is_finalized or not self._status_line:
            return ""
        return self._status_line

    def _calc_edit_interval(self) -> float:
        """Calculate edit interval - ВСЕГДА 2 секунды.

        Координатор обеспечивает rate limiting, поэтому адаптивные
        интервалы больше не нужны.
        """
        return self.MIN_UPDATE_INTERVAL  # Всегда 2.0 секунды

    async def show_tool_use(self, tool_name: str, details: str = ""):
        """Show that a tool is being used with nice formatting"""
        # Emoji mapping for different tools
        emoji_map = {
            "bash": "💻",
            "write": "📝",
            "read": "📖",
            "edit": "✏️",
            "glob": "🔍",
            "grep": "🔎",
            "task": "🤖",
            "webfetch": "🌐",
            "websearch": "🔎",
            "askuserquestion": "❓",
            "todowrite": "📋",
        }
        emoji = emoji_map.get(tool_name.lower(), "🔧")

        tool_display = f"\n{emoji} **{tool_name}**"
        if details:
            # Truncate long details
            if len(details) > 150:
                details = details[:150] + "..."
            tool_display += f"\n`{details}`"
        tool_display += "\n"
        await self.append(tool_display)

    async def show_tool_result(self, output: str, success: bool = True):
        """Show tool execution result with formatting"""
        if not output or not output.strip():
            return

        # Truncate long output
        truncated = output.strip()
        if len(truncated) > 1500:
            truncated = truncated[:1500] + "\n... (truncated)"

        status = "✅" if success else "❌"
        result_text = f"{status} {self._t('tool.output')}\n```\n{truncated}\n```\n"
        await self.append(result_text)

    async def show_todo_list(self, todos: list[dict]) -> None:
        """Show/update todo list at the bottom of the current message.

        Instead of creating a separate message, the todo list is now shown
        at the bottom of the main streaming message, so it's always visible
        as the message grows.

        Shows:
        - ✅ Completed tasks (strikethrough)
        - ⏳ Current task (bold)
        - ⬜ Pending tasks

        Args:
            todos: List of todo items with content, status, activeForm
        """
        if not todos:
            self._current_todo_html = ""
            return

        # Count stats for header
        completed = sum(1 for t in todos if t.get("status") == "completed")
        total = len(todos)

        lines = [self._t('plan.header', completed=completed, total=total)]

        for todo in todos:
            status = todo.get("status", "pending")
            # Use activeForm for in_progress, content for others
            if status == "in_progress":
                text = todo.get("activeForm", todo.get("content", ""))
            else:
                text = todo.get("content", "")

            if status == "completed":
                lines.append(f"  ✅ <s>{text}</s>")
            elif status == "in_progress":
                lines.append(f"  ⏳ <b>{text}</b>")
            else:  # pending
                lines.append(f"  ⬜ {text}")

        html_text = "\n".join(lines)  # Vertical layout - each task on new line

        # Skip if content unchanged
        if self._last_todo_html == html_text:
            return
        self._last_todo_html = html_text
        self._current_todo_html = html_text

        # Trigger an update to show the new todo status
        await self._do_update()

    async def show_plan_mode_enter(self) -> None:
        """Show that Claude entered plan mode.

        ВАЖНО: Обновления проходят через координатор!

        Displays a visual indicator that Claude is analyzing
        the task and creating a plan before execution.
        """
        self._is_plan_mode = True

        html_text = (
            f"{self._t('plan.mode_title')}\n\n"
            f"{self._t('plan.mode_desc')}"
        )

        try:
            if self._plan_mode_message:
                if self._coordinator:
                    await self._coordinator.update(
                        self._plan_mode_message,
                        html_text,
                        parse_mode="HTML"
                    )
                else:
                    try:
                        await self._plan_mode_message.edit_text(html_text, parse_mode="HTML")
                    except TelegramBadRequest as e:
                        if "message is not modified" not in str(e).lower():
                            logger.warning(f"Error updating plan mode message: {e}")
            else:
                if self._coordinator:
                    self._plan_mode_message = await self._coordinator.send_new(
                        self.chat_id,
                        html_text,
                        parse_mode="HTML"
                    )
                else:
                    self._plan_mode_message = await self.bot.send_message(
                        self.chat_id,
                        html_text,
                        parse_mode="HTML"
                    )
                if self._plan_mode_message:
                    logger.info(f"Created plan mode message: {self._plan_mode_message.message_id}")
        except Exception as e:
            logger.error(f"Error in show_plan_mode_enter: {e}")

    async def show_plan_mode_exit(self, plan_approved: bool = False) -> None:
        """Show that Claude exited plan mode.

        ВАЖНО: Обновления проходят через координатор!

        Args:
            plan_approved: Whether the plan was approved (True) or just ready (False)
        """
        self._is_plan_mode = False

        if plan_approved:
            html_text = self._t('plan.approved')
        else:
            html_text = self._t('plan.ready_approval')

        try:
            if self._plan_mode_message:
                if self._coordinator:
                    await self._coordinator.update(
                        self._plan_mode_message,
                        html_text,
                        parse_mode="HTML",
                        is_final=True
                    )
                else:
                    try:
                        await self._plan_mode_message.edit_text(html_text, parse_mode="HTML")
                    except TelegramBadRequest as e:
                        if "message is not modified" not in str(e).lower():
                            logger.warning(f"Error updating planmode exit: {e}")
                self._plan_mode_message = None
            else:
                if self._coordinator:
                    await self._coordinator.send_new(
                        self.chat_id,
                        html_text,
                        parse_mode="HTML"
                    )
                else:
                    await self.bot.send_message(
                        self.chat_id,
                        html_text,
                        parse_mode="HTML"
                    )
        except Exception as e:
            logger.error(f"Error in show_plan_mode_exit: {e}")

    async def show_question(
        self,
        question_id: str,
        questions: list[dict],
        keyboard: Optional[InlineKeyboardMarkup] = None
    ) -> Optional[Message]:
        """Show Claude's question with option buttons.

        Displays AskUserQuestion from Claude with inline keyboard
        for selecting answers.

        Args:
            question_id: Unique ID for callback matching
            questions: List of question dicts with question, header, options
            keyboard: Pre-built keyboard (optional, will be built if not provided)

        Returns:
            Sent message for later reference
        """
        if not questions:
            return None

        # Build message text
        lines = [f"{self._t('question.header')}\n"]

        for q in questions:
            header = q.get("header", "")
            question = q.get("question", "")

            if header:
                lines.append(f"<b>{header}</b>")
            lines.append(question)

            # Show option descriptions if available
            options = q.get("options", [])
            for opt in options:
                desc = opt.get("description", "")
                if desc:
                    label = opt.get("label", "")
                    lines.append(f"  • <b>{label}</b>: {desc}")

            lines.append("")  # Empty line between questions

        html_text = "\n".join(lines)

        # Build keyboard if not provided
        if keyboard is None:
            from presentation.keyboards.keyboards import Keyboards
            keyboard = Keyboards.question_options(questions, question_id)

        try:
            # Вопросы важны - используем координатор для надёжной доставки
            if self._coordinator:
                msg = await self._coordinator.send_new(
                    self.chat_id,
                    html_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            else:
                msg = await self.bot.send_message(
                    self.chat_id,
                    html_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            return msg
        except Exception as e:
            logger.error(f"Error showing question: {e}")
            return None

    async def _schedule_update(self):
        """Deprecated - просто вызывает _do_update().

        Вся логика rate limiting теперь в координаторе.
        """
        await self._do_update()

    async def _do_update(self, _retry_count: int = 0):
        """Actually perform the update to Telegram.

        ВАЖНО: Все обновления теперь проходят через координатор!
        Координатор гарантирует интервал 2 секунды между обновлениями.
        """
        # Обновляем если есть буфер ИЛИ статус (heartbeat)
        if (not self.buffer and not self._status_line) or self.is_finalized:
            logger.debug(f"Streaming: _do_update skipped (buffer={bool(self.buffer)}, status={bool(self._status_line)}, finalized={self.is_finalized})")
            return

        display_text = self._get_display_buffer()
        logger.info(f"Streaming: _do_update called, display_text={len(display_text)} chars")

        try:
            # Sync buffer to UI state to get accurate rendered length
            if display_text:
                self.ui.sync_from_buffer(display_text)

            # Check if we need to split into multiple messages
            # ВАЖНО: проверяем отрендеренный HTML, не raw buffer!
            rendered_html = self.ui.render_non_content()
            status = self._get_status_line()
            if status:
                rendered_html = f"{rendered_html}\n\n{status}" if rendered_html else status

            # Check for overflow with dynamic threshold for new continuation messages
            # If we just created a continuation, allow it to grow larger before splitting
            # This prevents creating nearly-empty "Part N" messages
            threshold = self.MAX_MESSAGE_LENGTH
            if self._just_created_continuation:
                # Allow 50% more space for the first chunk in a continuation message
                threshold = int(self.MAX_MESSAGE_LENGTH * 1.5)
                logger.debug(f"Streaming: using relaxed threshold {threshold} for new continuation message")

            is_overflow = len(rendered_html) > self.MAX_MESSAGE_LENGTH  # Still check against actual limit
            should_split = len(rendered_html) > threshold

            if should_split:
                logger.info(f"Streaming: overflow detected ({len(rendered_html)} chars > threshold {threshold}), handling...")
                await self._handle_overflow()
                self._just_created_continuation = False  # Clear flag after overflow
            else:
                # Clear the flag after first successful update
                if self._just_created_continuation:
                    self._just_created_continuation = False
                logger.debug(f"Streaming: editing message via coordinator...")
                await self._edit_current_message(display_text)

            self.last_update_time = time.time()
            logger.debug(f"Streaming: update completed")

        except Exception as e:
            # Координатор обрабатывает rate limits внутри
            logger.error(f"Error updating message: {e}")

    async def _edit_current_message(self, text: str, is_final: bool = False):
        """Edit the current message with valid HTML only.

        ВАЖНО: Все обновления проходят через MessageUpdateCoordinator!
        Координатор гарантирует минимум 2 секунды между обновлениями.

        Uses StreamingUIState.render_non_content() for interleaved content+tools.
        """
        if not self.current_message:
            logger.debug("_edit_current_message: no current_message, skipping")
            return

        # Get status line (already HTML formatted)
        status = self._get_status_line()

        # Sync buffer to UI state for interleaved rendering
        # UI state handles content + tools in correct order
        # IMPORTANT: Use sync_from_buffer to only get NEW content (after flushed parts)
        if text:
            self.ui.sync_from_buffer(text)

        # If finalizing, flush the buffer
        if is_final:
            self.ui.finalize()

        # Render everything through UI state (content + tools interleaved)
        html_text = self.ui.render_non_content()

        # Логируем для отладки
        logger.debug(
            f"_edit_current_message: text={len(text)}ch, html={len(html_text)}ch, "
            f"is_final={is_final}"
        )

        # If still nothing but we need to update status, that's ok
        if not html_text and not status:
            logger.debug("_edit_current_message: no html_text and no status, skipping")
            return

        # Add todo plan and status line at the bottom
        # Order: content → plan → empty line → status with timer
        footer_parts = []
        if self._current_todo_html:
            footer_parts.append(self._current_todo_html)
        if status:
            # Add extra empty line before status to separate from plan
            if footer_parts:
                footer_parts.append("")  # Empty line gap
            footer_parts.append(status)

        if footer_parts:
            footer = "\n".join(footer_parts)
            if html_text:
                html_text = f"{html_text}\n\n{footer}"
            else:
                html_text = footer

        if not html_text:
            return

        # КРИТИЧЕСКОЕ ЛОГИРОВАНИЕ - что отправляем в координатор
        logger.info(
            f"_edit_current_message -> coordinator: {len(html_text)}ch, "
            f"msg_id={self.current_message.message_id}"
        )

        # === ИСПОЛЬЗОВАТЬ КООРДИНАТОР ===
        if self._coordinator:
            await self._coordinator.update(
                self.current_message,
                html_text,
                parse_mode="HTML",
                reply_markup=self.reply_markup,
                is_final=is_final
            )
        else:
            # Fallback: прямой вызов (не рекомендуется)
            logger.warning("Streaming: coordinator not available, using direct edit")
            try:
                await self.current_message.edit_text(
                    html_text,
                    parse_mode="HTML",
                    reply_markup=self.reply_markup
                )
            except TelegramBadRequest as e:
                if "message is not modified" in str(e):
                    pass  # Same content, ignore
                else:
                    # Fallback - strip all HTML and send plain
                    plain_text = re.sub(r'<[^>]+>', '', html_text)
                    try:
                        await self.current_message.edit_text(
                            plain_text, parse_mode=None, reply_markup=self.reply_markup
                        )
                    except Exception:
                        pass  # Give up on this update

    async def _send_new_message(self, text: str, is_final: bool = False) -> Message:
        """Send a new message (converts Markdown to HTML)"""
        # Reset formatter for new message
        self._formatter.reset()

        # Convert Markdown to HTML with streaming support
        html_text = markdown_to_html(text, is_streaming=not is_final)
        # Prepare for Telegram - close unclosed tags, add cursor if not final
        html_text = prepare_html_for_telegram(html_text, is_final=is_final)
        try:
            msg = await self.bot.send_message(
                self.chat_id,
                html_text,
                parse_mode="HTML",
                reply_markup=self.reply_markup
            )
        except TelegramBadRequest:
            # Fallback without formatting
            msg = await self.bot.send_message(
                self.chat_id, text, parse_mode=None, reply_markup=self.reply_markup
            )

        self.messages.append(msg)
        self.current_message = msg
        return msg

    async def _handle_overflow(self, is_final: bool = False):
        """
        Handle buffer overflow by creating a new message instead of trimming.

        Multi-message streaming approach:
        - Finalize current message (remove buttons/status)
        - Create new message with continuation indicator
        - Continue streaming in the new message
        - Full history is preserved across messages
        """
        if is_final:
            # На финальном этапе просто обрезаем если нужно
            await self._handle_overflow_trim(is_final=True)
            return

        # Получаем размер отрендеренного HTML для логирования
        rendered_html = self.ui.render_non_content()
        logger.info(f"Buffer overflow (rendered={len(rendered_html)} chars), creating new message")

        # 1. Финализировать текущее сообщение (без статуса, без кнопок)
        old_status = self._status_line
        old_markup = self.reply_markup
        self._status_line = ""  # Убираем статус из старого сообщения
        self.reply_markup = None  # Убираем кнопки из старого сообщения

        # Финализируем UI state для старого сообщения
        self.ui.finalize()

        # Обрезаем если нужно, чтобы вписаться в лимит Telegram
        final_html = self.ui.render_non_content()
        if len(final_html) > self.MAX_MESSAGE_LENGTH:
            # Обрезаем до лимита с индикатором продолжения
            truncate_indicator = self._t('streaming.continuation')
            max_content = self.MAX_MESSAGE_LENGTH - len(truncate_indicator) - 100
            final_html = final_html[:max_content] + truncate_indicator
            logger.info(f"Truncated overflow message to {len(final_html)} chars")

        # Редактируем текущее сообщение напрямую (без повторного render)
        if self.current_message and self._coordinator:
            await self._coordinator.update(
                self.current_message,
                final_html,
                parse_mode="HTML",
                reply_markup=None,  # Убираем кнопки
                is_final=True
            )

        # 2. Восстанавливаем статус и кнопки для нового сообщения
        self._status_line = old_status
        self.reply_markup = old_markup

        # 3. Увеличиваем счётчик сообщений
        self._message_index += 1

        # 4. Сбрасываем форматтер и UI state для нового сообщения
        self._formatter.reset()
        self.ui.reset()  # КРИТИЧНО: сбросить UI state для нового сообщения!

        # 5. Создаём новый буфер с индикатором продолжения
        continuation_header = f"📨 <b>Часть {self._message_index}</b>\n\n"

        # 6. ФИКС: НЕ переносим старый контент - начинаем с чистого листа!
        #
        # Проблема была: старый код пытался перенести "хвост" в новое сообщение,
        # но это приводило к тому что:
        # - Часть 2 создавалась почти пустой (только header + маленький хвост)
        # - Новый контент сразу переполнял и создавалась Часть 3
        #
        # Решение: каждая часть начинается с чистого листа.
        # Весь контент старого сообщения уже сохранён в нём.
        # Новый контент будет добавляться в новое сообщение.

        self.buffer = continuation_header

        # 7. Устанавливаем флаг, чтобы предотвратить немедленный overflow
        # Если следующий chunk большой, дадим ему место в новом сообщении
        self._just_created_continuation = True

        logger.info(f"Created clean continuation message #{self._message_index}")

        # 7. Создаём новое сообщение
        self.current_message = await self._send_new_message(self.buffer)
        self.last_update_time = time.time()

    async def _handle_overflow_trim(self, is_final: bool = False):
        """Legacy trimming for final messages - keep only newest content."""
        # Extract header (first lines with emoji status)
        lines = self.buffer.split("\n")
        header_lines = []
        content_start = 0

        # Keep header lines (status and project info)
        for i, line in enumerate(lines):
            if line.startswith("🤖") or line.startswith("📂") or line.startswith("📁") or line.startswith("📨"):
                header_lines.append(line)
                content_start = i + 1
            elif header_lines:  # Stop after first non-header line
                break

        header = "\n".join(header_lines)
        content = "\n".join(lines[content_start:])

        # Target size - leave room for new content
        target_size = self.MAX_MESSAGE_LENGTH - 500

        # Remove oldest content blocks until we fit
        trimmed = False
        while len(header) + len(content) + 50 > target_size and content:
            trimmed = True
            # Find first block separator (double newline or tool result end)
            block_end = content.find("\n\n")
            if block_end > 0 and block_end < len(content)- 100:
                content = content[block_end + 2:]
            else:
                # Fallback: remove first 300 chars
                content = content[300:]

        # Build new buffer with trim indicator
        if trimmed:
            trim_indicator = "\n*(...)*\n"
            self.buffer = header + trim_indicator + content.lstrip("\n")
        else:
            self.buffer = header + "\n" + content if header else content

        # CRITICAL: Reset formatter when buffer is trimmed!
        if trimmed:
            self._formatter.reset()
            logger.debug(f"Buffer trimmed to {len(self.buffer)} chars, formatter reset")

        # Update message with trimmed content
        await self._edit_current_message(self.buffer, is_final=is_final)

    async def finalize(self, final_text: Optional[str] = None):
        """Finalize the stream with optional final text"""
        self.is_finalized = True

        # Cancel any pending updates
        if self._pending_update and not self._pending_update.done():
            self._pending_update.cancel()

        # Clear status line, todo plan, and cancel button
        self._status_line = ""
        self._current_todo_html = ""
        self.reply_markup = None

        if final_text:
            self.buffer = final_text

        # Force final update (without status, without cancel button, without cursor)
        if self.buffer:
            try:
                if len(self.buffer) > self.MAX_MESSAGE_LENGTH:
                    await self._handle_overflow(is_final=True)
                else:
                    await self._edit_current_message(self.buffer, is_final=True)
            except Exception as e:
                logger.error(f"Error finalizing: {e}")

    async def send_error(self, error: str):
        """Send an error message"""
        error_title = self._t("error.title")
        error_text = f"{error_title}\n```\n{error[:1000]}\n```"
        await self.append(f"\n\n{error_text}")
        await self.finalize()

    def set_completion_info(self, info: str):
        """Set completion info (cost, tokens) - rendered at the BOTTOM after tools"""
        self.ui.set_completion_info(info)

    async def send_completion(self, success: bool = True):
        """Send a completion indicator - rendered at the BOTTOM after tools"""
        if success:
            self.ui.set_completion_status(self._t("status.done_html"))
        else:
            self.ui.set_completion_status(self._t("status.completed_with_issues"))
        await self.finalize()

    async def move_to_bottom(self, header: str = ""):
        """
        Create a new message at the bottom for continued streaming.

        Call this after sending other messages (like permission requests)
        to ensure the streaming output stays at the bottom of the chat.
        """
        # Finalize current message without the completion marker
        if self.current_message and self.buffer:
            try:
                await self._edit_current_message(self.buffer)
            except Exception as e:
                logger.debug(f"Could not finalize old message: {e}")

        # Reset state for new message
        self.current_message = None
        continuing_text = self._t("status.continuing")
        self.buffer = header or f"{continuing_text}\n\n"
        self.is_finalized = False

        # Send new message at bottom
        self.current_message = await self._send_new_message(self.buffer)
        self.last_update_time = time.time()
        return self.current_message
