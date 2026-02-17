"""AI request handler - SDK/CLI integration"""

import logging
import asyncio
import html
import os
import re
import uuid
from typing import TYPE_CHECKING, Optional

from aiogram.types import Message
from aiogram import Bot

from presentation.handlers.streaming import StreamingHandler, HeartbeatTracker, StepStreamingHandler
from presentation.keyboards.keyboards import Keyboards
from shared.i18n import get_translator
from .base import BaseMessageHandler

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from application.services.project_service import ProjectService
    from application.services.context_service import ContextService
    from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService, TaskResult
    from infrastructure.claude_code.sdk_service import ClaudeAgentSDKService, SDKTaskResult
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.variable_manager import VariableInputManager
    from presentation.handlers.state.plan_manager import PlanApprovalManager
    from presentation.handlers.state.file_context import FileContextManager
    from domain.entities.claude_code_session import ClaudeCodeSession

logger = logging.getLogger(__name__)


class AIRequestHandler(BaseMessageHandler):
    """Handles AI request processing with SDK/CLI integration"""

    def __init__(
        self,
        bot_service: "BotService",
        user_state: "UserStateManager",
        hitl_manager: "HITLManager",
        file_context_manager: "FileContextManager",
        variable_manager: "VariableInputManager",
        plan_manager: "PlanApprovalManager",
        sdk_service: Optional["ClaudeAgentSDKService"] = None,
        claude_proxy: Optional["ClaudeCodeProxyService"] = None,
        project_service=None,
        context_service=None,
        default_working_dir: str = "/root",
    ):
        super().__init__(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )
        self.sdk_service = sdk_service
        self.claude_proxy = claude_proxy
        self.project_service = project_service
        self.context_service = context_service
        self.default_working_dir = default_working_dir
        self._step_handlers = {}

    async def _get_translator(self, user_id: int):
        """Get translator for user based on their language preference."""
        lang = "en"  # default
        if self.bot_service and hasattr(self.bot_service, 'account_service'):
            try:
                lang = await self.bot_service.account_service.get_user_language(user_id)
            except Exception:
                pass
        return get_translator(lang)

    # Copied from legacy messages.py:280-287
    def _is_task_running(self, user_id: int) -> bool:
        """Check if a task is already running for user"""
        is_running = False
        # Check SDK backend
        if self.sdk_service:
            try:
                # Try to check if SDK service has this method
                if hasattr(self.sdk_service, 'is_task_running'):
                    is_running = self.sdk_service.is_task_running(user_id)
            except Exception as e:
                logger.warning(f"Error checking SDK task status: {e}")

        # Check CLI backend
        if not is_running and self.claude_proxy:
            try:
                is_running = self.claude_proxy.is_task_running(user_id)
            except Exception as e:
                logger.warning(f"Error checking CLI task status: {e}")

        return is_running

    # Copied from legacy messages.py:291-327
    def _detect_cd_command(self, command: str, current_dir: str) -> Optional[str]:
        """
        Detect if a bash command changes directory and return the new path.

        Handles patterns like:
        - cd /path/to/dir (Linux)
        - cd C:\\path\\to\\dir (Windows)
        - cd D: (Windows drive change)
        - cd /d D:\\path (Windows with /d flag)
        - cd subdir
        - mkdir -p dir && cd dir
        - cd ~
        - cd ..
        """
        # Handle Windows "cd /d <drive>:<path>" pattern
        cd_d_pattern = r'(?:^|&&|;)\s*cd\s+/d\s+([A-Za-z]:[^\s;&|]*)'
        match = re.search(cd_d_pattern, command)
        if match:
            return match.group(1)

        # Standard cd patterns
        cd_patterns = [
            r'(?:^|&&|;)\s*cd\s+([^\s;&|]+)',
            r'(?:^|&&|;)\s*cd\s+"([^"]+)"',
            r"(?:^|&&|;)\s*cd\s+'([^']+)'",
        ]

        new_dir = None
        for pattern in cd_patterns:
            matches = re.findall(pattern, command)
            if matches:
                new_dir = matches[-1]
                break

        if not new_dir:
            return None

        # Windows absolute path (C:\ or D:\)
        if len(new_dir) >= 2 and new_dir[1] == ':':
            return new_dir

        # Windows forward-slash path (C:/ or D:/)
        if len(new_dir) >= 2 and new_dir[0].isalpha() and new_dir[1] == '/':
            return new_dir.replace('/', '\\')

        # Linux absolute path
        if new_dir.startswith('/'):
            return new_dir
        elif new_dir == '~':
            # Windows: use USERPROFILE, Linux: use /root
            return os.path.expanduser('~')
        elif new_dir == '-':
            return None
        elif new_dir == '..':
            return os.path.dirname(current_dir)
        else:
            return os.path.join(current_dir, new_dir)

    # Copied from legacy messages.py:873-893
    async def _on_text(self, user_id: int, text: str):
        """Handle streaming text output.

        ВАЖНО: TextBlock от Claude — это ОСНОВНОЙ ответ (content), не thinking!
        ThinkingBlock — это отдельный тип, который приходит в on_thinking.

        Step streaming mode: текст идёт в buffer через append(),
        а UI state синхронизируется при добавлении tools через sync_from_buffer().
        """
        streaming = self.user_state.get_streaming_handler(user_id)

        if streaming:
            # Текст ВСЕГДА идёт в основной буфер — это ответ Claude!
            # Step streaming и обычный режим используют одинаковую логику
            await streaming.append(text)

        # Update heartbeat to show Claude is thinking/writing
        heartbeat = self.user_state.get_heartbeat(user_id)
        if heartbeat:
            heartbeat.set_action("thinking")

    # Copied from legacy messages.py:894-995
    async def _on_tool_use(self, user_id: int, tool_name: str, tool_input: dict, message: Message):
        """Handle tool use notification"""
        streaming = self.user_state.get_streaming_handler(user_id)
        heartbeat = self.user_state.get_heartbeat(user_id)

        # Update heartbeat with current action
        if heartbeat:
            tool_lower = tool_name.lower()
            action_map = {
                "read": "reading",
                "glob": "searching",
                "grep": "searching",
                "ls": "searching",
                "write": "writing",
                "edit": "editing",
                "notebookedit": "editing",
                "bash": "executing",
                "task": "thinking",
                "webfetch": "reading",
                "websearch": "searching",
                "todowrite": "planning",
                "enterplanmode": "planning",
                "exitplanmode": "planning",
                "askuserquestion": "waiting",
            }
            action = action_map.get(tool_lower, "thinking")

            # Get detail (filename, command, pattern)
            detail = ""
            if tool_lower in ("read", "write", "edit", "notebookedit"):
                detail = tool_input.get("file_path", "")
                if detail:
                    detail = detail.split("/")[-1]  # Just filename
            elif tool_lower == "bash":
                cmd = tool_input.get("command", "")
                detail = cmd[:30] if cmd else ""
            elif tool_lower in ("glob", "grep"):
                detail = tool_input.get("pattern", "")[:30]

            heartbeat.set_action(action, detail)

        # Track file changes for end-of-session summary
        if streaming and tool_name.lower() in ("edit", "write", "bash"):
            streaming.track_file_change(tool_name, tool_input)

        # Detect cd command and update working directory
        if tool_lower == "bash":
            cmd = tool_input.get("command", "")
            if cmd:
                current_dir = self.user_state.get_working_dir(user_id)
                new_dir = self._detect_cd_command(cmd, current_dir)
                if new_dir:
                    self.user_state.set_working_dir(user_id, new_dir)
                    logger.info(f"[{user_id}] Working directory changed to: {new_dir}")

        # Step streaming mode: show brief tool notifications
        if self.user_state.is_step_streaming_mode(user_id):
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                await step_handler.on_tool_start(tool_name, tool_input)
            # Still show todo lists and plan mode in step streaming
            if streaming:
                if tool_name.lower() == "todowrite":
                    todos = tool_input.get("todos", [])
                    if todos:
                        await streaming.show_todo_list(todos)
                elif tool_name.lower() == "enterplanmode":
                    await streaming.show_plan_mode_enter()
                elif tool_name.lower() == "exitplanmode":
                    await streaming.show_plan_mode_exit()
            return

        if streaming:
            if tool_name.lower() == "todowrite":
                todos = tool_input.get("todos", [])
                if todos:
                    await streaming.show_todo_list(todos)
                return

            if tool_name.lower() == "enterplanmode":
                await streaming.show_plan_mode_enter()
                return

            if tool_name.lower() == "exitplanmode":
                await streaming.show_plan_mode_exit()
                return

            details = ""
            if tool_name.lower() == "bash":
                details = tool_input.get("command", "")[:100]
            elif tool_name.lower() in ["read", "write", "edit"]:
                details = tool_input.get("file_path", tool_input.get("path", ""))[:100]
            elif tool_name.lower() == "glob":
                details = tool_input.get("pattern", "")[:100]
            elif tool_name.lower() == "grep":
                details = tool_input.get("pattern", "")[:100]

            await streaming.show_tool_use(tool_name, details)

    # Copied from legacy messages.py:996-1020
    async def _on_tool_result(self, user_id: int, tool_id: str, output: str):
        """Handle tool result"""
        streaming = self.user_state.get_streaming_handler(user_id)

        # Step streaming mode: show brief completion status
        if self.user_state.is_step_streaming_mode(user_id):
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                # Get current tool name from step handler
                tool_name = step_handler.get_current_tool()
                await step_handler.on_tool_complete(tool_name, success=True)
            # Reset heartbeat
            heartbeat = self.user_state.get_heartbeat(user_id)
            if heartbeat:
                heartbeat.set_action("analyzing")
            return

        if streaming and output:
            await streaming.show_tool_result(output, success=True)

        # Reset heartbeat to "thinking" after tool completes
        heartbeat = self.user_state.get_heartbeat(user_id)
        if heartbeat:
            heartbeat.set_action("analyzing")

    # Copied from legacy messages.py:1021-1066
    async def _on_permission(self, user_id: int, tool_name: str, details: str, message: Message) -> bool:
        """Handle permission request (CLI mode)"""
        # Check YOLO mode from user_state
        if self.user_state.is_yolo_mode(user_id):
            streaming = self.user_state.get_streaming_handler(user_id)
            # In step streaming mode don't show "Auto-approved" - step handler already shows operations
            if streaming and not self.user_state.is_step_streaming_mode(user_id):
                truncated = details[:100] + "..." if len(details) > 100 else details
                t = await self._get_translator(user_id)
                await streaming.append(f"\n**{t('hitl.auto_approved')}:** `{tool_name}`\n```\n{truncated}\n```\n")
            return True

        session = self.user_state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        t = await self._get_translator(user_id)
        text = f"<b>{t('claude.permission_title')}</b>\n\n"
        text += f"<b>{t('claude.tool_label')}:</b> <code>{html.escape(tool_name)}</code>\n"
        if details:
            display_details = details if len(details) < 500 else details[:500] + "..."
            # Escape HTML entities to prevent parse errors (e.g., <<'EOF' -> &lt;&lt;'EOF')
            text += f"<b>{t('claude.details')}:</b>\n<pre>{html.escape(display_details)}</pre>"

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.claude_permission(user_id, tool_name, request_id)
        )

        event = self.hitl_manager.get_permission_event(user_id)
        if event:
            event.clear()
            try:
                from presentation.handlers.state.hitl_manager import PERMISSION_TIMEOUT_SECONDS
                await asyncio.wait_for(event.wait(), timeout=PERMISSION_TIMEOUT_SECONDS)
                approved = self.hitl_manager.get_permission_response(user_id)
            except asyncio.TimeoutError:
                t = await self._get_translator(user_id)
                await message.answer(t('claude.timeout_rejected'))
                approved = False

            if session:
                session.resume_running()

            return approved

        return False

    # Copied from legacy messages.py:1068-1107
    async def _on_question(self, user_id: int, question: str, options: list[str], message: Message) -> str:
        """Handle question (CLI mode)"""
        session = self.user_state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_answer(request_id, question, options)

        self.hitl_manager.set_question_context(user_id, request_id, question, options)

        t = await self._get_translator(user_id)
        text = f"<b>{t('claude.question_title')}</b>\n\n{html.escape(question)}"

        if options:
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
        else:
            self.hitl_manager.set_expecting_answer(user_id, True)
            await message.answer(f"<b>{t('claude.question_title')}</b>\n\n{html.escape(question)}\n\n{t('claude.enter_answer')}:", parse_mode="HTML")

        event = self.hitl_manager.get_question_event(user_id)
        if event:
            event.clear()
            try:
                from presentation.handlers.state.hitl_manager import QUESTION_TIMEOUT_SECONDS
                await asyncio.wait_for(event.wait(), timeout=QUESTION_TIMEOUT_SECONDS)
                answer = self.hitl_manager.get_question_response(user_id)
            except asyncio.TimeoutError:
                t = await self._get_translator(user_id)
                await message.answer(t('claude.question_timeout'))
                answer = ""

            if session:
                session.resume_running()

            self.hitl_manager.clear_question_state(user_id)
            return answer

        return ""

    # Copied from legacy messages.py:1109-1118
    async def _on_error(self, user_id: int, error: str):
        """Handle error from Claude Code"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            await streaming.send_error(error)

        session = self.user_state.get_claude_session(user_id)
        if session:
            session.fail(error)

    # Copied from legacy messages.py:1119-1138
    async def _on_thinking(self, user_id: int, thinking: str):
        """Handle thinking output.

        ThinkingBlock — это внутренние рассуждения Claude (extended thinking).
        В step streaming mode показываем в сворачиваемом блоке.
        """
        streaming = self.user_state.get_streaming_handler(user_id)
        if not streaming or not thinking:
            return

        # Step streaming mode: показываем thinking в сворачиваемом блоке
        if self.user_state.is_step_streaming_mode(user_id):
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                await step_handler.on_thinking(thinking)
        else:
            # Обычный режим - показываем как курсив
            preview = thinking[:200] + "..." if len(thinking) > 200 else thinking
            await streaming.append(f"\n*{preview}*\n")

    # Copied from legacy messages.py:1139-1169
    async def _on_permission_sdk(
        self,
        user_id: int,
        tool_name: str,
        details: str,
        tool_input: dict,
        message: Message
    ):
        """Handle permission request from SDK"""
        # В step streaming mode показываем ожидание разрешения в основном сообщении
        if self.user_state.is_step_streaming_mode(user_id):
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                await step_handler.on_permission_request(tool_name, tool_input)

        if self.user_state.is_yolo_mode(user_id):
            streaming = self.user_state.get_streaming_handler(user_id)
            # In step streaming mode don't show "Auto-approved" - step handler already shows operations
            if streaming and not self.user_state.is_step_streaming_mode(user_id):
                truncated = details[:100] + "..." if len(details) > 100 else details
                t = await self._get_translator(user_id)
                await streaming.append(f"\n**{t('hitl.auto_approved')}:** `{tool_name}`\n```\n{truncated}\n```\n")

            # In step streaming mode update status "Waiting" -> "Executing"
            if self.user_state.is_step_streaming_mode(user_id):
                step_handler = self._get_step_handler(user_id)
                if step_handler:
                    await step_handler.on_permission_granted(tool_name)

            if self.sdk_service:
                # Retry mechanism for YOLO mode to ensure permission is granted
                # SDK may need a small delay to set up the permission event
                for attempt in range(3):
                    success = await self.sdk_service.respond_to_permission(user_id, True)
                    if success:
                        logger.debug(f"[{user_id}] YOLO mode: permission auto-approved on attempt {attempt + 1}")
                        break
                    logger.debug(f"[{user_id}] YOLO mode: permission attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(0.1 * (attempt + 1))  # 0.1s, 0.2s, 0.3s
                else:
                    logger.warning(f"[{user_id}] YOLO mode: failed to auto-approve after 3 attempts")
            return

        session = self.user_state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        t = await self._get_translator(user_id)
        text = f"<b>{t('claude.permission_title')}</b>\n\n"
        text += f"<b>{t('claude.tool_label')}:</b> <code>{html.escape(tool_name)}</code>\n"
        if details:
            display_details = details if len(details) < 500 else details[:500] + "..."
            # Escape HTML entities to prevent parse errors (e.g., <<'EOF' -> &lt;&lt;'EOF')
            text += f"<b>{t('claude.details')}:</b>\n<pre>{html.escape(display_details)}</pre>"

        perm_msg = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.claude_permission(user_id, tool_name, request_id)
        )
        self.hitl_manager.set_permission_context(user_id, request_id, tool_name, details, perm_msg)

    # Copied from legacy messages.py:1191-1220
    async def _on_question_sdk(
        self,
        user_id: int,
        question: str,
        options: list[str],
        message: Message
    ):
        """Handle question from SDK"""
        session = self.user_state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_answer(request_id, question, options)

        self.hitl_manager.set_question_context(user_id, request_id, question, options)

        t = await self._get_translator(user_id)
        text = f"<b>{t('claude.question_title')}</b>\n\n{html.escape(question)}"

        if options:
            q_msg = await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
            self.hitl_manager.set_question_context(user_id, request_id, question, options, q_msg)
        else:
            self.hitl_manager.set_expecting_answer(user_id, True)
            q_msg = await message.answer(f"<b>{t('claude.question_title')}</b>\n\n{html.escape(question)}\n\n{t('claude.enter_answer')}:", parse_mode="HTML")
            self.hitl_manager.set_question_context(user_id, request_id, question, options, q_msg)

    # Copied from legacy messages.py:1221-1268
    async def _on_plan_request(
        self,
        user_id: int,
        plan_file: str,
        tool_input: dict,
        message: Message
    ):
        """
        Handle plan approval request from SDK (ExitPlanMode).

        NOTE: Plan approval is ALWAYS shown with inline keyboard, even in YOLO mode.
        Plans should always be reviewed by user before execution - this is intentional.
        """
        logger.info(f"[{user_id}] _on_plan_request called: plan_file={plan_file}")
        request_id = str(uuid.uuid4())[:8]

        plan_content = ""
        if plan_file:
            try:
                working_dir = self.user_state.get_working_dir(user_id)
                plan_path = os.path.join(working_dir, plan_file)

                if os.path.exists(plan_path):
                    with open(plan_path, 'r', encoding='utf-8') as f:
                        plan_content = f.read()
            except Exception as e:
                logger.error(f"[{user_id}] Error reading plan file: {e}")

        if not plan_content:
            plan_content = tool_input.get("planContent", "")

        if plan_content:
            if len(plan_content) > 3500:
                plan_content = plan_content[:3500] + "\n\n... (план сокращён)"
            # Escape HTML entities in plan content to prevent parse errors
            escaped_content = html.escape(plan_content)
            text = f"<b>📋 План готов к выполнению</b>\n\n<pre>{escaped_content}</pre>"
        else:
            text = "<b>📋 План готов к выполнению</b>\n\n<i>Содержимое плана недоступно</i>"

        plan_msg = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.plan_approval(user_id, request_id)
        )

        self.plan_manager.set_context(user_id, request_id, plan_file, plan_content, plan_msg)
        logger.info(f"[{user_id}] Plan approval requested, file: {plan_file}")

    # Copied from legacy messages.py:1270-1301
    async def _on_permission_completed(self, user_id: int, approved: bool):
        """Handle permission completion - edit message and continue streaming"""
        perm_msg = self.hitl_manager.get_permission_message(user_id)
        streaming = self.user_state.get_streaming_handler(user_id)

        # В step streaming mode обновляем строку ожидания
        if self.user_state.is_step_streaming_mode(user_id) and approved:
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                # Получаем имя инструмента из HITL контекста
                tool_name = self.hitl_manager.get_pending_tool_name(user_id) or "tool"
                await step_handler.on_permission_granted(tool_name)

        if perm_msg:
            # В step streaming mode удаляем сообщение о разрешении - информация уже в основном сообщении
            if self.user_state.is_step_streaming_mode(user_id):
                try:
                    await perm_msg.delete()
                except Exception as e:
                    logger.debug(f"Could not delete permission message: {e}")
            elif streaming:
                # Normal mode - edit message
                t = await self._get_translator(user_id)
                status = t("hitl.approved") if approved else t("hitl.rejected")
                try:
                    await perm_msg.edit_text(status, parse_mode=None)
                    streaming.current_message = perm_msg
                    streaming.buffer = f"{status}\n\n{t('claude.continuing')}...\n"
                    streaming.is_finalized = False
                except Exception as e:
                    logger.debug(f"Could not edit permission message: {e}")

        self.hitl_manager.clear_permission_state(user_id)

    # Copied from legacy messages.py:1303-1318
    async def _on_question_completed(self, user_id: int, answer: str):
        """Handle question completion"""
        q_msg = self.hitl_manager.get_question_message(user_id)
        streaming = self.user_state.get_streaming_handler(user_id)

        if q_msg and streaming:
            short_answer = answer[:50] + "..." if len(answer) > 50 else answer
            try:
                t = await self._get_translator(user_id)
                await q_msg.edit_text(f"{t('hitl.answer')}: {short_answer}\n\n{t('claude.continuing')}...", parse_mode=None)
                streaming.current_message = q_msg
                streaming.buffer = f"{t('hitl.answer')}: {short_answer}\n\n{t('claude.continuing')}...\n"
                streaming.is_finalized = False
            except Exception as e:
                logger.debug(f"Could not edit question message: {e}")

        self.hitl_manager.clear_question_state(user_id)

    # Copied from legacy messages.py:1320-1390
    async def _handle_result(self, user_id: int, result: "TaskResult", message: Message):
        """Handle task completion"""
        session = self.user_state.get_claude_session(user_id)
        streaming = self.user_state.get_streaming_handler(user_id)

        if result.cancelled:
            if streaming:
                t = await self._get_translator(user_id)
                await streaming.finalize(f"**{t('claude.task_cancelled')}**")
                # Show file changes even on cancel (user might want to see what was done)
                await streaming.show_file_changes_summary()
            if session:
                session.cancel()
            return

        if result.success:
            if streaming:
                await streaming.send_completion(success=True)
                # Show summary of all file changes (Cursor-style)
                await streaming.show_file_changes_summary()
            if session:
                session.complete(result.session_id)

            context_id = getattr(session, 'context_id', None) if session else None
            if context_id and self.context_service and result.session_id:
                try:
                    await self.context_service.set_claude_session_id(context_id, result.session_id)
                    logger.info(
                        f"[{user_id}] Saved claude_session_id {result.session_id[:16]}... "
                        f"to context {context_id[:16]}..."
                    )

                    if session and session.current_prompt:
                        await self.context_service.save_message(context_id, "user", session.current_prompt)
                    if result.output:
                        await self.context_service.save_message(context_id, "assistant", result.output[:5000])

                except Exception as e:
                    logger.warning(f"Error saving to context: {e}")

            if result.session_id:
                self.user_state.set_continue_session_id(user_id, result.session_id)

            if session and self.project_service:
                new_working_dir = self.user_state.get_working_dir(user_id)
                original_dir = getattr(session, '_original_working_dir', session.working_dir)

                if new_working_dir and new_working_dir != original_dir:
                    try:
                        from domain.value_objects.user_id import UserId
                        uid = UserId.from_int(user_id)

                        project = await self.project_service.get_or_create(uid, new_working_dir)
                        await self.project_service.switch_project(uid, project.id)
                        logger.info(f"[{user_id}] Switched to project at {new_working_dir}")
                    except Exception as e:
                        logger.warning(f"Error updating project path: {e}")

        else:
            if streaming:
                await streaming.send_completion(success=False)
                # Show file changes even on error (user might want to see what was done)
                await streaming.show_file_changes_summary()
            if session:
                session.fail(result.error or "Cancelled" if result.cancelled else "Unknown error")

            if result.error and not result.cancelled:
                t = await self._get_translator(user_id)
                await message.answer(
                    t("error.task_failed_html", error=html.escape(result.error[:1000])),
                    parse_mode="HTML"
                )

    # Copied from legacy messages.py:140-155
    def _get_step_handler(self, user_id: int) -> Optional["StepStreamingHandler"]:
        """Get or create StepStreamingHandler for user in step streaming mode."""
        streaming = self.user_state.get_streaming_handler(user_id)
        if not streaming:
            return None
        if not hasattr(self, '_step_handlers'):
            self._step_handlers = {}
        if user_id not in self._step_handlers:
            from presentation.handlers.streaming import StepStreamingHandler
            self._step_handlers[user_id] = StepStreamingHandler(streaming)
        return self._step_handlers[user_id]

    # Copied from legacy messages.py:152-155
    def _cleanup_step_handler(self, user_id: int):
        """Clean up step handler for user."""
        if hasattr(self, '_step_handlers') and user_id in self._step_handlers:
            del self._step_handlers[user_id]
